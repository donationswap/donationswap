function getElementsById() {
	const result = {};

	Array.prototype.forEach.call(
		document.querySelectorAll('body [id]'),
		v => result[v.getAttribute('id')] = v
	);

	return result;
}
