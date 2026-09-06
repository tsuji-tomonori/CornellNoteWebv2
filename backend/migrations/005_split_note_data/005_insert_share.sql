-- 既存ノートを検証しながら分割するデータ移行
INSERT INTO note_shares (note_id, token_hash, expires_at, created_by) VALUES (
 %(note_id)s, %(token_hash)s, %(expires_at)s, %(created_by)s
);
