-- 所有者が指定した閲覧リンクを失効する
DELETE FROM note_shares
WHERE note_id = %(note_id)s;
