#!/bin/bash -e

# download latest GeoLite database
URL="https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-Country&license_key=9MZWC7YpDlczgNoC&suffix=tar.gz"
wget $URL -O /tmp/geoip.tar.gz

# decompress
FILE=GeoLite2-Country.mmdb
tar xvzf /tmp/geoip.tar.gz --no-anchored $FILE -O > /srv/web/data/$FILE

# clean up
rm /tmp/geoip.tar.gz
