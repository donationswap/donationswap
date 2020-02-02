ALTER TABLE matches
ADD COLUMN feedback_requested BOOLEAN NOT NULL DEFAULT FALSE;

INSERT INTO event_types (id, name) VALUES (26, 'match feedback');

ALTER TABLE matches
ADD COLUMN new_amount_suggested INT NOT NULL DEFAULT -1;
ALTER TABLE matches
ADD COLUMN old_amount_suggested INT NOT NULL DEFAULT -1;