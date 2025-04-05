
frappe.ui.form.on('Purchase Requisition', {
    refresh: function (frm) {
        // Add a custom button to create Purchase Order
        frm.add_custom_button(__('Create Purchase Order'), function () {
            // Open a dialog to select the supplier
            let dialog = new frappe.ui.Dialog({
                title: __('Select Supplier'),
                fields: [
                    {
                        label: __('Supplier'),
                        fieldname: 'supplier',
                        fieldtype: 'Link',
                        options: 'Supplier',
                        reqd: 1
                    }
                ],
                primary_action_label: __('Create'),
                primary_action: function (data) {
                    if (!data.supplier) {
                        frappe.msgprint(__('Please select a supplier.'));
                        return;
                    }
                    dialog.hide();

                    // Call the server-side function to create the Purchase Order
                    frappe.call({
                        method: "purchase_requisition.purchase_requisition.doctype.purchase_requisition.purchase_requisition.make_purchase_order",
                        args: {
                            purchase_requisition_name: frm.doc.name,
                            supplier: data.supplier
                        },
                        callback: function (r) {
                            if (r.message) {
                                frappe.msgprint(__('Purchase Order {0} created successfully.', [r.message]));
                                frappe.set_route("Form", "Purchase Order", r.message);
                            }
                        }
                    });
                }
            });
            dialog.show();
        }, __("Create")); // Adds the button under the "Create" menu
    }
});
