-- 問い・本文・要約をそれぞれ一行として保存する
INSERT INTO note_sections (note_id, kind, body, updated_at) VALUES (
    %(note_id)s, %(kind)s, %(body)s, %(updated_at)s
);
