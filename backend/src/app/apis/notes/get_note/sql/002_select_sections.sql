-- 閲覧可能なノートの問い・本文・要約を取得する
SELECT
    s.note_id,
    s.kind,
    s.body
FROM note_sections AS s
INNER JOIN notes AS n ON s.note_id = n.id
WHERE n.owner_id = %(owner_id)s AND n.id = %(id)s;
