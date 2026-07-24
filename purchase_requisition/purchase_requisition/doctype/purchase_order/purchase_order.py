import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, money_in_words
import json


def _po_debug_print(label, payload=None):
	try:
		if payload is None:
			print(f"[PO-DEBUG] {label}")
		else:
			print(f"[PO-DEBUG] {label}: {json.dumps(payload, default=str)}")
	except Exception:
		print(f"[PO-DEBUG] {label}: {payload}")


def hello_world(doc, method=None):
	"""Recalculate custom gross / discount / net, then include tax heads in payable total."""
	for i in doc.items:
		gross = flt(i.qty) * flt(i.rate)
		i.custom_gross_rate = gross

		# Prefer discount % when set; otherwise derive % from amount.
		if i.custom_discount_ is not None and flt(i.custom_discount_) != 0:
			i.custom_discounted_amount = (flt(i.custom_discount_) / 100.0) * gross
		elif flt(i.custom_discounted_amount):
			i.custom_discount_ = (flt(i.custom_discounted_amount) / gross) * 100.0 if gross else 0
		else:
			i.custom_discounted_amount = 0
			i.custom_discount_ = flt(i.custom_discount_) or 0

		i.custom_discounted_amount = min(max(0, flt(i.custom_discounted_amount)), gross)
		i.custom_net_total = gross - flt(i.custom_discounted_amount)
		i.amount = i.custom_net_total
		if hasattr(i, "net_amount"):
			i.net_amount = i.custom_net_total
		if hasattr(i, "base_amount"):
			i.base_amount = i.custom_net_total * flt(doc.conversion_rate or 1)
		if hasattr(i, "base_net_amount"):
			i.base_net_amount = i.base_amount

	gross_rate = sum(flt(i.custom_gross_rate) for i in doc.items)
	discounted_amount = sum(flt(i.custom_discounted_amount) for i in doc.items)
	net_rate = sum(flt(i.custom_net_total) for i in doc.items)

	doc.custom_gross_rate = gross_rate
	doc.custom_discounted_amount = discounted_amount
	doc.custom_discounted_percentage = (discounted_amount / gross_rate) * 100.0 if gross_rate else 0
	doc.custom_net_rate = net_rate

	# Item net (after discount) — keep ERPNext net_total in sync.
	doc.total = net_rate
	doc.net_total = net_rate
	if hasattr(doc, "base_total"):
		doc.base_total = net_rate * flt(doc.conversion_rate or 1)
	if hasattr(doc, "base_net_total"):
		doc.base_net_total = doc.base_total

	# Payable = discounted item net + purchase tax heads (GST, AIT, etc.).
	total_taxes = flt(doc.total_taxes_and_charges or 0)
	# Fallback: sum tax rows if total_taxes_and_charges was not refreshed yet.
	if not total_taxes and doc.get("taxes"):
		total_taxes = sum(flt(t.tax_amount) for t in doc.taxes)

	grand_total = flt(net_rate) + flt(total_taxes)
	doc.grand_total = grand_total
	if hasattr(doc, "base_grand_total"):
		doc.base_grand_total = grand_total * flt(doc.conversion_rate or 1)
	if hasattr(doc, "rounded_total"):
		doc.rounded_total = grand_total
	if hasattr(doc, "base_rounded_total"):
		doc.base_rounded_total = doc.base_grand_total

	doc.in_words = money_in_words(grand_total, doc.currency or "PKR")


@frappe.whitelist()
def make_purchase_receipt_custom(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	pr_item_meta = frappe.get_meta("Purchase Receipt Item")

	def update_item(obj, target, source_parent):
		remaining_qty = flt(obj.qty) - flt(obj.received_qty)
		target.qty = remaining_qty
		target.stock_qty = remaining_qty * flt(obj.conversion_factor)
		target.amount = remaining_qty * flt(obj.rate)
		target.base_amount = remaining_qty * flt(obj.rate) * flt(source_parent.conversion_rate)

		gross_total = remaining_qty * flt(obj.rate)
		discount_percent = flt(getattr(obj, "custom_discount_", 0))
		discount_amount = getattr(obj, "custom_discounted_amount", None)

		if pr_item_meta.has_field("custom_gross_rate"):
			target.custom_gross_rate = gross_total
		if discount_percent:
			if pr_item_meta.has_field("custom_discount_"):
				target.custom_discount_ = discount_percent
			if pr_item_meta.has_field("custom_discounted_amount"):
				target.custom_discounted_amount = (discount_percent / 100) * gross_total
		elif discount_amount:
			source_qty = flt(getattr(obj, "qty", 0))
			scaled_discount_amount = 0
			if source_qty:
				scaled_discount_amount = flt(discount_amount) * (remaining_qty / source_qty)
			else:
				scaled_discount_amount = flt(discount_amount)
			if pr_item_meta.has_field("custom_discounted_amount"):
				target.custom_discounted_amount = scaled_discount_amount
			if pr_item_meta.has_field("custom_discount_"):
				target.custom_discount_ = (scaled_discount_amount / gross_total) * 100 if gross_total else 0
		else:
			if pr_item_meta.has_field("custom_discount_"):
				target.custom_discount_ = 0
			if pr_item_meta.has_field("custom_discounted_amount"):
				target.custom_discounted_amount = 0

		if pr_item_meta.has_field("custom_net_total"):
			target.custom_net_total = gross_total - flt(getattr(target, "custom_discounted_amount", 0))

		if remaining_qty:
			per_qty_discount = flt(getattr(target, "custom_discounted_amount", 0)) / remaining_qty
		else:
			per_qty_discount = 0

		net_rate_value = flt(obj.rate) - per_qty_discount
		net_amount_value = net_rate_value * remaining_qty

		if pr_item_meta.has_field("price_list_rate"):
			target.price_list_rate = flt(obj.rate)
		if pr_item_meta.has_field("discount_percentage"):
			target.discount_percentage = discount_percent
		if pr_item_meta.has_field("discount_amount"):
			target.discount_amount = per_qty_discount
		target.rate = net_rate_value

		if pr_item_meta.has_field("net_rate"):
			target.net_rate = net_rate_value
		if pr_item_meta.has_field("net_amount"):
			target.net_amount = net_amount_value
		target.amount = net_amount_value

		target.base_rate = net_rate_value * flt(source_parent.conversion_rate)
		target.base_amount = net_amount_value * flt(source_parent.conversion_rate)
		if pr_item_meta.has_field("base_net_rate"):
			target.base_net_rate = net_rate_value * flt(source_parent.conversion_rate)
		if pr_item_meta.has_field("base_net_amount"):
			target.base_net_amount = net_amount_value * flt(source_parent.conversion_rate)

		_po_debug_print(
			"map_po_to_pr_item",
			{
				"po": getattr(source_parent, "name", None),
				"po_item": getattr(obj, "name", None),
				"pr_row_idx": getattr(target, "idx", None),
				"remaining_qty": remaining_qty,
				"po_rate": flt(getattr(obj, "rate", 0)),
				"pr_price_list_rate": flt(getattr(target, "price_list_rate", 0)),
				"pr_rate": flt(getattr(target, "rate", 0)),
				"pr_amount": flt(getattr(target, "amount", 0)),
				"gross_total": flt(getattr(target, "custom_gross_rate", 0)),
				"discount_pct": flt(getattr(target, "custom_discount_", 0)),
				"discount_total": flt(getattr(target, "custom_discounted_amount", 0)),
				"net_total": flt(getattr(target, "custom_net_total", 0)),
			},
		)

	return get_mapped_doc(
		"Purchase Order",
		source_name,
		{
			"Purchase Order": {
				"doctype": "Purchase Receipt",
				"field_map": {"supplier_warehouse": "supplier_warehouse"},
				"validation": {"docstatus": ["=", 1]},
			},
			"Purchase Order Item": {
				"doctype": "Purchase Receipt Item",
				"field_map": {
					"name": "purchase_order_item",
					"parent": "purchase_order",
					"bom": "bom",
					"material_request": "material_request",
					"material_request_item": "material_request_item",
					"sales_order": "sales_order",
					"sales_order_item": "sales_order_item",
					"wip_composite_asset": "wip_composite_asset",
					"price_list_rate": "price_list_rate",
					"discount_percentage": "discount_percentage",
					"discount_amount": "discount_amount",
					"rate": "rate",
					"net_rate": "net_rate",
					"net_amount": "net_amount",
					"base_rate": "base_rate",
					"base_amount": "base_amount",
					"base_net_rate": "base_net_rate",
					"base_net_amount": "base_net_amount",
				},
				"postprocess": update_item,
				"condition": lambda doc: abs(doc.received_qty) < abs(doc.qty)
				and doc.delivered_by_supplier != 1,
			},
			"Purchase Taxes and Charges": {"doctype": "Purchase Taxes and Charges", "add_if_empty": True},
		},
		target_doc,
		set_missing_values,
	)
