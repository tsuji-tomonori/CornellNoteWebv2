-- ノートの基本情報を保存する
INSERT INTO notes (id, owner_id, title, group_name, version, updated_at) VALUES (
    %(id)s, %(owner_id)s, %(title)s, %(group_name)s, 1, %(updated_at)s
) RETURNING id, title, group_name, version, updated_at;
