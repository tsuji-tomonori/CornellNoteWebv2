-- 同一トランザクション内で保存対象のタスクを置き換える
DELETE FROM note_tasks
WHERE note_id = %(note_id)s;
