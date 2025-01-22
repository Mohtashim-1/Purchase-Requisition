// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.query_reports["Patient Appointment"] = {
	"filters": [
		{
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company")
        },
        {
            "fieldname": "date",
            "label": __("Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "practitioner",
            "label": __("Practitioner Name"),
            "fieldtype": "Link",
            "options": "Healthcare Practitioner"
        },
        {
            "fieldname": "patient",
            "label": __("Patient Name"),
            "fieldtype": "Link",
            "options": "Patient"
        },
        {
            "fieldname": "department",
            "label": __("Department"),
            "fieldtype": "Link",
			"options":"Medical Department"
        }
	]
};
