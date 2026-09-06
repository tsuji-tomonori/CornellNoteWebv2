-- 操作対象ノートの所有者を確認する
SELECT id FROM notes
WHERE id = %(id)s AND owner_id = %(owner_id)s;
