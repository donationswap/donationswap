CREATE TABLE declined_matches (
	new_offer_id INTEGER NOT NULL,
	old_offer_id INTEGER NOT NULL,
	FOREIGN KEY (new_offer_id) REFERENCES offers (id)
		ON DELETE CASCADE ON UPDATE CASCADE,
	FOREIGN KEY (old_offer_id) REFERENCES offers (id)
		ON DELETE CASCADE ON UPDATE CASCADE,
	PRIMARY KEY (new_offer_id, old_offer_id)
);
