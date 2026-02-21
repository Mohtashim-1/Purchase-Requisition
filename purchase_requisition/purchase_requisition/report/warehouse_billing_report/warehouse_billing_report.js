// Copyright (c) 2026, mohtashim and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Warehouse Billing Report"] = {
	"filters": [
		{
			"fieldname": "target_warehouse",
			"label": __("Target Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"default": "Ramswami Medical - HOM",
			"reqd": 1
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
		}
	]
};
