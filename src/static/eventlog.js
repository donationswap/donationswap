/* globals ajax, createNode, getElementsById */
/* jshint esversion: 6 */
(function () {
	'use strict';

	const ui = getElementsById();

	let timeout = null;
	let offset = 0;
	let limit = 20;

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

	function renderDetails(details) {
		const keys = Object.keys(details);
		keys.sort();
		return keys.map(key => `${key}: ${details[key]}`).join('\n');
	}

	function renderEvents(events) {
		ui.info.textContent = events.data.length ? `Showing entries ${events.offset+1}-${events.offset+events.data.length} of ${events.filtered_count} (filtered) of ${events.total_count} (total)` : `Showing none of a total of ${events.total_count} events.`;
		renderNumbers(events.offset, events.limit, events.filtered_count);

		ui.events.innerHTML = '';
		events.data.forEach(event => {
			ui.events.appendChild(createNode({
				xtype: 'li',
				children: [
					{
						xtype: 'details',
						children: [
							{
								xtype: 'summary',
								p_textContent: `${event.created_ts} ${event.id} ${event.event_type}`,
							},
							`${renderDetails(event.details)}`,
						],
					},
				],
			}));
		});
	}

	function load() {
		ajax('/special-secret-admin/read_log', {
			min_timestamp: ui.minTimestamp.value,
			max_timestamp: ui.maxTimestamp.value,
			event_types: Array.prototype.map.call(
				ui.eventType.selectedOptions,
				option => parseInt(option.value, 10)
			),
			offset: offset,
			limit: limit,
		})
			.then(events => renderEvents(events))
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

	ui.eventType.onchange = () => reload();
	ui.minTimestamp.oninput = () => reload();
	ui.maxTimestamp.oninput = () => reload();

	load();
}());
