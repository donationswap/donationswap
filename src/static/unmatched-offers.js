/* globals ajax, createNode, getElementsById */
/* jshint esversion: 6 */
(function () {
	'use strict';

	const ui = getElementsById();
	const state = {
		offersById: {},
		firstOfferId: 0,
	};

	function getSummary(offer) {
		return `${offer.country}, ${offer.charity}, ${offer.min_amount_localized}-${offer.amount_localized} ${offer.currency_localized}`;
	}

	function renderDetails(details) {
		const keys = Object.keys(details);
		keys.sort();
		return keys.map(key => `${key}: ${details[key]}`).join('\n');
	}

	function startMatch(offerId) {
		ajax('/special-secret-admin/get_match_scores', {
			offer_id: offerId,
		})
			.then(scores => {
				state.firstOfferId = offerId;
				Array.prototype.forEach.call(
					window.document.body.querySelectorAll('li'),
					li => li.classList.toggle('current', li.data === offerId)
				);
				Array.prototype.forEach.call(
					window.document.body.querySelectorAll('.score-number'),
					span => {
						const id = span.data;
						if (id !== offerId) {
							[span.textContent, span.title] = scores[id];
						} else {
							span.textContent = ''; // can't match an offer with itself
						}
					}
				);
			});
	}

	function completeMatch(offerId) {
		const first = getSummary(state.offersById[state.firstOfferId]);
		const second = getSummary(state.offersById[offerId]);

		const confirmed = window.confirm(`Please confirm that you want to create a match for the following two offers:\n\n${first}\n\n${second}`);

		if (confirmed) {
			ajax('/special-secret-admin/create_match', {
				offer_a_id: state.firstOfferId,
				offer_b_id: offerId,
			})
				.then(() => {
					alert('Match created. Emails sent.\n\nRefreshing page now...');
					window.location.reload();
				})
				.catch(error => {
					console.error(error);
					window.alert(`Unexpected error: ${error}`);
				});
		}
	}

	function renderOffers(offers) {
		ui.info.textContent = `Found ${offers.length} unmatched offer(s)`;

		ui.offers.innerHTML = '';
		offers.forEach(offer => {
			ui.offers.appendChild(createNode({
				xtype: 'li',
				p_data: offer.id,
				children: [
					{
						xtype: 'details',
						children: [
							{
								xtype: 'summary',
								children: [
									getSummary(offer),
									{
										xtype: 'span',
										a_class: 'menu',
										children: [
											{
												xtype: 'span',
												a_class: 'score-number',
												p_data: offer.id,
												p_onclick() {
													completeMatch(offer.id);
													return false; // prevent expand/collapse
												},
											},
											{
												xtype: 'span',
												a_class: 'match-button',
												a_title: 'See how well other offers would match',
												p_textContent: 'Score',
												p_onclick() {
													startMatch(offer.id);
													return false; // prevent expand/collapse
												},
											},
										],
									},
								],
							},
							`${renderDetails(offer)}`,
						],
					},
				],
			}));
		});
	}

	ajax('/special-secret-admin/get_unmatched_offers')
		.then(offers => {
			state.offersById = offers.toDictionary(i => i.id);
			renderOffers(offers);
		})
		.catch(error => {
			console.error(error);
			window.alert(`Unexpected error: ${error}`);
		});
}());
