/* globals ajax, getElementsById */
/* jshint esversion: 6 */

function captchaGood() {
	document.getElementById('btnSend').removeAttribute('disabled');
}

function captchaBad() {
	document.getElementById('btnSend').setAttribute('disabled', 'disabled');
}

(function () {
	'use strict';

	const ui = getElementsById();

	function handleError() {
		alert('There was an error when we tried to send your message. Sorry. We\'re looking into it.');
	}

	ui.btnSend.onclick = () => {
		ajax('/ajax/send_contact_message', {
			captcha_response: document.getElementsByName('g-recaptcha-response')[0].value,
			message: ui.message.value,
			name: ui.name.value,
			email: ui.email.value,
		}).then(() => {
			alert('Your message has been sent. Thank you.');
			window.location.pathname = '/';
		})
		.catch(handleError);
	};
}());
