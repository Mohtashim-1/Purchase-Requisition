app_name = "purchase_requisition"
app_title = "Purchase Requisition"
app_publisher = "mohtashim"
app_description = "purchase requisition"
app_email = "shoaibmohtashim973@gmail.com"
app_license = "mit"
# required_apps = []

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/purchase_requisition/css/purchase_requisition.css"
# app_include_js = "/assets/purchase_requisition/js/purchase_requisition.js"

# include js, css files in header of web template
# web_include_css = "/assets/purchase_requisition/css/purchase_requisition.css"
# web_include_js = "/assets/purchase_requisition/js/purchase_requisition.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "purchase_requisition/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Material Request" : "purchase_requisition/public/js/material_request.js",
    "Purchase Order": "purchase_requisition/public/js/purchase_order.js",
    "Purchase Invoice":"purchase_requisition/public/js/purchase_invoice.js",
    "Sales Invoice": "purchase_requisition/custom/sales_invoice.js",
    "Stock Entry": "purchase_requisition/public/js/stock_entry.js",
    }
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "purchase_requisition/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "purchase_requisition.utils.jinja_methods",
# 	"filters": "purchase_requisition.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "purchase_requisition.install.before_install"
# after_install = "purchase_requisition.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "purchase_requisition.uninstall.before_uninstall"
# after_uninstall = "purchase_requisition.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "purchase_requisition.utils.before_app_install"
# after_app_install = "purchase_requisition.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "purchase_requisition.utils.before_app_uninstall"
# after_app_uninstall = "purchase_requisition.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "purchase_requisition.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Stock Entry": "purchase_requisition.purchase_requisition.doctype.stock_entry_override.stock_entry_override.StockEntry"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Purchase Order": {
        "validate": "purchase_requisition.purchase_requisition.doctype.purchase_order.purchase_order.hello_world",
        "before_submit": "purchase_requisition.purchase_requisition.doctype.purchase_order.purchase_order.hello_world",
        "after_insert": "purchase_requisition.purchase_requisition.doctype.purchase_order.purchase_order.hello_world"
    },
    "Purchase Invoice": {
        "before_validate": "purchase_requisition.purchase_requisition.doctype.purchase_invoice.purchase_invoice.preserve_pr_amount",
        "validate": [
            "purchase_requisition.purchase_requisition.doctype.purchase_invoice.purchase_invoice.debug_validate_multiple_billing",
            "purchase_requisition.purchase_requisition.doctype.purchase_invoice.purchase_invoice.calculation_pi"
        ],
        "before_insert": "purchase_requisition.purchase_requisition.doctype.purchase_invoice.purchase_invoice.preserve_po_rate"
    },
    "Purchase Receipt": {
        "before_save": "purchase_requisition.purchase_requisition.doctype.purchase_receipt.purchase_receipt.get_pr_in_grn"
    },
    "Sales Invoice": {
        "before_insert": "purchase_requisition.purchase_requisition.custom.sales_invoice.before_insert",
        "onload": "purchase_requisition.purchase_requisition.custom.sales_invoice.onload"
    },
}


# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"purchase_requisition.tasks.all"
# 	],
# 	"daily": [
# 		"purchase_requisition.tasks.daily"
# 	],
# 	"hourly": [
# 		"purchase_requisition.tasks.hourly"
# 	],
# 	"weekly": [
# 		"purchase_requisition.tasks.weekly"
# 	],
# 	"monthly": [
# 		"purchase_requisition.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "purchase_requisition.install.before_tests"

# Overriding Methods
# ------------------------------
#

override_whitelisted_methods = {
	"erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice":
        "purchase_requisition.purchase_requisition.doctype.purchase_invoice.purchase_invoice.make_purchase_invoice_custom",
    "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt":
        "purchase_requisition.purchase_requisition.doctype.purchase_order.purchase_order.make_purchase_receipt_custom",
}

#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "purchase_requisition.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["purchase_requisition.utils.before_request"]
# after_request = ["purchase_requisition.utils.after_request"]

# Job Events
# ----------
# before_job = ["purchase_requisition.utils.before_job"]
# after_job = ["purchase_requisition.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"purchase_requisition.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
