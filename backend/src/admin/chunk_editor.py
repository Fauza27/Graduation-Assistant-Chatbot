import datetime
from loguru import logger
from supabase import Client

from src.admin.auth import ResourceNotFoundError
from src.ingestion.embedder import get_openai_embeddings

def list_knowledge_tree(supabase: Client) -> dict:
    """Returns the full knowledge tree and summary statistics.
    
    Note: 'source' is stored in child_documents, not parent_documents.
    We derive the source for each parent from its first child's 'source' field.
    """
    # Fetch all parents — domain is in parent_documents, source is NOT
    parents_res = supabase.table("parent_documents").select("parent_id, title, domain, section, updated_at").order("domain").order("section").order("parent_id").execute()
    parents = parents_res.data
    
    # Fetch all children (lightweight) — includes source field
    children_res = supabase.table("child_documents").select("id, parent_id, title, pages, source, embedding_status, updated_at").order("parent_id").order("pages").execute()
    children = children_res.data
    
    # Build parent_id -> source map (use first child's source as representative for the parent)
    parent_source_map = {}
    for child in children:
        pid = child["parent_id"]
        if pid not in parent_source_map and child.get("source"):
            parent_source_map[pid] = child["source"]
    
    # Group children by parent_id
    children_by_parent = {}
    for child in children:
        pid = child["parent_id"]
        if pid not in children_by_parent:
            children_by_parent[pid] = []
        children_by_parent[pid].append({
            "id": child["id"],
            "title": child["title"],
            "pages": child.get("pages"),
            "embedding_status": child["embedding_status"]
        })
        
    # Build tree
    tree_dict = {}
    total_parents = len(parents)
    total_children = len(children)
    
    # Calculate last_updated_at
    last_updated_at = None
    all_updated_ats = [p.get("updated_at") for p in parents if p.get("updated_at")] + \
                      [c.get("updated_at") for c in children if c.get("updated_at")]
    if all_updated_ats:
        last_updated_at = max(all_updated_ats)
        
    for p in parents:
        domain = p.get("domain", "")
        pid = p["parent_id"]
        # Get source from the first child of this parent
        source = parent_source_map.get(pid, "")
        section = p["section"]
        
        doc_key = (domain, source)
        if doc_key not in tree_dict:
            tree_dict[doc_key] = {}
            
        if section not in tree_dict[doc_key]:
            tree_dict[doc_key][section] = []
            
        p_children = children_by_parent.get(pid, [])
        
        tree_dict[doc_key][section].append({
            "parent_id": pid,
            "title": p["title"],
            "child_count": len(p_children),
            "children": p_children
        })
        
    documents_list = []
    for (domain, source), chapters_dict in tree_dict.items():
        chapters_list = []
        for section, parents_list in chapters_dict.items():
            chapters_list.append({
                "section": section,
                "parents": parents_list
            })
        documents_list.append({
            "domain": domain,
            "source": source,
            "chapters": chapters_list
        })
        
    summary = {
        "total_documents": len(tree_dict),
        "total_parents": total_parents,
        "total_children": total_children,
        "last_updated_at": last_updated_at
    }
    
    return {"summary": summary, "documents": documents_list}


def get_chunk_detail(child_id: str, supabase: Client) -> dict:
    """Returns the full detail of a single child chunk.
    
    Note: 'source' and 'domain' come from child_documents itself.
    Only section and parent title/id come from parent_documents.
    """
    res = supabase.table("child_documents").select("*").eq("id", child_id).limit(1).execute()
    if not res.data:
        raise ResourceNotFoundError(f"Child chunk {child_id} not found")
        
    child = res.data[0]
    
    # Get parent info (only title and section — no source/domain in parent_documents)
    parent_res = supabase.table("parent_documents").select("parent_id, title, section").eq("parent_id", child["parent_id"]).limit(1).execute()
    
    parent_info = None
    section = child.get("section")  # fallback to child's own section
    
    if parent_res.data:
        p = parent_res.data[0]
        parent_info = {"parent_id": p["parent_id"], "title": p["title"]}
        section = p["section"]
        
    # Get last reembedded_at from logs
    log_res = supabase.table("chunk_edit_logs").select("reembedded_at").eq("child_id", child_id).eq("status", "success").order("reembedded_at", desc=True).limit(1).execute()
    reembedded_at = log_res.data[0]["reembedded_at"] if log_res.data else None
    
    # pages is stored as TEXT[] in DB — serialize to comma-separated string for frontend
    pages_raw = child.get("pages") or []
    pages_str = ", ".join(pages_raw) if isinstance(pages_raw, list) else str(pages_raw)
    
    return {
        "id": child["id"],
        "title": child["title"],
        "pages": pages_str,
        "content": child["content"],
        "embedding_status": child["embedding_status"],
        "reembedded_at": reembedded_at,
        "parent": parent_info,
        "section": section,
        "domain": child.get("domain", ""),
        "source": child.get("source", "")
    }


def save_chunk(child_id: str, admin_id: str, supabase: Client, title: str = None, pages: str = None, content: str = None) -> dict:
    """Saves partial updates to a child chunk. If content changes, it marks embedding_status as stale."""
    res = supabase.table("child_documents").select("*").eq("id", child_id).limit(1).execute()
    if not res.data:
        raise ResourceNotFoundError(f"Child chunk {child_id} not found")
        
    child = res.data[0]
    updates = {}
    content_changed = False
    
    if content is not None and content != child["content"]:
        content_changed = True
        old_content = child["content"]
        updates["content"] = content
        updates["embedding_status"] = 'stale'
        
    if title is not None:
        updates["title"] = title
        
    if pages is not None:
        # pages comes as a string from frontend (e.g. "12-13") — store as TEXT[] in DB
        pages_arr = [p.strip() for p in pages.split(",") if p.strip()] if pages else []
        updates["pages"] = pages_arr
        
    if not updates:
        return {
            "child_id": child_id,
            "embedding_status": child["embedding_status"],
            "content_changed": False,
            "message": "Tidak ada perubahan."
        }
        
    updates["updated_at"] = "now()"
    
    supabase.table("child_documents").update(updates).eq("id", child_id).execute()
    
    if content_changed:
        log_data = {
            "child_id": child_id,
            "parent_id": child["parent_id"],
            "admin_id": admin_id,
            "old_content": old_content,
            "new_content": content,
            "status": "pending"
        }
        supabase.table("chunk_edit_logs").insert(log_data).execute()
        
    new_status = updates.get("embedding_status", child["embedding_status"])
    msg = "Perubahan disimpan."
    if content_changed:
        msg += " Klik Re-Embed agar chatbot pakai versi terbaru."
        
    return {
        "child_id": child_id,
        "embedding_status": new_status,
        "content_changed": content_changed,
        "message": msg
    }


def trigger_reembed(child_id: str, admin_id: str, supabase: Client) -> dict:
    """Triggers a re-embed by preparing the log and returning data for background task."""
    res = supabase.table("child_documents").select("parent_id, content").eq("id", child_id).limit(1).execute()
    if not res.data:
        raise ResourceNotFoundError(f"Child chunk {child_id} not found")
        
    child = res.data[0]
    
    # Check for latest pending log
    log_res = supabase.table("chunk_edit_logs").select("*").eq("child_id", child_id).eq("status", "pending").order("edited_at", desc=True).limit(1).execute()
    
    if log_res.data:
        log = log_res.data[0]
        log_id = log["log_id"]
        old_content = log["old_content"]
        new_content = log["new_content"]
    else:
        # First-embed or retry without new edit
        log_data = {
            "child_id": child_id,
            "parent_id": child["parent_id"],
            "admin_id": admin_id,
            "old_content": None,
            "new_content": child["content"],
            "status": "pending"
        }
        insert_res = supabase.table("chunk_edit_logs").insert(log_data).execute()
        log_id = insert_res.data[0]["log_id"]
        old_content = None
        new_content = child["content"]
        
    # Mark as processing
    supabase.table("chunk_edit_logs").update({"status": "processing"}).eq("log_id", log_id).execute()
    
    return {
        "log_id": log_id,
        "parent_id": child["parent_id"],
        "old_content": old_content,
        "new_content": new_content
    }


async def process_chunk_reembed(log_id: str, child_id: str, parent_id: str, old_content: str | None, new_content: str, supabase: Client, settings):
    """Background task to perform the embedding and parent content sync."""
    try:
        # Embed using openai
        from src.ingestion.embedder import get_openai_embeddings
        vector = get_openai_embeddings([new_content])[0]
        
        # Update child
        supabase.table("child_documents").update({
            "embedding": vector,
            "embedding_status": "success",
            "updated_at": "now()"
        }).eq("id", child_id).execute()
        
        # Sync parent content if it was an edit
        if old_content is not None:
            parent_res = supabase.table("parent_documents").select("content").eq("parent_id", parent_id).limit(1).execute()
            if parent_res.data:
                parent_content = parent_res.data[0]["content"]
                if old_content in parent_content:
                    new_parent_content = parent_content.replace(old_content, new_content, 1)
                    supabase.table("parent_documents").update({
                        "content": new_parent_content,
                        "updated_at": "now()"
                    }).eq("parent_id", parent_id).execute()
                else:
                    logger.warning(f"Parent {parent_id} content sync failed: old_content substring not found.")
                    
        # Mark log as success
        supabase.table("chunk_edit_logs").update({
            "status": "success",
            "reembedded_at": "now()"
        }).eq("log_id", log_id).execute()
        
    except Exception as e:
        logger.error(f"Re-embed failed for chunk {child_id} log {log_id}: {e}")
        supabase.table("child_documents").update({"embedding_status": "failed"}).eq("id", child_id).execute()
        supabase.table("chunk_edit_logs").update({
            "status": "failed",
            "error_message": str(e)
        }).eq("log_id", log_id).execute()


def get_edit_status(child_id: str, supabase: Client) -> dict | None:
    """Returns the latest edit status for a chunk."""
    res = supabase.table("chunk_edit_logs").select("*").eq("child_id", child_id).order("edited_at", desc=True).limit(1).execute()
    if not res.data:
        return None
    log = res.data[0]
    return {
        "log_id": log["log_id"],
        "child_id": log["child_id"],
        "status": log["status"],
        "error_message": log.get("error_message"),
        "edited_at": log["edited_at"],
        "reembedded_at": log.get("reembedded_at")
    }


def delete_chunk(child_id: str, supabase: Client) -> dict:
    """Deletes a child chunk and performs automatic parent housekeeping if necessary."""
    res = supabase.table("child_documents").select("parent_id").eq("id", child_id).limit(1).execute()
    if not res.data:
        raise ResourceNotFoundError(f"Child chunk {child_id} not found")
        
    parent_id = res.data[0]["parent_id"]
    
    # Postgres triggers (CASCADE) will delete chunk_edit_logs automatically
    supabase.table("child_documents").delete().eq("id", child_id).execute()
    
    # Remove from parent array
    # array_remove logic using raw SQL or RPC if possible, but Supabase python client doesn't support array_remove directly in update.
    # So we fetch the array, remove the item, and update.
    parent_res = supabase.table("parent_documents").select("child_ids").eq("parent_id", parent_id).limit(1).execute()
    if parent_res.data:
        child_ids = parent_res.data[0].get("child_ids", [])
        if child_id in child_ids:
            child_ids.remove(child_id)
            supabase.table("parent_documents").update({
                "child_ids": child_ids,
                "updated_at": "now()"
            }).eq("parent_id", parent_id).execute()
            
    # Housekeeping: check if parent is empty
    count_res = supabase.table("child_documents").select("id", count="exact").eq("parent_id", parent_id).execute()
    sisa_child = count_res.count if count_res.count is not None else len(count_res.data)
    
    parent_deleted = False
    if sisa_child == 0:
        supabase.table("parent_documents").delete().eq("parent_id", parent_id).execute()
        parent_deleted = True
        
    return {
        "child_id": child_id,
        "parent_id": parent_id,
        "parent_deleted": parent_deleted
    }
