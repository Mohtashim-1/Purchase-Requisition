# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime


class PatientAppointmentEntry(Document):
	def validate(self):
		self.get_user_default_company()
		self.calculate_age()
		
	def get_user_default_company(self):
		default_company = frappe.defaults.get_user_default("Company")
		if default_company:
			self.company = default_company 

	def calculate_age(self):
		if self.date_of_birth:
			dob = self.date_of_birth
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

			self.age = f"{years} Year{months} Month {days} Days" 


	
	