-- 認証済み所有者を初回のみ登録する
INSERT INTO users (id, created_at) VALUES (%(id)s, %(created_at)s) ON CONFLICT (id) DO NOTHING;
