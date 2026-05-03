import frappe
from frappe.utils import money_in_words, flt
from frappe.model.mapper import get_mapped_doc
import json


def _pi_debug_print(label, payload=None):
    """Print debug lines directly to bench web logs."""
    try:
        if payload is None:
            print(f"[PI-DEBUG] {label}")
        else:
            print(f"[PI-DEBUG] {label}: {json.dumps(payload, default=str)}")
    except Exception:
        print(f"[PI-DEBUG] {label}: {payload}")
        
def get_source_visible_rate(pr_detail=None, po_detail=None, fallback_rate=0):
    """Return the gross/display rate we want to show on PI rows."""
    rate = 0

    if po_detail:
        rate = flt(frappe.db.get_value("Purchase Order Item", po_detail, "rate") or 0)
        if rate:
            return rate

    if pr_detail:
        pr_data = frappe.db.get_value(
            "Purchase Receipt Item",
            pr_detail,
            ["price_list_rate", "custom_gross_rate", "qty", "rate", "purchase_order_item"],
            as_dict=True,
        ) or {}

        rate = flt(pr_data.get("price_list_rate") or 0)
        if rate:
            return rate

        gross_total = flt(pr_data.get("custom_gross_rate") or 0)
        qty = flt(pr_data.get("qty") or 0)
        if gross_total and qty:
            return flt(gross_total / qty)

        linked_po_detail = pr_data.get("purchase_order_item")
        if linked_po_detail and linked_po_detail != po_detail:
            rate = flt(frappe.db.get_value("Purchase Order Item", linked_po_detail, "rate") or 0)
            if rate:
                return rate

        rate = flt(pr_data.get("rate") or 0)
        if rate:
            return rate

    return flt(fallback_rate or 0)


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


def _is_user_override_on_pr_row(doc, item):
    """
    Detect whether a PR-linked row has been manually edited by user input.
    If edited, we should not force-reset values from PR defaults.
    """
    if not item.get("pr_detail"):
        return False

    # Existing draft row: compare with value before current save.
    before_doc = None if doc.is_new() else doc.get_doc_before_save()
    if before_doc and item.get("name"):
        prev_row = next((d for d in before_doc.items if d.name == item.name), None)
        if prev_row:
            tracked_fields = (
                "qty",
                "custom_po_rate",
                "custom_discount_percentage",
                "custom_discounted_amount",
                "custom_gross_total",
                "custom_net_amount",
                "amount",
            )
            tolerance = 0.000001
            for fieldname in tracked_fields:
                if abs(flt(getattr(item, fieldname, 0) or 0) - flt(getattr(prev_row, fieldname, 0) or 0)) > tolerance:
                    return True

    # New doc first-save: compare against PR defaults.
    pr_data = frappe.db.get_value(
        "Purchase Receipt Item",
        item.pr_detail,
        [
            "qty",
            "rate",
            "price_list_rate",
            "purchase_order_item",
            "custom_discount_",
            "custom_discounted_amount",
            "custom_gross_rate",
            "custom_net_total",
            "amount",
        ],
        as_dict=True,
    ) or {}

    pr_qty = flt(pr_data.get("qty") or 0)
    po_rate = 0
    if pr_data.get("purchase_order_item"):
        po_rate = flt(frappe.db.get_value("Purchase Order Item", pr_data.get("purchase_order_item"), "rate") or 0)
    default_po_rate = flt(po_rate or pr_data.get("price_list_rate") or pr_data.get("rate") or 0)
    default_discount_pct = flt(pr_data.get("custom_discount_") or 0)
    default_discount_amt = flt(pr_data.get("custom_discounted_amount") or 0)
    default_gross = flt(pr_data.get("custom_gross_rate") or (pr_qty * default_po_rate))
    default_amount = flt(
        pr_data.get("custom_net_total")
        if pr_data.get("custom_net_total") is not None
        else pr_data.get("amount")
    )

    tolerance = 0.000001
    if abs(flt(item.qty or 0) - pr_qty) > tolerance:
        return True
    if abs(flt(getattr(item, "custom_po_rate", 0) or 0) - default_po_rate) > tolerance:
        return True
    if abs(flt(getattr(item, "custom_discount_percentage", 0) or 0) - default_discount_pct) > tolerance:
        return True
    if abs(flt(getattr(item, "custom_discounted_amount", 0) or 0) - default_discount_amt) > tolerance:
        return True
    if abs(flt(getattr(item, "custom_gross_total", 0) or 0) - default_gross) > tolerance:
        return True
    if abs(flt(item.amount or 0) - default_amount) > tolerance:
        return True

    return bool(getattr(item, "_discount_manually_edited", False) or getattr(item, "_po_rate_manually_edited", False))


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
            if _is_user_override_on_pr_row(doc, item):
                continue
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
                    [
                        "amount",
                        "qty",
                        "rate",
                        "received_qty",
                        "billed_amt",
                        "purchase_order_item",
                        "price_list_rate",
                        "discount_percentage",
                        "discount_amount",
                        "custom_gross_rate",
                        "custom_discounted_amount",
                        "custom_net_total",
                        "custom_discount_",
                    ],
                    as_dict=True
                )
                
                if pr_item_data and pr_item_data.get("amount") is not None:
                    pr_net_amount = pr_item_data.get("custom_net_total")
                    pr_amount = flt(
                        pr_net_amount if pr_net_amount is not None else pr_item_data.get("amount")
                    )
                    pr_qty = flt(pr_item_data.get("qty", 0))
                    pr_received_qty = flt(pr_item_data.get("received_qty", 0))
                    pr_billed_amt = flt(pr_item_data.get("billed_amt", 0))
                    pr_rate = flt(pr_item_data.get("rate", 0))
                    pr_price_list_rate = flt(pr_item_data.get("price_list_rate", 0))
                    pr_custom_gross_total = flt(pr_item_data.get("custom_gross_rate", 0))
                    pr_discount_pct = flt(
                        pr_item_data.get("custom_discount_")
                        if pr_item_data.get("custom_discount_") is not None
                        else pr_item_data.get("discount_percentage", 0)
                    )
                    pr_discount_amt = flt(
                        pr_item_data.get("custom_discounted_amount")
                        if pr_item_data.get("custom_discounted_amount") is not None
                        else pr_item_data.get("discount_amount", 0)
                    )
                    po_detail = pr_item_data.get("purchase_order_item")
                    
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
                    
                    # Determine the correct amount to use.
                    # Always clamp to remaining PR billable amount so custom UI/script
                    # side effects on `amount` can never trigger over-billing.
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
                    else:
                        safe_remaining = flt(max(0, remaining_amount), amount_precision)

                        if current_amount <= 0:
                            # Fresh row with no amount: use full remaining amount.
                            correct_amount = safe_remaining
                        elif current_amount > safe_remaining + tolerance:
                            # Amount was inflated (usually from custom rate/gross logic): clamp it.
                            correct_amount = safe_remaining
                            log_purchase_invoice_error(
                                doc, item, "Adjusting Amount to Remaining PR Amount",
                                f"Item {item.idx}: current amount {current_amount} exceeded remaining PR amount {safe_remaining}. Clamped to remaining amount.",
                                {
                                    "pr_detail": pr_detail,
                                    "pr_amount": pr_amount,
                                    "already_billed": already_billed,
                                    "current_amount": current_amount,
                                    "remaining_amount": safe_remaining,
                                    "invoice": doc.name or "New"
                                }
                            )
                        else:
                            # Partial billing row and still within remaining amount.
                            correct_amount = flt(current_amount, amount_precision)
                    
                    # Set the amount
                    item.amount = correct_amount

                    # Keep PI amount safe for ERPNext overbilling validation:
                    # - PI amount is always net and must stay equal to PR remaining net amount
                    # - PI visible rate should follow the gross/source rate the user expects to see
                    # - store the same gross/source rate in price_list_rate for consistency
                    rate_precision = item.precision("rate") if hasattr(item, "precision") else 6
                    qty_precision = item.precision("qty") if hasattr(item, "precision") else 6
                    source_gross_rate = flt(
                        get_source_visible_rate(pr_detail=pr_detail, po_detail=po_detail, fallback_rate=pr_price_list_rate),
                        rate_precision,
                    )
                    source_net_rate = flt(pr_rate, rate_precision)

                    # Keep transactional rate net-safe. PO/list rate is shown in
                    # price_list_rate and gross custom fields.
                    display_rate = source_net_rate
                    if not display_rate and flt(item.qty or 0):
                        display_rate = flt(correct_amount / flt(item.qty or 0), rate_precision)
                    current_rate = flt(item.rate, rate_precision)
                    rate_edited = bool(
                        current_rate and (
                            not display_rate or abs(current_rate - display_rate) > (1 / (10 ** rate_precision))
                        )
                    )

                    if rate_edited:
                        item.rate = current_rate
                        if hasattr(item, "base_rate"):
                            item.base_rate = current_rate

                        item.qty = flt(pr_qty or item.qty or 0, qty_precision)
                        if hasattr(item, "stock_qty"):
                            item.stock_qty = flt(item.qty) * flt(item.conversion_factor or 1)
                    elif display_rate:
                        item.rate = display_rate
                        if hasattr(item, "base_rate"):
                            item.base_rate = display_rate

                        item.qty = flt(pr_qty or item.qty or 0, qty_precision)
                        if hasattr(item, "stock_qty"):
                            item.stock_qty = flt(item.qty) * flt(item.conversion_factor or 1)
                    else:
                        # Fallback only when both gross and net source rates are unavailable.
                        qty = flt(item.qty or 0)
                        if qty:
                            fallback_rate = flt(correct_amount / qty, rate_precision)
                            item.rate = fallback_rate
                            if hasattr(item, "base_rate"):
                                item.base_rate = fallback_rate

                    if hasattr(item, "base_amount"):
                        item.base_amount = flt(correct_amount, item.precision("base_amount"))

                    if hasattr(item, "price_list_rate") and source_gross_rate:
                        item.price_list_rate = source_gross_rate

                    if pr_custom_gross_total:
                        item.custom_gross_total = pr_custom_gross_total
                    if pr_discount_amt or pr_discount_amt == 0:
                        item.custom_discounted_amount = pr_discount_amt
                    item.custom_net_amount = correct_amount

                    # Preserve line-level discount fields to match PO/PR view semantics.
                    if hasattr(item, "discount_percentage"):
                        item.discount_percentage = pr_discount_pct
                    if hasattr(item, "discount_amount"):
                        item.discount_amount = pr_discount_amt

                    _pi_debug_print(
                        "preserve_pr_amount row",
                        {
                            "doc": doc.name or "New",
                            "idx": item.idx,
                            "pr_detail": pr_detail,
                            "current_amount_before": current_amount,
                            "set_amount": item.amount,
                            "set_rate": item.rate,
                            "set_qty": item.qty,
                            "price_list_rate_set": getattr(item, "price_list_rate", None),
                            "source_gross_rate": source_gross_rate,
                            "source_net_rate": source_net_rate,
                            "display_rate": display_rate,
                            "current_rate": current_rate,
                            "rate_edited": rate_edited,
                            "expected_amount_from_qty_rate": flt(flt(item.qty or 0) * flt(item.rate or 0), amount_precision),
                            "pr_amount": pr_amount,
                            "already_billed": already_billed,
                            "remaining_amount": remaining_amount,
                        },
                    )
                    
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

    # One consolidated snapshot for this save attempt to debug over-billing inputs.
    log_pre_validate_overbilling_snapshot(doc)


def log_pre_validate_overbilling_snapshot(doc):
    """
    Capture exact values that ERPNext over-billing validation is expected to compare.
    """
    from frappe.utils import flt
    from frappe.query_builder.functions import Sum
    from erpnext.controllers.status_updater import get_allowance_for

    try:
        if not doc.items:
            return

        # Group current document amounts by pr_detail (same behavior as validation grouping).
        grouped_current = {}
        for row in doc.items:
            if not row.get("pr_detail"):
                continue
            grouped_current.setdefault(row.pr_detail, frappe._dict(item_code=row.item_code, rows=[], current_total=0.0))
            grouped_current[row.pr_detail].rows.append(row.idx)
            grouped_current[row.pr_detail].current_total += flt(row.amount or 0)

        if not grouped_current:
            return

        pii = frappe.qb.DocType("Purchase Invoice Item")
        pri = frappe.qb.DocType("Purchase Receipt Item")

        snapshot_rows = []
        for pr_detail, entry in grouped_current.items():
            pr_data = frappe.db.get_value(
                "Purchase Receipt Item",
                pr_detail,
                ["amount", "item_code"],
                as_dict=True,
            ) or {}

            pr_amount = flt(pr_data.get("amount") or 0)
            item_code = entry.item_code or pr_data.get("item_code")
            allowance = get_allowance_for(item_code, {}, None, None, "amount")[0] if item_code else 0
            max_allowed = flt(pr_amount * (100 + flt(allowance)) / 100)

            already_billed_query = (
                frappe.qb.from_(pii)
                .select(Sum(pii.amount))
                .where((pii.pr_detail == pr_detail) & (pii.docstatus == 1) & (pii.parent != (doc.name or "")))
            ).run()
            already_billed = flt(already_billed_query[0][0]) if already_billed_query and already_billed_query[0] else 0

            projected_total = flt(already_billed + flt(entry.current_total))
            over_by = flt(projected_total - max_allowed)

            snapshot_rows.append(
                {
                    "pr_detail": pr_detail,
                    "item_code": item_code,
                    "rows": entry.rows,
                    "pr_amount": pr_amount,
                    "allowance_percent": flt(allowance),
                    "max_allowed": max_allowed,
                    "already_billed_submitted": already_billed,
                    "current_doc_total_for_pr_detail": flt(entry.current_total),
                    "projected_total": projected_total,
                    "over_by": over_by,
                }
            )

        log_purchase_invoice_error(
            doc,
            doc.items[0] if doc.items else None,
            "Pre-Validate Overbilling Snapshot",
            "Snapshot of values before ERPNext validate_multiple_billing.",
            {
                "doc": doc.name or "New",
                "currency": doc.currency,
                "rows": snapshot_rows,
            },
        )
        _pi_debug_print(
            "pre_validate_overbilling_snapshot",
            {"doc": doc.name or "New", "rows": snapshot_rows},
        )
    except Exception as e:
        log_purchase_invoice_error(
            doc,
            doc.items[0] if doc.items else None,
            "Pre-Validate Snapshot Failed",
            f"Failed to capture pre-validate overbilling snapshot: {str(e)}",
            {"traceback": frappe.get_traceback()},
        )


def _has_user_edited_pr_row(doc, item, before_doc):
    """Detect explicit user edits on an existing PR-linked PI row."""
    if not item.get("pr_detail"):
        return False

    # For new docs, compare current values against mapped PR defaults.
    # This ensures first-save user edits are not overwritten by sync hooks.
    if not before_doc:
        pr_data = frappe.db.get_value(
            "Purchase Receipt Item",
            item.pr_detail,
            [
                "qty",
                "rate",
                "price_list_rate",
                "purchase_order_item",
                "custom_discount_",
                "custom_discounted_amount",
            ],
            as_dict=True,
        ) or {}

        pr_qty = flt(pr_data.get("qty") or 0)
        po_rate = 0
        if pr_data.get("purchase_order_item"):
            po_rate = flt(
                frappe.db.get_value("Purchase Order Item", pr_data.get("purchase_order_item"), "rate") or 0
            )
        mapped_committed_rate = flt(po_rate or pr_data.get("price_list_rate") or pr_data.get("rate") or 0)
        current_committed_rate = flt(getattr(item, "custom_po_rate", 0) or item.rate or 0)

        mapped_discount_pct = flt(pr_data.get("custom_discount_") or 0)
        current_discount_pct = flt(getattr(item, "custom_discount_percentage", 0) or 0)

        mapped_discount_amt = flt(pr_data.get("custom_discounted_amount") or 0)
        current_discount_amt = flt(getattr(item, "custom_discounted_amount", 0) or 0)

        tolerance = 0.000001
        if abs(flt(item.qty or 0) - pr_qty) > tolerance:
            return True
        if abs(current_committed_rate - mapped_committed_rate) > tolerance:
            return True
        if abs(current_discount_pct - mapped_discount_pct) > tolerance:
            return True
        if abs(current_discount_amt - mapped_discount_amt) > tolerance:
            return True

        if getattr(item, "_discount_manually_edited", False) or getattr(
            item, "_po_rate_manually_edited", False
        ):
            return True
        return False

    if not item.get("name"):
        return False

    prev_row = next((d for d in before_doc.items if d.name == item.name), None)
    if not prev_row:
        return False

    tracked_fields = (
        "qty",
        "custom_po_rate",
        "rate",
        "amount",
        "custom_gross_total",
        "custom_discount_percentage",
        "custom_discounted_amount",
        "custom_net_amount",
    )
    tolerance = 0.000001
    for fieldname in tracked_fields:
        if abs(flt(getattr(item, fieldname, 0) or 0) - flt(getattr(prev_row, fieldname, 0) or 0)) > tolerance:
            return True
    return False


def _sync_pi_row_exact_from_pr(item):
    """Copy PR row values exactly into PI row for deterministic mapping."""
    if not item.get("pr_detail"):
        return False

    pr_data = frappe.db.get_value(
        "Purchase Receipt Item",
        item.pr_detail,
        [
            "qty",
            "rate",
            "amount",
            "price_list_rate",
            "purchase_order_item",
            "custom_gross_rate",
            "custom_discounted_amount",
            "custom_discount_",
            "custom_net_total",
            "discount_percentage",
            "discount_amount",
        ],
        as_dict=True,
    ) or {}

    if not pr_data:
        return False

    pr_qty = flt(pr_data.get("qty") or item.qty or 0)
    pr_rate = flt(pr_data.get("rate") or item.rate or 0)
    po_item_rate = 0
    if pr_data.get("purchase_order_item"):
        po_item_rate = flt(
            frappe.db.get_value("Purchase Order Item", pr_data.get("purchase_order_item"), "rate") or 0
        )
    pr_amount = flt(
        pr_data.get("custom_net_total")
        if pr_data.get("custom_net_total") is not None
        else pr_data.get("amount")
    )
    pr_gross_total = flt(
        pr_data.get("custom_gross_rate")
        if pr_data.get("custom_gross_rate") is not None
        else (pr_qty * pr_rate)
    )
    pr_discount_amt = flt(
        pr_data.get("custom_discounted_amount")
        if pr_data.get("custom_discounted_amount") is not None
        else pr_data.get("discount_amount")
    )
    pr_discount_pct = flt(
        pr_data.get("custom_discount_")
        if pr_data.get("custom_discount_") is not None
        else pr_data.get("discount_percentage")
    )
    committed_rate = flt(po_item_rate or pr_data.get("price_list_rate") or pr_rate)
    pr_visible_rate = committed_rate

    item.qty = pr_qty
    item.rate = pr_rate
    if hasattr(item, "base_rate"):
        item.base_rate = pr_rate

    item.amount = pr_amount
    if hasattr(item, "base_amount"):
        item.base_amount = pr_amount
    if hasattr(item, "net_amount"):
        item.net_amount = pr_amount
    if hasattr(item, "base_net_amount"):
        item.base_net_amount = pr_amount

    item.custom_gross_total = pr_gross_total
    item.custom_discounted_amount = pr_discount_amt
    item.custom_discount_percentage = pr_discount_pct
    item.custom_net_amount = pr_amount

    if hasattr(item, "discount_percentage"):
        item.discount_percentage = pr_discount_pct
    if hasattr(item, "discount_amount"):
        item.discount_amount = pr_discount_amt
    if hasattr(item, "price_list_rate"):
        item.price_list_rate = pr_visible_rate
    if hasattr(item, "custom_po_rate"):
        item.custom_po_rate = committed_rate

    return True


def preserve_po_rate(doc, method):
    for item in doc.items:
        user_override = _is_user_override_on_pr_row(doc, item)

        # For PR-linked rows, keep transactional rate net-safe (PR rate) to avoid
        # ERPNext over-billing checks treating gross PO rate as billable amount.
        if item.get("pr_detail"):
            po_detail = frappe.db.get_value("Purchase Receipt Item", item.pr_detail, "purchase_order_item")
            po_rate = flt(frappe.db.get_value("Purchase Order Item", po_detail, "rate") or 0) if po_detail else 0
            pr_rate = flt(frappe.db.get_value("Purchase Receipt Item", item.pr_detail, "rate") or 0)
            visible_rate = get_source_visible_rate(
                pr_detail=item.get("pr_detail"),
                po_detail=item.get("po_detail"),
                fallback_rate=item.get("price_list_rate") or item.get("rate"),
            )
            if pr_rate:
                item.rate = pr_rate
                if hasattr(item, "base_rate"):
                    item.base_rate = pr_rate
            if hasattr(item, "price_list_rate") and not user_override:
                item.price_list_rate = flt(po_rate or visible_rate or pr_rate)
            if hasattr(item, "custom_po_rate") and not user_override:
                item.custom_po_rate = flt(po_rate or visible_rate or pr_rate)
            continue

        visible_rate = get_source_visible_rate(
            pr_detail=item.get("pr_detail"),
            po_detail=item.get("po_detail"),
            fallback_rate=item.get("price_list_rate") or item.get("rate"),
        )
        if visible_rate:
            item.rate = visible_rate
            if hasattr(item, "base_rate"):
                item.base_rate = visible_rate
            if hasattr(item, "price_list_rate") and not user_override:
                item.price_list_rate = visible_rate
            if hasattr(item, "custom_po_rate") and not user_override:
                item.custom_po_rate = visible_rate

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
            _pi_debug_print(
                "validate_multiple_billing_row_state",
                {
                    "doc": doc.name or "New",
                    "idx": item.idx,
                    "pr_detail": pr_detail,
                    "qty": flt(item.qty or 0),
                    "rate": flt(item.rate or 0),
                    "price_list_rate": flt(getattr(item, "price_list_rate", 0) or 0),
                    "discount_percentage": flt(getattr(item, "discount_percentage", 0) or 0),
                    "discount_amount": flt(getattr(item, "discount_amount", 0) or 0),
                    "amount": current_amount,
                    "qty_x_rate": flt(flt(item.qty or 0) * flt(item.rate or 0)),
                    "already_billed_erpnext": already_billed_erpnext,
                    "pr_amount": pr_amount,
                    "projected_total": total_billed,
                },
            )
            
            # Use actual configured allowance instead of hardcoded value.
            from erpnext.controllers.status_updater import get_allowance_for
            allowance_pct = flt(get_allowance_for(item.item_code, {}, None, None, "amount")[0] or 0)
            max_allowed = flt(pr_amount * (100 + allowance_pct) / 100)
            remaining_allowed = flt(max_allowed - already_billed_erpnext)

            if total_billed > max_allowed:
                # Final guard rail: clamp line amount to what ERPNext allows so
                # validate_multiple_billing won't block user on save/submit.
                safe_amount = max(0, remaining_allowed)
                previous_amount = current_amount
                item.amount = safe_amount
                if hasattr(item, "base_amount"):
                    item.base_amount = safe_amount
                item.custom_net_amount = safe_amount

                log_purchase_invoice_error(
                    doc, item, "DEBUG - Over-Billing Detected",
                    f"Item {item.idx}: ERPNext saw over-billing input and amount was auto-clamped from {previous_amount} to {safe_amount}.",
                    {
                        "pr_detail": pr_detail,
                        "pr_amount": pr_amount,
                        "allowance_pct": allowance_pct,
                        "already_billed_erpnext": already_billed_erpnext,
                        "current_amount_before": previous_amount,
                        "current_amount_after": safe_amount,
                        "total_billed": total_billed,
                        "max_allowed": max_allowed,
                        "remaining_allowed": remaining_allowed,
                        "overbill_amount": total_billed - max_allowed,
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
        before_doc = None if doc.is_new() else doc.get_doc_before_save()
        gross_total = 0
        discounted_total = 0
        net_total = 0

        for i in doc.items:
            if i.get("pr_detail") and not _has_user_edited_pr_row(doc, i, before_doc):
                _sync_pi_row_exact_from_pr(i)
                gross_total += flt(i.custom_gross_total)
                discounted_total += flt(i.custom_discounted_amount)
                net_total += flt(i.amount)
                continue

            original_rate = flt(i.rate)
            original_base_rate = flt(i.base_rate) if hasattr(i, "base_rate") else None
            original_po_rate = flt(getattr(i, "custom_po_rate", 0) or 0)
            editable_rate = flt(getattr(i, "custom_po_rate", 0) or i.rate or 0)

            # Check if this item is linked to Purchase Receipt
            is_from_pr = bool(i.get("pr_detail"))
            rate_edited = False
            
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
            
            # Always calculate gross total from editable PO committed rate.
            # This applies to both PR and non-PR items
            calculated_gross = flt(i.qty) * editable_rate
            i.custom_gross_total = calculated_gross
            
            # For PR-linked items, check if user has manually edited discount
            # If edited, use edited values; otherwise preserve from PR
            discount_edited = False
            if is_from_pr and i.get("pr_detail"):
                pr_custom = frappe.db.get_value(
                    "Purchase Receipt Item",
                    i.pr_detail,
                    ["custom_gross_rate", "custom_discounted_amount", "custom_discount_", "custom_net_total", "price_list_rate", "rate", "purchase_order_item"],
                    as_dict=True,
                ) or {}

                pr_discount_pct = flt(pr_custom.get("custom_discount_")) if pr_custom.get("custom_discount_") is not None else 0
                pr_discount_amt = flt(pr_custom.get("custom_discounted_amount", 0))
                po_detail = pr_custom.get("purchase_order_item")
                pr_visible_rate = get_source_visible_rate(
                    pr_detail=i.pr_detail,
                    po_detail=po_detail,
                    fallback_rate=pr_custom.get("price_list_rate") or pr_custom.get("rate"),
                )
                
                # Check if user has edited discount (compare current values with PR values)
                current_discount_pct = flt(i.custom_discount_percentage) if i.custom_discount_percentage is not None else 0
                current_discount_amt = flt(i.custom_discounted_amount) if i.custom_discounted_amount is not None else 0
                current_rate = flt(getattr(i, "custom_po_rate", 0) or i.rate or 0)
                rate_edited = bool(current_rate and pr_visible_rate and abs(current_rate - pr_visible_rate) > 0.000001)
                
                # If discount values differ from PR, assume user edited them
                if rate_edited or abs(current_discount_pct - pr_discount_pct) > 0.01 or abs(current_discount_amt - pr_discount_amt) > 0.01:
                    discount_edited = True
                
                # If discount was not edited, preserve from PR
                if not discount_edited:
                    if pr_discount_amt:
                        i.custom_discounted_amount = pr_discount_amt
                    else:
                        i.custom_discounted_amount = 0

                    if pr_discount_pct is not None:
                        i.custom_discount_percentage = pr_discount_pct
                    else:
                        i.custom_discount_percentage = 0

            # Calculate discount/net: custom_gross_total - custom_discounted_amount = custom_net_amount
            # For non-PR items or PR items with edited discount, recalculate based on user input
            if not is_from_pr or discount_edited:
                # Recalculate discount based on user input
                if i.custom_discount_percentage is not None:
                    # Recalculate discounted amount from percentage, including explicit 0%.
                    i.custom_discounted_amount = flt((flt(i.custom_discount_percentage) / 100) * flt(i.custom_gross_total))
                elif i.custom_discounted_amount is not None and i.custom_discounted_amount != 0:
                    # Calculate percentage from amount
                    if i.custom_gross_total and i.custom_gross_total != 0:
                        i.custom_discount_percentage = flt((flt(i.custom_discounted_amount) / flt(i.custom_gross_total)) * 100)
                    else:
                        i.custom_discount_percentage = 0
                else:
                    # Both missing, set to 0
                    i.custom_discounted_amount = 0
                    i.custom_discount_percentage = 0

                if flt(i.custom_discounted_amount) > flt(i.custom_gross_total):
                    i.custom_discounted_amount = flt(i.custom_gross_total)

            # Always calculate net amount: custom_gross_total - custom_discounted_amount = custom_net_amount
            i.custom_net_amount = max(0, flt(i.custom_gross_total) - flt(i.custom_discounted_amount or 0))
            
            # CRITICAL: Set amount = custom_net_amount (custom_net_amount = amount)
            # But for PR items, validate against PR constraints to avoid over-billing
            calculated_amount = flt(i.custom_net_amount)
            
            if hasattr(i, '_pr_amount_preserved') and i._pr_amount_preserved:
                # Amount was already set in before_validate
                # If discount was edited, we need to update amount but respect PR constraints
                if discount_edited:
                    remaining_amount = getattr(i, '_remaining_amount', None)
                    
                    if remaining_amount is not None:
                        # Clamp to remaining PR amount to avoid over-billing
                        if calculated_amount > remaining_amount:
                            i.amount = flt(remaining_amount)
                            # Adjust custom_net_amount to match
                            i.custom_net_amount = flt(remaining_amount)
                            log_purchase_invoice_error(
                                doc, i, "Discount Edit Clamped to PR Remaining",
                                f"Item {i.idx}: Edited discount resulted in amount {calculated_amount} exceeding PR remaining {remaining_amount}. Clamped to remaining amount.",
                                {
                                    "pr_detail": i.get("pr_detail"),
                                    "calculated_amount": calculated_amount,
                                    "remaining_amount": remaining_amount,
                                    "final_amount": i.amount
                                }
                            )
                        else:
                            i.amount = calculated_amount
                    else:
                        i.amount = calculated_amount
                else:
                    # Discount not edited - preserve PR amount for over-billing validation
                    # But ensure custom_net_amount reflects the actual calculation
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
                    # For PR items without discount edit, keep amount as set (for over-billing validation)
                    # But update custom_net_amount to match for display consistency
                    i.custom_net_amount = flt(i.amount)
            elif is_from_pr and pr_amount is not None:
                # For items from PR: Check if discount was edited
                if discount_edited:
                    # User edited discount - use calculated net amount but validate against PR
                    remaining_amount = None
                    if hasattr(i, '_remaining_amount'):
                        remaining_amount = i._remaining_amount
                    else:
                        # Calculate remaining amount
                        already_billed = getattr(i, '_already_billed', 0)
                        remaining_amount = flt(pr_amount - already_billed)
                    
                    if remaining_amount is not None and calculated_amount > remaining_amount:
                        i.amount = flt(remaining_amount)
                        i.custom_net_amount = flt(remaining_amount)
                        log_purchase_invoice_error(
                            doc, i, "Discount Edit Clamped to PR Remaining",
                            f"Item {i.idx}: Edited discount resulted in amount {calculated_amount} exceeding PR remaining {remaining_amount}. Clamped to remaining amount.",
                            {
                                "pr_detail": i.get("pr_detail"),
                                "calculated_amount": calculated_amount,
                                "remaining_amount": remaining_amount,
                                "final_amount": i.amount
                            }
                        )
                    else:
                        i.amount = calculated_amount
                else:
                    # Discount not edited - use PR amount for over-billing validation
                    i.amount = pr_amount
                    # Update custom_net_amount to match for consistency
                    i.custom_net_amount = flt(pr_amount)
                    # Log if there's a discrepancy for debugging
                    if abs(flt(i.amount) - calculated_amount) > 0.01:
                        log_purchase_invoice_error(
                            doc, i, "Amount Mismatch with PR",
                            f"Item {i.idx} from PR: PI amount ({i.amount}) differs from calculated net amount ({calculated_amount}). Using PR amount for validation.",
                            {
                                "pr_detail": i.get("pr_detail"),
                                "pr_amount": pr_amount,
                                "calculated_net_amount": calculated_amount,
                                "difference": abs(flt(i.amount) - calculated_amount)
                            }
                        )
            elif is_from_pr and pr_amount is None:
                # PR item but couldn't get PR amount - use calculated amount
                log_purchase_invoice_error(
                    doc, i, "Cannot Get PR Amount",
                    f"Item {i.idx} has pr_detail but couldn't fetch PR amount. Using calculated amount.",
                    {"pr_detail": i.get("pr_detail"), "calculated_net_amount": calculated_amount}
                )
                i.amount = calculated_amount
            else:
                # For new items or items not from PR: custom_net_amount = amount
                i.amount = calculated_amount

            # Keep the user/PR-selected rate stable when only discount fields change.
            i.rate = original_rate
            if original_base_rate is not None and hasattr(i, "base_rate"):
                i.base_rate = original_base_rate
            if hasattr(i, "custom_po_rate"):
                i.custom_po_rate = original_po_rate or editable_rate

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


def finalize_pi_amounts(doc, method):
    before_doc = None if doc.is_new() else doc.get_doc_before_save()
    gross_total = 0
    discount_total = 0
    net_total = 0

    for item in doc.items:
        user_override = _is_user_override_on_pr_row(doc, item)

        if item.get("pr_detail") and not _has_user_edited_pr_row(doc, item, before_doc):
            _sync_pi_row_exact_from_pr(item)
            gross_total += flt(item.custom_gross_total)
            discount_total += flt(item.custom_discounted_amount)
            net_total += flt(item.amount)
            continue

        if item.get("pr_detail") or item.get("po_detail"):
            visible_rate = get_source_visible_rate(
                pr_detail=item.get("pr_detail"),
                po_detail=item.get("po_detail"),
                fallback_rate=item.get("price_list_rate") or item.get("rate"),
            )

            if item.get("pr_detail"):
                po_detail = frappe.db.get_value("Purchase Receipt Item", item.pr_detail, "purchase_order_item")
                po_rate = flt(frappe.db.get_value("Purchase Order Item", po_detail, "rate") or 0) if po_detail else 0
                pr_rate = flt(frappe.db.get_value("Purchase Receipt Item", item.pr_detail, "rate") or 0)
                if pr_rate:
                    item.rate = pr_rate
                    if hasattr(item, "base_rate"):
                        item.base_rate = pr_rate
                if hasattr(item, "price_list_rate") and not user_override:
                    item.price_list_rate = flt(po_rate or visible_rate or pr_rate)
                if hasattr(item, "custom_po_rate") and not user_override:
                    item.custom_po_rate = flt(po_rate or visible_rate or pr_rate)
            elif visible_rate:
                item.rate = visible_rate
                if hasattr(item, "base_rate"):
                    item.base_rate = visible_rate
                if hasattr(item, "price_list_rate") and not user_override:
                    item.price_list_rate = visible_rate
                if hasattr(item, "custom_po_rate") and not user_override:
                    item.custom_po_rate = visible_rate

        editable_rate = flt(getattr(item, "custom_po_rate", 0) or item.rate or 0)
        gross_total_value = flt(item.custom_gross_total) or (flt(item.qty) * editable_rate)
        discount_pct_value = item.custom_discount_percentage

        if discount_pct_value is not None:
            discount_pct_value = flt(discount_pct_value)
            discount_total_value = (discount_pct_value / 100) * gross_total_value
        else:
            discount_total_value = flt(item.custom_discounted_amount)

        discount_total_value = min(max(0, discount_total_value), gross_total_value)
        net_amount_value = max(0, gross_total_value - discount_total_value)

        item.custom_gross_total = gross_total_value
        item.custom_discounted_amount = discount_total_value
        item.custom_net_amount = net_amount_value
        item.amount = net_amount_value

        if hasattr(item, "base_amount"):
            item.base_amount = net_amount_value
        if hasattr(item, "net_amount"):
            item.net_amount = net_amount_value
        if hasattr(item, "base_net_amount"):
            item.base_net_amount = net_amount_value

        gross_total += gross_total_value
        discount_total += discount_total_value
        net_total += net_amount_value

    doc.custom_gross_rate = gross_total
    doc.custom_discounted_amount = discount_total
    doc.custom_discounted_percentage = (discount_total / gross_total) * 100 if gross_total else 0
    doc.custom_net_rate = net_total

    # Include taxes in grand_total so GL entries balance (debit = credit).
    # ERPNext make_supplier_gl_entry uses grand_total/rounded_total for the supplier credit;
    # make_tax_gl_entries posts tax debits from doc.taxes. If we set grand_total = net_total
    # only, supplier credit would be short by tax amount → "Debit and Credit not equal".
    total_taxes = flt(doc.total_taxes_and_charges or 0)
    base_total_taxes = flt(doc.base_total_taxes_and_charges or 0)

    if hasattr(doc, "total"):
        doc.total = net_total
    if hasattr(doc, "net_total"):
        doc.net_total = net_total
    if hasattr(doc, "base_total"):
        doc.base_total = net_total
    if hasattr(doc, "base_net_total"):
        doc.base_net_total = net_total

    grand_total_val = flt(net_total) + total_taxes
    base_grand_total_val = flt(getattr(doc, "base_net_total", net_total) or net_total) + base_total_taxes

    if hasattr(doc, "grand_total"):
        doc.grand_total = grand_total_val
    if hasattr(doc, "base_grand_total"):
        doc.base_grand_total = base_grand_total_val
    if hasattr(doc, "rounded_total"):
        doc.rounded_total = grand_total_val
    if hasattr(doc, "base_rounded_total"):
        doc.base_rounded_total = base_grand_total_val
    if hasattr(doc, "outstanding_amount"):
        doc.outstanding_amount = grand_total_val

@frappe.whitelist()
def make_purchase_invoice_custom(source_name, target_doc=None):
    def postprocess(source_doc, target_doc):
        target_doc.ignore_pricing_rule = 1
        target_doc.run_method("set_missing_values")
        # Run ERPNext totals first because it may recompute amount from qty * rate.
        target_doc.run_method("calculate_taxes_and_totals")
        # Re-apply custom line logic last so amount stays equal to net amount.
        calculation_pi(target_doc, "validate")

    def set_missing_discount_fields(source_item, target_item, source_parent):
        """ 
        Map custom fields from Purchase Receipt Item to Purchase Invoice Item
        Purchase Receipt uses: custom_gross_rate, custom_discount_, custom_net_total
        Purchase Invoice uses: custom_gross_total, custom_discount_percentage, custom_net_amount
        """
        # Map from PR fields to PI fields
        source_visible_rate = get_source_visible_rate(
            pr_detail=getattr(source_item, "name", None),
            po_detail=getattr(source_item, "purchase_order_item", None),
            fallback_rate=getattr(source_item, "price_list_rate", 0) or getattr(source_item, "rate", 0),
        )
        source_po_rate = flt(
            frappe.db.get_value("Purchase Order Item", getattr(source_item, "purchase_order_item", None), "rate")
            or 0
        )

        if source_visible_rate:
            target_item.rate = source_visible_rate
            if hasattr(target_item, "base_rate"):
                target_item.base_rate = source_visible_rate

        if hasattr(target_item, "price_list_rate") and source_visible_rate:
            target_item.price_list_rate = source_visible_rate
        if hasattr(target_item, "custom_po_rate"):
            target_item.custom_po_rate = flt(source_po_rate or source_visible_rate or target_item.rate or 0)

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
            gross_rate = flt(getattr(target_item, "custom_po_rate", 0) or target_item.rate or 0)
            target_item.custom_gross_total = target_item.qty * gross_rate
        
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

        _pi_debug_print(
            "map_pr_to_pi_item",
            {
                "pr_name": source_parent.name if source_parent else None,
                "pr_item": getattr(source_item, "name", None),
                "pi_row_idx": getattr(target_item, "idx", None),
                "qty": flt(getattr(target_item, "qty", 0)),
                "rate": flt(getattr(target_item, "rate", 0)),
                "price_list_rate": flt(getattr(target_item, "price_list_rate", 0) or 0),
                "amount": flt(getattr(target_item, "amount", 0)),
                "custom_gross_total": flt(getattr(target_item, "custom_gross_total", 0)),
                "custom_discounted_amount": flt(getattr(target_item, "custom_discounted_amount", 0)),
                "custom_discount_percentage": flt(getattr(target_item, "custom_discount_percentage", 0)),
                "custom_net_amount": flt(getattr(target_item, "custom_net_amount", 0)),
            },
        )

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
