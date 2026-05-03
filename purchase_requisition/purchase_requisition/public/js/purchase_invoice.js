function pi_flt(value) {
    return flt(value || 0);
}

function pi_log(label, payload) {
    try {
        // Keep logs concise but structured for debugging save-time resets.
        // eslint-disable-next-line no-console
        console.log(`[PI-CLIENT] ${label}`, payload || {});
    } catch (e) {
        // no-op
    }
}

function get_editable_rate(row) {
    return pi_flt(row.custom_po_rate || row.rate);
}

function normalize_row_display_rate(row) {
    if (!row) return;

    if (Object.prototype.hasOwnProperty.call(row, 'custom_po_rate') && !pi_flt(row.custom_po_rate)) {
        const po_rate_candidate = pi_flt(row.price_list_rate || row.rate);
        if (po_rate_candidate) row.custom_po_rate = po_rate_candidate;
    }

    const current_rate = get_editable_rate(row);
    if (current_rate) return;

    const price_list_rate = pi_flt(row.price_list_rate);
    if (price_list_rate) {
        row.custom_po_rate = price_list_rate;
        row.rate = price_list_rate;
        if (Object.prototype.hasOwnProperty.call(row, 'base_rate')) {
            row.base_rate = price_list_rate;
        }
        return;
    }

    const qty = pi_flt(row.qty);
    const gross_total = pi_flt(row.custom_gross_total);
    if (qty && gross_total) {
        const derived_rate = gross_total / qty;
        row.custom_po_rate = derived_rate;
        row.rate = derived_rate;
        if (Object.prototype.hasOwnProperty.call(row, 'base_rate')) {
            row.base_rate = derived_rate;
        }
        if (Object.prototype.hasOwnProperty.call(row, 'price_list_rate')) {
            row.price_list_rate = derived_rate;
        }
    }
}

function preserve_rate_after_discount_update(row, callback) {
    normalize_row_display_rate(row);
    const preserved_rate = get_editable_rate(row);
    const preserved_base_rate = pi_flt(row.base_rate || row.rate);

    callback();

    row.custom_po_rate = preserved_rate;
    row.rate = preserved_rate;
    if (Object.prototype.hasOwnProperty.call(row, 'base_rate')) {
        row.base_rate = preserved_base_rate;
    }
}

function recalculate_row_from_discount(row) {
    normalize_row_display_rate(row);
    pi_log('recalculate_row_from_discount:before', {
        idx: row.idx,
        qty: row.qty,
        custom_po_rate: row.custom_po_rate,
        rate: row.rate,
        custom_discounted_amount: row.custom_discounted_amount,
        custom_discount_percentage: row.custom_discount_percentage,
        custom_gross_total: row.custom_gross_total,
        custom_net_amount: row.custom_net_amount,
        amount: row.amount
    });
    preserve_rate_after_discount_update(row, () => {
        row.custom_gross_total = pi_flt(row.qty) * get_editable_rate(row);
        row.custom_net_amount = pi_flt(row.custom_gross_total) - pi_flt(row.custom_discounted_amount);
        row.amount = row.custom_net_amount;
    });
    pi_log('recalculate_row_from_discount:after', {
        idx: row.idx,
        qty: row.qty,
        custom_po_rate: row.custom_po_rate,
        rate: row.rate,
        custom_discounted_amount: row.custom_discounted_amount,
        custom_discount_percentage: row.custom_discount_percentage,
        custom_gross_total: row.custom_gross_total,
        custom_net_amount: row.custom_net_amount,
        amount: row.amount
    });
}

function recalculate_row_from_qty_or_rate(row) {
    normalize_row_display_rate(row);
    pi_log('recalculate_row_from_qty_or_rate:before', {
        idx: row.idx,
        qty: row.qty,
        custom_po_rate: row.custom_po_rate,
        rate: row.rate,
        custom_discounted_amount: row.custom_discounted_amount,
        custom_discount_percentage: row.custom_discount_percentage,
        custom_gross_total: row.custom_gross_total,
        custom_net_amount: row.custom_net_amount,
        amount: row.amount
    });
    row.custom_gross_total = pi_flt(row.qty) * get_editable_rate(row);

    if (row.custom_discount_percentage !== null && row.custom_discount_percentage !== undefined) {
        row.custom_discounted_amount = (pi_flt(row.custom_discount_percentage) / 100) * pi_flt(row.custom_gross_total);
    } else if (!row.custom_discounted_amount) {
        row.custom_discounted_amount = 0;
    }

    row.custom_discounted_amount = Math.min(pi_flt(row.custom_discounted_amount), pi_flt(row.custom_gross_total));
    row.custom_net_amount = Math.max(0, pi_flt(row.custom_gross_total) - pi_flt(row.custom_discounted_amount));
    row.amount = row.custom_net_amount;
    pi_log('recalculate_row_from_qty_or_rate:after', {
        idx: row.idx,
        qty: row.qty,
        custom_po_rate: row.custom_po_rate,
        rate: row.rate,
        custom_discounted_amount: row.custom_discounted_amount,
        custom_discount_percentage: row.custom_discount_percentage,
        custom_gross_total: row.custom_gross_total,
        custom_net_amount: row.custom_net_amount,
        amount: row.amount
    });
}

function sync_mapped_pi_amounts(frm) {
    pi_log('sync_mapped_pi_amounts:start', {
        doc: frm.doc.name,
        is_new: frm.is_new(),
        item_count: (frm.doc.items || []).length
    });
    let gross_total = 0;
    let discount_total = 0;
    let net_total = 0;
    let has_changes = false;

    (frm.doc.items || []).forEach((row) => {
        const before = {
            idx: row.idx,
            qty: row.qty,
            custom_po_rate: row.custom_po_rate,
            rate: row.rate,
            custom_discounted_amount: row.custom_discounted_amount,
            custom_discount_percentage: row.custom_discount_percentage,
            custom_gross_total: row.custom_gross_total,
            custom_net_amount: row.custom_net_amount,
            amount: row.amount
        };
        normalize_row_display_rate(row);
        row.custom_gross_total = pi_flt(row.custom_gross_total) || (pi_flt(row.qty) * get_editable_rate(row));
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
        pi_log('sync_mapped_pi_amounts:row', {
            before,
            after: {
                idx: row.idx,
                qty: row.qty,
                custom_po_rate: row.custom_po_rate,
                rate: row.rate,
                custom_discounted_amount: row.custom_discounted_amount,
                custom_discount_percentage: row.custom_discount_percentage,
                custom_gross_total: row.custom_gross_total,
                custom_net_amount: row.custom_net_amount,
                amount: row.amount
            }
        });
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
    pi_log('sync_mapped_pi_amounts:end', {
        doc: frm.doc.name,
        gross_total,
        discount_total,
        net_total,
        has_changes
    });
}

frappe.ui.form.on('Purchase Invoice Item', {
    custom_discount_percentage: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row._discount_manually_edited = true;

        if (row.custom_discount_percentage !== null && row.custom_discount_percentage !== undefined) {
            row.custom_gross_total = pi_flt(row.qty) * get_editable_rate(row);
            row.custom_discounted_amount = (pi_flt(row.custom_discount_percentage) / 100) * pi_flt(row.custom_gross_total);
            recalculate_row_from_discount(row);
        }

        frm.trigger('recalculate_totals');
        frm.refresh_field('items');
    },

    custom_discounted_amount: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row._discount_manually_edited = true;
        row.custom_gross_total = pi_flt(row.qty) * get_editable_rate(row);

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
        row._po_rate_manually_edited = true;
        if (row.qty && get_editable_rate(row)) {
            recalculate_row_from_qty_or_rate(row);
            frm.trigger('recalculate_totals');
            frm.refresh_field('items');
        }
    },

    rate: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row._po_rate_manually_edited = true;
        if (row.qty && get_editable_rate(row)) {
            recalculate_row_from_qty_or_rate(row);
            frm.trigger('recalculate_totals');
            frm.refresh_field('items');
        }
    },

    custom_po_rate: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row._po_rate_manually_edited = true;
        if (row.qty && get_editable_rate(row)) {
            recalculate_row_from_qty_or_rate(row);
            frm.trigger('recalculate_totals');
            frm.refresh_field('items');
        }
    }
});

frappe.ui.form.on('Purchase Invoice', {
    onload: function(frm) {
        pi_log('form_onload', { doc: frm.doc.name, is_new: frm.is_new() });
        sync_mapped_pi_amounts(frm);
    },

    refresh: function(frm) {
        pi_log('form_refresh', { doc: frm.doc.name, is_new: frm.is_new() });
        sync_mapped_pi_amounts(frm);
    },

    validate: function(frm) {
        pi_log('form_validate:before_save_snapshot', {
            doc: frm.doc.name,
            is_new: frm.is_new(),
            items: (frm.doc.items || []).map((i) => ({
                idx: i.idx,
                name: i.name,
                pr_detail: i.pr_detail,
                qty: i.qty,
                custom_po_rate: i.custom_po_rate,
                rate: i.rate,
                custom_discount_percentage: i.custom_discount_percentage,
                custom_discounted_amount: i.custom_discounted_amount,
                custom_gross_total: i.custom_gross_total,
                custom_net_amount: i.custom_net_amount,
                amount: i.amount
            }))
        });
    },

    recalculate_totals: function(frm) {
        pi_log('recalculate_totals:start', { doc: frm.doc.name, is_new: frm.is_new() });
        let gross_total = 0, discount_total = 0, net_total = 0;
        frm.doc.items.forEach(i => {
            if (!i.custom_gross_total) {
                i.custom_gross_total = pi_flt(i.qty) * get_editable_rate(i);
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
        pi_log('recalculate_totals:end', { gross_total, discount_total, net_total });
    }
});
