// Copyright (c) 2026, mohtashim and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["BM Purchased Report"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "stock_entry_type",
			"label": __("Stock Entry Type"),
			"fieldtype": "Data",
			"default": "BM IN"
		},
		{
			"fieldname": "item_code",
			"label": __("Item Code"),
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname": "target_warehouse",
			"label": __("Target Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse"
		}
	]
};
