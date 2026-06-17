import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today


class GenericVendorQuotation(Document):
	def validate(self):
		self._pull_pricing_from_legacy_row()
		self._set_status()
		self._set_quotation_no()
		self._validate_required_fields()
		self._calculate_parent_total()
		self._sync_pricing_line()
		self._validate_overlapping_active()

	def on_submit(self):
		self.status = "Submitted"

	def on_cancel(self):
		self.status = "Cancelled"

	def _pull_pricing_from_legacy_row(self):
		"""Older quotations may only have child rows; copy to parent fields once."""
		if flt(self.rate):
			return
		row = (self.get("items") or [None])[0]
		if not row:
			return
		self.item = self.item or row.item
		self.qty = self.qty or row.qty or 1
		self.uom = self.uom or row.uom
		self.rate = row.rate
		self.discount_percent = row.discount_percent
		self.tax_amount = row.tax_amount
		self.total_rate = row.total_rate

	def _set_status(self):
		if self.docstatus == 1:
			self.status = "Submitted"
			return
		if self.docstatus == 2:
			self.status = "Cancelled"
			return
		if self.valid_upto and getdate(self.valid_upto) < getdate(today()):
			self.status = "Expired"
		else:
			self.status = self.status or "Draft"

	def _validate_required_fields(self):
		missing = []
		if not self.supplier:
			missing.append("supplier")
		if not self.generic:
			missing.append("generic")
		if not self.valid_from:
			missing.append("valid_from")
		if not self.valid_upto:
			missing.append("valid_upto")
		if self.rate is None or self.rate == "":
			missing.append("rate")
		if missing:
			frappe.throw(_("Missing required fields: {0}").format(", ".join(missing)))

		if self.valid_from and self.valid_upto:
			if getdate(self.valid_upto) < getdate(self.valid_from):
				frappe.throw(_("Valid Upto must be on or after Valid From."))

	def _set_quotation_no(self):
		if not self.quotation_no and self.name:
			self.quotation_no = self.name

	def _calculate_parent_total(self):
		discount_amount = flt(self.rate) * flt(self.discount_percent) / 100
		self.total_rate = flt(self.rate) - discount_amount + flt(self.tax_amount)

	def _sync_pricing_line(self):
		"""Keep one child row in sync for reports; parent form is the entry point."""
		while len(self.get("items") or []) > 1:
			self.items.pop()

		if not self.get("items"):
			self.append("items", {})

		row = self.items[0]
		row.generic = self.generic
		row.item = self.item
		row.uom = self.uom or "Nos"
		row.qty = flt(self.qty) or 1
		row.rate = flt(self.rate)
		row.discount_percent = flt(self.discount_percent)
		row.tax_amount = flt(self.tax_amount)
		row.total_rate = flt(self.total_rate)

	def _validate_overlapping_active(self):
		if not (self.supplier and self.generic and self.valid_from and self.valid_upto):
			return
		if self.status in ("Cancelled", "Expired"):
			return

		overlap = frappe.db.sql(
			"""
			SELECT name
			FROM `tabGeneric Vendor Quotation`
			WHERE supplier = %(supplier)s
			  AND generic = %(generic)s
			  AND docstatus < 2
			  AND status NOT IN ("Cancelled", "Expired")
			  AND name != %(name)s
			  AND valid_from <= %(valid_upto)s
			  AND valid_upto >= %(valid_from)s
			LIMIT 1
			""",
			{
				"supplier": self.supplier,
				"generic": self.generic,
				"valid_from": self.valid_from,
				"valid_upto": self.valid_upto,
				"name": self.name or "",
			},
		)
		if overlap:
			frappe.throw(
				_(
					"Active quotation already exists for this Supplier and Generic within the selected validity period."
				)
			)
