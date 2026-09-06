-- 閲覧可能なノートのタスクを表示順に取得する
SELECT
    t.note_id,
    t.id,
    t.text,
    t.done,
    t.due
FROM note_tasks AS t
INNER JOIN notes AS n ON t.note_id = n.id
WHERE n.owner_id = %(owner_id)s AND n.id = %(id)s
ORDER BY t.note_id, t.position;
