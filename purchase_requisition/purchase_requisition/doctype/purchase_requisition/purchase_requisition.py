import frappe
from frappe.model.document import Document

class PurchaseRequisition(Document):
    def validate(self):
        self.last_purchase_rate()
    
    def last_purchase_rate(self):
        frappe.msgprint('c')
        for i in self.purchase_requisition_ct:
            # Ensure that the query is properly parameterized
            rate = frappe.db.sql("""
                SELECT poi.rate, poi.amount, po.supplier 
                FROM `tabPurchase Order` po
                LEFT JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
                WHERE poi.item_code = %s
                ORDER BY po.creation DESC
                LIMIT 1
            """, (i.item_code,), as_dict=True)
            
            frappe.msgprint(f'Fetched rate: {rate}')
            
            # Check if a result is returned
            if rate:
                # Update the existing row with the fetched rate and supplier
                i.last_purchase_rate = rate[0].get('rate', 0.0)  # Default to 0.0 if rate is None
                i.last_purchased_vendor = rate[0].get('supplier', '')
            else:
                # Handle the case where no result is found (optional)
                frappe.msgprint(f'No purchase order found for item code: {i.item_code}')
        
        # Save the document after all updates
        # self.save()
        
        # Commit the changes to the database
        frappe.db.commit()  
        frappe.msgprint('Please refresh to view updated data')

@frappe.whitelist()
def get_data(mr_name):
    # Query the Material Request items based on the selected Material Request
    items = frappe.db.sql("""
        SELECT item_code, item_name, qty, uom, rate
        FROM `tabMaterial Request Item`
        WHERE parent = %s
    """, (mr_name,), as_dict=True)

    return items
