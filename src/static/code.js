/* jshint esversion: 6 */

function ajax(action, payload) {
	'use strict';

	return new Promise((resolve, reject) => {
		if (!payload) {
			payload = {};
		}

		const request = new XMLHttpRequest();
		request.open('POST', `${action}`, true);
		request.onreadystatechange = () => {
			if (request.readyState === 4) {
				if (request.status < 300) {
					resolve(JSON.parse(request.responseText));
				} else {
					reject(request.responseText);
				}
			}
		};

		request.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

		request.send(JSON.stringify(payload));
	});
}

function createNode(cfg) {
	'use strict';

	if (cfg === null) {
		return null;
	}

	if (typeof(cfg) === 'string') {
		return document.createTextNode(cfg);
	}

	const element = document.createElement(cfg.xtype);

	Object.keys(cfg).forEach(key => {
		const value = cfg[key];
		if (key.substr(0, 2) === 'a_') {
			element.setAttribute(key.substr(2), value);
		} else if (key.substr(0, 2) === 'p_') {
			element[key.substr(2)] = value;
		} else if (key === 'children') {
			for (let i = 0; i < value.length; i += 1) {
				if (value[i] !== null) {
					element.appendChild(
						(value[i].hasOwnProperty('xtype') || typeof(value[i]) === 'string') ? createNode(value[i]) : value[i]
					);
				}
			}
		} else if (key !== 'xtype') {
			console.error('invalid argument', key, value);
		}
	});

	return element;
}

function getElementsById() {
	'use strict';

	const result = {};

	Array.prototype.forEach.call(
		document.querySelectorAll('body [id]'),
		v => result[v.getAttribute('id')] = v
	);

	return result;
}

// var date = Date.fromUtcIsoString('2012-12-22_06-40-41')
Date.fromUtcIsoString = function (isoString) {
	const utc = Date.UTC(
		parseInt(isoString.substr(0, 4), 10),
		parseInt(isoString.substr(5, 2) || '00', 10)-1,
		parseInt(isoString.substr(8, 2) || '01', 10),
		parseInt(isoString.substr(11, 2) || '00', 10),
		parseInt(isoString.substr(14, 2) || '00', 10),
		parseInt(isoString.substr(17, 2) || '00', 10)
	);
	return new Date(utc);
};

// (new Date()).toLocalString('%Y-%m-%d %H:%M:%S')
Date.prototype.toLocalString = function (format='%Y-%m-%d %H:%M:%S') {
	const date = this;
	function replace(match) {
		switch (match) {
		case '%Y':
			return ('000' + date.getFullYear()).slice(-4);
		case '%m':
			return ('0' + (date.getMonth() + 1)).slice(-2);
		case '%d':
			return ('0' + date.getDate()).slice(-2);
		case '%H':
			return ('0' + date.getHours()).slice(-2);
		case '%M':
			return ('0' + date.getMinutes()).slice(-2);
		case '%S':
			return ('0' + date.getSeconds()).slice(-2);
		}
	}

	return format.replace(/%./g, replace);
};
