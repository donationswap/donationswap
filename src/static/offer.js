/* globals ajax, getElementsById */
/* jshint esversion: 6 */
(function () {
	'use strict';

	const ui = getElementsById();
	const secret = window.location.hash.substr(1);

	function setVisibility(offer) {
		ui.table.classList.toggle('hidden', !offer);
		ui.btnDelete.classList.toggle('hidden', !offer);
		ui.confirmed.classList.toggle('hidden', !offer);
		ui.message.classList.toggle('hidden', !ui.message.textContent);
	}

	function handleError() {
		ui.message.innerHTML = '<p>Something went wrong.</p><p>We\'re probably already working on it, but if this happens a lot, feel free to <a href="/contact">let us know</a>.</p>';
		setVisibility(null);
	}

	ajax('/ajax/confirm_offer', { secret })
		.then(offer => {
			if (offer) {
				ui.confirmed.classList.toggle('hidden', offer.was_confirmed);
				ui.currency1.textContent = offer.currency;
				ui.currency2.textContent = offer.currency;
				ui.name.textContent = offer.name;
				ui.amount.textContent = offer.amount;
				ui.minAmount.textContent = offer.min_amount;
				ui.charity.textContent = offer.charity;
				ui.creationDate.textContent = Date.fromUtcIsoString(offer.created_ts).toLocalString('%Y-%m-%d %H:%M');
				ui.expirationDate.textContent = Date.fromUtcIsoString(offer.expires_ts).toLocalString('%Y-%m-%d %H:%M');
				ui.message.textContent = '';
			} else {
				ui.message.innerHTML = '<p>The requested post could not be found.</p><p>Maybe it was deleted or expired?</p><p>You can create a new one <a href="/">here</a>.</p>';
			}
			setVisibility(offer);
		})
		.catch(handleError);

	ui.btnDelete.onclick = () => {
		if (confirm('Do you want to delete this offer?')) {
			ajax('/ajax/delete_offer', { secret })
				.then(response => {
					ui.message.innerHTML = '<p>The offer has been deleted. Click <a href="/">here</a> to create a new one.</p>';
					setVisibility(null);
				})
				.catch(handleError);
		}
	};
}());
