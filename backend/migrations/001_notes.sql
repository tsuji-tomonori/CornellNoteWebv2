CREATE TABLE IF NOT EXISTS notes (
 id UUID PRIMARY KEY, owner_id VARCHAR(128) NOT NULL, title VARCHAR(200) NOT NULL,
 group_name VARCHAR(80) NOT NULL, cue TEXT NOT NULL, content TEXT NOT NULL,
 summary TEXT NOT NULL, tasks TEXT NOT NULL, version INTEGER NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL, share_hash VARCHAR(64), share_expires TIMESTAMPTZ
);
COMMENT ON TABLE notes IS '利用者ごとのコーネル式ノート';
COMMENT ON COLUMN notes.id IS 'ノート識別子（ランダムUUID）';
COMMENT ON COLUMN notes.owner_id IS '所有者のCognito sub';
COMMENT ON COLUMN notes.title IS 'ノートの題名';
COMMENT ON COLUMN notes.group_name IS '科目またはプロジェクトの分類名';
COMMENT ON COLUMN notes.cue IS '問い・キーワード';
COMMENT ON COLUMN notes.content IS '自由記述の記録本文';
COMMENT ON COLUMN notes.summary IS '自分の言葉による要約';
COMMENT ON COLUMN notes.tasks IS 'チェック項目・完了状態・期日のJSON配列';
COMMENT ON COLUMN notes.version IS '同時更新検知の連番';
COMMENT ON COLUMN notes.updated_at IS '最終更新日時（UTC）';
COMMENT ON COLUMN notes.share_hash IS '共有トークンのSHA256（生トークンは保存しない）';
COMMENT ON COLUMN notes.share_expires IS '共有リンクの有効期限';
