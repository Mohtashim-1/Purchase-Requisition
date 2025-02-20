# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime
from datetime import datetime, timedelta



class PatientAppointmentEntry(Document):
	def validate(self):
		self.get_user_default_company()
		# self.get_customer_id()
		# self.calculate_age()
		# self.create_payment_entry()

	def on_submit(self):
		self.create_payment_entry()
	
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

	def create_payment_entry(self):
		if self.paid_amount > 0:
			try:
				# Step 1: Validate Customer Exists
				customer_id = frappe.db.get_value("Customer", {"customer_name": self.patient_name}, "name")

				if not customer_id:
					frappe.throw(f"Customer {self.patient_name} does not exist.")

				# Step 2: Create Sales Invoice
				sales_invoice = frappe.new_doc("Sales Invoice")
				sales_invoice.customer = customer_id  # Use fetched Customer ID
				sales_invoice.company = self.company
				sales_invoice.due_date = (datetime.strptime(self.posting_date, "%Y-%m-%d") + timedelta(days=1)).date()

				# Fetch payment terms template, if available
				payment_terms_template = frappe.db.get_value("Customer", {"name": customer_id}, "payment_terms")
				if payment_terms_template:
					sales_invoice.payment_terms_template = payment_terms_template

				# Add items to the Sales Invoice
				item = sales_invoice.append("items", {})
				item.item_name = "Consultation Fee"
				item.description = "Consultation Fee for Patient Appointment"
				item.qty = 1
				item.rate = self.paid_amount
				item.amount = self.paid_amount

				# Set Income Account
				company = frappe.get_doc("Company", self.company)
				if company.default_income_account:
					item.income_account = company.default_income_account
				else:
					frappe.throw("No default Income Account found for the company.")

				# Retrieve the cost center from the company's settings
				if company.cost_center:
					item.cost_center = company.cost_center
				else:
					frappe.throw("No default Cost Center found for the company.")

				# Insert and submit Sales Invoice
				sales_invoice.insert()
				sales_invoice.submit()

				# Save the Sales Invoice number after submission
				self.invoice = sales_invoice.name

				# self.save()

				frappe.db.commit()  # Commit to the database after submission
				frappe.msgprint(f"Sales Invoice {sales_invoice.name} created and submitted.")

				# Step 3: Create Payment Entry
				pe = frappe.new_doc("Payment Entry")
				pe.payment_type = "Receive"
				pe.posting_date = self.posting_date
				pe.party_type = "Customer"
				pe.party = customer_id  # Use fetched Customer ID
				pe.company = self.company
				pe.paid_amount = self.paid_amount
				pe.received_amount = self.paid_amount
				pe.reference_no = self.name
				pe.reference_date = self.posting_date
				pe.mode_of_payment = "Cash"  # Adjust as needed

				# Add reference to the Sales Invoice in Payment Entry
				reference_row = pe.append("references", {})
				reference_row.reference_doctype = "Sales Invoice"
				reference_row.reference_name = sales_invoice.name
				reference_row.due_date = sales_invoice.due_date
				reference_row.total_amount = sales_invoice.grand_total
				reference_row.outstanding_amount = sales_invoice.outstanding_amount
				reference_row.allocated_amount = self.paid_amount

				# Get Default Cash Account
				if company.default_cash_account:
					pe.paid_to = company.default_cash_account
					paid_to_account = frappe.get_doc("Account", company.default_cash_account)
					pe.paid_to_account_currency = paid_to_account.account_currency
				else:
					frappe.throw("Default Cash Account is not set for the company.")

				# Insert and submit Payment Entry
				pe.insert()
				pe.submit()

				# Save the Payment Entry number after submission
				# self.payment_voucher = pe.name

				frappe.db.commit()  # Commit to the database after submission
				frappe.msgprint(f"Payment Entry {pe.name} created and submitted.")

			except frappe.DoesNotExistError as e:
				frappe.throw(f"Missing Data: {str(e)}")
			except frappe.ValidationError as e:
				frappe.throw(f"Validation Error: {str(e)}")
			except Exception as e:
				frappe.log_error(f"Error creating Sales Invoice and Payment Entry for {self.name}: {str(e)}", "Payment Entry Error")
				frappe.throw(f"An unexpected error occurred: {str(e)}")