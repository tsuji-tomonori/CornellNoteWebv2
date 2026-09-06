-- 所有者のノートに期限付き共有を発行する
UPDATE notes SET share_hash = %(share_hash)s, share_expires = %(share_expires)s
WHERE id = %(id)s AND owner_id = %(owner_id)s RETURNING id;
