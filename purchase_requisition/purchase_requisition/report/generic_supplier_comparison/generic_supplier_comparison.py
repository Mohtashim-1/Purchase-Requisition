import frappe
from frappe.utils import flt, today


def execute(filters=None):
    filters = frappe._dict(filters or {})

    if not filters.get("generic"):
        frappe.throw("Generic is required.")

    conditions = ["parent.docstatus < 2", "parent.generic = %(generic)s"]
    values = {"generic": filters.generic}

    if filters.get("company"):
        conditions.append("parent.company = %(company)s")
        values["company"] = filters.company

    if filters.get("from_date"):
        conditions.append("parent.quotation_date >= %(from_date)s")
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        conditions.append("parent.quotation_date <= %(to_date)s")
        values["to_date"] = filters.to_date

    if filters.get("currency"):
        conditions.append("parent.currency = %(currency)s")
        values["currency"] = filters.currency

    if filters.get("valid_only"):
        conditions.append(
            "parent.valid_from <= %(today)s AND parent.valid_upto >= %(today)s "
            "AND parent.status NOT IN ('Expired', 'Cancelled')"
        )
        values["today"] = today()

    where_clause = " AND ".join(conditions)
    total_rate_expr = (
        "(child.rate - (child.rate * IFNULL(child.discount_percent, 0) / 100) "
        "+ IFNULL(child.tax_amount, 0))"
    )

    sort_by = filters.get("sort_by") or "Lowest Total Rate"
    order_by_map = {
        "Lowest Total Rate": f"total_rate ASC",
        "Lowest Net Unit Cost": "net_unit_cost ASC",
        "Shortest Lead Time": "lead_time_days ASC",
        "Latest Validity": "valid_upto DESC",
    }
    order_by = order_by_map.get(sort_by, "total_rate ASC")

    query = f"""
        SELECT
            parent.name AS quotation_no,
            parent.quotation_date AS quotation_date,
            parent.supplier AS supplier,
            parent.generic AS generic,
            child.item AS item,
            child.uom AS uom,
            child.qty AS qty,
            child.rate AS rate,
            child.discount_percent AS discount_percent,
            child.tax_amount AS tax_amount,
            IFNULL(child.total_rate, {total_rate_expr}) AS total_rate,
            parent.lead_time_days AS lead_time_days,
            parent.payment_terms AS payment_terms,
            parent.valid_upto AS valid_upto,
            parent.status AS status,
            parent.currency AS currency
        FROM `tabGeneric Vendor Quotation Item` child
        INNER JOIN `tabGeneric Vendor Quotation` parent
            ON child.parent = parent.name
        WHERE {where_clause}
    """

    data = frappe.db.sql(query, values, as_dict=True)

    for row in data:
        qty = flt(row.qty)
        total_rate = flt(row.total_rate)
        row.net_unit_cost = (total_rate / qty) if qty else 0

    min_net_unit_cost = None
    min_lead_time = None
    for row in data:
        if min_net_unit_cost is None or flt(row.net_unit_cost) < min_net_unit_cost:
            min_net_unit_cost = flt(row.net_unit_cost)
        if row.lead_time_days is not None:
            if min_lead_time is None or flt(row.lead_time_days) < min_lead_time:
                min_lead_time = flt(row.lead_time_days)

    for row in data:
        row.is_lowest_cost = min_net_unit_cost is not None and flt(row.net_unit_cost) == min_net_unit_cost
        row.is_fastest_lead_time = (
            min_lead_time is not None and row.lead_time_days is not None and flt(row.lead_time_days) == min_lead_time
        )

    if order_by == "net_unit_cost ASC":
        data.sort(key=lambda d: flt(d.net_unit_cost))
    elif order_by == "lead_time_days ASC":
        data.sort(key=lambda d: (flt(d.lead_time_days) if d.lead_time_days is not None else 10**9))
    elif order_by == "valid_upto DESC":
        data.sort(key=lambda d: d.valid_upto or "", reverse=True)
    else:
        data.sort(key=lambda d: flt(d.total_rate))

    columns = [
        {"fieldname": "quotation_no", "label": "Quotation", "fieldtype": "Link", "options": "Generic Vendor Quotation", "width": 160},
        {"fieldname": "quotation_date", "label": "Quotation Date", "fieldtype": "Date", "width": 110},
        {"fieldname": "supplier", "label": "Supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
        {"fieldname": "generic", "label": "Generic", "fieldtype": "Link", "options": "Item Group", "width": 160},
        {"fieldname": "item", "label": "Item", "fieldtype": "Link", "options": "Item", "width": 160},
        {"fieldname": "uom", "label": "UOM", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"fieldname": "qty", "label": "Qty", "fieldtype": "Float", "width": 90},
        {"fieldname": "rate", "label": "Rate", "fieldtype": "Currency", "width": 100},
        {"fieldname": "discount_percent", "label": "Discount %", "fieldtype": "Float", "width": 90},
        {"fieldname": "tax_amount", "label": "Tax Amount", "fieldtype": "Currency", "width": 110},
        {"fieldname": "total_rate", "label": "Total Rate", "fieldtype": "Currency", "width": 110},
        {"fieldname": "net_unit_cost", "label": "Net Unit Cost", "fieldtype": "Currency", "width": 120},
        {"fieldname": "lead_time_days", "label": "Lead Time (Days)", "fieldtype": "Int", "width": 120},
        {"fieldname": "payment_terms", "label": "Payment Terms", "fieldtype": "Link", "options": "Payment Terms Template", "width": 160},
        {"fieldname": "valid_upto", "label": "Valid Upto", "fieldtype": "Date", "width": 110},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 90},
        {"fieldname": "currency", "label": "Currency", "fieldtype": "Link", "options": "Currency", "width": 90},
        {"fieldname": "is_lowest_cost", "label": "Lowest Cost", "fieldtype": "Check", "hidden": 1},
        {"fieldname": "is_fastest_lead_time", "label": "Fastest Lead", "fieldtype": "Check", "hidden": 1},
    ]

    return columns, data
