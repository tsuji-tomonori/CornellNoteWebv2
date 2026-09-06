-- 既存ノートを検証しながら分割するデータ移行
INSERT INTO note_sections (note_id, kind, body, updated_at) VALUES (
 %(note_id)s, %(kind)s, %(body)s, %(updated_at)s
);
