# Copyright (c) 2026, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "stock_entry",
			"label": "Stock Entry",
			"fieldtype": "Link",
			"options": "Stock Entry",
			"width": 120
		},
		{
			"fieldname": "posting_date",
			"label": "Posting Date",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"fieldname": "item_code",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120
		},
		{
			"fieldname": "item_name",
			"label": "Item Name",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "qty",
			"label": "Quantity",
			"fieldtype": "Float",
			"width": 100
		},
		{
			"fieldname": "uom",
			"label": "UOM",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 80
		},
		{
			"fieldname": "s_warehouse",
			"label": "Source Warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 150
		},
		{
			"fieldname": "t_warehouse",
			"label": "Target Warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 150
		},
		{
			"fieldname": "po_valuation_per_pcs",
			"label": "PO Valuation Per Pcs",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"fieldname": "po_total_valuation",
			"label": "PO Total Valuation",
			"fieldtype": "Currency",
			"width": 150
		}
	]


def get_data(filters):
	# Default filter for target warehouse
	target_warehouse = filters.get("target_warehouse") or "Ramswami Medical - HOM"
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	
	# Build conditions
	conditions = [
		"se.docstatus = 1",
		"se.purpose = 'Material Transfer'",
		"sed.t_warehouse = %(target_warehouse)s"
	]
	
	params = {
		"target_warehouse": target_warehouse
	}
	
	if from_date:
		conditions.append("se.posting_date >= %(from_date)s")
		params["from_date"] = from_date
	
	if to_date:
		conditions.append("se.posting_date <= %(to_date)s")
		params["to_date"] = to_date
	
	where_clause = " AND ".join(conditions)
	
	# Build the query to get stock entry data
	query = f"""
		SELECT
			se.name AS stock_entry,
			se.posting_date,
			sed.item_code,
			sed.item_name,
			sed.qty,
			sed.uom,
			sed.s_warehouse,
			sed.t_warehouse,
			sed.po_detail
		FROM
			`tabStock Entry` se
		INNER JOIN
			`tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE
			{where_clause}
		ORDER BY
			se.posting_date DESC, se.name DESC, sed.idx
	"""
	
	data = frappe.db.sql(query, params, as_dict=True)
	
	# For each row, find the Purchase Order Item with custom_net_total
	for row in data:
		po_valuation_per_pcs = 0
		po_total_valuation = 0
		
		# Try to get PO via po_detail first (if exists)
		po_item = None
		if row.get("po_detail"):
			po_item = frappe.db.get_value(
				"Purchase Order Item",
				row.po_detail,
				["custom_net_total", "qty"],
				as_dict=True
			)
		
		# If not found via po_detail, find the most recent PO Item for this item
		if not po_item or not po_item.get("custom_net_total"):
			po_item_result = frappe.db.sql("""
				SELECT 
					poi.custom_net_total,
					poi.qty
				FROM `tabPurchase Order Item` poi
				INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
				WHERE poi.item_code = %(item_code)s
					AND po.docstatus = 1
					AND po.transaction_date <= %(posting_date)s
					AND IFNULL(poi.custom_net_total, 0) > 0
					AND IFNULL(poi.qty, 0) > 0
				ORDER BY po.transaction_date DESC, po.creation DESC
				LIMIT 1
			""", {
				"item_code": row.item_code,
				"posting_date": row.posting_date
			}, as_dict=True)
			
			if po_item_result:
				po_item = po_item_result[0]
		
		# Calculate valuation if PO item found
		if po_item and po_item.get("custom_net_total") and po_item.get("qty"):
			po_qty = flt(po_item.qty, 6)
			po_net_total = flt(po_item.custom_net_total, 6)
			
			if po_qty > 0:
				po_valuation_per_pcs = flt(po_net_total / po_qty, 6)
				po_total_valuation = flt(po_valuation_per_pcs * row.qty, 2)
		
		row.po_valuation_per_pcs = po_valuation_per_pcs
		row.po_total_valuation = po_total_valuation
		# Remove po_detail from output as it's not needed
		row.pop("po_detail", None)
	
	return data
