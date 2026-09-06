-- 閲覧条件を満たすノートの基本情報を取得する
SELECT
    n.id,
    n.title,
    n.group_name,
    n.version,
    n.updated_at
FROM notes AS n
WHERE n.owner_id = %(owner_id)s AND n.id = %(id)s
ORDER BY n.updated_at DESC, n.id ASC;
