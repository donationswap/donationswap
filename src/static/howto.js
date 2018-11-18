/* globals ajax, createNode, getElementsById */
/* jshint esversion: 6 */
(function () {
	'use strict';

	const ui = getElementsById();

	ajax('/ajax/get_info')
		.then(info => {
			// populate charities
			ui.lstCharities.innerHTML = '';
			const categories = [... new Set(info.charities.map(charity => charity.category))];
			const categoryByName = {};
			categories.forEach(category => {
				ui.lstCharities.appendChild(categoryByName[category] = createNode({
					xtype: 'li',
					children: [
						category,
						{
							xtype: 'ul',
						}
					],
				}));
			});
			info.charities.forEach(charity => {
				categoryByName[charity.category].children[0].appendChild(createNode({
					xtype: 'li',
					p_textContent: charity.name,
				}));
			});

			// populate countries
			ui.lstCountries.innerHTML = '';
			info.countries.forEach(country => {
				ui.lstCountries.appendChild(createNode({
					xtype: 'li',
					p_textContent: country.name,
				}));
			});
		});
}());
