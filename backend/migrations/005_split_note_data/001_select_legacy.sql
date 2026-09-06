-- 既存ノートを検証しながら分割するデータ移行
SELECT
 id,
 owner_id,
 title,
 group_name,
 cue,
 content,
 summary,
 tasks,
 version,
 updated_at,
 share_hash,
 share_expires
FROM notes
WHERE id > %(after_id)s
ORDER BY id
LIMIT 1;
