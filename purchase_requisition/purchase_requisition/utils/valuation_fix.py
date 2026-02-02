import time

import frappe
from frappe.utils import flt, getdate
from frappe.model.naming import make_autoname
from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
    EmptyStockReconciliationItemsError,
)

POSTING_DATE = getdate("2026-01-01")
MAX_ROWS_PER_DOC = 100
LOCK_RETRY_COUNT = 3
LOCK_RETRY_SLEEP_SEC = 5

# If your PO Item custom field is different name, change here:
PO_NET_TOTAL_FIELD = "custom_net_total"


def get_last_po_rate_map():
    """
    Returns {item_code: rate} based on LAST Purchase Order Item before POSTING_DATE.
    rate = poi.custom_net_total / poi.qty

    Uses window function ROW_NUMBER (MariaDB 10.2+). If your DB doesn't support it,
    tell me and I'll give you the fallback query.
    """
    rows = frappe.db.sql(
        f"""
        SELECT item_code, rate
        FROM (
            SELECT
                poi.item_code,
                (poi.{PO_NET_TOTAL_FIELD} / NULLIF(poi.qty, 0)) AS rate,
                ROW_NUMBER() OVER (
                    PARTITION BY poi.item_code
                    ORDER BY po.transaction_date DESC, po.creation DESC, poi.idx DESC
                ) AS rn
            FROM `tabPurchase Order` po
            JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
            WHERE po.docstatus = 1
              AND po.transaction_date < %(cutoff)s
              AND IFNULL(poi.{PO_NET_TOTAL_FIELD}, 0) > 0
              AND IFNULL(poi.qty, 0) > 0
        ) x
        WHERE x.rn = 1
        """,
        {"cutoff": POSTING_DATE},
        as_dict=True,
    )

    return {r.item_code: flt(r.rate, 6) for r in rows if r.rate is not None}


def get_batch_stock():
    """
    Returns batch stock qty as-of POSTING_DATE (excluding expired batches).
    We no longer use SUM(stock_value_difference) for "current_rate" because it's unreliable.
    """
    return frappe.db.sql(
        """
        SELECT
            sle.item_code,
            sle.warehouse,
            sle.batch_no,
            b.item AS batch_item,
            b.expiry_date AS batch_expiry_date,
            SUM(sle.actual_qty) AS qty
        FROM `tabStock Ledger Entry` sle
        JOIN `tabBatch` b ON b.name = sle.batch_no
        WHERE sle.is_cancelled = 0
          AND sle.batch_no IS NOT NULL
          AND sle.batch_no != ''
          AND sle.posting_date < %s
          AND (b.expiry_date IS NULL OR b.expiry_date > %s)
        GROUP BY sle.item_code, sle.warehouse, sle.batch_no
        HAVING SUM(sle.actual_qty) > 0
        """,
        (POSTING_DATE, POSTING_DATE),
        as_dict=True,
    )


def get_last_sle_rate(item_code, warehouse, batch_no):
    """
    Get last known valuation_rate for this exact item+warehouse+batch before POSTING_DATE.
    Much safer than SUM(stock_value_difference)/SUM(qty).
    """
    row = frappe.db.sql(
        """
        SELECT sle.valuation_rate
        FROM `tabStock Ledger Entry` sle
        WHERE sle.is_cancelled = 0
          AND sle.item_code = %(item_code)s
          AND sle.warehouse = %(warehouse)s
          AND sle.batch_no = %(batch_no)s
          AND sle.posting_date < %(cutoff)s
        ORDER BY sle.posting_date DESC, sle.posting_time DESC, sle.creation DESC
        LIMIT 1
        """,
        {"item_code": item_code, "warehouse": warehouse, "batch_no": batch_no, "cutoff": POSTING_DATE},
        as_dict=True,
    )
    return flt(row[0].valuation_rate) if row else 0.0


def run_fix(dry_run=False):
    po_rates = get_last_po_rate_map()
    stock_rows = get_batch_stock()

    warehouse_map = {}
    stats = {
        "total_rows": 0,
        "queued": 0,
        "skipped_no_po_rate": 0,
        "skipped_item_not_batch": 0,
        "skipped_item_disabled": 0,
        "skipped_batch_item_mismatch": 0,
        "skipped_expired": 0,
        "skipped_no_change": 0,
        "skipped_zero_qty": 0,
    }

    for row in stock_rows:
        stats["total_rows"] += 1

        item = row.item_code
        warehouse = row.warehouse
        batch = row.batch_no

        qty = flt(row.qty)
        if qty <= 0:
            stats["skipped_zero_qty"] += 1
            continue

        if item not in po_rates:
            stats["skipped_no_po_rate"] += 1
            continue

        item_doc = frappe.get_cached_doc("Item", item)
        if item_doc.disabled:
            stats["skipped_item_disabled"] += 1
            continue
        if not item_doc.has_batch_no:
            stats["skipped_item_not_batch"] += 1
            continue

        # batch-item mismatch safety
        if row.batch_item != item:
            stats["skipped_batch_item_mismatch"] += 1
            continue

        # hard expiry check (ERPNext-safe)
        if row.batch_expiry_date and getdate(row.batch_expiry_date) <= POSTING_DATE:
            stats["skipped_expired"] += 1
            continue

        current_rate = get_last_sle_rate(item, warehouse, batch)
        new_rate = flt(po_rates[item])

        # if no current rate found, we still want to set new rate (opening)
        if current_rate and abs(current_rate - new_rate) < 0.0001:
            stats["skipped_no_change"] += 1
            continue

        # IMPORTANT: also set amount to lock stock value
        line = {
            "item_code": item,
            "warehouse": warehouse,
            "batch_no": batch,
            "qty": qty,
            "valuation_rate": new_rate,
            "amount": flt(qty) * flt(new_rate),
        }

        warehouse_map.setdefault(warehouse, []).append(line)
        stats["queued"] += 1

    if dry_run:
        return {
            "per_warehouse_counts": {wh: len(items) for wh, items in warehouse_map.items()},
            "stats": stats,
        }

    total_items = sum(len(items) for items in warehouse_map.values())
    processed_items = 0
    start_ts = time.monotonic()

    for warehouse, items in warehouse_map.items():
        for i in range(0, len(items), MAX_ROWS_PER_DOC):
            chunk = items[i:i + MAX_ROWS_PER_DOC]

            # extra expiry re-check (DB truth)
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
                "items": chunk,
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

                except EmptyStockReconciliationItemsError:
                    # All items were removed because they have no change
                    frappe.db.rollback()
                    stats["skipped_no_change"] += len(chunk)
                    # Skip this document and continue
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

    return {"done": True, "stats": stats}
