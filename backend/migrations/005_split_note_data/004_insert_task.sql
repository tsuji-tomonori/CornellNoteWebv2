-- 既存ノートを検証しながら分割するデータ移行
INSERT INTO note_tasks (note_id, id, text, done, due, position) VALUES (
 %(note_id)s, %(id)s, %(text)s, %(done)s, %(due)s, %(position)s
);
