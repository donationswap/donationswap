CREATE TABLE event_types (
	id INT NOT NULL,
	name varchar(20) NOT NULL,
	PRIMARY KEY (id)
);

INSERT INTO event_types (id, name) VALUES
(1, 'offer created'),
(2, 'offer confirmed'),
(3, 'offer deleted'),
(4, 'offer expired'),
(21, 'match generated'),
(22, 'match approved'),
(23, 'match declined'),
(24, 'match expired'),
(41, 'contact message sent');

CREATE TABLE event_log (
	id SERIAL,
	event_type_id INT NOT NULL,
	json_details text NOT NULL,
	created_ts timestamp NOT NULL DEFAULT now(),
	FOREIGN KEY (event_type_id) REFERENCES event_types (id)
		ON DELETE NO ACTION ON UPDATE CASCADE,
	PRIMARY KEY (id)
);
