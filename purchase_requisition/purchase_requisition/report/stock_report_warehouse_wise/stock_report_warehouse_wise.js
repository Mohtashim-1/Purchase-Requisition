// Copyright (c) 2024, mohtashim and contributors
// For license information, please see license.txt

frappe.query_reports["Stock Report WareHouse Wise"] = {

		"filters": [
        {
            "fieldname": "stock_entry_type",
            "label": "Stock Entry Type",
            "fieldtype": "Select",
            "options": "\nMaterial Transfer\nMaterial Issue\nMaterial Receipt\nManufacture\nRepack",
            "reqd": 1
        },
        {
            "fieldname": "from_warehouse",
            "label": "From Warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "reqd": 0
        },
        {
            "fieldname": "to_warehouse",
            "label": "To Warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "reqd": 0
        },
        {
            "fieldname": "from_date",
            "label": "From Date",
            "fieldtype": "Date",
            "reqd": 0
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date",
            "reqd": 0
        }
    ]
	
};
