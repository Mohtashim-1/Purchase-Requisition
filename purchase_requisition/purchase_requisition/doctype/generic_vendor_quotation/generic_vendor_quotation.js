// Copyright (c) 2026, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on("Generic Vendor Quotation", {
	generic(frm) {
		if (!frm.doc.generic) {
			return;
		}
		frappe.db.get_value(
			"Generic",
			frm.doc.generic,
			["generic_name", "strength", "form"],
			(r) => {
				if (!r) {
					return;
				}
				const parts = [r.generic_name, r.strength, r.form].filter(Boolean).join(" · ");
				if (parts) {
					frm.set_intro(__("Selected generic: {0}", [parts]), "blue");
				}
			}
		);
	},
	refresh(frm) {
		if (!frm.doc.generic) {
			frm.set_intro("");
		}
	},
});
