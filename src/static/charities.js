/* globals ajax, createNode, getElementsById */
/* jshint esversion: 6 */
(function () {
	'use strict';

	const ui = getElementsById();

	ui.btnClose.onclick = () => {
		ui.background.classList.add('hidden');
	};

	window.onkeydown = e => {
		if (e.keyCode === 27) {
			ui.btnClose.click();
		}
	};

	function onCellClicked(charity, country) {
		ajax('/ajax/get_charity_in_country_info', {
			charity_id: charity.id,
			country_id: country.id,
		})
			.then(info => {
				ui.infoTitle.textContent = `How to donate to ${charity.name} from ${country.live_in_name}:`;
				ui.infoText.textContent = info;
				ui.background.classList.remove('hidden');
			});
	}

	ajax('/ajax/get_info')
		.then(info => {
			info.countries.sort2(x => x.iso_name);
			info.charities.sort2(x => x.name);

			ui.matrix.appendChild(createNode({
				xtype: 'tr',
				children: [
					{
						xtype: 'td',
					},
				].concat(info.countries.map(country => {
					return {
						xtype: 'td',
						a_class: 'country',
						a_title: country.name,
						p_textContent: country.iso_name,
					};
				})),
			}));

			info.charities.forEach(charity => {
				ui.matrix.appendChild(createNode({
					xtype: 'tr',
					children: [
						{
							xtype: 'td',
							a_class: 'charity',
							p_textContent: charity.name,
						},
					].concat(info.countries.map(country => {
						return info.charities_in_countries[country.id].indexOf(charity.id) === -1 ? {
							xtype: 'td',
						} : {
							xtype: 'td',
							a_class: 'dot',
							p_textContent: '\u2022',
							p_onclick() {
								onCellClicked(charity, country);
							},
						};
					})),
				}));
			});
		});
}());
