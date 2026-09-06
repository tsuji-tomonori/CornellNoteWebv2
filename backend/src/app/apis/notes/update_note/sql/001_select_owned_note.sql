-- 所有者に一致するノートと現在の版を確認する
SELECT
    id,
    title,
    group_name,
    version,
    updated_at
FROM notes
WHERE id = %(id)s AND owner_id = %(owner_id)s;
