CREATE TABLE IF NOT EXISTS users (
 id VARCHAR(128) PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL
);
COMMENT ON TABLE users IS 'Cognitoで認証されたノート所有者。パスワードは保持しない';
COMMENT ON COLUMN users.id IS 'Cognito sub。ローカルでは検証用ユーザー名';
COMMENT ON COLUMN users.created_at IS 'アプリのユーザー行を登録した日時（UTC）';
CREATE TABLE IF NOT EXISTS note_sections (
 note_id UUID NOT NULL REFERENCES notes (id), kind VARCHAR(16) NOT NULL,
 body TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
 PRIMARY KEY (note_id, kind), CHECK (kind IN ('cue', 'content', 'summary'))
);
COMMENT ON TABLE note_sections IS 'ノートごとの問い・本文・要約。種類ごとに一行';
COMMENT ON COLUMN note_sections.note_id IS '所属ノートの識別子';
COMMENT ON COLUMN note_sections.kind IS '記入欄の種類（cue:問い、content:本文、summary:要約）';
COMMENT ON COLUMN note_sections.body IS 'この記入欄の自由記述本文';
COMMENT ON COLUMN note_sections.updated_at IS '記入欄を保存した日時（UTC）';
CREATE TABLE IF NOT EXISTS note_tasks (
 note_id UUID NOT NULL REFERENCES notes (id), id UUID NOT NULL,
 text VARCHAR(500) NOT NULL, done BOOLEAN NOT NULL, due DATE,
 position INTEGER NOT NULL, PRIMARY KEY (note_id, id)
);
COMMENT ON TABLE note_tasks IS 'ノートに紐づく個別タスク。完了状態や期日で横断検索する';
COMMENT ON COLUMN note_tasks.note_id IS '所属ノートの識別子';
COMMENT ON COLUMN note_tasks.id IS 'ノート内で一意なタスク識別子';
COMMENT ON COLUMN note_tasks.text IS 'タスクの内容';
COMMENT ON COLUMN note_tasks.done IS '完了していればtrue、未完了ならfalse';
COMMENT ON COLUMN note_tasks.due IS '期日。未指定はNULL';
COMMENT ON COLUMN note_tasks.position IS 'ノート内の表示順序（0始まり）';
CREATE TABLE IF NOT EXISTS note_shares (
 note_id UUID PRIMARY KEY REFERENCES notes (id),
 token_hash VARCHAR(64) NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
 created_by VARCHAR(128) NOT NULL REFERENCES users (id)
);
COMMENT ON TABLE note_shares IS 'ノートごとに一つの期限付き閲覧リンク。再発行で旧リンクを失効する';
COMMENT ON COLUMN note_shares.note_id IS '閲覧を許可するノート';
COMMENT ON COLUMN note_shares.token_hash IS '共有トークンのSHA256。生トークンは保持しない';
COMMENT ON COLUMN note_shares.expires_at IS '閲覧リンクの有効期限（UTC）';
COMMENT ON COLUMN note_shares.created_by IS 'リンクを発行したノート所有者';
CREATE INDEX IF NOT EXISTS note_shares_token_idx ON note_shares (token_hash);
CREATE INDEX IF NOT EXISTS note_tasks_state_idx ON note_tasks (done, due);
