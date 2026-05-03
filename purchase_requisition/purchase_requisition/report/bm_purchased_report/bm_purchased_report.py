# Copyright (c) 2026, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	currency = get_company_currency(filters)

	report_summary = get_report_summary(data, currency)
	return columns, data, None, None, report_summary


def get_columns():
	return [
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Stock Entry"),
			"fieldname": "stock_entry",
			"fieldtype": "Link",
			"options": "Stock Entry",
			"width": 140,
		},
		{
			"label": _("Stock Entry Type"),
			"fieldname": "stock_entry_type",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 170,
		},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 130,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 170,
		},
		{
			"label": _("Target Warehouse"),
			"fieldname": "target_warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 180,
		},
		{
			"label": _("Item In Qty"),
			"fieldname": "item_in_qty",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Rate"),
			"fieldname": "basic_rate",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Item Costing"),
			"fieldname": "item_costing",
			"fieldtype": "Currency",
			"width": 140,
		},
	]


def get_data(filters):
	conditions = ["se.docstatus = 1", "IFNULL(sed.t_warehouse, '') != ''"]
	params = {}

	if filters.get("company"):
		conditions.append("se.company = %(company)s")
		params["company"] = filters.get("company")

	stock_entry_type = filters.get("stock_entry_type") or "BM IN"
	if stock_entry_type:
		conditions.append("se.stock_entry_type = %(stock_entry_type)s")
		params["stock_entry_type"] = stock_entry_type

	if filters.get("from_date"):
		conditions.append("se.posting_date >= %(from_date)s")
		params["from_date"] = filters.get("from_date")

	if filters.get("to_date"):
		conditions.append("se.posting_date <= %(to_date)s")
		params["to_date"] = filters.get("to_date")

	if filters.get("item_code"):
		conditions.append("sed.item_code = %(item_code)s")
		params["item_code"] = filters.get("item_code")

	if filters.get("target_warehouse"):
		conditions.append("sed.t_warehouse = %(target_warehouse)s")
		params["target_warehouse"] = filters.get("target_warehouse")

	where_clause = " AND ".join(conditions)

	data = frappe.db.sql(
		f"""
		SELECT
			se.posting_date,
			se.name AS stock_entry,
			se.stock_entry_type,
			se.company,
			sed.item_code,
			sed.item_name,
			sed.t_warehouse AS target_warehouse,
			sed.qty AS item_in_qty,
			sed.basic_rate,
			IFNULL(sed.basic_amount, sed.qty * sed.basic_rate) AS item_costing
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE {where_clause}
		ORDER BY se.posting_date DESC, se.creation DESC, sed.idx ASC
		""",
		params,
		as_dict=True,
	)

	for row in data:
		row.item_in_qty = flt(row.item_in_qty)
		row.basic_rate = flt(row.basic_rate)
		row.item_costing = flt(row.item_costing)

	return data


def get_company_currency(filters):
	company = filters.get("company")
	if company:
		return frappe.get_cached_value("Company", company, "default_currency")

	return frappe.defaults.get_global_default("currency")


def get_report_summary(data, currency):
	total_qty = sum(flt(row.get("item_in_qty")) for row in data)
	total_costing = sum(flt(row.get("item_costing")) for row in data)

	return [
		{
			"label": _("Total Item In Qty"),
			"value": total_qty,
			"datatype": "Float",
		},
		{
			"label": _("Total Item Costing"),
			"value": total_costing,
			"datatype": "Currency",
			"currency": currency,
		},
	]
