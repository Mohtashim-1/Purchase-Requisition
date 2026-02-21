frappe.ui.form.on('Purchase Invoice Item', {
    // Handle discount percentage change
    custom_discount_percentage: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Calculate gross total first
        if (!row.custom_gross_total) {
            row.custom_gross_total = row.qty * row.rate;
        }

        // Recalculate discounted amount and net amount for the row
        if (row.custom_discount_percentage) {
            row.custom_discounted_amount = (row.custom_discount_percentage / 100) * row.custom_gross_total;
            row.custom_net_amount = row.custom_gross_total - row.custom_discounted_amount;
            row.amount = row.custom_net_amount;
        }

        // Trigger calculation
        frm.trigger('recalculate_totals');
        frm.refresh_field("items");
    },
    
    // Handle discounted amount change
    custom_discounted_amount: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Calculate gross total first
        if (!row.custom_gross_total) {
            row.custom_gross_total = row.qty * row.rate;
        }

        // Recalculate discount percentage and net amount
        if (row.custom_discounted_amount && row.custom_gross_total) {
            row.custom_discount_percentage = (row.custom_discounted_amount / row.custom_gross_total) * 100;
            row.custom_net_amount = row.custom_gross_total - row.custom_discounted_amount;
            row.amount = row.custom_net_amount;
        }

        // Trigger calculation
        frm.trigger('recalculate_totals');
        frm.refresh_field("items");
    },
    
    // Handle qty or rate change
    qty: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.qty && row.rate) {
            row.custom_gross_total = row.qty * row.rate;
            if (row.custom_discount_percentage) {
                row.custom_discounted_amount = (row.custom_discount_percentage / 100) * row.custom_gross_total;
            }
            row.custom_net_amount = row.custom_gross_total - (row.custom_discounted_amount || 0);
            row.amount = row.custom_net_amount;
            frm.trigger('recalculate_totals');
            frm.refresh_field("items");
        }
    },
    
    rate: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.qty && row.rate) {
            row.custom_gross_total = row.qty * row.rate;
            if (row.custom_discount_percentage) {
                row.custom_discounted_amount = (row.custom_discount_percentage / 100) * row.custom_gross_total;
            }
            row.custom_net_amount = row.custom_gross_total - (row.custom_discounted_amount || 0);
            row.amount = row.custom_net_amount;
            frm.trigger('recalculate_totals');
            frm.refresh_field("items");
        }
    }
});

frappe.ui.form.on('Purchase Invoice', {
    recalculate_totals: function(frm) {
        // Manually update parent level totals
        let gross_total = 0, discount_total = 0, net_total = 0;
        frm.doc.items.forEach(i => {
            gross_total += i.custom_gross_total || (i.qty * i.rate);
            discount_total += i.custom_discounted_amount || 0;
            net_total += i.custom_net_amount || (i.amount || 0);
        });

        frm.set_value('custom_gross_rate', gross_total);
        frm.set_value('custom_discounted_amount', discount_total);
        frm.set_value('custom_discounted_percentage', (gross_total > 0 ? (discount_total / gross_total) * 100 : 0));
        frm.set_value('custom_net_rate', net_total);
    }
});
