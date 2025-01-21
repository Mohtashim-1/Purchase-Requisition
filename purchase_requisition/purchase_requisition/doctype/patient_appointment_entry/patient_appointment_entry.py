# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PatientAppointmentEntry(Document):
	def validate(self):
		self.get_user_default_company()
		
	def get_user_default_company(self):
		default_company = frappe.defaults.get_user_default("Company")
		if default_company:
			self.company = default_company 
