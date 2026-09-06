-- 既存ノートを検証しながら分割するデータ移行
INSERT INTO users (id, created_at) VALUES (%(id)s, %(created_at)s) ON CONFLICT (id) DO NOTHING;
