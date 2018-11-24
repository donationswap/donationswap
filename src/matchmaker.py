#!/usr/bin/env python3

class Matchmaker:

	def _send_mail_about_match_feedback(self, match):
		replacements = {
		}

		#xxx

		logging.info('Sending match feedback email to %s and %s',
			match.old_offer.email,
			match.new_offer.email,
		)

	def _delete_old_matches(self):
		'''Four weeks after a match was made we delete it and
		send the two donors a feedback email.

		(It only gets to be four weeks old if it was accepted by both
		donors, otherwise it would have been deleted within 72 hours.)'''

		four_weeks_ago = datetime.datetime.utcnow() - datetime.timedelta(days=28)

		with self._database.connect() as db:
			for match in entities.Match.get_all(lambda x: x.new_agrees is True and x.old_agrees is True and x.created_ts < four_weeks_ago):
				match.delete(db)
				self._send_mail_about_match_feedback(match)

	def clean(self):
		#xxx self._delete_unconfirmed_offers()
		#xxx self._delete_unapproved_matches()
		self._delete_old_matches()

		now = datetime.datetime.utcnow()
		one_week = datetime.timedelta(days=7)

		with self._database.connect() as db:

			# delete unapproved matches after one week
			for match in entities.Match.get_all(lambda x: (x.new_agrees is None or x.old_agrees is None) and x.created_ts + one_week < now):
				eventlog.match_expired(db, match)
				match.delete(db)

			#xxx also...
			# ... delete expired offers that aren't part of a match
