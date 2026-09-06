-- 所有者とIDでノートを取得する
SELECT
    id,
    title,
    group_name,
    cue,
    content,
    summary,
    tasks,
    version,
    updated_at
FROM notes
WHERE id = %(id)s AND owner_id = %(owner_id)s;
