-- 本人のノートに紐づくタスクを横断取得する
SELECT
    t.note_id,
    t.id,
    t.text,
    t.done,
    t.due,
    n.title,
    n.group_name
FROM note_tasks AS t
INNER JOIN notes AS n ON t.note_id = n.id
WHERE n.owner_id = %(owner_id)s
ORDER BY t.done, t.due, t.note_id, t.position;
