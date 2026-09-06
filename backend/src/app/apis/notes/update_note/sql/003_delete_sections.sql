-- 同一トランザクション内で保存対象の記入欄を置き換える
DELETE FROM note_sections
WHERE note_id = %(note_id)s;
