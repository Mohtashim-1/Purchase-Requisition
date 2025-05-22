import frappe
from frappe.utils import money_in_words


def preserve_po_rate(doc, method):
    for item in doc.items:
        if item.po_detail:
            po_item = frappe.db.get_value("Purchase Order Item", item.po_detail, "rate")
            if po_item:
                item.rate = po_item

def calculation_pi(doc, method):
    for i in doc.items:
        i.custom_gross_total = i.qty * i.rate
        i.amount = i.custom_net_amount
        i.custom_net_amount = i.custom_gross_total - i.custom_discounted_amount 

        frappe.db.commit()

        # percentage calculation

        if not i.custom_gross_total or i.custom_gross_total <= 0:
            return

        if i.custom_discount_percentage is not None:
            # Recalculate the discounted amount when the discount percentage is present
            i.custom_discounted_amount = (i.custom_discount_percentage / 100) * i.custom_gross_total
            i.custom_net_amount = i.custom_gross_total - i.custom_discounted_amount
            i.amount = i.custom_net_amount

        elif i.custom_discounted_amount is not None:
            # Recalculate the discount percentage when the discounted amount is present
            i.custom_discount_percentage = (i.custom_discounted_amount / i.custom_gross_total) * 100
            i.custom_net_amount = i.custom_gross_total - i.custom_discounted_amount
            i.amount = i.custom_net_amount

        frappe.db.commit()
    
    tax_total = 0    
    for j in doc.taxes:
        j.tax_amount = float(doc.custom_net_rate) * (float(j.rate) / 100)
        tax_total += j.tax_amount  # Now summing the updated value
    doc.taxes_and_charges_added = tax_total
    doc.total_taxes_and_charges = tax_total
    frappe.db.commit()    
    
    # amount total
    total = 0
    for i in doc.items:
        total += i.amount
    doc.total = total
    # gross rate total 
    gross_rate = 0
    for i in doc.items:
        gross_rate += i.custom_gross_total   
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
        net_rate += i.custom_net_amount 
    doc.custom_net_rate = net_rate
    doc.grand_total = net_rate + doc.total_taxes_and_charges
    doc.rounded_total = net_rate + doc.total_taxes_and_charges
    doc.outstanding_amount = net_rate + doc.total_taxes_and_charges
    doc.in_words = money_in_words(doc.grand_total, doc.currency)
    # doc.in_words = # how to do  i have this doc.in_words field it is showing in_words from doc.grand_total field i want in_words will show from doc.net_total is it possible in erpnext python 

