// Copyright (c) 2026, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on("Generic", {
	generic_id(frm) {
		if (frm.doc.generic_id) {
			frm.set_value("generic_id", String(frm.doc.generic_id).trim().toUpperCase());
		}
	},
});
