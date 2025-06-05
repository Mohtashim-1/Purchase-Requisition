import frappe
from frappe.utils import money_in_words
from frappe.model.mapper import get_mapped_doc


def preserve_po_rate(doc, method):
    for item in doc.items:
        if item.po_detail:
            po_item = frappe.db.get_value("Purchase Order Item", item.po_detail, "rate")
            if po_item:
                item.rate = po_item

def calculation_pi(doc, method):
    gross_total = 0
    discounted_total = 0
    net_total = 0

    for i in doc.items:
        # Always compute gross
        i.custom_gross_total = i.qty * i.rate

        # Only compute discount if one value is missing
        if i.custom_discount_percentage and not i.custom_discounted_amount:
            i.custom_discounted_amount = (i.custom_discount_percentage / 100) * i.custom_gross_total

        elif i.custom_discounted_amount and not i.custom_discount_percentage:
            i.custom_discount_percentage = (i.custom_discounted_amount / i.custom_gross_total) * 100

        # If both missing, assume 0
        if not i.custom_discounted_amount:
            i.custom_discounted_amount = 0
        if not i.custom_discount_percentage:
            i.custom_discount_percentage = 0

        # Final net and amount calculation
        i.custom_net_amount = i.custom_gross_total - i.custom_discounted_amount
        i.amount = i.custom_net_amount

        # Totals
        gross_total += i.custom_gross_total
        discounted_total += i.custom_discounted_amount
        net_total += i.custom_net_amount

    # Update parent fields
    doc.custom_gross_rate = gross_total
    doc.custom_discounted_amount = discounted_total
    doc.custom_discounted_percentage = (discounted_total / gross_total * 100) if gross_total else 0
    doc.custom_net_rate = net_total

    # Taxes (if any)
    # tax_total = 0
    # for j in doc.taxes:
    #     j.tax_amount = float(net_total) * (float(j.rate) / 100)
    #     tax_total += j.tax_amount

    # doc.taxes_and_charges_added = tax_total
    # doc.total_taxes_and_charges = tax_total

    # Final totals
    doc.total = net_total
    doc.grand_total = net_total + doc.total_taxes_and_charges
    doc.rounded_total = doc.grand_total
    doc.outstanding_amount = doc.grand_total

    # Set in_words from custom_net_rate (your request)
    doc.in_words = money_in_words(doc.custom_net_rate, doc.currency)

@frappe.whitelist()
def make_purchase_invoice_custom(source_name, target_doc=None):
    def postprocess(source_doc, target_doc):
        target_doc.ignore_pricing_rule = 1
        target_doc.run_method("set_missing_values")
        target_doc.run_method("calculate_taxes_and_totals")

    
@frappe.whitelist()
def make_purchase_invoice_custom(source_name, target_doc=None):
    def postprocess(source_doc, target_doc):
        target_doc.ignore_pricing_rule = 1
        target_doc.run_method("set_missing_values")
        target_doc.run_method("calculate_taxes_and_totals")

    def set_missing_discount_fields(source_item, target_item, source_parent):
        # Get PO and PO Item if available
        purchase_order = getattr(source_item, "purchase_order", None)
        purchase_order_item = getattr(source_item, "purchase_order_item", None)

        if purchase_order and purchase_order_item:
            po_item = frappe.get_value(
                "Purchase Order Item",
                purchase_order_item,
                [
                    "custom_gross_rate",
                    "custom_discount_",
                    "custom_discounted_amount",
                    "custom_net_total"
                ],
                as_dict=True
            )
            if po_item:
                target_item.custom_gross_rate = po_item.custom_gross_rate
                target_item.custom_discount_ = po_item.custom_discount_
                target_item.custom_discounted_amount = po_item.custom_discounted_amount
                target_item.custom_net_total = po_item.custom_net_total

    return get_mapped_doc(
        "Purchase Receipt",
        source_name,
        {
            "Purchase Receipt": {
                "doctype": "Purchase Invoice",
                "validation": {"docstatus": ["=", 1]},
            },
            "Purchase Receipt Item": {
                "doctype": "Purchase Invoice Item",
                "field_map": {
                    "name": "pr_detail",
                    "parent": "purchase_receipt",
                    "purchase_order": "purchase_order",
                    "purchase_order_item": "po_detail",  # Needed by ERPNext
                    "custom_gross_total":"custom_gross_rate",
                    "custom_discounted_amount": "custom_discounted_amount",
                    "custom_discounted_percentage": "custom_discount_",
                    "custom_net_rate": "custom_net_total"
                },
                "postprocess": set_missing_discount_fields,
            },
        },
        target_doc,
        postprocess,
    )
