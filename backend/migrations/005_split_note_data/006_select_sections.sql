-- 既存ノートを検証しながら分割するデータ移行
SELECT
 kind,
 body
FROM note_sections
WHERE note_id = %(note_id)s;
