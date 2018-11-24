/* globals ajax, createNode, getElementsById */
/* jshint esversion: 6 */
(function () {
	'use strict';

	const ui = getElementsById();

	function handleError(response) {
		console.error(response);
		alert(`Error: ${response}`);
	}

	function editCharityCategory(charityCategory) {
		ui.charityCategoryId.textContent = charityCategory.id;
		ui.charityCategoryName.value = charityCategory.name;

		ui.editCharityCategory.classList.remove('hidden');
		ui.charityCategoryName.select();
	}

	function editCharity(charity) {
		ui.charityId.textContent = charity.id;
		ui.charityName.value = charity.name;
		ui.charityCategory.value = charity.category_id;

		ui.editCharity.classList.remove('hidden');
		ui.charityName.select();
	}

	function editCountry(country) {
		ui.countryId.textContent = country.id;
		ui.countryName.value = country.name;
		ui.countryLiveInName.value = country.live_in_name || '';
		ui.countryIsoName.value = country.iso_name;
		ui.countryCurrency.value = country.currency_id;
		ui.countryMinDonationAmount.value = country.min_donation_amount;
		ui.countryMinDonationCurrencyId.value = country.min_donation_currency_id;
		ui.giftAid.value = country.gift_aid;

		ui.editCountry.classList.remove('hidden');
		ui.countryName.select();
	}

	function editCharityInCountry(charityInCountry) {
		ui.charityInCountryCharity.data = charityInCountry.charity_id;
		ui.charityInCountryCharity.textContent = data.charities.filter(charity => charity.id === charityInCountry.charity_id)[0].name;
		ui.charityInCountryCountry.data = charityInCountry.country_id;
		ui.charityInCountryCountry.textContent = data.countries.filter(country => country.id === charityInCountry.country_id)[0].name;
		ui.charityInCountryInstructions.value = charityInCountry.instructions || '';

		ui.editCharityInCountry.classList.remove('hidden');
		ui.charityInCountryInstructions.focus();
	}

	function populateUi(data) {

		function findCell(charityId, countryId) {
			let countryIndex, result;

			Array.prototype.every.call(
				ui.matrix.querySelectorAll('thead tr td'),
				(cell, index) => {
					if (cell.data && cell.data.id === countryId) {
						countryIndex = index;
						return false;
					}
					return true;
				}
			);

			Array.prototype.every.call(
				ui.matrix.querySelectorAll('tbody tr'),
				row => {
					if (row.data.id === charityId) {
						result = row.children[countryIndex];
						return false;
					}
					return true;
				}
			);

			return result;
		}

		function createHeader() {
			const head = ui.matrix.querySelector('thead');
			head.innerHTML = '';
			head.appendChild(createNode({
				xtype: 'tr',
				children: [
					{
						xtype: 'td',
					},
				].concat(data.countries.map(country => {
					const node = createNode({
						xtype: 'td',
						p_data: country,
						a_class: 'edit',
						a_style: 'width: 2em;',
						a_title: JSON.stringify(country, null, 3),
						p_textContent: country.iso_name,
					});
					node.onclick = () => editCountry(country);
					return node;
				}))
			}));
		}

		function createRows() {
			const body = ui.matrix.querySelector('tbody');
			body.innerHTML = '';
			data.charities.forEach(charity => {
				body.appendChild(createNode({
					xtype: 'tr',
					p_data: charity,
					children:[
						(function () {
							const node = createNode({
								xtype: 'td',
								a_class: 'edit',
								a_title: JSON.stringify(charity, null, 3),
								p_textContent: charity.name,
							});
							node.onclick = () => editCharity(charity);
							return node;
						}()),
					].concat(data.countries.map(country => {
						const node = createNode({
							xtype: 'td',
							a_class: 'edit white',
						});
						node.onclick = () => editCharityInCountry({
							charity_id: charity.id,
							country_id: country.id,
						});
						return node;
					})),
				}));
			});
		}

		createHeader();

		createRows();

		data.charity_categories.forEach(cc => {
			ui.categories.appendChild(createNode({
				xtype: 'li',
				children: [
					{
						xtype: 'span',
						a_class: 'edit',
						a_title: JSON.stringify(cc, null, 3),
						p_textContent: cc.name,
						p_onclick() {
							editCharityCategory(cc);
						},
					},
				],
			}));
		});

		data.charities_in_countries.forEach(cic => {
			let cell = findCell(cic.charity_id, cic.country_id);
			if (cic) {
				cell.classList.remove('white');
				cell.setAttribute('title', JSON.stringify(cic, null, 3));
				cell.classList.add(cic.instructions ? 'green' : 'yellow');
			}
			cell.onclick = () => {
				editCharityInCountry(cic);
			};
		});

		ui.charityCategory.innerHTML = '';
		data.charity_categories.forEach(category => {
			ui.charityCategory.appendChild(createNode({
				xtype: 'option',
				a_value: category.id,
				p_textContent: category.name,
			}));
		});

		ui.countryCurrency.innerHTML = '';
		data.currencies.forEach(currency => {
			ui.countryCurrency.appendChild(createNode({
				xtype: 'option',
				a_value: currency.id,
				p_textContent: `${currency.iso} (${currency.name})`,
			}));
		});

		ui.countryMinDonationCurrencyId.innerHTML = '';
		data.currencies.forEach(currency => {
			ui.countryMinDonationCurrencyId.appendChild(createNode({
				xtype: 'option',
				a_value: currency.id,
				p_textContent: `${currency.iso} (${currency.name})`,
			}));
		});
	}

	ui.btnCreateCharity.onclick = () => {
		editCharity({
			id: '',
			name: 'New Charity',
		});
	};

	ui.btnCreateCountry.onclick = () => {
		editCountry({
			id: '',
			name: 'New Country',
			iso_name: '',
		});
	};

	ui.btnCreateCharityCategory.onclick = () => {
		editCharityCategory({
			id: '',
			name: 'New Category',
		});
	};

	ui.btnDeleteCharityCategory.onclick = () => {
		if (window.confirm('Are you sure?')) {
			ajax('/special-secret-admin/delete_charity_category', {
				category_id: parseInt(ui.charityCategoryId.textContent, 10),
			})
				.then(() => window.location.reload())
				.catch(handleError);
		}
	};

	ui.btnSaveCharityCategory.onclick = () => {
		const args = {
			name: ui.charityCategoryName.value,
		};

		if (ui.charityCategoryId.textContent) {
			args.category_id = parseInt(ui.charityCategoryId.textContent, 10);
			ajax('/special-secret-admin/update_charity_category', args)
				.then(() => window.location.reload())
				.catch(handleError);
		} else {
			ajax('/special-secret-admin/create_charity_category', args)
				.then(() => window.location.reload())
				.catch(handleError);
		}
	};

	ui.btnCancelCharityCategory.onclick = () => ui.editCharityCategory.classList.add('hidden');

	ui.btnDeleteCharity.onclick = () => {
		if (window.confirm('Are you sure?')) {
			ajax('/special-secret-admin/delete_charity', {
				charity_id: parseInt(ui.charityId.textContent, 10),
			})
				.then(() => window.location.reload())
				.catch(handleError);
		}
	};

	ui.btnSaveCharity.onclick = () => {
		const args = {
			name: ui.charityName.value,
			category_id: parseInt(ui.charityCategory.value, 10),
		};

		if (ui.charityId.textContent) {
			args.charity_id = parseInt(ui.charityId.textContent, 10);
			ajax('/special-secret-admin/update_charity', args)
				.then(() => window.location.reload())
				.catch(handleError);
		} else {
			ajax('/special-secret-admin/create_charity', args)
				.then(() => window.location.reload())
				.catch(handleError);
		}
	};

	ui.btnCancelCharity.onclick = () => ui.editCharity.classList.add('hidden');

	ui.btnDeleteCountry.onclick = () => {
		if (window.confirm('Are you sure?')) {
			ajax('/special-secret-admin/delete_country', {
				country_id: parseInt(ui.countryId.textContent, 10),
			})
				.then(() => window.location.reload())
				.catch(handleError);
		}
	};

	ui.btnSaveCountry.onclick = () => {
		const args = {
			name: ui.countryName.value,
			live_in_name: ui.countryLiveInName.value.trim() ? ui.countryLiveInName.value.trim() : null,
			iso_name: ui.countryIsoName.value.toUpperCase(),
			currency_id: parseInt(ui.countryCurrency.value, 10),
			min_donation_amount: parseInt(ui.countryMinDonationAmount.value, 10),
			min_donation_currency_id: parseInt(ui.countryMinDonationCurrencyId.value, 10),
			gift_aid: parseFloat(ui.giftAid.value),
		};

		if (ui.countryId.textContent) {
			args.country_id = parseInt(ui.countryId.textContent, 10);
			ajax('/special-secret-admin/update_country', args)
				.then(() => window.location.reload())
				.catch(handleError);
		} else {
			ajax('/special-secret-admin/create_country', args)
				.then(() => window.location.reload())
				.catch(handleError);
		}
	};

	ui.btnCancelCountry.onclick = () => ui.editCountry.classList.add('hidden');

	ui.btnDeleteCharityInCountry.onclick = () => {
		if (window.confirm('Are you sure?')) {
			ajax('/special-secret-admin/delete_charity_in_country', {
				charity_id: ui.charityInCountryCharity.data,
				country_id: ui.charityInCountryCountry.data,
			})
				.then(() => window.location.reload())
				.catch(handleError);
		}
	};

	ui.btnSaveCharityInCountry.onclick = () => {
		const args = {
			charity_id: ui.charityInCountryCharity.data,
			country_id: ui.charityInCountryCountry.data,
			instructions: ui.charityInCountryInstructions.value.trim(),
		};
		if (data.charities_in_countries.find(cic => cic.charity_id === args.charity_id && cic.country_id === args.country_id)) {
			ajax('/special-secret-admin/update_charity_in_country', args)
				.then(() => window.location.reload())
				.catch(handleError);
		} else {
			ajax('/special-secret-admin/create_charity_in_country', args)
				.then(() => window.location.reload())
				.catch(handleError);
		}
	};

	ui.btnCancelCharityInCountry.onclick = () => ui.editCharityInCountry.classList.add('hidden');

	window.onkeydown = e => {
		if (e.key === 'Escape') {
			ui.btnCancelCharityCategory.click();
			ui.btnCancelCharity.click();
			ui.btnCancelCountry.click();
			ui.btnCancelCharityInCountry.click();
		}
	};

	let data = {};

	ajax('/special-secret-admin/read_all')
		.then(reply => {
			data = reply;
			populateUi(data);
		});
}());
