-- 更新失敗が権限不足か版競合かを区別する
SELECT id FROM notes
WHERE id = %(id)s AND owner_id = %(owner_id)s;
