import frappe
from frappe import _
from frappe.model.document import Document


class Generic(Document):
	def validate(self):
		self.generic_id = (self.generic_id or "").strip().upper()
		if not self.generic_id:
			frappe.throw(_("Generic ID is required."))

		if self.disabled:
			return

		duplicate = frappe.db.exists(
			"Generic",
			{"generic_id": self.generic_id, "name": ("!=", self.name or "")},
		)
		if duplicate:
			frappe.throw(_("Generic ID {0} already exists.").format(self.generic_id))
