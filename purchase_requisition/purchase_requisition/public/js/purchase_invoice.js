function pi_flt(value) {
    return flt(value || 0);
}

function preserve_rate_after_discount_update(row, callback) {
    const preserved_rate = pi_flt(row.rate);
    const preserved_base_rate = pi_flt(row.base_rate || row.rate);

    callback();

    row.rate = preserved_rate;
    if (Object.prototype.hasOwnProperty.call(row, 'base_rate')) {
        row.base_rate = preserved_base_rate;
    }
}

function recalculate_row_from_discount(row) {
    preserve_rate_after_discount_update(row, () => {
        row.custom_gross_total = pi_flt(row.qty) * pi_flt(row.rate);
        row.custom_net_amount = pi_flt(row.custom_gross_total) - pi_flt(row.custom_discounted_amount);
        row.amount = row.custom_net_amount;
    });
}

function recalculate_row_from_qty_or_rate(row) {
    row.custom_gross_total = pi_flt(row.qty) * pi_flt(row.rate);

    if (row._discount_manually_edited) {
        if (row.custom_discount_percentage) {
            row.custom_discounted_amount = (pi_flt(row.custom_discount_percentage) / 100) * pi_flt(row.custom_gross_total);
        } else if (!row.custom_discounted_amount) {
            row.custom_discounted_amount = 0;
        }
    }

    row.custom_net_amount = pi_flt(row.custom_gross_total) - pi_flt(row.custom_discounted_amount);
    row.amount = row.custom_net_amount;
}

frappe.ui.form.on('Purchase Invoice Item', {
    custom_discount_percentage: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row._discount_manually_edited = true;

        if (row.custom_discount_percentage !== null && row.custom_discount_percentage !== undefined) {
            row.custom_gross_total = pi_flt(row.qty) * pi_flt(row.rate);
            row.custom_discounted_amount = (pi_flt(row.custom_discount_percentage) / 100) * pi_flt(row.custom_gross_total);
            recalculate_row_from_discount(row);
        }

        frm.trigger('recalculate_totals');
        frm.refresh_field('items');
    },

    custom_discounted_amount: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row._discount_manually_edited = true;
        row.custom_gross_total = pi_flt(row.qty) * pi_flt(row.rate);

        if (row.custom_discounted_amount !== null && row.custom_discounted_amount !== undefined && row.custom_gross_total) {
            row.custom_discount_percentage = (pi_flt(row.custom_discounted_amount) / pi_flt(row.custom_gross_total)) * 100;
            recalculate_row_from_discount(row);
        }

        frm.trigger('recalculate_totals');
        frm.refresh_field('items');
    },

    qty: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.qty && row.rate) {
            recalculate_row_from_qty_or_rate(row);
            frm.trigger('recalculate_totals');
            frm.refresh_field('items');
        }
    },

    rate: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.qty && row.rate) {
            recalculate_row_from_qty_or_rate(row);
            frm.trigger('recalculate_totals');
            frm.refresh_field('items');
        }
    }
});

frappe.ui.form.on('Purchase Invoice', {
    recalculate_totals: function(frm) {
        let gross_total = 0, discount_total = 0, net_total = 0;
        frm.doc.items.forEach(i => {
            if (!i.custom_gross_total) {
                i.custom_gross_total = pi_flt(i.qty) * pi_flt(i.rate);
            }
            gross_total += pi_flt(i.custom_gross_total);
            discount_total += pi_flt(i.custom_discounted_amount);
            net_total += pi_flt(i.amount || i.custom_net_amount);
        });

        frm.set_value('custom_gross_rate', gross_total);
        frm.set_value('custom_discounted_amount', discount_total);
        frm.set_value('custom_discounted_percentage', gross_total > 0 ? (discount_total / gross_total) * 100 : 0);
        frm.set_value('custom_net_rate', net_total);
    }
});
