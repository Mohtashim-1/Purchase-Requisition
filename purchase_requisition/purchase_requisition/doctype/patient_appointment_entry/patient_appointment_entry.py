# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime
from frappe.utils import add_days, flt, getdate


ACCOUNTING_JOB_METHOD = (
	"purchase_requisition.purchase_requisition.doctype.patient_appointment_entry."
	"patient_appointment_entry.create_sales_invoice_and_payment_entry"
)



class PatientAppointmentEntry(Document):
	def validate(self):
		self.get_user_default_company()
		# self.get_customer_id()
		# self.calculate_age()
		# self.create_payment_entry()

	def on_submit(self):
		self.enqueue_sales_invoice_and_payment_entry()
	
	# def get_customer_id(self):
	# 	cust_id = frappe.get_doc("Customer",)
		
	def get_user_default_company(self):
		default_company = frappe.defaults.get_user_default("Company")
		if default_company:
			self.company = default_company 

	def calculate_age(self):
		if self.date_of_birth:
			try:
				dob = datetime.strptime(self.date_of_birth, "%Y-%m-%d").date()
			except:
				frappe.error_log(f"Invalid Date of Birth. Expected format is YYYY-MM-DD")
			today = datetime.today()

			years = today.year - dob.year
			months = today.month - dob.month
			days = today.day - dob.day

			if days < 0:
				months -= 1
				previous_month = (today.month -1 ) if today.month > 1 else 12
				days += (datetime(today.year, previous_month + 1 , 1) - datetime(today.year, previous_month , 1)).days

			if months < 0:
				years -= 1
				months += 12

			self.age = f"{years} Year {months} Month {days} Days" 

	def enqueue_sales_invoice_and_payment_entry(self):
		if flt(self.paid_amount) <= 0:
			return

		frappe.enqueue(
			ACCOUNTING_JOB_METHOD,
			queue="default",
			timeout=300,
			enqueue_after_commit=True,
			job_id=f"patient-appointment-accounting-{self.name}",
			appointment_entry=self.name,
		)

	def create_payment_entry(self):
		if flt(self.paid_amount) <= 0:
			return

		customer_id = self.get_customer_id()
		company = frappe.get_doc("Company", self.company)
		sales_invoice = self.get_or_create_sales_invoice(customer_id, company)

		if self.get_existing_payment_entry(sales_invoice.name):
			return

		pe = frappe.new_doc("Payment Entry")
		pe.flags.ignore_permissions = True
		pe.payment_type = "Receive"
		pe.posting_date = self.posting_date
		pe.party_type = "Customer"
		pe.party = customer_id
		pe.company = self.company
		pe.paid_amount = self.paid_amount
		pe.received_amount = self.paid_amount
		pe.reference_no = self.name
		pe.reference_date = self.posting_date
		pe.mode_of_payment = self.mode_of_payment or "Cash"

		reference_row = pe.append("references", {})
		reference_row.reference_doctype = "Sales Invoice"
		reference_row.reference_name = sales_invoice.name
		reference_row.due_date = sales_invoice.due_date
		reference_row.total_amount = sales_invoice.grand_total
		reference_row.outstanding_amount = sales_invoice.outstanding_amount
		reference_row.allocated_amount = self.paid_amount

		if company.default_cash_account:
			pe.paid_to = company.default_cash_account
			paid_to_account = frappe.get_doc("Account", company.default_cash_account)
			pe.paid_to_account_currency = paid_to_account.account_currency
		else:
			frappe.throw("Default Cash Account is not set for the company.")

		pe.insert(ignore_permissions=True)
		pe.flags.ignore_permissions = True
		pe.submit()

	def get_customer_id(self):
		for customer in (
			self.customer,
			self.customer_id,
			frappe.db.get_value("Patient", self.patient, "customer"),
		):
			if customer and frappe.db.exists("Customer", customer):
				return customer

		customer_id = frappe.db.get_value("Customer", {"customer_name": self.patient_name}, "name")
		if not customer_id:
			frappe.throw(f"Customer {self.patient_name} does not exist.")

		return customer_id

	def get_or_create_sales_invoice(self, customer_id, company):
		if self.invoice and frappe.db.exists("Sales Invoice", self.invoice):
			sales_invoice = frappe.get_doc("Sales Invoice", self.invoice)
			if sales_invoice.docstatus == 1:
				return sales_invoice

		sales_invoice = frappe.new_doc("Sales Invoice")
		sales_invoice.flags.ignore_permissions = True
		sales_invoice.customer = customer_id
		sales_invoice.company = self.company
		sales_invoice.posting_date = getdate(self.posting_date)
		sales_invoice.due_date = add_days(self.posting_date, 1)

		payment_terms_template = frappe.db.get_value("Customer", customer_id, "payment_terms")
		if payment_terms_template:
			sales_invoice.payment_terms_template = payment_terms_template

		item = sales_invoice.append("items", {})
		item.item_name = "Consultation Fee"
		item.description = "Consultation Fee for Patient Appointment"
		item.qty = 1
		item.rate = self.paid_amount
		item.amount = self.paid_amount

		if company.default_income_account:
			item.income_account = company.default_income_account
		else:
			frappe.throw("No default Income Account found for the company.")

		if company.cost_center:
			item.cost_center = company.cost_center
		else:
			frappe.throw("No default Cost Center found for the company.")

		sales_invoice.insert(ignore_permissions=True)
		sales_invoice.flags.ignore_permissions = True
		sales_invoice.submit()

		self.db_set("invoice", sales_invoice.name, update_modified=False)
		self.db_set("invoiced", 1, update_modified=False)

		return sales_invoice

	def get_existing_payment_entry(self, sales_invoice):
		existing_payment_entry = frappe.db.sql(
			"""
			select per.parent
			from `tabPayment Entry Reference` per
			inner join `tabPayment Entry` pe on pe.name = per.parent
			where per.reference_doctype = %s
				and per.reference_name = %s
				and pe.docstatus != 2
			limit 1
			""",
			("Sales Invoice", sales_invoice),
		)

		return existing_payment_entry[0][0] if existing_payment_entry else None


def create_sales_invoice_and_payment_entry(appointment_entry):
	try:
		doc = frappe.get_doc("Patient Appointment Entry", appointment_entry)
		doc.create_payment_entry()
	except Exception as e:
		if frappe.db.is_deadlocked(e) or frappe.db.is_timedout(e):
			raise

		frappe.log_error(
			title="Patient Appointment Accounting Error",
			message=frappe.get_traceback(),
			reference_doctype="Patient Appointment Entry",
			reference_name=appointment_entry,
		)
		raise
