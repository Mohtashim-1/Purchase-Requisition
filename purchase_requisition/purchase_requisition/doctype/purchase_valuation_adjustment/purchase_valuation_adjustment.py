# Copyright (c) 2026, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from erpnext.controllers.stock_controller import create_repost_item_valuation_entry
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import adjust_incoming_rate_for_pr


class PurchaseValuationAdjustment(Document):
	def validate(self):
		if self.purchase_invoice and not self.items:
			self.extend("items", get_adjustment_rows_for_purchase_invoice_from_name(self.purchase_invoice))

		self.status = "Draft"
		self.company = self.company or frappe.db.get_value("Purchase Invoice", self.purchase_invoice, "company")
		self.posting_date = self.posting_date or frappe.db.get_value(
			"Purchase Invoice", self.purchase_invoice, "posting_date"
		)
		self.remarks = self.remarks or (
			"Auto-created from Purchase Invoice actual billed amount to adjust Purchase Receipt valuation."
		)

	def on_submit(self):
		self.status = "Submitted"
		self.apply_adjustments()

	def on_cancel(self):
		self.status = "Cancelled"
		self.apply_adjustments()

	def apply_adjustments(self):
		affected_pr_details = {row.purchase_receipt_item for row in self.items if row.purchase_receipt_item}
		if not affected_pr_details:
			return

		affected_receipts = recompute_pr_item_rate_differences(affected_pr_details)
		update_adjustment_row_snapshots(self)
		repost_receipts(affected_receipts)


def create_adjustment_from_purchase_invoice(doc, method=None):
	if frappe.db.exists(
		"Purchase Valuation Adjustment",
		{"purchase_invoice": doc.name, "docstatus": ["!=", 2]},
	):
		return

	rows = get_adjustment_rows_for_purchase_invoice(doc)
	if not rows:
		return

	adjustment = frappe.new_doc("Purchase Valuation Adjustment")
	adjustment.purchase_invoice = doc.name
	adjustment.company = doc.company
	adjustment.posting_date = doc.posting_date
	for row in rows:
		adjustment.append("items", row)

	adjustment.flags.ignore_permissions = True
	adjustment.insert()
	adjustment.submit()


def cancel_adjustments_for_purchase_invoice(doc, method=None):
	adjustment_names = frappe.get_all(
		"Purchase Valuation Adjustment",
		filters={"purchase_invoice": doc.name, "docstatus": 1},
		pluck="name",
	)

	for name in adjustment_names:
		adjustment = frappe.get_doc("Purchase Valuation Adjustment", name)
		adjustment.flags.ignore_permissions = True
		adjustment.cancel()


def get_adjustment_rows_for_purchase_invoice(doc):
	rows = []
	conversion_rate = flt(doc.conversion_rate or 1)

	for item in doc.items:
		if not item.get("pr_detail") or not item.get("purchase_receipt"):
			continue

		pr_item = frappe.db.get_value(
			"Purchase Receipt Item",
			item.pr_detail,
			["item_code", "warehouse", "qty", "base_net_amount", "amount"],
			as_dict=True,
		)
		if not pr_item:
			continue

		pr_amount = flt(pr_item.base_net_amount or pr_item.amount)
		pr_qty = flt(pr_item.qty)
		pi_qty = flt(item.qty)
		proportional_pr_amount = get_proportional_amount(pr_amount, pr_qty, pi_qty)
		pi_amount = get_actual_pi_base_amount(item, conversion_rate)
		difference_amount = flt(pi_amount - proportional_pr_amount, 2)

		rows.append(
			{
				"purchase_receipt": item.purchase_receipt,
				"purchase_receipt_item": item.pr_detail,
				"purchase_invoice_item": item.name,
				"item_code": pr_item.item_code,
				"warehouse": pr_item.warehouse,
				"qty": pi_qty,
				"purchase_receipt_qty": pr_qty,
				"purchase_receipt_amount": pr_amount,
				"proportional_purchase_receipt_amount": proportional_pr_amount,
				"purchase_invoice_amount": pi_amount,
				"difference_amount": difference_amount,
			}
		)

	return rows


def get_adjustment_rows_for_purchase_invoice_from_name(purchase_invoice):
	doc = frappe.get_doc("Purchase Invoice", purchase_invoice)
	return get_adjustment_rows_for_purchase_invoice(doc)


@frappe.whitelist()
def get_purchase_invoice_adjustment_preview(purchase_invoice):
	if not purchase_invoice:
		return {
			"company": None,
			"posting_date": None,
			"items": [],
		}

	doc = frappe.get_doc("Purchase Invoice", purchase_invoice)
	return {
		"company": doc.company,
		"posting_date": doc.posting_date,
		"items": get_adjustment_rows_for_purchase_invoice(doc),
	}


def recompute_pr_item_rate_differences(pr_detail_names):
	affected_receipts = {}

	for pr_detail in pr_detail_names:
		pr_item = frappe.db.get_value(
			"Purchase Receipt Item",
			pr_detail,
			["parent", "item_code", "warehouse", "qty", "base_net_amount", "amount"],
			as_dict=True,
		)
		if not pr_item:
			continue

		actual_billed_amount, billed_qty = get_cumulative_pi_actuals_for_pr_item(pr_detail)
		pr_qty = flt(pr_item.qty)
		pr_amount = flt(pr_item.base_net_amount or pr_item.amount)
		proportional_pr_amount = get_proportional_amount(pr_amount, pr_qty, billed_qty)
		applied_difference = flt(actual_billed_amount - proportional_pr_amount, 2)

		frappe.db.set_value(
			"Purchase Receipt Item",
			pr_detail,
			"rate_difference_with_purchase_invoice",
			applied_difference,
			update_modified=False,
		)

		if pr_item.parent not in affected_receipts:
			affected_receipts[pr_item.parent] = {
				"item_rows": set(),
				"items": [],
			}

		item_key = (pr_item.item_code, pr_item.warehouse)
		if item_key not in affected_receipts[pr_item.parent]["item_rows"]:
			affected_receipts[pr_item.parent]["item_rows"].add(item_key)
			affected_receipts[pr_item.parent]["items"].append(
				{
					"item_code": pr_item.item_code,
					"warehouse": pr_item.warehouse,
				}
			)

	return affected_receipts


def get_cumulative_pi_actuals_for_pr_item(pr_detail):
	pi_items = frappe.get_all(
		"Purchase Invoice Item",
		filters={"pr_detail": pr_detail, "docstatus": 1},
		fields=["name", "parent", "qty", "base_net_amount", "base_amount", "amount", "custom_net_amount"],
	)
	if not pi_items:
		return 0, 0

	invoice_rates = frappe._dict(
		frappe.get_all(
			"Purchase Invoice",
			filters={"name": ["in", list({row.parent for row in pi_items})]},
			fields=["name", "conversion_rate"],
			as_list=True,
		)
	)

	total_amount = 0
	total_qty = 0
	for item in pi_items:
		total_amount += get_actual_pi_base_amount(item, invoice_rates.get(item.parent))
		total_qty += flt(item.qty)

	return flt(total_amount, 2), flt(total_qty, 6)


def get_actual_pi_base_amount(item, conversion_rate=None):
	base_amount = flt(item.get("base_net_amount") or item.get("base_amount"))
	if base_amount:
		return base_amount

	actual_amount = flt(item.get("custom_net_amount") or item.get("amount"))
	return flt(actual_amount * flt(conversion_rate or 1), 2)


def get_proportional_amount(total_amount, total_qty, billed_qty):
	total_amount = flt(total_amount, 2)
	total_qty = flt(total_qty, 6)
	billed_qty = flt(billed_qty, 6)

	if not total_qty or not billed_qty:
		return 0

	return flt(total_amount * (billed_qty / total_qty), 2)


def repost_receipts(affected_receipts):
	for purchase_receipt, payload in affected_receipts.items():
		pr_doc = frappe.get_doc("Purchase Receipt", purchase_receipt)
		adjust_incoming_rate_for_pr(pr_doc)

		for item in payload["items"]:
			create_repost_item_valuation_entry(
				{
					"based_on": "Item and Warehouse",
					"item_code": item["item_code"],
					"warehouse": item["warehouse"],
					"posting_date": pr_doc.posting_date,
					"posting_time": pr_doc.posting_time,
					"company": pr_doc.company,
				}
			)


def update_adjustment_row_snapshots(doc):
	applied_differences = frappe._dict(
		frappe.get_all(
			"Purchase Receipt Item",
			filters={"name": ["in", [row.purchase_receipt_item for row in doc.items if row.purchase_receipt_item]]},
			fields=["name", "rate_difference_with_purchase_invoice"],
			as_list=True,
		)
	)

	for row in doc.items:
		row.applied_rate_difference = flt(applied_differences.get(row.purchase_receipt_item), 2)

	doc.db_update()
	for row in doc.items:
		row.db_update()
