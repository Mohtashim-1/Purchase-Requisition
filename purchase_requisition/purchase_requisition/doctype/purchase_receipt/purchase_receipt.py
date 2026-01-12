import frappe
from frappe.utils import flt


def _copy_po_item_fields(po_item, receipt_item):
    meta = frappe.get_meta("Purchase Receipt Item")
    field_map = {
        "price_list_rate": "price_list_rate",
        "discount_percentage": "discount_percentage",
        "discount_amount": "discount_amount",
        "rate": "rate",
        "amount": "amount",
        "net_rate": "net_rate",
        "net_amount": "net_amount",
        "base_rate": "base_rate",
        "base_amount": "base_amount",
        "base_net_rate": "base_net_rate",
        "base_net_amount": "base_net_amount",
        "custom_gross_rate": "custom_gross_rate",
        "custom_discount_": "custom_discount_",
        "custom_discounted_amount": "custom_discounted_amount",
        "custom_net_total": "custom_net_total",
    }

    for source_field, target_field in field_map.items():
        if not meta.has_field(target_field):
            continue
        value = getattr(po_item, source_field, None)
        if value is not None and (getattr(receipt_item, target_field, None) in (None, 0, "")):
            setattr(receipt_item, target_field, value)


def _recalculate_item_totals(receipt_item, source_rate, conversion_rate):
    meta = frappe.get_meta("Purchase Receipt Item")
    qty = flt(receipt_item.qty)
    gross_rate = flt(source_rate)
    gross_total = qty * gross_rate

    discount_percent = flt(getattr(receipt_item, "custom_discount_", 0))
    discount_total = flt(getattr(receipt_item, "custom_discounted_amount", 0))

    if discount_percent and gross_total:
        discount_total = (discount_percent / 100) * gross_total
    elif discount_total and gross_total:
        discount_percent = (discount_total / gross_total) * 100

    net_total = gross_total - discount_total

    per_unit_discount = discount_total / qty if qty else 0
    net_rate = gross_rate - per_unit_discount

    if meta.has_field("custom_gross_rate"):
        receipt_item.custom_gross_rate = gross_total
    if meta.has_field("custom_discount_"):
        receipt_item.custom_discount_ = discount_percent
    if meta.has_field("custom_discounted_amount"):
        receipt_item.custom_discounted_amount = discount_total
    if meta.has_field("custom_net_total"):
        receipt_item.custom_net_total = net_total

    if meta.has_field("price_list_rate"):
        receipt_item.price_list_rate = gross_rate
    if meta.has_field("discount_percentage"):
        receipt_item.discount_percentage = discount_percent
    if meta.has_field("discount_amount"):
        receipt_item.discount_amount = per_unit_discount

    receipt_item.rate = net_rate
    receipt_item.net_rate = net_rate
    receipt_item.amount = net_total
    receipt_item.net_amount = net_total

    base_rate = net_rate * flt(conversion_rate or 1)
    base_amount = net_total * flt(conversion_rate or 1)
    receipt_item.base_rate = base_rate
    receipt_item.base_amount = base_amount
    receipt_item.base_net_rate = receipt_item.base_rate
    receipt_item.base_net_amount = receipt_item.base_amount


def get_pr_in_grn(doc, method):
    meta = frappe.get_meta("Purchase Receipt Item")
    conversion_rate = flt(doc.conversion_rate or 1)
    for i in doc.items:
        if not i.purchase_order_item:
            continue

        purchase_order_ref = frappe.get_doc("Purchase Order Item", i.purchase_order_item)

        i.custom_purchase_requisition = purchase_order_ref.custom_purchase_requisition
        i.custom_purchase_requisition_item = purchase_order_ref.custom_purchase_requisition_item

        _copy_po_item_fields(purchase_order_ref, i)
        source_rate = purchase_order_ref.rate or i.rate
        _recalculate_item_totals(i, source_rate, conversion_rate)

        frappe.db.commit()

    doc.run_method("calculate_taxes_and_totals")
    
