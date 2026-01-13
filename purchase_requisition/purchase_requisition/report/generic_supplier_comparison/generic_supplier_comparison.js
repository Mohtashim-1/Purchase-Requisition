// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.query_reports["Generic Supplier Comparison"] = {
	"filters": [
		{
			"fieldname": "generic",
			"label": "Generic",
			"fieldtype": "Link",
			"options": "Item Group",
			"reqd": 1
		},
		{
			"fieldname": "company",
			"label": "Company",
			"fieldtype": "Link",
			"options": "Company"
		},
		{
			"fieldname": "from_date",
			"label": "Quotation From",
			"fieldtype": "Date"
		},
		{
			"fieldname": "to_date",
			"label": "Quotation To",
			"fieldtype": "Date"
		},
		{
			"fieldname": "valid_only",
			"label": "Valid Only",
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname": "currency",
			"label": "Currency",
			"fieldtype": "Link",
			"options": "Currency"
		},
		{
			"fieldname": "sort_by",
			"label": "Sort By",
			"fieldtype": "Select",
			"options": "Lowest Total Rate\nLowest Net Unit Cost\nShortest Lead Time\nLatest Validity",
			"default": "Lowest Total Rate"
		}
	],
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) {
			return value;
		}
		if (column.fieldname === "net_unit_cost" && data.is_lowest_cost) {
			value = `<span style="color: #14804a; font-weight: 600;">${value}</span>`;
		}
		if (column.fieldname === "lead_time_days" && data.is_fastest_lead_time) {
			value = `<span style="color: #1d4ed8; font-weight: 600;">${value}</span>`;
		}
		return value;
	}
};
