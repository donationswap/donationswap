/* globals ajax, getElementsById */
/* jshint esversion: 6 */
(function () {
	'use strict';

	const ui = getElementsById();
	const secret = window.location.hash.substr(1);

	ajax('/ajax/get_match', { secret })
		.then(match => {
			if (match === null) {
				alert('We cannot find the requested offer. Maybe it expired or was declined. Redirecting you to the home page.');
				window.location.pathname = '/';
				return;
			}
			ui.txtMyCharity.textContent = match.my_charity;
			ui.txtMyAmount.textContent = `${match.my_amount} ${match.my_currency}`;
			ui.txtTheirCharity.textContent = match.their_charity;
			ui.btnApprove.disabled = !match.can_edit;
			ui.btnDecline.disabled = !match.can_edit;
			ui.btnApprove.title = ui.btnDecline.title = match.can_edit ? '' : 'You have already approved or declined this match';
		});

	ui.btnApprove.onclick = () => {
		ui.btnApprove.disabled = true;
		ui.btnDecline.disabled = true;
		ajax('/ajax/approve_match', { secret })
			.then(() => {
				//xxx say "you'll get an email soon."
				alert('Thanks!');
			})
			.catch((err) => {
				alert("Something went wrong:\n" + err + "\nmaybe check your emails or reload the page?")
			});
	};

	ui.btnDecline.onclick = () => {
		ui.btnApprove.disabled = true;
		ui.btnDecline.disabled = true;

		//xxx un-hide feedback form and actual decline button
		const feedback = 'xxx not implemented yet';
		ajax('/ajax/decline_match', { secret, feedback })
			.then(() => {
				//xxx let them know their offer has been suspended
				alert('The match has been declined.');
			})
			.catch((err) => {
				alert("Something went wrong:\n" + err + "\nmaybe check your emails or reload the page?")
			});
	};
}());
