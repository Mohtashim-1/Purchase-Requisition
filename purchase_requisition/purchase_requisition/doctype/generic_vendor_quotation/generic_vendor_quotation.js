// Copyright (c) 2026, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on("Generic Vendor Quotation", {
	refresh(frm) {
		frm.set_df_property("items", "hidden", 1);
		frm.set_df_property("items_section", "hidden", 1);
		if (!frm.doc.generic) {
			frm.set_intro("");
		}
	},

	generic(frm) {
		set_generic_intro(frm);
		set_default_qty_from_generic(frm);
		set_item_from_mapping(frm);
	},

	supplier(frm) {
		set_item_from_mapping(frm);
	},

	rate(frm) {
		calculate_total_rate(frm);
	},

	discount_percent(frm) {
		calculate_total_rate(frm);
	},

	tax_amount(frm) {
		calculate_total_rate(frm);
	},
});

function calculate_total_rate(frm) {
	const rate = flt(frm.doc.rate);
	const discount = (rate * flt(frm.doc.discount_percent)) / 100;
	frm.set_value("total_rate", rate - discount + flt(frm.doc.tax_amount));
}

function set_generic_intro(frm) {
	if (!frm.doc.generic) {
		frm.set_intro("");
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
}

function set_default_qty_from_generic(frm) {
	if (!frm.doc.generic || flt(frm.doc.qty) > 1) {
		return;
	}
	frappe.db.get_value("Generic", frm.doc.generic, "default_unit", (r) => {
		if (r && r.default_unit) {
			frm.set_value("qty", r.default_unit);
		}
	});
}

function set_item_from_mapping(frm) {
	if (!frm.doc.generic || !frm.doc.supplier || frm.doc.item) {
		return;
	}
	frappe.db.get_value(
		"Generic Mapping",
		{ generic: frm.doc.generic, supplier: frm.doc.supplier },
		"item",
		(r) => {
			if (r && r.item) {
				frm.set_value("item", r.item);
			}
		}
	);
}
