-- 個別タスクの内容・完了状態・期日・表示順序を保存する
INSERT INTO note_tasks (note_id, id, text, done, due, position) VALUES (
    %(note_id)s, %(id)s, %(text)s, %(done)s, %(due)s, %(position)s
);
