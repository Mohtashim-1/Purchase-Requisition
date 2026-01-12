import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt

def hello_world(doc, method):
    for i in doc.items:
        # i.amount = i.qty * i.rate  # standard amount calculation
        i.custom_gross_rate = i.qty * i.rate
        
        i.custom_net_total = i.custom_gross_rate - i.custom_discounted_amount 
        i.amount = i.custom_net_total
        frappe.db.commit()

        # percentage calculation

        # if not i.custom_gross_rate or i.custom_gross_rate <= 0:
        #     return

        if i.custom_discount_ is not None:
            # Recalculate the discounted amount when the discount percentage is present
            i.custom_discounted_amount = (i.custom_discount_ / 100) * i.custom_gross_rate
            

        elif i.custom_discounted_amount is not None:
            # Recalculate the discount percentage when the discounted amount is present
            i.custom_discount_ = (i.custom_discounted_amount / i.custom_gross_rate) * 100

        frappe.db.commit()
    
    # amount total
    total = 0
    for i in doc.items:
        total += i.amount
    doc.total = total
    # gross rate total 
    gross_rate = 0
    for i in doc.items:
        gross_rate += i.custom_gross_rate   
    doc.custom_gross_rate = gross_rate
    # discounted amount total
    discounted_amount = 0
    for i in doc.items:
        discounted_amount += i.custom_discounted_amount
    doc.custom_discounted_amount = discounted_amount

    # discounted percentage total
    doc.custom_discounted_percentage = (doc.custom_discounted_amount / doc.custom_gross_rate) * 100


    # net rate total 
    net_rate = 0 
    for i in doc.items:
        net_rate += i.custom_net_total 
    doc.custom_net_rate = net_rate


@frappe.whitelist()
def make_purchase_receipt_custom(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")

    pr_item_meta = frappe.get_meta("Purchase Receipt Item")

    def update_item(obj, target, source_parent):
        remaining_qty = flt(obj.qty) - flt(obj.received_qty)
        target.qty = remaining_qty
        target.stock_qty = remaining_qty * flt(obj.conversion_factor)
        target.amount = remaining_qty * flt(obj.rate)
        target.base_amount = remaining_qty * flt(obj.rate) * flt(source_parent.conversion_rate)

        gross_total = remaining_qty * flt(obj.rate)
        discount_percent = flt(getattr(obj, "custom_discount_", 0))
        discount_amount = getattr(obj, "custom_discounted_amount", None)

        if pr_item_meta.has_field("custom_gross_rate"):
            target.custom_gross_rate = gross_total
        if discount_percent:
            if pr_item_meta.has_field("custom_discount_"):
                target.custom_discount_ = discount_percent
            if pr_item_meta.has_field("custom_discounted_amount"):
                target.custom_discounted_amount = (discount_percent / 100) * gross_total
        elif discount_amount:
            source_qty = flt(getattr(obj, "qty", 0))
            scaled_discount_amount = 0
            if source_qty:
                scaled_discount_amount = flt(discount_amount) * (remaining_qty / source_qty)
            else:
                scaled_discount_amount = flt(discount_amount)
            if pr_item_meta.has_field("custom_discounted_amount"):
                target.custom_discounted_amount = scaled_discount_amount
            if pr_item_meta.has_field("custom_discount_"):
                target.custom_discount_ = (scaled_discount_amount / gross_total) * 100 if gross_total else 0
        else:
            if pr_item_meta.has_field("custom_discount_"):
                target.custom_discount_ = 0
            if pr_item_meta.has_field("custom_discounted_amount"):
                target.custom_discounted_amount = 0

        if pr_item_meta.has_field("custom_net_total"):
            target.custom_net_total = gross_total - flt(getattr(target, "custom_discounted_amount", 0))

        if remaining_qty:
            per_qty_discount = flt(getattr(target, "custom_discounted_amount", 0)) / remaining_qty
        else:
            per_qty_discount = 0

        net_rate_value = flt(obj.rate) - per_qty_discount
        net_amount_value = net_rate_value * remaining_qty

        if pr_item_meta.has_field("price_list_rate"):
            target.price_list_rate = flt(obj.rate)
        if pr_item_meta.has_field("discount_percentage"):
            target.discount_percentage = discount_percent
        if pr_item_meta.has_field("discount_amount"):
            target.discount_amount = per_qty_discount
        target.rate = net_rate_value

        if pr_item_meta.has_field("net_rate"):
            target.net_rate = net_rate_value
        if pr_item_meta.has_field("net_amount"):
            target.net_amount = net_amount_value
        target.amount = net_amount_value

        target.base_rate = net_rate_value * flt(source_parent.conversion_rate)
        target.base_amount = net_amount_value * flt(source_parent.conversion_rate)
        if pr_item_meta.has_field("base_net_rate"):
            target.base_net_rate = net_rate_value * flt(source_parent.conversion_rate)
        if pr_item_meta.has_field("base_net_amount"):
            target.base_net_amount = net_amount_value * flt(source_parent.conversion_rate)

    return get_mapped_doc(
        "Purchase Order",
        source_name,
        {
            "Purchase Order": {
                "doctype": "Purchase Receipt",
                "field_map": {"supplier_warehouse": "supplier_warehouse"},
                "validation": {"docstatus": ["=", 1]},
            },
            "Purchase Order Item": {
                "doctype": "Purchase Receipt Item",
                "field_map": {
                    "name": "purchase_order_item",
                    "parent": "purchase_order",
                    "bom": "bom",
                    "material_request": "material_request",
                    "material_request_item": "material_request_item",
                    "sales_order": "sales_order",
                    "sales_order_item": "sales_order_item",
                    "wip_composite_asset": "wip_composite_asset",
                    "price_list_rate": "price_list_rate",
                    "discount_percentage": "discount_percentage",
                    "discount_amount": "discount_amount",
                    "rate": "rate",
                    "net_rate": "net_rate",
                    "net_amount": "net_amount",
                    "base_rate": "base_rate",
                    "base_amount": "base_amount",
                    "base_net_rate": "base_net_rate",
                    "base_net_amount": "base_net_amount",
                },
                "postprocess": update_item,
                "condition": lambda doc: abs(doc.received_qty) < abs(doc.qty)
                and doc.delivered_by_supplier != 1,
            },
            "Purchase Taxes and Charges": {"doctype": "Purchase Taxes and Charges", "add_if_empty": True},
        },
        target_doc,
        set_missing_values,
    )
