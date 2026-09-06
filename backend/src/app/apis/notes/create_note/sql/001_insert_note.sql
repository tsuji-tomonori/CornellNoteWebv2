-- 所有者に紐づく新しいノートを保存する
INSERT INTO notes (
    id, owner_id, title, group_name, cue, content, summary, tasks, version, updated_at
) VALUES (
    %(id)s,
    %(owner_id)s,
    %(title)s,
    %(group_name)s,
    %(cue)s,
    %(content)s,
    %(summary)s,
    %(tasks)s,
    1,
    %(updated_at)s
);
