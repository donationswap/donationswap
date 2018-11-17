ALTER TABLE admins
ADD COLUMN currency_id INT;

ALTER TABLE admins
ADD FOREIGN KEY (currency_id) REFERENCES currencies (id)
	ON DELETE NO ACTION ON UPDATE CASCADE;

UPDATE admins
SET currency_id = (SELECT id FROM currencies WHERE iso = 'USD');

ALTER TABLE admins
ALTER COLUMN currency_id SET NOT NULL;
