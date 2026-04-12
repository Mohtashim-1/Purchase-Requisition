frappe.ui.form.on("Purchase Valuation Adjustment", {
	async purchase_invoice(frm) {
		if (!frm.doc.purchase_invoice) {
			frm.clear_table("items");
			frm.set_value("company", null);
			frm.set_value("posting_date", null);
			frm.refresh_field("items");
			return;
		}

		const response = await frappe.call({
			method: "purchase_requisition.purchase_requisition.doctype.purchase_valuation_adjustment.purchase_valuation_adjustment.get_purchase_invoice_adjustment_preview",
			args: {
				purchase_invoice: frm.doc.purchase_invoice,
			},
		});

		const data = response.message || {};
		await frm.set_value("company", data.company || null);
		await frm.set_value("posting_date", data.posting_date || null);

		frm.clear_table("items");
		(data.items || []).forEach((row) => {
			const child = frm.add_child("items");
			Object.keys(row).forEach((key) => {
				child[key] = row[key];
			});
		});

		frm.refresh_field("items");
	},
});
