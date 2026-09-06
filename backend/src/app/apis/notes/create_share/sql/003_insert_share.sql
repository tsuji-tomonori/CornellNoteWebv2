-- 期限付き閲覧リンクのハッシュと発行者を保存する
INSERT INTO note_shares (note_id, token_hash, expires_at, created_by) VALUES (
    %(note_id)s, %(token_hash)s, %(expires_at)s, %(created_by)s
);
