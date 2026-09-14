-- Apply before deploying the corresponding chunk_editor.py changes.
-- Each RPC is one transaction; embedding generation stays outside the database.
-- No external embedding request should be running while applying this migration.
BEGIN;

LOCK TABLE public.parent_documents IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE public.child_documents IN SHARE ROW EXCLUSIVE MODE;

ALTER TABLE public.child_documents
    ADD COLUMN IF NOT EXISTS published_content text;

COMMENT ON COLUMN public.child_documents.published_content IS
    'Last child content synchronized into the parent; NULL means the legacy baseline is unresolved.';

-- A -> B -> C before re-embedding must retain A, including after failed retries.
-- Start from the earliest unfinished edit after the last successful publication.
-- With no such edit, a successful or newly ingested row starts at current content.
WITH last_success AS (
    SELECT child_id, max(coalesce(reembedded_at, edited_at)) AS completed_at
    FROM public.chunk_edit_logs
    WHERE status = 'success'
    GROUP BY child_id
), unfinished_edits AS (
    SELECT log.*
    FROM public.chunk_edit_logs AS log
    LEFT JOIN last_success ON last_success.child_id = log.child_id
    WHERE log.status IN ('pending', 'processing', 'failed')
      AND log.old_content IS NOT NULL
      AND log.old_content IS DISTINCT FROM log.new_content
      AND log.edited_at > coalesce(last_success.completed_at, '-infinity'::timestamptz)
), first_edit AS (
    SELECT child_id, min(edited_at) AS edited_at
    FROM unfinished_edits GROUP BY child_id
), baseline_candidates AS (
    SELECT child.id, coalesce(min(log.old_content), child.content) AS published_content
    FROM public.child_documents AS child
    LEFT JOIN first_edit ON first_edit.child_id = child.id
    LEFT JOIN unfinished_edits AS log
        ON log.child_id = first_edit.child_id AND log.edited_at = first_edit.edited_at
    WHERE child.published_content IS NULL
    GROUP BY child.id, child.content
    -- Equal timestamps with different old contents cannot establish edit order.
    HAVING count(DISTINCT log.old_content) <= 1
)
UPDATE public.child_documents AS child
SET published_content = baseline.published_content
FROM baseline_candidates AS baseline, public.parent_documents AS parent
WHERE child.id = baseline.id
  AND parent.parent_id = child.parent_id
  AND baseline.published_content <> ''
  AND strpos(parent.content, baseline.published_content) > 0
  AND strpos(substr(parent.content, strpos(parent.content, baseline.published_content) + 1), baseline.published_content) = 0;

-- Previously reported successes with unidentifiable parent content must not be
-- served as synchronized knowledge. Review these rows instead of overwriting.
UPDATE public.child_documents
SET embedding_status = 'failed', updated_at = now()
WHERE published_content IS NULL AND embedding_status = 'success';

UPDATE public.child_documents
SET embedding_status = 'stale', updated_at = now()
WHERE published_content IS NOT NULL AND published_content <> content AND embedding_status = 'success';

CREATE OR REPLACE FUNCTION public.lock_knowledge_chunk_for_update(p_child_id text)
RETURNS public.child_documents
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_parent_id text;
    v_parent_content text;
    v_child public.child_documents%ROWTYPE;
BEGIN
    SELECT parent_id INTO v_parent_id
    FROM public.child_documents WHERE id = p_child_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Child chunk % not found', p_child_id USING ERRCODE = 'P0002';
    END IF;

    -- Every RPC takes the parent lock before the child lock, including deletion.
    SELECT content INTO v_parent_content
    FROM public.parent_documents WHERE parent_id = v_parent_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Parent document % not found', v_parent_id USING ERRCODE = 'P0002';
    END IF;

    SELECT * INTO v_child
    FROM public.child_documents WHERE id = p_child_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Child chunk % not found', p_child_id USING ERRCODE = 'P0002';
    END IF;
    IF v_child.parent_id IS DISTINCT FROM v_parent_id THEN
        RAISE EXCEPTION 'Parent changed for chunk %; retry the operation', p_child_id
            USING ERRCODE = '40001';
    END IF;

    -- Support newly ingested rows whose loader does not set published_content.
    IF v_child.published_content IS NULL
       AND NOT EXISTS (SELECT 1 FROM public.chunk_edit_logs WHERE child_id = p_child_id)
       AND v_child.content <> ''
       AND strpos(v_parent_content, v_child.content) > 0
       AND strpos(substr(v_parent_content, strpos(v_parent_content, v_child.content) + 1), v_child.content) = 0 THEN
        UPDATE public.child_documents
        SET published_content = content
        WHERE id = p_child_id
        RETURNING * INTO v_child;
    END IF;
    RETURN v_child;
END;
$$;

CREATE OR REPLACE FUNCTION public.replace_published_chunk_content(
    p_parent_content text, p_old_content text, p_new_content text
)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_position integer;
BEGIN
    IF p_old_content IS NULL OR p_old_content = '' THEN
        RAISE EXCEPTION 'Published content is unresolved; review the parent and edit history'
            USING ERRCODE = '40001';
    END IF;
    v_position := strpos(p_parent_content, p_old_content);
    IF v_position = 0 THEN
        RAISE EXCEPTION 'Published content is missing from the parent; review the parent before retrying'
            USING ERRCODE = '40001';
    END IF;
    -- Start one character later to detect overlapping occurrences as well.
    IF strpos(substr(p_parent_content, v_position + 1), p_old_content) > 0 THEN
        RAISE EXCEPTION 'Published content occurs multiple times in the parent; automatic replacement is ambiguous'
            USING ERRCODE = '40001';
    END IF;
    RETURN overlay(p_parent_content PLACING p_new_content FROM v_position FOR length(p_old_content));
END;
$$;

CREATE OR REPLACE FUNCTION public.save_knowledge_chunk(
    p_child_id text,
    p_admin_id uuid,
    p_title text DEFAULT NULL,
    p_pages text[] DEFAULT NULL,
    p_content text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_child public.child_documents%ROWTYPE;
    v_content_changed boolean;
BEGIN
    v_child := public.lock_knowledge_chunk_for_update(p_child_id);
    v_content_changed := p_content IS NOT NULL AND p_content IS DISTINCT FROM v_child.content;
    IF v_content_changed AND v_child.embedding_status = 'processing' THEN
        RAISE EXCEPTION 'Chunk % is being reembedded; wait before editing its content', p_child_id
            USING ERRCODE = '40001';
    END IF;
    IF v_content_changed AND v_child.published_content IS NULL THEN
        RAISE EXCEPTION 'Chunk % has unresolved published content; review its parent and edit history', p_child_id
            USING ERRCODE = '40001';
    END IF;
    IF NOT v_content_changed
       AND (p_title IS NULL OR p_title = v_child.title)
       AND (p_pages IS NULL OR p_pages = v_child.pages) THEN
        RETURN jsonb_build_object(
            'child_id', p_child_id, 'embedding_status', v_child.embedding_status,
            'content_changed', false, 'message', 'Tidak ada perubahan.'
        );
    END IF;

    UPDATE public.child_documents
    SET title = coalesce(p_title, title),
        pages = coalesce(p_pages, pages),
        content = coalesce(p_content, content),
        embedding_status = CASE WHEN v_content_changed THEN 'stale' ELSE embedding_status END,
        updated_at = now()
    WHERE id = p_child_id;

    IF v_content_changed THEN
        INSERT INTO public.chunk_edit_logs (child_id, parent_id, admin_id, old_content, new_content, status)
        VALUES (p_child_id, v_child.parent_id, p_admin_id, v_child.content, p_content, 'pending');
    END IF;
    RETURN jsonb_build_object(
        'child_id', p_child_id,
        'embedding_status', CASE WHEN v_content_changed THEN 'stale' ELSE v_child.embedding_status END,
        'content_changed', v_content_changed,
        'message', CASE WHEN v_content_changed
            THEN 'Perubahan disimpan. Klik Re-Embed agar chatbot pakai versi terbaru.'
            ELSE 'Perubahan disimpan.' END
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.begin_chunk_reembed(p_child_id text, p_admin_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_child public.child_documents%ROWTYPE;
    v_log_id uuid;
BEGIN
    v_child := public.lock_knowledge_chunk_for_update(p_child_id);
    IF v_child.embedding_status = 'processing' OR EXISTS (
        SELECT 1 FROM public.chunk_edit_logs WHERE child_id = p_child_id AND status = 'processing'
    ) THEN
        RAISE EXCEPTION 'Chunk % is already being reembedded', p_child_id USING ERRCODE = '40001';
    END IF;
    IF v_child.published_content IS NULL THEN
        RAISE EXCEPTION 'Chunk % has unresolved published content; review its parent and edit history', p_child_id
            USING ERRCODE = '40001';
    END IF;

    SELECT log_id INTO v_log_id
    FROM public.chunk_edit_logs
    WHERE child_id = p_child_id AND status = 'pending'
    ORDER BY edited_at DESC NULLS LAST, log_id DESC
    LIMIT 1 FOR UPDATE;

    IF v_log_id IS NULL THEN
        INSERT INTO public.chunk_edit_logs (child_id, parent_id, admin_id, old_content, new_content, status)
        VALUES (p_child_id, v_child.parent_id, p_admin_id, v_child.published_content, v_child.content, 'processing')
        RETURNING log_id INTO v_log_id;
    ELSE
        -- Read the current child, never a possibly obsolete pending log payload.
        UPDATE public.chunk_edit_logs
        SET old_content = v_child.published_content, new_content = v_child.content,
            status = 'processing', error_message = NULL, reembedded_at = NULL
        WHERE log_id = v_log_id;
    END IF;
    UPDATE public.child_documents
    SET embedding_status = 'processing', updated_at = now()
    WHERE id = p_child_id;

    RETURN jsonb_build_object(
        'log_id', v_log_id, 'parent_id', v_child.parent_id,
        'old_content', v_child.published_content, 'new_content', v_child.content
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.complete_chunk_reembed(
    p_log_id uuid, p_child_id text, p_embedding public.vector
)
RETURNS void
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_child public.child_documents%ROWTYPE;
    v_log public.chunk_edit_logs%ROWTYPE;
    v_parent_content text;
    v_updated_content text;
BEGIN
    v_child := public.lock_knowledge_chunk_for_update(p_child_id);
    SELECT * INTO v_log FROM public.chunk_edit_logs WHERE log_id = p_log_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Reembedding log % not found', p_log_id USING ERRCODE = 'P0002';
    END IF;
    IF v_child.embedding_status <> 'processing' OR v_log.status <> 'processing'
       OR v_log.child_id IS DISTINCT FROM p_child_id
       OR v_log.parent_id IS DISTINCT FROM v_child.parent_id
       OR v_log.new_content IS DISTINCT FROM v_child.content
       OR v_log.old_content IS DISTINCT FROM v_child.published_content THEN
        RAISE EXCEPTION 'Reembedding job no longer owns the current chunk content'
            USING ERRCODE = '40001';
    END IF;
    IF p_embedding IS NULL OR public.vector_dims(p_embedding) <> 2000 THEN
        RAISE EXCEPTION 'Embedding must contain 2000 dimensions' USING ERRCODE = '22023';
    END IF;

    SELECT content INTO v_parent_content FROM public.parent_documents WHERE parent_id = v_child.parent_id;
    v_updated_content := public.replace_published_chunk_content(
        v_parent_content, v_child.published_content, v_child.content
    );
    IF v_updated_content IS DISTINCT FROM v_parent_content THEN
        UPDATE public.parent_documents
        SET content = v_updated_content, updated_at = now()
        WHERE parent_id = v_child.parent_id;
    END IF;
    UPDATE public.child_documents
    SET embedding = p_embedding, embedding_status = 'success',
        published_content = content, updated_at = now()
    WHERE id = p_child_id;
    UPDATE public.chunk_edit_logs
    SET status = 'success', reembedded_at = now(), error_message = NULL
    WHERE child_id = p_child_id AND (log_id = p_log_id OR status = 'pending');
END;
$$;

CREATE OR REPLACE FUNCTION public.fail_chunk_reembed(p_log_id uuid, p_child_id text, p_error text)
RETURNS void
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_child public.child_documents%ROWTYPE;
    v_log public.chunk_edit_logs%ROWTYPE;
BEGIN
    v_child := public.lock_knowledge_chunk_for_update(p_child_id);
    SELECT * INTO v_log FROM public.chunk_edit_logs WHERE log_id = p_log_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Reembedding log % not found', p_log_id USING ERRCODE = 'P0002';
    END IF;
    IF v_child.embedding_status <> 'processing' OR v_log.status <> 'processing'
       OR v_log.child_id IS DISTINCT FROM p_child_id
       OR v_log.parent_id IS DISTINCT FROM v_child.parent_id
       OR v_log.new_content IS DISTINCT FROM v_child.content THEN
        RAISE EXCEPTION 'Reembedding job no longer owns the current chunk content'
            USING ERRCODE = '40001';
    END IF;
    UPDATE public.child_documents
    SET embedding_status = 'failed', updated_at = now()
    WHERE id = p_child_id;
    UPDATE public.chunk_edit_logs
    SET status = 'failed', error_message = left(p_error, 500)
    WHERE log_id = p_log_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.delete_knowledge_chunk(p_child_id text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_child public.child_documents%ROWTYPE;
    v_parent_content text;
    v_updated_content text;
    v_parent_deleted boolean;
BEGIN
    v_child := public.lock_knowledge_chunk_for_update(p_child_id);
    IF v_child.embedding_status = 'processing' OR EXISTS (
        SELECT 1 FROM public.chunk_edit_logs WHERE child_id = p_child_id AND status = 'processing'
    ) THEN
        RAISE EXCEPTION 'Chunk % is being reembedded; wait before deleting it', p_child_id
            USING ERRCODE = '40001';
    END IF;
    SELECT NOT EXISTS (
        SELECT 1 FROM public.child_documents WHERE parent_id = v_child.parent_id AND id <> p_child_id
    ) INTO v_parent_deleted;

    IF NOT v_parent_deleted THEN
        SELECT content INTO v_parent_content FROM public.parent_documents WHERE parent_id = v_child.parent_id;
        v_updated_content := public.replace_published_chunk_content(
            v_parent_content, v_child.published_content, ''
        );
        UPDATE public.parent_documents
        SET content = v_updated_content, child_ids = array_remove(child_ids, p_child_id), updated_at = now()
        WHERE parent_id = v_child.parent_id;
    END IF;
    -- Foreign keys remove this child's edit history inside the same transaction.
    DELETE FROM public.child_documents WHERE id = p_child_id;
    IF v_parent_deleted THEN
        DELETE FROM public.parent_documents WHERE parent_id = v_child.parent_id;
    END IF;
    RETURN jsonb_build_object(
        'child_id', p_child_id, 'parent_id', v_child.parent_id, 'parent_deleted', v_parent_deleted
    );
END;
$$;

REVOKE ALL ON FUNCTION public.lock_knowledge_chunk_for_update(text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.replace_published_chunk_content(text, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.save_knowledge_chunk(text, uuid, text, text[], text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.begin_chunk_reembed(text, uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.complete_chunk_reembed(uuid, text, public.vector) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.fail_chunk_reembed(uuid, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.delete_knowledge_chunk(text) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.lock_knowledge_chunk_for_update(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.replace_published_chunk_content(text, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.save_knowledge_chunk(text, uuid, text, text[], text) TO service_role;
GRANT EXECUTE ON FUNCTION public.begin_chunk_reembed(text, uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.complete_chunk_reembed(uuid, text, public.vector) TO service_role;
GRANT EXECUTE ON FUNCTION public.fail_chunk_reembed(uuid, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.delete_knowledge_chunk(text) TO service_role;

NOTIFY pgrst, 'reload schema';
COMMIT;

-- Rows needing manual parent/history reconciliation before further content edits:
SELECT id, parent_id, embedding_status
FROM public.child_documents WHERE published_content IS NULL ORDER BY parent_id, id;
