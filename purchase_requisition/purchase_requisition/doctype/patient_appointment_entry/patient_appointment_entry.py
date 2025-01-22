# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime


class PatientAppointmentEntry(Document):
	def validate(self):
		self.get_user_default_company()
		# self.calculate_age()
		# self.create_payment_entry()

	def on_submit(self):
		self.create_payment_entry()
		
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
				# Step 1: Create Sales Invoice
				sales_invoice = frappe.new_doc("Sales Invoice")
				sales_invoice.customer = self.patient
				sales_invoice.company = self.company
				sales_invoice.due_date = self.posting_date

				# Create items and add them to the Sales Invoice
				item = sales_invoice.append("items", {})
				item.item_name = "Consultation Fee"  # Adjust as needed
				item.description = "Consultation Fee for Patient Appointment"
				item.qty = 1
				item.rate = self.paid_amount
				item.amount = self.paid_amount

				# Set the Income Account manually (use the default income account for the company)
				company = frappe.get_doc("Company", self.company)
				if company.default_income_account:
					item.income_account = company.default_income_account
				else:
					frappe.throw("No default Income Account found for the company.")

				sales_invoice.insert()  # Insert the Sales Invoice document
				sales_invoice.submit()  # Submit the Sales Invoice
				frappe.msgprint(f"Sales Invoice {sales_invoice.name} created and submitted.")

				# Step 2: Create Payment Entry for Sales Invoice
				pe = frappe.new_doc("Payment Entry")
				pe.payment_type = "Receive"
				pe.posting_date = self.posting_date
				pe.party_type = "Customer"
				pe.party = self.patient
				pe.company = self.company
				pe.paid_amount = self.paid_amount
				pe.received_amount = self.paid_amount
				pe.reference_no = self.name
				pe.reference_date = self.posting_date
				pe.mode_of_payment = "Cash"  # Change to appropriate mode of payment

				# Add reference to the Sales Invoice in Payment Entry
				reference_row = pe.append("references", {})
				reference_row.reference_doctype = "Sales Invoice"
				reference_row.reference_name = sales_invoice.name
				reference_row.due_date = sales_invoice.due_date
				reference_row.total_amount = sales_invoice.grand_total
				reference_row.outstanding_amount = sales_invoice.outstanding_amount
				reference_row.allocated_amount = self.paid_amount

				# Get the default cash account for the company
				if company.default_cash_account:
					pe.paid_to = company.default_cash_account
					paid_to_account = frappe.get_doc("Account", company.default_cash_account)
					pe.paid_to_account_currency = paid_to_account.account_currency
				else:
					frappe.throw("Default Cash Account is not set for the company.")

				pe.insert()
				pe.submit()
				frappe.msgprint(f"Payment Entry {pe.name} created and submitted.")
			except Exception as e:
				frappe.log_error(message=f"Error creating Payment Entry for {self.name}: {str(e)}", title="Payment Entry Error")
				frappe.throw(f"An unexpected error occurred: {str(e)}")






	
	