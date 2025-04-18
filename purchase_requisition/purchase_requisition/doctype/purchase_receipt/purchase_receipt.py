import frappe
from frappe.model.document import Document

def get_pr_in_grn(doc, method):
    for i in doc.items:
        purchase_order_ref = frappe.get_doc("Purchase Order Item",i.purchase_order_item)
        
        purchase_requisition = purchase_order_ref.custom_purchase_requisition
        purchase_requisition_item = purchase_order_ref.custom_purchase_requisition_item
        
        i.custom_purchase_requisition = purchase_requisition
        i.custom_purchase_requisition_item = purchase_requisition_item
        
        frappe.db.commit()
    