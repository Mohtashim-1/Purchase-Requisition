import time

import frappe
from frappe.utils import flt, getdate
from frappe.model.naming import make_autoname

POSTING_DATE = getdate("2026-01-01")
MAX_ROWS_PER_DOC = 100
LOCK_RETRY_COUNT = 3
LOCK_RETRY_SLEEP_SEC = 5


def get_po_valuation_map():
    data = frappe.db.sql("""
        SELECT
            poi.item_code,
            ROUND(
                SUM(
                    CASE
                        WHEN IFNULL(poi.discount_amount,0) > 0
                            THEN (poi.amount - poi.discount_amount)
                        WHEN IFNULL(poi.discount_percentage,0) > 0
                            THEN poi.amount * (1 - poi.discount_percentage / 100)
                        ELSE poi.amount
                    END
                ) / NULLIF(SUM(poi.qty),0),
                6
            ) AS rate
        FROM `tabPurchase Order` po
        JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
        WHERE po.docstatus = 1
          AND po.transaction_date < %s
        GROUP BY poi.item_code
    """, POSTING_DATE, as_dict=True)

    return {d.item_code: flt(d.rate) for d in data}


def get_batch_stock():
    return frappe.db.sql("""
        SELECT
            sle.item_code,
            sle.warehouse,
            sle.batch_no,
            b.item AS batch_item,
            b.expiry_date AS batch_expiry_date,
            SUM(sle.actual_qty) AS qty,
            SUM(sle.stock_value_difference) AS value
        FROM `tabStock Ledger Entry` sle
        JOIN `tabBatch` b ON b.name = sle.batch_no
        WHERE sle.is_cancelled = 0
          AND sle.batch_no IS NOT NULL
          AND sle.batch_no != ''
          AND sle.posting_date < %s
          AND (b.expiry_date IS NULL OR b.expiry_date > %s)
        GROUP BY sle.item_code, sle.warehouse, sle.batch_no
        HAVING SUM(sle.actual_qty) > 0
    """, (POSTING_DATE, POSTING_DATE), as_dict=True)


def run_fix(dry_run=False):
    po_rates = get_po_valuation_map()
    stock_rows = get_batch_stock()

    warehouse_map = {}

    for row in stock_rows:
        item = row.item_code
        warehouse = row.warehouse
        batch = row.batch_no

        if item not in po_rates:
            continue

        item_doc = frappe.get_cached_doc("Item", item)
        if not item_doc.has_batch_no or item_doc.disabled:
            continue

        # batch-item mismatch
        if row.batch_item != item:
            continue

        # hard expiry check (ERPNext-safe)
        if row.batch_expiry_date:
            if getdate(row.batch_expiry_date) <= POSTING_DATE:
                continue


        current_rate = flt(row.value) / flt(row.qty)
        new_rate = po_rates[item]

        if abs(current_rate - new_rate) < 0.0001:
            continue

        warehouse_map.setdefault(warehouse, []).append({
            "item_code": item,
            "warehouse": warehouse,
            "batch_no": batch,
            "qty": flt(row.qty),
            "valuation_rate": new_rate
        })

    if dry_run:
        return {
            wh: len(items) for wh, items in warehouse_map.items()
        }

    total_items = sum(len(items) for items in warehouse_map.values())
    processed_items = 0
    start_ts = time.monotonic()

    for warehouse, items in warehouse_map.items():
        for i in range(0, len(items), MAX_ROWS_PER_DOC):
            chunk = items[i:i + MAX_ROWS_PER_DOC]
            batch_nos = [d["batch_no"] for d in chunk if d.get("batch_no")]
            if batch_nos:
                expired = frappe.db.sql(
                    """
                    SELECT name
                    FROM `tabBatch`
                    WHERE name IN %(batch_nos)s
                      AND expiry_date IS NOT NULL
                      AND expiry_date <= %(posting_date)s
                    """,
                    {"batch_nos": tuple(batch_nos), "posting_date": POSTING_DATE},
                    as_dict=True,
                )
                if expired:
                    expired_set = {d.name for d in expired}
                    chunk = [d for d in chunk if d.get("batch_no") not in expired_set]

            if not chunk:
                continue

            doc = frappe.get_doc({
                "doctype": "Stock Reconciliation",
                "naming_series": "MAT-RECO-.YYYY.-",
                "posting_date": POSTING_DATE,
                "posting_time": "00:00:01",
                "set_posting_time": 1,
                "purpose": "Stock Reconciliation",
                "items": chunk
            })

            for attempt in range(1, LOCK_RETRY_COUNT + 1):
                try:
                    doc.name = make_autoname(doc.naming_series)
                    doc.set_parent_in_children()
                    doc.insert(ignore_permissions=True)
                    doc.flags.ignore_validate_update_after_submit = True
                    doc.submit()
                    frappe.db.commit()
                    processed_items += len(chunk)
                    elapsed = max(time.monotonic() - start_ts, 0.001)
                    rate = processed_items / elapsed
                    remaining = max(total_items - processed_items, 0)
                    eta_sec = remaining / rate if rate else 0
                    print(
                        f"Processed {processed_items}/{total_items} items "
                        f"({rate:.2f} items/sec), ETA {int(eta_sec)}s"
                    )
                    break
                except frappe.DuplicateEntryError:
                    frappe.db.rollback()
                    if attempt == LOCK_RETRY_COUNT:
                        raise
                except frappe.QueryTimeoutError:
                    frappe.db.rollback()
                    if attempt == LOCK_RETRY_COUNT:
                        raise
                    time.sleep(LOCK_RETRY_SLEEP_SEC)
