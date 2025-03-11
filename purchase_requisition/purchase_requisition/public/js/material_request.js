frappe.ui.form.on('Material Request', {
    refresh: function (frm) {
        if (!frm.doc.__islocal) {  // Ensure the document is saved before allowing PR creation
            frm.add_custom_button(__('Create Purchase Requisition'), function () {
                frappe.call({
                    method: "purchase_requisition.purchase_requisition.doctype.purchase_requisition.purchase_requisition.create_purchase_requisition",
                    args: {
                        material_request: frm.doc.name
                    },
                    callback: function (r) {
                        if (r.message) {
                            frappe.msgprint(__('Purchase Requisition {0} created successfully.', [r.message]));
                            frappe.set_route("Form", "Purchase Requisition", r.message);
                        }
                    }
                });
            }, __("Create")); // Adds button under "Create" menu
        }
    }
});
