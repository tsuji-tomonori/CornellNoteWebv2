-- 既存ノートを検証しながら分割するデータ移行
SELECT
 id,
 text,
 done,
 due
FROM note_tasks
WHERE note_id = %(note_id)s
ORDER BY position;
