-- 閲覧可能なノートのタスクを表示順に取得する
SELECT
    t.note_id,
    t.id,
    t.text,
    t.done,
    t.due
FROM note_tasks AS t
INNER JOIN notes AS n ON t.note_id = n.id
INNER JOIN note_shares AS sh ON n.id = sh.note_id
WHERE sh.token_hash = %(token_hash)s AND sh.expires_at > %(expires_at)s
ORDER BY t.note_id, t.position;
