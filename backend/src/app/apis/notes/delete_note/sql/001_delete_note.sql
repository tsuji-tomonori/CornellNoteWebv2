-- 所有者に一致するノートだけを削除する
DELETE FROM notes
WHERE id = %(id)s AND owner_id = %(owner_id)s;
