frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Set default company if not already set
        if (!frm.doc.company && frm.doc.__islocal) {
            frappe.call({
                method: 'purchase_requisition.purchase_requisition.custom.sales_invoice.get_user_default_company',
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('company', r.message);
                    }
                }
            });
        }
    },
    
    company: function(frm) {
        // This function will be called when company field changes
        // You can add additional logic here if needed
        console.log('Company changed to:', frm.doc.company);
    }
}); 