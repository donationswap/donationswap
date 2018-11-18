ALTER TABLE countries
ADD COLUMN gift_aid INT NOT NULL DEFAULT 0;

ALTER TABLE countries
ALTER COLUMN gift_aid DROP DEFAULT;

UPDATE countries
SET gift_aid=25
WHERE iso_name='GB';

UPDATE countries
SET gift_aid=45
WHERE iso_name='IE';