-- 所有者に一致するノートの基本情報を最後に削除する
DELETE FROM notes
WHERE id = %(id)s AND owner_id = %(owner_id)s;
