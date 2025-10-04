import frappe

@frappe.whitelist()
def get_user_default_company():
    """Get the default company for the current user"""
    user_company = frappe.get_value("User", frappe.session.user, "company")
    return user_company

@frappe.whitelist()
def set_default_company(doc, method):
    """Hook function to set default company"""
    if not doc.company:
        user_company = frappe.get_value("User", frappe.session.user, "company")
        if user_company:
            doc.company = user_company

def before_insert(doc, method):
    """Set default company before insert"""
    if not doc.company:
        user_company = frappe.get_value("User", frappe.session.user, "company")
        if user_company:
            doc.company = user_company

def onload(doc, method):
    """Set default company on form load"""
    if not doc.company and doc.is_new():
        user_company = frappe.get_value("User", frappe.session.user, "company")
        if user_company:
            doc.company = user_company 