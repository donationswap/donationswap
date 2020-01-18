CREATE TABLE admins (
	id SERIAL,
	email TEXT NOT NULL UNIQUE,
	password_hash varchar(200) NOT NULL,
	secret varchar(24) UNIQUE,
	last_login_ts timestamp,
	PRIMARY KEY (id)
);

/*
>>> from passlib.apps import custom_app_context as pwd_context
>>> pwd_context.encrypt('password')
'$6$rounds=656000$5c0cWcDUaKxxNvCY$IT/diOeBANnnqbOF/SVATSpQ85AisI/FbxD.NoRpWIVj4mXOFxMAQ0Ny3LiX8nhbhdgcOWcnLExaYvQ0PcTre.'
*/
