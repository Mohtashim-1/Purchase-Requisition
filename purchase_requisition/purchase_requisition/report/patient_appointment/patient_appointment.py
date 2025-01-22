# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt


import frappe
from frappe.utils import flt, getdate

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data

def get_columns():
    return [
        {"label": "S. No", "fieldname": "serial_no", "fieldtype": "Int", "width": 50},
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "Patient Name", "fieldname": "patient_name", "fieldtype": "Link", "options": "Patient", "width": 150},
        {"label": "Practitioner Name", "fieldname": "practitioner", "fieldtype": "Link", "options": "Doctor", "width": 150},
        {"label": "Paid Amount", "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 100},
        {"label": "Department", "fieldname": "department", "fieldtype": "Data", "width": 150},
    ]

def get_data(filters):
    conditions = get_conditions(filters)

    query = f"""
        SELECT 
            ROW_NUMBER() OVER (ORDER BY pa.name) AS serial_no,
            pa.company,
            pa.patient_name,
            pa.practitioner,
            pa.paid_amount,
            pa.appointment_date AS date,
            pa.department
        FROM `tabPatient Appointment` pa
        WHERE {conditions}
    """

    return frappe.db.sql(query, filters, as_dict=True)

def get_conditions(filters):
    conditions = ["1=1"]

    if filters.get("company"):
        conditions.append("pa.company = %(company)s")
    if filters.get("date"):
        conditions.append("pa.appointment_date = %(date)s")
    if filters.get("practitioner"):
        conditions.append("pa.practitioner = %(practitioner)s")
    if filters.get("patient"):
        conditions.append("pa.patient_name = %(patient)s")
    if filters.get("department"):
        conditions.append("pa.department = %(department)s")

    return " AND ".join(conditions)
