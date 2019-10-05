/* globals ajax, createNode, getElementsById */
/* jshint esversion: 6 */
[window.captchaGood, window.captchaBad] = (function () {
	'use strict';

	const ui = getElementsById();
	const offer = {};
	const currencyByCountry = {};

	let autoMin = true;
	let captchaValid = false;
	let offerValid = false;

	function updateButton(errorMessage) {
		if (captchaValid && offerValid) {
			ui.btnSend.removeAttribute('disabled');
		} else {
			ui.btnSend.setAttribute('disabled', 'disabled');
		}

		ui.errorText.textContent = errorMessage;

		ui.errorContainer.classList.toggle('hidden', !errorMessage);
	}

	function captchaGood() {
		const tmp = document.getElementsByName('g-recaptcha-response');
		offer.captcha_response = tmp.length ? tmp[0].value : null;

		captchaValid = true;
		updateButton();
	}

	function captchaBad() {
		captchaValid = false;
		updateButton();
	}

	function populateDropdowns(info) {
		// countries
		info.countries.forEach(country => {
			currencyByCountry[country.id] = {
				iso: country.currency_iso,
				name: country.currency_name,
			};
			ui.idCountry.appendChild(createNode({
				xtype: 'option',
				a_value: country.id,
				p_textContent: country.live_in_name,
			}));
		});

		// charities
		const categories = [... new Set(info.charities.map(charity => charity.category))];
		const categoryByName = {};
		const optgroups = [];

		categories.forEach(category => {
			optgroups.push(categoryByName[category] = createNode({
				xtype: 'optgroup',
				a_label: category,
			}));
		});

		info.charities.forEach(charity => {
			categoryByName[charity.category].appendChild(createNode({
				xtype: 'option',
				a_value: charity.id,
				p_textContent: charity.name,
			}));
		});

		ui.idCharity.innerHTML = '';
		optgroups.forEach(optgroup => {
			if (optgroup.children.length > 0) {
				ui.idCharity.appendChild(optgroup);
			}
		});

		// calendar
		for (let day = 1; day <= 31; day++) {
			ui.intExpirationDay.appendChild(createNode({
				xtype: 'option',
				a_value: day,
				p_textContent: `${('0' + day).substr(-2)}.`,
			}));
		}
		const monthNames = ['Octember',
			'January', 'February', 'March', 'April',
			'May', 'June', 'July', 'August',
			'September', 'October', 'November', 'December'];
		for (let month = 1; month <= 12; month++) {
			ui.intExpirationMonth.appendChild(createNode({
				xtype: 'option',
				a_value: month,
				p_textContent: monthNames[month],
			}));
		}
		for (let year = info.today.year; year <= info.today.year + 2; year++) {
			ui.intExpirationYear.appendChild(createNode({
				xtype: 'option',
				a_value: year,
				p_textContent: year,
			}));
		}
	}

	function attachEventHandlers() {
		ui.txtName.onchange = () => validate();

		ui.idCountry.onchange = () => {
			const currency = currencyByCountry[ui.idCountry.value];
			ui.txtCurrency1.textContent = currency.iso;
			ui.txtCurrency1.setAttribute('title', currency.name);
			ui.txtCurrency2.textContent = currency.iso;
			ui.txtCurrency2.setAttribute('title', currency.name);
			validate();
		};

		ui.intAmount.oninput = () => {
			if (autoMin) {
				ui.intMinAmount.value = Math.floor(ui.intAmount.value / 2);
			}
		};
		
		ui.intAmount.onchange = () => validate();

		ui.intMinAmount.onchange = () => {
			autoMin = false;
			validate();
		};

		ui.intExpirationDay.onchange = () => validate();
		ui.intExpirationMonth.onchange = () => validate();
		ui.intExpirationYear.onchange = () => validate();

		ui.txtEmail.onchange = () => validate();

		ui.btnSend.onclick = () => {
			captchaBad(); // disable send button
			ajax('/ajax/create_offer', offer)
				.then(() => {
					ui.successContainer.classList.remove('hidden');
					ui.form.classList.add('hidden');
				})
				.catch(error => {
					console.error(error);
					alert('Something went awfully wrong on our server. Sorry.');
				});
		};
	}

	function initialize(obj, fallback) {
		ui.txtName.value = obj.name || fallback.name;
		ui.idCountry.value = obj.country || fallback.country;
		ui.intAmount.value = obj.amount || fallback.amount;
		ui.idCharity.value = obj.charity || fallback.charity;
		ui.intMinAmount.value = obj.min_amount;
		ui.intExpirationDay.value = (obj.expires || {}).day || fallback.expires.day;
		ui.intExpirationMonth.value = (obj.expires || {}).month || fallback.expires.month;
		ui.intExpirationYear.value = (obj.expires || {}).year || fallback.expires.year;
		ui.txtEmail.value = obj.email || fallback.email;

		ui.idCountry.onchange(); // to set currency
	}

	function validate() {
		offer.captcha_response = offer.captcha_response || '';
		offer.name = ui.txtName.value;
		offer.country = parseInt(ui.idCountry.value, 10);
		offer.amount = parseInt(ui.intAmount.value, 10);
		offer.min_amount = parseInt(ui.intMinAmount.value, 10);
		offer.charity = parseInt(ui.idCharity.value, 10);
		offer.email = ui.txtEmail.value;
		offer.expiration = {
			day: ui.intExpirationDay.value,
			month: ui.intExpirationMonth.value,
			year: ui.intExpirationYear.value,
		};
		
		ajax('/ajax/validate_offer', offer)
			.then(errorMessage => {
				offerValid = !errorMessage;
				updateButton(errorMessage);
			});
	}

	ajax('/ajax/get_info')
		.then(info => {
			populateDropdowns(info);
			attachEventHandlers();

			var day = info.today.day;
			var month = info.today.month;
			var year = info.today.year;

			month += 3;
			if (month > 12) {
				month -= 12;
				year += 1;
			}

			// month coming in and going out is 1-12, javascript Date takes 0-11 but day 0 gives last day of previous month
			day = Math.min(day, new Date(year, month, 0).getDate());

			const defaults = {
				name: '',
				country: info.client_country,
				amount: 100,
				min_amount: 50,
				charity: 30, // Animal Equality (first in alphabet)
				email: '',
				expires: {
					day: day,
					month: month,
					year: year
				},
			};
			try {
				const args = JSON.parse(decodeURIComponent(window.location.hash.substr(1)));
				initialize(args, defaults);
			}
			catch(e) {
				initialize(defaults, defaults);
			}

			validate();
		});

	captchaBad();

	return [captchaGood, captchaBad];
}());
