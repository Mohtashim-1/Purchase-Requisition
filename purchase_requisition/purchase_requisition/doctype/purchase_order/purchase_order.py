import frappe

def hello_world(doc, method):
    for i in doc.items:
        i.custom_gross_rate = i.qty * i.rate
        i.amount -= i.custom_discounted_amount
        i.custom_net_total = i.custom_gross_rate - i.custom_discounted_amount 

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

