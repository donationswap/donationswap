ALTER TABLE matches
ADD COLUMN feedback_requested BOOLEAN NOT NULL DEFAULT FALSE;

INSERT INTO event_types (id, name) VALUES (26, 'requesting match feedback');