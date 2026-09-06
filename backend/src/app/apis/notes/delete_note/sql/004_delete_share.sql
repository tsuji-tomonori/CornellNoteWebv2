-- ノートに属する子データを削除する
DELETE FROM note_shares
WHERE note_id = %(note_id)s;
