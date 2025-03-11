import frappe
from frappe.model.document import Document

class PurchaseRequisition(Document):
    def validate(self):
        self.last_purchase_rate()
        self.schedule_date()
    
    def schedule_date(self):
        delivery = self.delivery_date
        for i in self.purchase_requisition_ct:
            i.schedule_date = delivery
    
    def last_purchase_rate(self):
        # frappe.msgprint('c')
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
            
            # frappe.msgprint(f'Fetched rate: {rate}')
            
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
        # frappe.msgprint('Please refresh to view updated data')

@frappe.whitelist()
def get_data(mr_name):
    # Query the Material Request items based on the selected Material Request
    items = frappe.db.sql("""
        SELECT name,item_code, item_name, qty, uom, rate,warehouse
        FROM `tabMaterial Request Item`
        WHERE parent = %s
    """, (mr_name,), as_dict=True)

    return items



@frappe.whitelist()
def make_purchase_order(purchase_requisition_name, supplier):
    # Get the Purchase Requisition document
    purchase_requisition = frappe.get_doc("Purchase Requisition", purchase_requisition_name)
    
    # Create a new Purchase Order document
    purchase_order = frappe.new_doc("Purchase Order")
    purchase_order.supplier = supplier
    purchase_order.schedule_date = purchase_requisition.delivery_date
    
    # Map items from Purchase Requisition child table to Purchase Order
    for item in purchase_requisition.purchase_requisition_ct:  # Assuming 'purchase_requisition_ct' is the child table name in Purchase Requisition
        purchase_order.append("items", {
            "item_code": item.item_code,
            "qty": item.qty,
            "schedule_date": item.schedule_date,
            "warehouse": item.target_warehouse
        })
    
    # Save and return the newly created document
    purchase_order.insert()
    return purchase_order.name



@frappe.whitelist()
def create_purchase_requisition(material_request):
    # Fetch Material Request document
    mr_doc = frappe.get_doc("Material Request", material_request)

    # Create new Purchase Requisition document
    pr_doc = frappe.new_doc("Purchase Requisition")
    pr_doc.material_request = mr_doc.name  # Link the MR to PR
    pr_doc.company = mr_doc.company  # Copy company
    pr_doc.transaction_date = frappe.utils.today()

    # Copy items from Material Request to Purchase Requisition
    for item in mr_doc.items:
        pr_doc.append("purchase_requisition_ct", {  # Replace with your actual child table name
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "material_request": mr_doc.name  # Link the MR item to PR
        })

    # Save and submit the Purchase Requisition
    pr_doc.insert()
    # pr_doc.submit()

    return pr_doc.name  # Return the new PR name


@frappe.whitelist()
def get_pr_items(pr_name):
    # Fetch items from Purchase Requisition
    items = frappe.db.sql("""
        SELECT item_code, name1, qty, uom, last_purchase_rate,target_warehouse
        FROM `tabPurchase Requisition CT`
        WHERE parent = %s
    """, (pr_name,), as_dict=True)

    return items
