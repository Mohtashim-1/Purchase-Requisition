import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, flt


class GenericVendorQuotation(Document):
    def validate(self):
        self._set_status()
        self._set_quotation_no()
        self._validate_required_fields()
        self._set_child_defaults()
        self._calculate_child_totals()
        self._validate_overlapping_active()

    def on_submit(self):
        self.status = "Submitted"

    def on_cancel(self):
        self.status = "Cancelled"

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
        if missing:
            frappe.throw("Missing required fields: {0}".format(", ".join(missing)))

        if self.valid_from and self.valid_upto:
            if getdate(self.valid_upto) < getdate(self.valid_from):
                frappe.throw("Valid Upto must be on or after Valid From.")

    def _set_quotation_no(self):
        if not self.quotation_no and self.name:
            self.quotation_no = self.name

    def _set_child_defaults(self):
        for row in self.get("items") or []:
            if not row.generic:
                row.generic = self.generic

    def _calculate_child_totals(self):
        for row in self.get("items") or []:
            discount_amount = flt(row.rate) * flt(row.discount_percent) / 100
            total_rate = flt(row.rate) - discount_amount + flt(row.tax_amount)
            row.total_rate = total_rate

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
                "Active quotation already exists for this Supplier and Generic within the selected validity period."
            )
