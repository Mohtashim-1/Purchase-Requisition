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
