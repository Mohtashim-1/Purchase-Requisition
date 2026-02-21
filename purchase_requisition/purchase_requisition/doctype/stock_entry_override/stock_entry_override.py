# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry as ERPNextStockEntry
from erpnext.stock.stock_ledger import is_negative_stock_allowed, get_previous_sle, validate_negative_qty_in_future_sle
from frappe.utils import flt, formatdate, format_time
from erpnext.stock.utils import get_stock_balance


class StockEntry(ERPNextStockEntry):
	"""
	Custom Stock Entry override to handle insufficient stock scenarios
	"""
	
	def validate(self):
		"""
		Override validate to handle negative stock validation more gracefully
		"""
		# Check for future transaction conflicts before parent validate
		if self._action == "submit":
			self.check_future_transaction_conflicts()
		
		# Call parent validate first
		super().validate()
		
		# Additional validation for insufficient stock
		self.handle_insufficient_stock_validation()
	
	def check_future_transaction_conflicts(self):
		"""
		Check if this transaction would cause future transactions to have negative stock
		"""
		for item in self.get("items"):
			if not item.item_code or not item.s_warehouse:
				continue
			
			# Check for future conflicts
			conflicts = self.check_future_transactions_for_item(item)
			if conflicts:
				# Build warning message but don't throw - let the system handle it with better message
				frappe.msgprint(
					frappe._(
						"⚠️ <b>Warning:</b> This transaction may conflict with future-dated transactions.<br>"
						"Use 'Check Future Transactions' button to see details."
					),
					indicator="orange",
					title=_("Future Transaction Warning")
				)
	
	def handle_insufficient_stock_validation(self):
		"""
		Handle insufficient stock scenarios with better error messages and options
		"""
		for item in self.get("items"):
			if not item.s_warehouse:
				continue
			
			# Check if negative stock is allowed
			allow_negative_stock = is_negative_stock_allowed(item_code=item.item_code)
			
			if allow_negative_stock:
				continue
			
			# Get actual stock
			previous_sle = get_previous_sle(
				{
					"item_code": item.item_code,
					"warehouse": item.s_warehouse,
					"posting_date": self.posting_date,
					"posting_time": self.posting_time,
				}
			)
			
			actual_qty = previous_sle.get("qty_after_transaction") or 0
			
			# Check if there's insufficient stock
			if flt(actual_qty, item.precision("actual_qty")) < flt(item.transfer_qty, item.precision("transfer_qty")):
				shortage = flt(item.transfer_qty, item.precision("transfer_qty")) - flt(actual_qty, item.precision("actual_qty"))
				
				# Provide helpful error message with solutions
				frappe.throw(
					frappe._(
						"<b>Insufficient Stock Error</b><br><br>"
						"Row {0}: {1} units of {2} needed in warehouse {3} to complete this transaction.<br><br>"
						"<b>Details:</b><br>"
						"• Required Quantity: {4}<br>"
						"• Available Quantity: {5}<br>"
						"• Shortage: {1}<br><br>"
						"<b>Solutions:</b><br>"
						"1. Enable 'Allow Negative Stock' in Stock Settings (Stock Settings > Allow Negative Stock)<br>"
						"2. Enable 'Allow Negative Stock' for this specific item ({2})<br>"
						"3. Add stock to warehouse {3} before submitting<br>"
						"4. Reduce the quantity in this Stock Entry"
					).format(
						item.idx,
						frappe.bold(shortage),
						frappe.get_desk_link("Item", item.item_code),
						frappe.get_desk_link("Warehouse", item.s_warehouse),
						frappe.bold(item.transfer_qty),
						frappe.bold(actual_qty)
					),
					title=_("Insufficient Stock")
				)
	
	def make_sl_entries(self, sl_entries, allow_negative_stock=False, via_landed_cost_voucher=False):
		"""
		Override to handle negative stock validation more gracefully
		Check for future-dated transactions that would cause negative stock
		"""
		# Check for future transactions before creating SLEs
		for sle in sl_entries:
			if sle.get("actual_qty", 0) < 0:  # Only check for outgoing stock
				self.check_future_transactions(sle, allow_negative_stock)
		
		# Temporarily allow negative stock if needed for critical transactions
		if self.should_allow_negative_stock():
			allow_negative_stock = True
		
		return super().make_sl_entries(sl_entries, allow_negative_stock, via_landed_cost_voucher)
	
	def check_future_transactions(self, sle_args, allow_negative_stock=False):
		"""
		Check for future-dated transactions that would cause negative stock
		and provide detailed diagnostics
		"""
		from erpnext.stock.stock_ledger import get_future_sle_with_negative_qty, is_negative_stock_allowed
		
		if allow_negative_stock or is_negative_stock_allowed(item_code=sle_args.get("item_code")):
			return
		
		# Get future transactions that would go negative
		future_sles = get_future_sle_with_negative_qty(sle_args)
		
		if future_sles:
			future_sle = future_sles[0]
			shortage = abs(future_sle.get("qty_after_transaction", 0))
			
			# Get current stock for better diagnostics
			from erpnext.stock.utils import get_stock_balance
			current_stock = get_stock_balance(
				sle_args.get("item_code"),
				sle_args.get("warehouse"),
				sle_args.get("posting_date"),
				sle_args.get("posting_time")
			)
			
			# Get all future transactions for this item/warehouse to show full picture
			all_future_transactions = self.get_all_future_transactions(sle_args)
			
			# Build detailed error message
			message = frappe._(
				"<b>Insufficient Stock - Future Transaction Conflict</b><br><br>"
				"This transaction would cause a future-dated transaction to have negative stock.<br><br>"
				"<b>Current Transaction Details:</b><br>"
				"• Item: {0}<br>"
				"• Warehouse: {1}<br>"
				"• Posting Date/Time: {2} {3}<br>"
				"• Current Stock Available: {4}<br>"
				"• Quantity Being Transferred: {5}<br><br>"
				"<b>Future Transaction Causing Issue:</b><br>"
				"• Document: {6} ({7})<br>"
				"• Posting Date/Time: {8} {9}<br>"
				"• Shortage After This Transaction: {10} units<br><br>"
			).format(
				frappe.get_desk_link("Item", sle_args.get("item_code")),
				frappe.get_desk_link("Warehouse", sle_args.get("warehouse")),
				sle_args.get("posting_date"),
				sle_args.get("posting_time", ""),
				frappe.bold(current_stock),
				frappe.bold(abs(sle_args.get("actual_qty", 0))),
				frappe.get_desk_link(future_sle.get("voucher_type"), future_sle.get("voucher_no")),
				future_sle.get("voucher_type"),
				future_sle.get("posting_date"),
				future_sle.get("posting_time", ""),
				frappe.bold(shortage)
			)
			
			if all_future_transactions:
				message += frappe._("<b>All Future Transactions for this Item/Warehouse:</b><br>")
				message += "<table class='table table-bordered' style='margin-top: 10px;'>"
				message += "<thead><tr><th>Document</th><th>Date</th><th>Time</th><th>Qty</th><th>Qty After</th></tr></thead><tbody>"
				for txn in all_future_transactions[:10]:  # Show first 10
					qty_after = txn.get("qty_after_transaction", 0)
					row_class = "danger" if qty_after < 0 else ""
					message += f"<tr class='{row_class}'>"
					message += f"<td>{frappe.get_desk_link(txn.get('voucher_type'), txn.get('voucher_no'))}</td>"
					message += f"<td>{txn.get('posting_date')}</td>"
					message += f"<td>{txn.get('posting_time', '')}</td>"
					message += f"<td>{txn.get('actual_qty', 0)}</td>"
					message += f"<td>{qty_after}</td>"
					message += "</tr>"
				message += "</tbody></table><br>"
			
			message += frappe._(
				"<b>Solutions:</b><br>"
				"1. Enable 'Allow Negative Stock' in Stock Settings or for this item<br>"
				"2. Cancel or adjust the future transaction ({6})<br>"
				"3. Add stock to warehouse {1} before the future transaction date<br>"
				"4. Change the posting date of this transaction to after the future transaction"
			).format(
				frappe.get_desk_link("Item", sle_args.get("item_code")),
				frappe.get_desk_link("Warehouse", sle_args.get("warehouse")),
				future_sle.get("voucher_type"),
				future_sle.get("voucher_no")
			)
			
			frappe.throw(message, title=_("Insufficient Stock - Future Transaction Conflict"))
	
	def get_all_future_transactions(self, sle_args):
		"""
		Get all future-dated transactions for this item/warehouse
		"""
		return frappe.db.sql("""
			SELECT 
				voucher_type,
				voucher_no,
				posting_date,
				posting_time,
				actual_qty,
				qty_after_transaction
			FROM `tabStock Ledger Entry`
			WHERE 
				item_code = %(item_code)s
				AND warehouse = %(warehouse)s
				AND voucher_no != %(voucher_no)s
				AND is_cancelled = 0
				AND (
					posting_date > %(posting_date)s
					OR (
						posting_date = %(posting_date)s
						AND posting_time > %(posting_time)s
					)
				)
			ORDER BY posting_date, posting_time
			LIMIT 20
		""", sle_args, as_dict=True)
	
	def should_allow_negative_stock(self):
		"""
		Determine if negative stock should be allowed for this Stock Entry
		Override this method based on your business requirements
		"""
		# Check if there's a custom field or flag
		if hasattr(self, 'allow_negative_stock_override') and self.allow_negative_stock_override:
			return True
		
		# Allow for specific stock entry types (customize as needed)
		allowed_types = []  # Add your stock entry types here if needed
		if self.stock_entry_type in allowed_types:
			return True
		
		return False
	
	@frappe.whitelist()
	def enable_negative_stock_for_items(self):
		"""
		Enable negative stock for all items in this Stock Entry
		"""
		if not self.items:
			frappe.throw(_("No items found in this Stock Entry"))
		
		item_codes = []
		for item in self.items:
			if item.item_code and item.item_code not in item_codes:
				item_codes.append(item.item_code)
		
		if not item_codes:
			frappe.throw(_("No valid items found"))
		
		updated_items = []
		for item_code in item_codes:
			try:
				frappe.db.set_value("Item", item_code, "allow_negative_stock", 1)
				updated_items.append(item_code)
			except Exception as e:
				frappe.log_error(f"Error enabling negative stock for {item_code}: {str(e)}")
		
		if updated_items:
			frappe.msgprint(
				_("Negative stock enabled for the following items: {0}").format(", ".join(updated_items)),
				indicator="green"
			)
			return updated_items
		else:
			frappe.throw(_("Failed to enable negative stock for any items"))
	
	@frappe.whitelist()
	def get_stock_availability_report(self):
		"""
		Get a detailed stock availability report for all items
		"""
		if not self.items:
			return []
		
		report = []
		for item in self.items:
			if not item.item_code or not item.s_warehouse:
				continue
			
			from erpnext.stock.utils import get_stock_balance
			
			available_qty = get_stock_balance(
				item.item_code,
				item.s_warehouse,
				self.posting_date,
				self.posting_time
			)
			
			required_qty = item.transfer_qty or 0
			shortage = required_qty - available_qty if available_qty < required_qty else 0
			
			# Check for future transactions
			future_conflicts = self.check_future_transactions_for_item(item)
			
			report.append({
				"item_code": item.item_code,
				"item_name": item.item_name,
				"warehouse": item.s_warehouse,
				"required_qty": required_qty,
				"available_qty": available_qty,
				"shortage": shortage,
				"has_sufficient_stock": available_qty >= required_qty,
				"future_conflicts": future_conflicts
			})
		
		return report
	
	def check_future_transactions_for_item(self, item):
		"""
		Check if this item transfer would cause future transactions to go negative
		"""
		if not item.item_code or not item.s_warehouse:
			return []
		
		# Simulate what would happen if this transaction is processed
		sle_args = {
			"item_code": item.item_code,
			"warehouse": item.s_warehouse,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time or "00:00:00",
			"actual_qty": -(item.transfer_qty or 0),  # Negative because it's outgoing
			"voucher_type": "Stock Entry",
			"voucher_no": self.name or "NEW"
		}
		
		# Get future transactions that would be affected
		future_txns = self.get_all_future_transactions(sle_args)
		
		# Calculate what the qty_after_transaction would be after this transaction
		current_stock = frappe.db.sql("""
			SELECT qty_after_transaction
			FROM `tabStock Ledger Entry`
			WHERE 
				item_code = %(item_code)s
				AND warehouse = %(warehouse)s
				AND is_cancelled = 0
				AND (
					posting_date < %(posting_date)s
					OR (
						posting_date = %(posting_date)s
						AND posting_time <= %(posting_time)s
					)
				)
			ORDER BY posting_date DESC, posting_time DESC, creation DESC
			LIMIT 1
		""", sle_args, as_dict=True)
		
		current_qty = current_stock[0].get("qty_after_transaction", 0) if current_stock else 0
		qty_after_this_txn = current_qty - (item.transfer_qty or 0)
		
		conflicts = []
		for txn in future_txns:
			# Calculate what the qty would be after this transaction
			projected_qty = txn.get("qty_after_transaction", 0) + sle_args["actual_qty"]
			if projected_qty < 0:
				conflicts.append({
					"voucher_type": txn.get("voucher_type"),
					"voucher_no": txn.get("voucher_no"),
					"posting_date": txn.get("posting_date"),
					"posting_time": txn.get("posting_time"),
					"current_qty_after": txn.get("qty_after_transaction"),
					"projected_qty_after": projected_qty,
					"shortage": abs(projected_qty)
				})
		
		return conflicts
	
	@frappe.whitelist()
	def get_future_transaction_details(self):
		"""
		Get detailed information about future transactions that would be affected
		"""
		if not self.items:
			return {"conflicts": [], "message": "No items found"}
		
		all_conflicts = []
		for item in self.items:
			if not item.item_code or not item.s_warehouse:
				continue
			
			conflicts = self.check_future_transactions_for_item(item)
			if conflicts:
				all_conflicts.append({
					"item_code": item.item_code,
					"item_name": item.item_name,
					"warehouse": item.s_warehouse,
					"transfer_qty": item.transfer_qty,
					"conflicts": conflicts
				})
		
		return {
			"conflicts": all_conflicts,
			"has_conflicts": len(all_conflicts) > 0,
			"message": f"Found {len(all_conflicts)} item(s) with future transaction conflicts" if all_conflicts else "No conflicts found"
		}

