-- 所有者のノートを更新日時順に取得する
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
WHERE owner_id = %(owner_id)s
ORDER BY updated_at DESC;
