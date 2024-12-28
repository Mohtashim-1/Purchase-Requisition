import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    # chart = get_chart(data)
    # return columns, data, chart
    return columns, data, chart, report_summary

report_summary = [
    {"label":"cats","value":2287,'indicator':'Red'},
    {"label":"dogs","value":3647,'indicator':'Blue'}
]


def get_columns():
    return [
        {"label": _("Stock Entry Type"), "fieldname": "stock_entry_type", "fieldtype": "Data", "width": 200},
        {"label": _("From Warehouse"), "fieldname": "from_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200},
        {"label": _("To Warehouse"), "fieldname": "to_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200},
        {"label": _("Total Incoming Value"), "fieldname": "total_incoming_value", "fieldtype": "Currency", "width": 150},
    ]

def get_data(filters):
    # Initialize the base query
    query = """
        SELECT 
            stock_entry_type, 
            from_warehouse, 
            to_warehouse, 
            SUM(total_incoming_value) AS total_incoming_value
        FROM `tabStock Entry`
    """
    
    # If filters are provided, dynamically add the WHERE clause
    conditions = []
    
    if filters.get('stock_entry_type'):
        conditions.append(f"stock_entry_type = '{filters['stock_entry_type']}'")
    
    if filters.get('from_warehouse'):
        conditions.append(f"from_warehouse = '{filters['from_warehouse']}'")
    
    if filters.get('to_warehouse'):
        conditions.append(f"to_warehouse = '{filters['to_warehouse']}'")

    if filters.get('from_date'):
        conditions.append(f"posting_date >= '{filters['from_date']}'")

    if filters.get('to_date'):
        conditions.append(f"posting_date <= '{filters['to_date']}'")
    
    
    # Add conditions to the query if any filters were applied
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    # Add the GROUP BY clause (group by to_warehouse)
    query += " GROUP BY to_warehouse, stock_entry_type"
    
    # Execute the query and return the results as a list of dictionaries
    data = frappe.db.sql(query, as_dict=True)
    
    return data

chart = {
    'data':{
        'labels':['d','o','g','s'],
        'datasets':[
            #In axis-mixed charts you have to list the bar type first
            {'name':'Number','values':[3,6,4,7],'chartType':'bar'},
            {'name':'Vowel','values':[0,1,0,0],'chartType':'line'}
        ]
    },
    'type':'axis-mixed'
}