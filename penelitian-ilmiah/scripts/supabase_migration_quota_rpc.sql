CREATE OR REPLACE FUNCTION increment_quota_if_under_limit(
    p_user_id      TEXT,
    p_date         TEXT,
    p_daily_limit  INTEGER
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_new_count INTEGER;
BEGIN
    -- Atomic upsert: insert baru atau increment yang ada.
    -- WHERE pada DO UPDATE memastikan increment hanya terjadi
    -- jika count saat ini masih di bawah limit.
    INSERT INTO user_quotas (user_id, date, message_count)
    VALUES (p_user_id, p_date, 1)
    ON CONFLICT (user_id, date)
    DO UPDATE
        SET message_count = user_quotas.message_count + 1
        WHERE user_quotas.message_count < p_daily_limit
    RETURNING message_count INTO v_new_count;

    -- Jika v_new_count NULL berarti DO UPDATE WHERE gagal
    -- (count sudah >= limit). Return FALSE.
    IF v_new_count IS NULL THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$;
