    

frappe.ui.form.on('Purchase Order', {
    refresh: function (frm) {
        if (frm.doc.docstatus === 0) {  // Ensure it's only available in draft mode
            frm.add_custom_button(__('Purchase Requisition'), function () {
                frappe.prompt(
                    [
                        {
                            fieldname: 'pr_name',
                            label: 'Purchase Requisition',
                            fieldtype: 'Link',
                            options: 'Purchase Requisition',
                            reqd: 1
                        }
                    ],
                    function (values) {
                        frappe.call({
                            method: "purchase_requisition.purchase_requisition.doctype.purchase_requisition.purchase_requisition.get_pr_items",
                            args: { pr_name: values.pr_name },  
                            callback: function (r) {
                                console.log("Fetched PR Items:", r.message);  

                                if (r.message && r.message.length > 0) {
                                    // **Clear Existing Rows Before Adding**
                                    frm.clear_table("items");

                                    r.message.forEach(item => {
                                        let child_row = frm.add_child('items');  
                                        child_row.item_code = item.item_code;
                                        child_row.item_name = item.name1;
                                        child_row.qty = item.qty;
                                        child_row.uom = item.uom;
                                        child_row.rate = item.last_purchase_rate;
                                        child_row.schedule_date = item.schedule_date;
                                        child_row.warehouse = item.target_warehouse;
                                        child_row.custom_purchase_requisition = values.pr_name; 
                                        child_row.custom_purchase_requisition_item = item.name;  
                                    });

                                    // **Refresh the table once after adding all rows**
                                    frm.refresh_field('items');
                                }
                            }
                        });
                    },
                    __('Get Items From'),
                    __('Fetch')
                );
            }, __("Get Items From"));  // This ensures it appears under "Get Items From"
        }
    }
});



  
// frappe.ui.form.on('Purchase Order', {
//     refresh: function (frm) {
//         frm.add_custom_button(__('Purchase Invoice New'), function () {
//             // Create a new Purchase Invoice and set values
//             frappe.model.with_doctype('Purchase Invoice', function () {
//                 let pi = frappe.model.get_new_doc('Purchase Invoice');

//                 // Set values from Purchase Order
//                 pi.supplier = frm.doc.supplier;
//                 // pi.purchase_order = frm.doc.name;

//                 // Optionally copy items from the Purchase Order
//                 frm.doc.items.forEach(item => {
//                     let pi_item = frappe.model.add_child(pi, 'items');
//                     pi_item.item_code = item.item_code;
//                     pi_item.item_name = item.item_name;
//                     pi_item.qty = item.qty;
//                     pi_item.uom = item.uom;
//                     pi_item.rate = item.rate || 0;
//                     pi_item.discount_percentage = item.discount_percentage;
//                     pi_item.discount_amount = item.discount_amount;

//                     pi_item.custom_gross_total = item.custom_gross_rate;
//                     pi_item.custom_discount_percentage = item.custom_discount_;
//                     pi_item.custom_discounted_amount = item.custom_discounted_amount;
//                     pi_item.custom_net_amount = item.custom_net_total;

//                     pi_item.custom_material_request = item.material_request;
//                     pi_item.custom_material_request_item = item.material_request_item;

//                     pi_item.custom_purchase_requisition = item.custom_purchase_requisition;
//                     pi_item.custom_purchase_requisition_item = item.custom_purchase_requisition_item;

//                     pi_item.po_detail = item.name;
//                     pi_item.purchase_order = frm.doc.name;


//                 });

//                 // Route to the new Purchase Invoice form
//                 frappe.set_route('Form', 'Purchase Invoice', pi.name);
//             });
//         }, __("Create"));
//     }
// });


frappe.ui.form.on('Purchase Order', {
    refresh: function (frm) {
        frm.add_custom_button(__('Purchase Invoice New'), function () {
            frappe.model.with_doctype('Purchase Invoice', function () {
                let pi = frappe.model.get_new_doc('Purchase Invoice');

                pi.supplier = frm.doc.supplier;
                pi.apply_price_list = 0;

                frm.doc.items.forEach(item => {
                    let pi_item = frappe.model.add_child(pi, 'items');
                    pi_item.item_code = item.item_code;
                    pi_item.item_name = item.item_name;
                    pi_item.qty = item.qty;
                    pi_item.uom = item.uom;
                    pi_item.rate = item.rate || 0;
                    pi_item.discount_percentage = item.discount_percentage;
                    pi_item.discount_amount = item.discount_amount;

                    pi_item.custom_gross_total = item.custom_gross_rate;
                    pi_item.custom_discount_percentage = item.custom_discount_;
                    pi_item.custom_discounted_amount = item.custom_discounted_amount;
                    pi_item.custom_net_amount = item.custom_net_total;

                    pi_item.custom_material_request = item.material_request;
                    pi_item.custom_material_request_item = item.material_request_item;

                    pi_item.custom_purchase_requisition = item.custom_purchase_requisition;
                    pi_item.custom_purchase_requisition_item = item.custom_purchase_requisition_item;

                    pi_item.po_detail = item.name;
                    pi_item.purchase_order = frm.doc.name;
                });

                // Insert and then route to form
                frappe.call({
                    method: "frappe.client.insert",
                    args: {
                        doc: pi
                    },
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.set_route('Form', 'Purchase Invoice', r.message.name);
                            frappe.msgprint(__('Purchase Invoice {0} created and saved.', [r.message.name]));
                        }
                    }
                });
            });
        }, __("Create"));
    }
});
