-- 既存ノートを検証しながら分割するデータ移行
SELECT
 token_hash,
 expires_at,
 created_by
FROM note_shares
WHERE note_id = %(note_id)s;
