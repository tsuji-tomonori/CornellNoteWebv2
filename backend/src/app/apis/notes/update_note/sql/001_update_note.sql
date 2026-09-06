-- 所有者と版が一致するノートを更新する
UPDATE notes SET
    title = %(title)s,
    group_name = %(group_name)s,
    cue = %(cue)s,
    content = %(content)s,
    summary = %(summary)s,
    tasks = %(tasks)s,
    version = version + 1,
    updated_at = %(updated_at)s
WHERE id = %(id)s AND owner_id = %(owner_id)s AND version = %(version)s RETURNING
    id, title, group_name, cue, content, summary, tasks, version, updated_at;
