#!/usr/bin/env python3

import json

ISO_FORMAT = '%Y-%m-%d %H:%M:%S'

def _log_permanently(db, event_type, args):
	db.write('''
		INSERT INTO event_log (event_type_id, json_details)
		VALUES (%(event_type)s, %(details)s);
	''', event_type=event_type, details=json.dumps(args))

def _offer_to_obj(offer, prefix=None):
	if prefix is None:
		prefix = ''
	return {
		prefix+'id': offer.id,
		prefix+'name': offer.name,
		prefix+'email': offer.email,
		prefix+'country': offer.country.name,
		prefix+'amount': offer.amount,
		prefix+'min_amount': offer.min_amount,
		prefix+'currency': offer.country.currency.iso,
		prefix+'charity': offer.charity.name,
		prefix+'expires_ts': offer.expires_ts.strftime(ISO_FORMAT),
	}

def _match_to_obj(match):
	obj_a = _offer_to_obj(match.new_offer, 'new_offer_')
	obj_b = _offer_to_obj(match.old_offer, 'old_offer_')
	obj = {
		'match_id': match.id,
	}
	obj.update(obj_a)
	obj.update(obj_b)
	return obj

def created_offer(db, offer):
	_log_permanently(db, 1, _offer_to_obj(offer))

def confirmed_offer(db, offer):
	_log_permanently(db, 2, _offer_to_obj(offer))

def deleted_offer(db, offer):
	_log_permanently(db, 3, _offer_to_obj(offer))

def offer_expired(db, offer):
	_log_permanently(db, 4, _offer_to_obj(offer))

def offer_unconfirmed(db, offer):
	_log_permanently(db, 5, _offer_to_obj(offer))

def match_generated(db, match):
	_log_permanently(db, 21, _match_to_obj(match))

def approved_match(db, match, offer):
	obj = _match_to_obj(match)
	obj['offer_id'] = offer.id
	_log_permanently(db, 22, obj)

def declined_match(db, match, offer, feedback):
	obj = _match_to_obj(match)
	obj['offer_id'] = offer.id
	obj['feedback'] = feedback
	_log_permanently(db, 23, obj)

def match_expired(db, match):
	_log_permanently(db, 24, _match_to_obj(match))

def sent_contact_message(db, message, to, cc, bcc):
	_log_permanently(db, 41, {
		'message': message,
		'to': to,
		'cc': cc,
		'bcc': bcc,
	})

def get_events(db, min_timestamp=None, max_timestamp=None, event_types=None, offset=0, limit=20):
	conditions = []

	if min_timestamp and max_timestamp and min_timestamp > max_timestamp:
		min_timestamp, max_timestamp = max_timestamp, min_timestamp

	if min_timestamp:
		conditions.append(db.escape('created_ts >= %(ts)s', ts=min_timestamp))

	if max_timestamp:
		conditions.append(db.escape('created_ts <= %(ts)s', ts=max_timestamp))

	event_types = [int(i) for i in (event_types or [])]
	if event_types:
		conditions.append('event_type_id IN (%s)' % ', '.join(str(i) for i in event_types))

	if conditions:
		conditions = 'WHERE %s' % ' AND '.join(conditions)
	else:
		conditions = ''

	query = '''SELECT count(1) AS count FROM event_log;'''
	total_count = db.read_one(query)['count']

	query = '''SELECT count(1) AS count FROM event_log %s;''' % conditions
	filtered_count = db.read_one(query)['count']

	query = '''
		SELECT
			event_log.id AS id,
			event_types.name AS event_type,
			event_log.json_details AS json_details,
			event_log.created_ts AS created_ts
		FROM event_log
		JOIN event_types ON event_log.event_type_id = event_types.id
		%s
		ORDER BY created_ts DESC
		OFFSET %i
		LIMIT %i''' % (conditions, int(offset), int(limit))

	data = [
		{
			'id': i['id'],
			'event_type': i['event_type'],
			'details': json.loads(i['json_details']),
			'created_ts': i['created_ts'].strftime(ISO_FORMAT),
		}
		for i in db.read(query)
	]

	return {
		'total_count': total_count,
		'filtered_count': filtered_count,
		'offset': offset,
		'limit': limit,
		'data': data,
	}
