-- ハッシュと期限が一致する共有ノートを取得する
SELECT
    id,
    title,
    group_name,
    cue,
    content,
    summary,
    tasks,
    version,
    updated_at
FROM notes
WHERE share_hash = %(share_hash)s AND share_expires > %(share_expires)s;
