-- 閲覧条件を満たすノートの基本情報を取得する
SELECT
    n.id,
    n.title,
    n.group_name,
    n.version,
    n.updated_at
FROM notes AS n
INNER JOIN note_shares AS sh ON n.id = sh.note_id
WHERE sh.token_hash = %(token_hash)s AND sh.expires_at > %(expires_at)s
ORDER BY n.updated_at DESC, n.id ASC;
