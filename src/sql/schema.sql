CREATE TABLE currencies (
	id SERIAL,
	iso varchar(3) UNIQUE NOT NULL,
	name varchar(50) NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE charity_categories (
	id SERIAL,
	name varchar(100) UNIQUE NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE charities (
	id SERIAL,
	name varchar(100) UNIQUE NOT NULL,
	category_id INT NOT NULL,
	FOREIGN KEY (category_id) REFERENCES charity_categories (id)
		ON DELETE NO ACTION ON UPDATE CASCADE,
	PRIMARY KEY (id)
);

CREATE TABLE countries (
	id SERIAL,
	name varchar(100) NOT NULL,
	live_in_name varchar(100),
	iso_name varchar(2) UNIQUE NOT NULL,
	currency_id INT NOT NULL,
	min_donation_amount INT NOT NULL,
	min_donation_currency_id INT NOT NULL,
	FOREIGN KEY (currency_id) REFERENCES currencies (id)
		ON DELETE NO ACTION ON UPDATE CASCADE,
	FOREIGN KEY (min_donation_currency_id) REFERENCES currencies (id)
		ON DELETE NO ACTION ON UPDATE CASCADE,
	PRIMARY KEY (id)
);

CREATE TABLE charities_in_countries (
	charity_id INTEGER NOT NULL,
	country_id INTEGER NOT NULL,
	tax_factor FLOAT NOT NULL,
	instructions TEXT,
	FOREIGN KEY (charity_id) REFERENCES charities (id)
		ON DELETE NO ACTION ON UPDATE CASCADE,
	FOREIGN KEY (country_id) REFERENCES countries (id)
		ON DELETE NO ACTION ON UPDATE CASCADE,
	PRIMARY KEY (charity_id, country_id)
);

CREATE TABLE offers (
	id SERIAL,
	secret varchar(24) UNIQUE NOT NULL,
	email TEXT NOT NULL,
	country_id INTEGER NOT NULL,
	amount INTEGER NOT NULL,
	charity_id INTEGER NOT NULL,
	created_ts timestamp NOT NULL DEFAULT now(),
	expires_ts timestamp NOT NULL,
	confirmed BOOLEAN NOT NULL DEFAULT false,
	FOREIGN KEY (country_id) REFERENCES countries (id)
		ON DELETE NO ACTION ON UPDATE CASCADE,
	FOREIGN KEY (charity_id) REFERENCES charities (id)
		ON DELETE NO ACTION ON UPDATE CASCADE,
	PRIMARY KEY (id)
);

CREATE TABLE matches (
	id SERIAL,
	secret varchar(24) UNIQUE NOT NULL,
	new_offer_id INTEGER NOT NULL,
	old_offer_id INTEGER NOT NULL,
	new_agrees BOOLEAN,
	old_agrees BOOLEAN,
	created_ts timestamp NOT NULL DEFAULT now(),
	FOREIGN KEY (new_offer_id) REFERENCES offers (id)
		ON DELETE CASCADE ON UPDATE CASCADE,
	FOREIGN KEY (old_offer_id) REFERENCES offers (id)
		ON DELETE CASCADE ON UPDATE CASCADE,
	PRIMARY KEY (id)
);

CREATE TABLE dbupgrade (
	script_name varchar(255) UNIQUE NOT NULL,
	executed_ts timestamp NOT NULL DEFAULT now(),
	PRIMARY KEY (script_name)
);
