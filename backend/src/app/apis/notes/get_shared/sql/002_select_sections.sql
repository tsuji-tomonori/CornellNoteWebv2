-- 閲覧可能なノートの問い・本文・要約を取得する
SELECT
    s.note_id,
    s.kind,
    s.body
FROM note_sections AS s
INNER JOIN notes AS n ON s.note_id = n.id
INNER JOIN note_shares AS sh ON n.id = sh.note_id
WHERE sh.token_hash = %(token_hash)s AND sh.expires_at > %(expires_at)s;
