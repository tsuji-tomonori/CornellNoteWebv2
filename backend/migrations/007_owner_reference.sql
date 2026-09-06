ALTER TABLE notes ADD CONSTRAINT notes_owner_fk FOREIGN KEY (owner_id) REFERENCES users (id);
