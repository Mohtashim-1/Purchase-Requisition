frappe.ui.form.on('Purchase Requisition', {
    refresh: function (frm) {
        frm.add_custom_button(__('Fetch Items from MR'), function () {
            frappe.prompt(
                [
                    {
                        fieldname: 'mr_name',
                        label: 'Material Request',
                        fieldtype: 'Link',
                        options: 'Material Request',
                        reqd: 1
                    }
                ],
                function (values) {
                    // Call the backend method to get the data from the selected Material Request
                    frappe.call({
                        method: "purchase_requisition.purchase_requisition.doctype.purchase_requisition.purchase_requisition.get_data",
                        args: { mr_name: values.mr_name },  // Pass the selected MR name
                        callback: function (r) {
                            console.log(r.message);  // Log the response to check the data

                            if (r.message && r.message.length > 0) {
                                // Loop through the fetched items
                                r.message.forEach(item => {
                                    // Add each item to the child table
                                    let child_row = frm.add_child('purchase_requisition_ct');  // Assuming 'items' is your child table fieldname
                                    child_row.item_code = item.item_code;
                                    child_row.qty = item.qty;
                                    child_row.uom = item.uom;  // Add other fields as necessary
                                    // child_row.rate = item.rate;  // Add fields like rate, amount, etc.

                                    // Refresh the child table
                                    frm.refresh_field('purchase_requisition_ct');
                                });
                            }
                        }
                    });
                },
                __('Select Material Request'),
                __('Fetch')
            );
        });
    }
});


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
