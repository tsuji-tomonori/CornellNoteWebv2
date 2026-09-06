-- 所有者のノートの共有を失効させる
UPDATE notes SET share_hash = NULL, share_expires = NULL
WHERE id = %(id)s AND owner_id = %(owner_id)s;
