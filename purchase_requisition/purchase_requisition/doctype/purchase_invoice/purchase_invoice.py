import frappe
from frappe.utils import money_in_words
from frappe.model.mapper import get_mapped_doc


def log_purchase_invoice_error(doc, item, error_type, message, details=None):
    """
    Centralized error logging for Purchase Invoice custom calculations
    All errors are logged to a single error log for easy tracking
    """
    try:
        error_title = f"Purchase Invoice Calculation Error - {error_type}"
        
        error_message = f"Purchase Invoice: {doc.name if hasattr(doc, 'name') and doc.name else 'New'}\n"
        error_message += f"Error Type: {error_type}\n"
        error_message += f"Message: {message}\n"
        
        if item:
            error_message += f"\nItem Row: {getattr(item, 'idx', 'N/A')}\n"
            error_message += f"Item Code: {getattr(item, 'item_code', 'N/A')}\n"
            error_message += f"\nItem Details:\n"
            error_message += f"- Qty: {getattr(item, 'qty', 'N/A')}\n"
            error_message += f"- Rate: {getattr(item, 'rate', 'N/A')}\n"
            error_message += f"- Amount: {getattr(item, 'amount', 'N/A')}\n"
            error_message += f"- Gross Total: {getattr(item, 'custom_gross_total', 'N/A')}\n"
            error_message += f"- Discount %: {getattr(item, 'custom_discount_percentage', 'N/A')}\n"
            error_message += f"- Discounted Amount: {getattr(item, 'custom_discounted_amount', 'N/A')}\n"
            error_message += f"- Net Amount: {getattr(item, 'custom_net_amount', 'N/A')}\n"
            error_message += f"- From PR: {bool(getattr(item, 'pr_detail', None))}\n"
            error_message += f"- PR Detail: {getattr(item, 'pr_detail', 'N/A')}\n"
        
        if details:
            import json
            error_message += f"\nAdditional Details:\n{json.dumps(details, indent=2, default=str)}\n"
        
        frappe.log_error(
            title=error_title,
            message=error_message
        )
    except Exception as e:
        # Fallback if error logging itself fails
        frappe.log_error(
            title="Purchase Invoice Error Logging Failed",
            message=f"Failed to log error: {str(e)}\nOriginal error: {error_type} - {message}"
        )


def preserve_pr_amount(doc, method):
    """
    CRITICAL: Preserve PR amount BEFORE any calculations
    This runs before validate to ensure amount is never changed for PR items
    This MUST run before calculation_pi to prevent over-billing errors
    
    IMPORTANT: The amount field must match the PR Item amount exactly
    The over-billing validation checks: already_billed + current_item.amount <= PR_item.amount * (1 + allowance)
    """
    from frappe.utils import flt
    
    # Track pr_details to detect duplicates
    pr_details_seen = {}
    
    for item in doc.items:
        if item.get("pr_detail"):
            pr_detail = item.pr_detail
            
            # Check for duplicate pr_detail in the same invoice
            if pr_detail in pr_details_seen:
                # DUPLICATE DETECTED - This is likely the root cause!
                first_item_idx = pr_details_seen[pr_detail]
                first_item = next((i for i in doc.items if i.idx == first_item_idx), None)
                first_item_amount = flt(first_item.amount) if first_item else 0
                current_item_amount = flt(item.amount) if item.amount else 0
                
                log_purchase_invoice_error(
                    doc, item, "Duplicate PR Detail - ROOT CAUSE",
                    f"Item {item.idx} has duplicate pr_detail {pr_detail}. Already seen in row {first_item_idx}. First item amount: {first_item_amount}, Current item amount: {current_item_amount}, Total: {first_item_amount + current_item_amount}. This will cause over-billing!",
                    {
                        "pr_detail": pr_detail,
                        "first_occurrence_row": first_item_idx,
                        "first_item_amount": first_item_amount,
                        "current_row": item.idx,
                        "current_item_amount": current_item_amount,
                        "total_if_both_used": first_item_amount + current_item_amount,
                        "pr_amount": None  # Will be set below
                    }
                )
            
            pr_details_seen[pr_detail] = item.idx
            
            # Get the EXACT amount from Purchase Receipt Item
            # This is what the over-billing validation will check against
            try:
                pr_item_data = frappe.db.get_value(
                    "Purchase Receipt Item",
                    pr_detail,
                    ["amount", "qty", "rate", "received_qty", "billed_amt"],
                    as_dict=True
                )
                
                if pr_item_data and pr_item_data.get("amount") is not None:
                    pr_amount = flt(pr_item_data.get("amount"))
                    pr_qty = flt(pr_item_data.get("qty", 0))
                    pr_received_qty = flt(pr_item_data.get("received_qty", 0))
                    pr_billed_amt = flt(pr_item_data.get("billed_amt", 0))
                    
                    # Check for already billed amount
                    # CRITICAL: Replicate ERPNext's get_billed_amount_for_item logic EXACTLY
                    # This is what validate_multiple_billing uses
                    amount_precision = item.precision("amount") if hasattr(item, "precision") else 6
                    tolerance = 1 / (10 ** amount_precision)
                    
                    # Use ERPNext's exact query builder logic
                    from frappe.query_builder import Criterion
                    from frappe.query_builder.functions import Sum
                    
                    item_doctype = frappe.qb.DocType("Purchase Invoice Item")
                    based_on_field = frappe.qb.Field("amount")
                    join_field = frappe.qb.Field("pr_detail")
                    
                    # This is the EXACT query from get_billed_amount_for_item
                    result = (
                        frappe.qb.from_(item_doctype)
                        .select(Sum(based_on_field))
                        .where(join_field == pr_detail)
                        .where(
                            Criterion.any(
                                [
                                    Criterion.all([
                                        item_doctype.docstatus == 1,
                                        item_doctype.parent != (doc.name or ''),
                                    ]),
                                    Criterion.all([
                                        item_doctype.docstatus == 0,
                                        item_doctype.parent == (doc.name or ''),
                                        item_doctype.name != (item.name or ''),
                                    ]),
                                ]
                            )
                        )
                    ).run()
                    
                    already_billed = flt(result[0][0], amount_precision) if result and result[0] else 0
                    
                    # Also check unsaved items in current doc.items (for new/unsaved items)
                    already_billed_unsaved = 0
                    for other_item in doc.items:
                        if (other_item.get("pr_detail") == pr_detail and 
                            other_item != item and  # Different item object
                            not other_item.get("name")):  # Not saved yet (no name)
                            # This is an unsaved item in the current document
                            already_billed_unsaved += flt(other_item.amount or 0, amount_precision)
                    
                    already_billed += already_billed_unsaved
                    
                    # Get breakdown for logging
                    result_submitted = frappe.db.sql("""
                        SELECT IFNULL(SUM(amount), 0)
                        FROM `tabPurchase Invoice Item`
                        WHERE pr_detail = %s
                        AND docstatus = 1
                        AND parent != %s
                    """, (pr_detail, doc.name or ''))
                    already_billed_submitted = flt(result_submitted[0][0], amount_precision) if result_submitted and result_submitted[0] else 0
                    
                    result_current = frappe.db.sql("""
                        SELECT IFNULL(SUM(amount), 0)
                        FROM `tabPurchase Invoice Item`
                        WHERE pr_detail = %s
                        AND docstatus = 0
                        AND parent = %s
                        AND name != %s
                    """, (pr_detail, doc.name or '', item.name or ''))
                    already_billed_current = flt(result_current[0][0], amount_precision) if result_current and result_current[0] else 0
                    
                    # Calculate remaining billable amount
                    remaining_amount = flt(pr_amount - already_billed, amount_precision)
                    
                    # CRITICAL: The amount field must be set correctly for over-billing validation
                    # The validation checks: already_billed + current_item.amount <= pr_amount * (1 + allowance)
                    # So we must ensure: current_item.amount <= remaining_amount (with allowance)
                    
                    current_amount = flt(item.amount, amount_precision) if item.amount else 0
                    
                    # Determine the correct amount to use
                    # CRITICAL: The validation checks: already_billed + current_item.amount <= pr_amount * (1 + allowance)
                    # So we must ensure: current_item.amount <= remaining_amount (with allowance)
                    
                    if already_billed >= flt(pr_amount, amount_precision) - tolerance:
                        # PR is already fully billed - amount should be 0
                        correct_amount = 0
                        log_purchase_invoice_error(
                            doc, item, "PR Fully Billed",
                            f"Item {item.idx}: PR {pr_detail} is already fully billed ({already_billed} >= {pr_amount}). Setting amount to 0.",
                            {
                                "pr_detail": pr_detail,
                                "pr_amount": pr_amount,
                                "already_billed": already_billed,
                                "remaining": remaining_amount,
                                "current_amount": current_amount
                            }
                        )
                    elif already_billed > 0:
                        # There's already a partial bill - must use remaining amount
                        # Allow 1% tolerance for rounding
                        max_allowed = flt(pr_amount * 1.01, amount_precision)  # With 1% allowance
                        if current_amount == 0:
                            # Amount not set - use remaining amount
                            correct_amount = flt(max(0, remaining_amount), amount_precision)
                        elif (already_billed + current_amount) > (max_allowed + tolerance):
                            # Would cause over-billing - use remaining amount
                            correct_amount = flt(max(0, remaining_amount), amount_precision)
                            log_purchase_invoice_error(
                                doc, item, "Adjusting Amount to Prevent Over-Billing",
                                f"Item {item.idx}: Current amount {current_amount} + already_billed {already_billed} = {already_billed + current_amount} would exceed max allowed {max_allowed}. Setting to remaining {remaining_amount}.",
                                {
                                    "pr_detail": pr_detail,
                                    "pr_amount": pr_amount,
                                    "already_billed": already_billed,
                                    "current_amount": current_amount,
                                    "remaining_amount": remaining_amount,
                                    "max_allowed": max_allowed,
                                    "total_if_used": already_billed + current_amount
                                }
                            )
                        else:
                            # Current amount is within limits - keep it
                            correct_amount = flt(current_amount, amount_precision)
                    else:
                        # No existing bill - but be conservative
                        # If invoice exists and was previously saved, there might be a bill we're not detecting
                        # Use remaining amount to be safe
                        if doc.name and doc.name != 'New':
                            # Invoice exists - be conservative and use remaining amount
                            # This prevents over-billing if ERPNext finds something we don't
                            correct_amount = flt(max(0, remaining_amount), amount_precision)
                            if correct_amount != pr_amount:
                                log_purchase_invoice_error(
                                    doc, item, "Conservative Amount Setting",
                                    f"Item {item.idx}: Invoice {doc.name} exists. Using remaining amount {correct_amount} instead of PR amount {pr_amount} to prevent over-billing.",
                                    {
                                        "pr_detail": pr_detail,
                                        "pr_amount": pr_amount,
                                        "remaining_amount": remaining_amount,
                                        "correct_amount": correct_amount,
                                        "invoice_exists": True
                                    }
                                )
                        else:
                            # New invoice - use PR amount if not set, otherwise keep current
                            correct_amount = flt(pr_amount if current_amount == 0 else current_amount, amount_precision)
                    
                    # Set the amount
                    item.amount = correct_amount
                    
                    # Store flags so calculation_pi knows not to change it
                    item._pr_amount_preserved = True
                    item._original_pr_amount = pr_amount
                    item._pr_detail_id = pr_detail
                    item._pr_qty = pr_qty
                    item._pr_received_qty = pr_received_qty
                    item._already_billed = already_billed
                    item._remaining_amount = remaining_amount
                    
                    # Check if this pr_detail appears multiple times in the invoice
                    duplicate_count = sum(1 for i in doc.items if i.get("pr_detail") == pr_detail)
                    is_duplicate = duplicate_count > 1
                    
                    # Log for debugging - always log when setting PR amount
                    log_purchase_invoice_error(
                        doc, item, "PR Amount Preserved",
                        f"Item {item.idx}: Preserved PR amount {pr_amount} before calculations. Already billed: {already_billed} (submitted: {already_billed_submitted}, current_db: {already_billed_current}, unsaved: {already_billed_unsaved}), Remaining: {remaining_amount}. Duplicate count: {duplicate_count}",
                        {
                            "pr_detail": pr_detail,
                            "pr_amount": pr_amount,
                            "pr_qty": pr_qty,
                            "pr_received_qty": pr_received_qty,
                            "pr_billed_amt": pr_billed_amt,
                            "already_billed_total": already_billed,
                            "already_billed_submitted": already_billed_submitted,
                            "already_billed_current_db": already_billed_current,
                            "already_billed_unsaved": already_billed_unsaved,
                            "remaining_amount": remaining_amount,
                            "duplicate_count": duplicate_count,
                            "is_duplicate": is_duplicate,
                            "pi_qty": getattr(item, 'qty', 'N/A'),
                            "pi_amount_set": item.amount,
                            "pi_name": doc.name or 'New',
                            "item_name": item.name or 'New',
                            "item_idx": item.idx,
                            "all_items_with_same_pr_detail": [
                                {"idx": i.idx, "name": i.name or 'New', "amount": flt(i.amount) if i.amount else 0}
                                for i in doc.items if i.get("pr_detail") == pr_detail
                            ]
                        }
                    )
                else:
                    log_purchase_invoice_error(
                        doc, item, "PR Amount Not Found",
                        f"Item {item.idx}: Could not get PR amount from pr_detail {pr_detail}",
                        {"pr_detail": pr_detail}
                    )
            except Exception as e:
                # Log error but don't fail
                log_purchase_invoice_error(
                    doc, item, "Failed to Get PR Amount",
                    f"Could not get PR amount for pr_detail {pr_detail}: {str(e)}",
                    {"pr_detail": pr_detail, "error": str(e), "traceback": frappe.get_traceback()}
                )


def preserve_po_rate(doc, method):
    for item in doc.items:
        if item.po_detail:
            po_item = frappe.db.get_value("Purchase Order Item", item.po_detail, "rate")
            if po_item:
                item.rate = po_item

def debug_validate_multiple_billing(doc, method):
    """
    Debug hook to see what ERPNext's validate_multiple_billing will see
    This runs right before validate_multiple_billing
    """
    from frappe.utils import flt
    from frappe.query_builder import Criterion
    from frappe.query_builder.functions import Sum
    
    for item in doc.items:
        if item.get("pr_detail"):
            pr_detail = item.pr_detail
            
            # Use ERPNext's exact method to see what it will find
            item_doctype = frappe.qb.DocType("Purchase Invoice Item")
            based_on_field = frappe.qb.Field("amount")
            join_field = frappe.qb.Field("pr_detail")
            
            result = (
                frappe.qb.from_(item_doctype)
                .select(Sum(based_on_field))
                .where(join_field == pr_detail)
                .where(
                    Criterion.any(
                        [
                            Criterion.all([
                                item_doctype.docstatus == 1,
                                item_doctype.parent != (doc.name or ''),
                            ]),
                            Criterion.all([
                                item_doctype.docstatus == 0,
                                item_doctype.parent == (doc.name or ''),
                                item_doctype.name != (item.name or ''),
                            ]),
                        ]
                    )
                )
            ).run()
            
            already_billed_erpnext = flt(result[0][0]) if result and result[0] else 0
            current_amount = flt(item.amount) if item.amount else 0
            total_billed = already_billed_erpnext + current_amount
            
            # Get PR amount
            pr_amount = frappe.db.get_value("Purchase Receipt Item", pr_detail, "amount") or 0
            pr_amount = flt(pr_amount)
            
            if total_billed > pr_amount * 1.01:  # With 1% allowance
                log_purchase_invoice_error(
                    doc, item, "DEBUG - Over-Billing Detected",
                    f"Item {item.idx}: ERPNext will see already_billed={already_billed_erpnext}, current_amount={current_amount}, total={total_billed}, PR_amount={pr_amount}. This will cause over-billing error!",
                    {
                        "pr_detail": pr_detail,
                        "pr_amount": pr_amount,
                        "already_billed_erpnext": already_billed_erpnext,
                        "current_amount": current_amount,
                        "total_billed": total_billed,
                        "max_allowed": pr_amount * 1.01,
                        "overbill_amount": total_billed - (pr_amount * 1.01),
                        "item_name": item.name or 'New',
                        "doc_name": doc.name or 'New',
                        "doc_docstatus": doc.docstatus
                    }
                )

def calculation_pi(doc, method):
    """
    Calculate custom fields: Gross Total, Discount, Net Total for Purchase Invoice
    This runs on validate to ensure all calculations are correct
    IMPORTANT: We preserve the original 'amount' field when coming from PR to avoid over-billing errors
    """
    from frappe.utils import flt
    
    try:
        gross_total = 0
        discounted_total = 0
        net_total = 0

        for i in doc.items:
            # Check if this item is linked to Purchase Receipt
            is_from_pr = bool(i.get("pr_detail"))
            
            # CRITICAL: If amount was preserved in before_validate, use it
            # This ensures we never change the PR amount
            if hasattr(i, '_pr_amount_preserved') and i._pr_amount_preserved:
                pr_amount = getattr(i, '_original_pr_amount', None)
            else:
                # Fallback: Get PR amount if not already preserved
                pr_amount = None
                if is_from_pr and i.get("pr_detail"):
                    try:
                        pr_amount = frappe.db.get_value("Purchase Receipt Item", i.pr_detail, "amount")
                        pr_amount = flt(pr_amount) if pr_amount else None
                    except:
                        pr_amount = None
            
            # Calculate gross total (qty * rate)
            if not i.custom_gross_total or i.custom_gross_total == 0:
                i.custom_gross_total = flt(i.qty) * flt(i.rate)
            else:
                # Ensure it's recalculated if qty or rate changed
                calculated_gross = flt(i.qty) * flt(i.rate)
                if abs(flt(i.custom_gross_total) - calculated_gross) > 0.01:
                    i.custom_gross_total = calculated_gross

            # Calculate discount - prioritize percentage if both exist
            if i.custom_discount_percentage and i.custom_discount_percentage != 0:
                # Recalculate discounted amount from percentage
                i.custom_discounted_amount = flt((flt(i.custom_discount_percentage) / 100) * flt(i.custom_gross_total))
            elif i.custom_discounted_amount and i.custom_discounted_amount != 0:
                # Calculate percentage from amount
                if i.custom_gross_total and i.custom_gross_total != 0:
                    i.custom_discount_percentage = flt((flt(i.custom_discounted_amount) / flt(i.custom_gross_total)) * 100)
                else:
                    i.custom_discount_percentage = 0
            else:
                # Both missing, set to 0
                i.custom_discounted_amount = 0
                i.custom_discount_percentage = 0

            # Calculate net amount for display/calculation purposes
            i.custom_net_amount = flt(i.custom_gross_total) - flt(i.custom_discounted_amount)
            
            # CRITICAL: Preserve amount field when item is from Purchase Receipt
            # The over-billing validation compares PI amount against PR amount
            # We must NEVER change the amount if it was preserved in before_validate
            if hasattr(i, '_pr_amount_preserved') and i._pr_amount_preserved:
                # Amount was already set in before_validate - DO NOT CHANGE IT
                # Just log if there's a discrepancy for debugging
                if abs(flt(i.amount) - flt(i.custom_net_amount)) > 0.01:
                    log_purchase_invoice_error(
                        doc, i, "Amount Mismatch with PR",
                        f"Item {i.idx} from PR: PI amount ({i.amount}) differs from calculated net amount ({i.custom_net_amount}). Using PR amount for validation.",
                        {
                            "pr_detail": i.get("pr_detail"),
                            "pr_amount": getattr(i, '_original_pr_amount', None),
                            "current_amount": flt(i.amount),
                            "calculated_net_amount": flt(i.custom_net_amount),
                            "difference": abs(flt(i.amount) - flt(i.custom_net_amount))
                        }
                    )
                # DO NOT change i.amount - it's already set correctly
            elif is_from_pr and pr_amount is not None:
                # For items from PR: Use the EXACT amount from Purchase Receipt
                # This is what the over-billing validation expects
                i.amount = pr_amount
                
                # Log if there's a discrepancy for debugging
                if abs(flt(i.amount) - flt(i.custom_net_amount)) > 0.01:
                    log_purchase_invoice_error(
                        doc, i, "Amount Mismatch with PR",
                        f"Item {i.idx} from PR: PI amount ({i.amount}) differs from calculated net amount ({i.custom_net_amount}). Using PR amount for validation.",
                        {
                            "pr_detail": i.get("pr_detail"),
                            "pr_amount": pr_amount,
                            "calculated_net_amount": flt(i.custom_net_amount),
                            "difference": abs(flt(i.amount) - flt(i.custom_net_amount))
                        }
                    )
            elif is_from_pr and pr_amount is None:
                # PR item but couldn't get PR amount - log error
                log_purchase_invoice_error(
                    doc, i, "Cannot Get PR Amount",
                    f"Item {i.idx} has pr_detail but couldn't fetch PR amount. Using calculated amount.",
                    {"pr_detail": i.get("pr_detail"), "calculated_net_amount": flt(i.custom_net_amount)}
                )
                i.amount = flt(i.custom_net_amount)
            else:
                # For new items or items not from PR, use custom_net_amount
                i.amount = flt(i.custom_net_amount)

            # Accumulate totals
            gross_total += flt(i.custom_gross_total)
            discounted_total += flt(i.custom_discounted_amount)
            # For totals, use amount (which may be from PR) instead of custom_net_amount
            net_total += flt(i.amount)

        # Update parent document fields
        doc.custom_gross_rate = flt(gross_total)
        doc.custom_discounted_amount = flt(discounted_total)
        
        # Calculate overall discount percentage
        if doc.custom_gross_rate and doc.custom_gross_rate != 0:
            doc.custom_discounted_percentage = flt((doc.custom_discounted_amount / doc.custom_gross_rate) * 100)
        else:
            doc.custom_discounted_percentage = 0
        
        doc.custom_net_rate = flt(net_total)

        # Update standard totals (ensure they match custom calculations)
        doc.total = flt(net_total)
        doc.grand_total = flt(net_total) + flt(doc.total_taxes_and_charges or 0)
        doc.rounded_total = flt(doc.grand_total)
        doc.outstanding_amount = flt(doc.grand_total)

        # Set in_words from custom_net_rate
        if doc.custom_net_rate:
            doc.in_words = money_in_words(doc.custom_net_rate, doc.currency or "PKR")
    
    except Exception as e:
        # Log any calculation errors to centralized error log
        try:
            log_purchase_invoice_error(
                doc, doc.items[0] if doc.items else None,
                "Calculation Error",
                f"Error in calculation_pi: {str(e)}",
                {"error_type": type(e).__name__, "traceback": frappe.get_traceback()}
            )
        except:
            # If error logging fails, use standard frappe.log_error
            frappe.log_error(
                title="Purchase Invoice Calculation Error",
                message=f"Error in calculation_pi for {doc.name or 'New PI'}: {str(e)}\n\nTraceback:\n{frappe.get_traceback()}"
            )
        # Re-raise to prevent silent failures
        raise

@frappe.whitelist()
def make_purchase_invoice_custom(source_name, target_doc=None):
    def postprocess(source_doc, target_doc):
        target_doc.ignore_pricing_rule = 1
        target_doc.run_method("set_missing_values")
        # Run custom calculation to ensure all fields are calculated correctly
        calculation_pi(target_doc, "validate")
        target_doc.run_method("calculate_taxes_and_totals")

    def set_missing_discount_fields(source_item, target_item, source_parent):
        """
        Map custom fields from Purchase Receipt Item to Purchase Invoice Item
        Purchase Receipt uses: custom_gross_rate, custom_discount_, custom_net_total
        Purchase Invoice uses: custom_gross_total, custom_discount_percentage, custom_net_amount
        """
        # Map from PR fields to PI fields
        if hasattr(source_item, "custom_gross_rate") and source_item.custom_gross_rate:
            target_item.custom_gross_total = source_item.custom_gross_rate
        
        if hasattr(source_item, "custom_discount_") and source_item.custom_discount_ is not None:
            target_item.custom_discount_percentage = source_item.custom_discount_
        
        if hasattr(source_item, "custom_discounted_amount") and source_item.custom_discounted_amount:
            target_item.custom_discounted_amount = source_item.custom_discounted_amount
        
        if hasattr(source_item, "custom_net_total") and source_item.custom_net_total:
            target_item.custom_net_amount = source_item.custom_net_total
        
        # Recalculate gross total if not set or if qty/rate changed
        if not target_item.custom_gross_total or target_item.custom_gross_total == 0:
            target_item.custom_gross_total = target_item.qty * target_item.rate
        
        # Calculate discount if percentage is set but amount is not
        if target_item.custom_discount_percentage and not target_item.custom_discounted_amount:
            target_item.custom_discounted_amount = (target_item.custom_discount_percentage / 100) * target_item.custom_gross_total
        
        # Calculate net amount for display
        if target_item.custom_gross_total:
            if not target_item.custom_discounted_amount:
                target_item.custom_discounted_amount = 0
            target_item.custom_net_amount = target_item.custom_gross_total - target_item.custom_discounted_amount
            
            # IMPORTANT: Preserve the original amount from Purchase Receipt
            # Don't override amount field - it needs to match PR amount for over-billing validation
            # The amount field is already set by ERPNext's standard mapping from PR
            # Only set it if it's 0 or not set
            if not target_item.amount or target_item.amount == 0:
                target_item.amount = target_item.custom_net_amount
            # Otherwise, keep the amount from PR (which is correct for validation)

    return get_mapped_doc(
        "Purchase Receipt",
        source_name,
        {
            "Purchase Receipt": {
                "doctype": "Purchase Invoice",
                "validation": {"docstatus": ["=", 1]},
            },
            "Purchase Receipt Item": {
                "doctype": "Purchase Invoice Item",
                "field_map": {
                    "name": "pr_detail",
                    "parent": "purchase_receipt",
                    "purchase_order": "purchase_order",
                    "purchase_order_item": "po_detail",  # Needed by ERPNext
                    # Map PR fields to PI fields correctly
                    "custom_gross_rate": "custom_gross_total",  # PR.gross_rate -> PI.gross_total
                    "custom_discounted_amount": "custom_discounted_amount",  # Same name
                    "custom_discount_": "custom_discount_percentage",  # PR.discount_ -> PI.discount_percentage
                    "custom_net_total": "custom_net_amount"  # PR.net_total -> PI.net_amount
                },
                "postprocess": set_missing_discount_fields,
            },
        },
        target_doc,
        postprocess,
    )
