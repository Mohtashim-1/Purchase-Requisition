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
