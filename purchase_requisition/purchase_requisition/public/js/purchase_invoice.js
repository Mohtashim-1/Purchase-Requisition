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

    if (row.custom_discount_percentage !== null && row.custom_discount_percentage !== undefined) {
        row.custom_discounted_amount = (pi_flt(row.custom_discount_percentage) / 100) * pi_flt(row.custom_gross_total);
    } else if (!row.custom_discounted_amount) {
        row.custom_discounted_amount = 0;
    }

    row.custom_discounted_amount = Math.min(pi_flt(row.custom_discounted_amount), pi_flt(row.custom_gross_total));
    row.custom_net_amount = Math.max(0, pi_flt(row.custom_gross_total) - pi_flt(row.custom_discounted_amount));
    row.amount = row.custom_net_amount;
}

function sync_mapped_pi_amounts(frm) {
    let gross_total = 0;
    let discount_total = 0;
    let net_total = 0;
    let has_changes = false;

    (frm.doc.items || []).forEach((row) => {
        row.custom_gross_total = pi_flt(row.custom_gross_total) || (pi_flt(row.qty) * pi_flt(row.rate));
        row.custom_discounted_amount = pi_flt(row.custom_discounted_amount);
        row.custom_net_amount = pi_flt(row.custom_net_amount) || (pi_flt(row.custom_gross_total) - pi_flt(row.custom_discounted_amount));

        if (row.pr_detail && Math.abs(pi_flt(row.amount) - pi_flt(row.custom_net_amount)) > 0.01) {
            row.amount = pi_flt(row.custom_net_amount);
            if (Object.prototype.hasOwnProperty.call(row, 'base_amount')) {
                row.base_amount = pi_flt(row.custom_net_amount);
            }
            has_changes = true;
        }

        gross_total += pi_flt(row.custom_gross_total);
        discount_total += pi_flt(row.custom_discounted_amount);
        net_total += pi_flt(row.amount || row.custom_net_amount);
    });

    frm.doc.custom_gross_rate = gross_total;
    frm.doc.custom_discounted_amount = discount_total;
    frm.doc.custom_discounted_percentage = gross_total > 0 ? (discount_total / gross_total) * 100 : 0;
    frm.doc.custom_net_rate = net_total;

    if (Math.abs(pi_flt(frm.doc.total) - net_total) > 0.01) {
        frm.doc.total = net_total;
        frm.doc.net_total = net_total;
        frm.doc.base_total = net_total;
        frm.doc.base_net_total = net_total;
        frm.doc.grand_total = net_total;
        frm.doc.base_grand_total = net_total;
        frm.doc.rounded_total = net_total;
        frm.doc.base_rounded_total = net_total;
        frm.doc.outstanding_amount = net_total;
        has_changes = true;
    }

    if (has_changes) {
        frm.refresh_field('items');
        frm.refresh_fields([
            'custom_gross_rate',
            'custom_discounted_amount',
            'custom_discounted_percentage',
            'custom_net_rate',
            'total',
            'net_total',
            'grand_total',
            'outstanding_amount'
        ]);
    }
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
        } else if (!pi_flt(row.custom_discounted_amount)) {
            row.custom_discounted_amount = 0;
            row.custom_discount_percentage = 0;
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
    onload: function(frm) {
        sync_mapped_pi_amounts(frm);
    },

    refresh: function(frm) {
        sync_mapped_pi_amounts(frm);
    },

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

        if (Math.abs(pi_flt(frm.doc.total) - net_total) > 0.01) {
            frm.doc.total = net_total;
            frm.doc.net_total = net_total;
            frm.doc.base_total = net_total;
            frm.doc.base_net_total = net_total;
            frm.doc.grand_total = net_total;
            frm.doc.base_grand_total = net_total;
            frm.doc.rounded_total = net_total;
            frm.doc.base_rounded_total = net_total;
            frm.doc.outstanding_amount = net_total;
            frm.refresh_fields(['total', 'net_total', 'grand_total', 'outstanding_amount']);
        }
    }
});
