/* globals ajax, createNode, getElementsById */
/* jshint esversion: 6 */
(function () {
	'use strict';

	const ui = getElementsById();

	let timeout = null;
	let offset = 0;

	function renderNumbers(current_offset, limit, total) {
		ui.numbers.innerHTML = '';
		for (let i = 0; i < total; i += limit) {
			const clickable = current_offset !== i;
			ui.numbers.appendChild(createNode({
				xtype: 'span',
				a_class: `number ${clickable ? 'clickable' : ''}`,
				p_textContent: `${i+1}-${Math.min(total, i+limit)}`,
				p_onclick: clickable ? () => {
					offset = i;
					load();
				} : null,
			}));
		}
	}

	function renderStats(events) {
		ui.info.textContent = events.data.length ? `Showing entries ${events.offset+1}-${events.offset+events.data.length} of ${events.filtered_count} (filtered) of ${events.total_count} (total)` : `Showing none of a total of ${events.total_count} events.`;
		renderNumbers(events.offset, events.limit, events.filtered_count);

		ui.stats.innerHTML = '';
		ui.stats.appendChild(createNode({
			xtype: 'li',
			children: [
				`date match generated, USD value, charity1, country1, charity2, country2`
			],
		}));
		events.data.forEach(event => {
			ui.stats.appendChild(createNode({
				xtype: 'li',
				children: [
					`${event.created_ts}, ${event.value}, ${event.details.new_offer_charity}, ${event.details.new_offer_country}, ${event.details.old_offer_charity}, ${event.details.old_offer_country}`
				],
			}));
		});
	}

	function load() {
		ajax('/special-secret-admin/read_log_stats', {
			min_timestamp: ui.minTimestamp.value,
			max_timestamp: ui.maxTimestamp.value,
			offset: offset,
			limit: 1000000, // absurdly high number because this is just a data dump
		})
			.then(events => renderStats(events))
			.catch(error => {
				console.error(error);
				window.alert('Unexpected error. See console.');
			});
	}

	function reload() {
		offset = 0;
		window.clearTimeout(timeout);
		timeout = window.setTimeout(() => load(), 1000);
	}

	ui.minTimestamp.oninput = () => reload();
	ui.maxTimestamp.oninput = () => reload();

	load();
}());
