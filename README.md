# Effective Altruist Donation Swap

This is the repository of the Effective Altruist Donation Swap project.

## Deployment for development on Linux

	sudo pip3 install psycopg2-binary
	sudo pip3 install geoip2
	sudo pip3 install tornado

	mkdir deployed
	cd deployed
	../src/deploy.py deployed

Put the right passwords and such into app-config.json

	pico app-config.json

Start the server

	sudo ./main.py

## Database

Install PostgreSQL

	sudo apt-get install postgresql

Change to listen to external connections

	pico /etc/postgresql/9.6/main/postgresql.conf
	listen_addresses = '*'

	pico /etc/postgresql/9.6/main/pg_hba.conf
	host all all 101.98.189.34/32 md5

Start database server

	sudo service postgresql status

Change password

	sudo su - postgres
	psql
	alter user postgres with password 'databasepassword';

Create a database

	sudo su - postgres
	createdb production

Connect to database via command-line ...

	sudo su - postgres
	psql production

... or use pgAdmin4 to administrate

	mkdir pgadmin4-venv
	cd pgadmin4-venv
	python3 -m venv env
	source env/bin/activate
	wget https://ftp.postgresql.org/pub/pgadmin/pgadmin4/v3.4/pip/pgadmin4-3.4-py2.py3-none-any.whl
	wget https://ftp.postgresql.org/pub/pgadmin/pgadmin4/v3.4/pip/pgadmin4-3.4-py2.py3-none-any.whl.asc
	pip3 install ./pgadmin4-3.4-py2.py3-none-any.whl
	python3 /usr/local/lib/pyon3.6/site-packages/pgadmin4/pgAdmin4.py
	firefox http://127.0.0.1:5050

Now create tables etc.

When creating a database, please make sure to set the encoding to utf-8.
That's what Python is using, and it's the encoding of the html templates.

## Webserver

We're using Tornado.

Run it like this:

	cd web
	sudo ./main.py -d

If it's running as a daemon, kill it like this:

	kill `cat /var/run/webserver.pid`

Get help like this:

	cd web
	./main.py -h

## Letsencrypt

Install

	sudo apt-get install certbot
	sudo certbot certonly --standalone --email [email_address] --agree-tos --domain donationswap.eahub.org

Note that the second command will use port 80 -- stop the webserver first

Back up the certificate

		/etc/letsencrypt

Add a cronjob

	sudo crontab -e

with the following line

	42 6 * * * certbot renew --standalone --preferred-challenges http-01 --http-01-port 5433 >> /srv/certlog.txt 2>&1
