import frappe

def execute(filters=None):
    conditions = ["sle.docstatus = 1", "sle.is_cancelled = 0", "b.expiry_date IS NOT NULL"]
    values = {}

    if filters.get("warehouse"):
        conditions.append("sle.warehouse = %(warehouse)s")
        values["warehouse"] = filters["warehouse"]

    if filters.get("from_date") and filters.get("to_date"):
        conditions.append("b.expiry_date BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters["from_date"]
        values["to_date"] = filters["to_date"]
    else:
        conditions.append("b.expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 90 DAY)")

    where_clause = " AND ".join(conditions)

    print("Filters:", filters)  # Debugging: Check if from_date and to_date are coming correctly

    query = f"""
        SELECT 
            sle.item_code AS item_code,
            sle.batch_no AS batch_no,
            sle.warehouse AS warehouse,
            SUM(sle.actual_qty) AS stock_qty,
            b.expiry_date AS expiry_date,
            DATEDIFF(b.expiry_date, CURDATE()) AS remaining_days
        FROM `tabStock Ledger Entry` sle
        LEFT JOIN `tabBatch` b ON sle.batch_no = b.name
        WHERE {where_clause}
        GROUP BY sle.item_code, sle.batch_no, sle.warehouse, b.expiry_date
        HAVING SUM(sle.actual_qty) > 0
        ORDER BY b.expiry_date ASC, sle.warehouse ASC
    """

    data = frappe.db.sql(query, values, as_dict=True)

    columns = [
        {"fieldname": "item_code", "label": "Item Code", "fieldtype": "Link", "options": "Item", "width": 200},
        {"fieldname": "batch_no", "label": "Batch No", "fieldtype": "Link", "options": "Batch", "width": 150},
        {"fieldname": "warehouse", "label": "Warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200},
        {"fieldname": "stock_qty", "label": "Stock Quantity", "fieldtype": "Float", "width": 120},
        {"fieldname": "expiry_date", "label": "Expiry Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "remaining_days", "label": "Remaining Days", "fieldtype": "Int", "width": 150},
    ]

    return columns, data
