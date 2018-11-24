#!/bin/bash -e

# download latest GeoLite database
URL=https://geolite.maxmind.com/download/geoip/database/GeoLite2-Country.tar.gz
wget $URL -O /tmp/geoip.tar.gz

# decompress
FILE=GeoLite2-Country.mmdb
tar xvzf /tmp/geoip.tar.gz --no-anchored $FILE -O > /srv/web/data/$FILE

# clean up
rm /tmp/geoip.tar.gz
