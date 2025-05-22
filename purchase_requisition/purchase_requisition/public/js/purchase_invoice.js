frappe.ui.form.on('Purchase Invoice Item', {
    custom_discount_: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Recalculate discounted amount and net total for the row
        if (row.custom_discount_) {
            row.custom_discounted_amount = (row.custom_discount_ / 100) * (row.qty * row.rate);
            row.custom_net_total = (row.qty * row.rate) - row.custom_discounted_amount;
        }

        // Manually update parent level totals
        let gross_total = 0, discount_total = 0, net_total = 0;
        frm.doc.items.forEach(i => {
            gross_total += i.qty * i.rate;
            discount_total += i.custom_discounted_amount || 0;
            net_total += i.custom_net_total || 0;
        });

        frm.set_value('custom_gross_rate', gross_total);
        frm.set_value('custom_discounted_amount', discount_total);
        frm.set_value('custom_discounted_percentage', (gross_total > 0 ? (discount_total / gross_total) * 100 : 0));
        frm.set_value('custom_net_rate', net_total);

        frm.refresh_field("items");
    }
});
