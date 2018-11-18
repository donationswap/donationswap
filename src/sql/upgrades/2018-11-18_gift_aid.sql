ALTER TABLE countries
ADD COLUMN gift_aid FLOAT NOT NULL DEFAULT 0;

ALTER TABLE countries
ALTER COLUMN gift_aid DROP DEFAULT;

UPDATE TABLE countries
SET gift_aid=0.25
WHERE iso_name='GB';

UPDATE TABLE countries
SET gift_aid=0.45
WHERE iso_name='IE';