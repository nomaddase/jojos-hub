import json
import uuid
from contextlib import closing
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from app.core.config import LABEL_PRINTER_HOST, LABEL_PRINTER_PORT
from app.core.db import get_conn
from app.modules.orders.service import build_order_response
from app.modules.printing.label_template_58x40 import (
    expand_order_to_unit_labels,
    render_kitchen_label_58x40_text,
    render_unit_label_58x40_escpos,
    render_unit_label_58x40_text,
)
from app.modules.printing.printer_adapters import PrinterAdapter, RawTcpEscPosAdapter


class LabelPayload(BaseModel):
    order_id: str
    order_number: str
    service_mode: str
    created_at: str
    target_prep_seconds: int
    items: list[dict[str, Any]]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_label_payload(order: dict) -> LabelPayload:
    return LabelPayload(
        order_id=order["id"],
        order_number=order["number"],
        service_mode=order.get("service_mode") or "dine_in",
        created_at=order["created_at"],
        target_prep_seconds=int(order.get("target_prep_seconds") or 0),
        items=order.get("items", []),
    )


def render_label_58x40(payload: LabelPayload) -> str:
    return render_kitchen_label_58x40_text(payload.model_dump())


def _resolve_printer_endpoint() -> tuple[str, int]:
    return LABEL_PRINTER_HOST, LABEL_PRINTER_PORT


def _insert_job(
    order_id: str,
    payload: LabelPayload,
    unit: dict[str, Any],
    rendered_label: str,
    printer_host: str,
    printer_port: int,
) -> str:
    job_id = str(uuid.uuid4())
    now = utc_now_iso()
    stored_payload = payload.model_dump()
    stored_payload["unit_label"] = unit

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO print_jobs (
                id, order_id, job_type, printer_host, printer_port, status,
                attempts, payload_json, rendered_label, created_at, sent_at, last_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                order_id,
                "xp365_escpos_label_58x40",
                printer_host,
                printer_port,
                "queued",
                0,
                json.dumps(stored_payload, ensure_ascii=False),
                rendered_label,
                now,
                None,
                None,
            ),
        )
        conn.commit()

    return job_id


def _update_job(job_id: str, status: str, attempts: int, error: str | None = None):
    sent_at = utc_now_iso() if status == "sent" else None
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE print_jobs SET status = ?, attempts = ?, sent_at = COALESCE(?, sent_at), last_error = ? WHERE id = ?",
            (status, attempts, sent_at, error, job_id),
        )
        conn.commit()


def create_kitchen_label_job(order_id: str, adapter: PrinterAdapter | None = None) -> dict:
    """
    Print one physical 58x40 label per ordered unit.

    Example: an order containing 10 drinks with qty=10 produces 10 labels. Every
    label carries the same large order marker plus its 1/10 ... 10/10 sequence.
    Printing failures do not roll back the already-created order; each failed
    physical label remains visible as its own print_jobs row for diagnostics.
    """
    order = build_order_response(order_id)
    payload = build_label_payload(order)
    payload_dict = payload.model_dump()
    units = expand_order_to_unit_labels(payload_dict)
    host, port = _resolve_printer_endpoint()
    active_adapter = adapter or RawTcpEscPosAdapter()

    results: list[dict[str, Any]] = []
    for unit in units:
        preview = render_unit_label_58x40_text(payload_dict, unit)
        escpos = render_unit_label_58x40_escpos(payload_dict, unit)
        job_id = _insert_job(order_id, payload, unit, preview, host, port)
        attempts = 1
        try:
            active_adapter.send(escpos, host=host, port=port)
            _update_job(job_id, status="sent", attempts=attempts)
            results.append(
                {
                    "job_id": job_id,
                    "status": "sent",
                    "label_no": unit["label_no"],
                    "label_count": unit["label_count"],
                    "item_name": unit["name"],
                }
            )
        except Exception as exc:
            error = str(exc)
            _update_job(job_id, status="failed", attempts=attempts, error=error)
            results.append(
                {
                    "job_id": job_id,
                    "status": "failed",
                    "label_no": unit["label_no"],
                    "label_count": unit["label_count"],
                    "item_name": unit["name"],
                    "error": error,
                }
            )

    sent = sum(1 for row in results if row["status"] == "sent")
    failed = len(results) - sent
    return {
        "status": "sent" if results and failed == 0 else ("failed" if sent == 0 else "partial"),
        "printer": {"host": host, "port": port, "model": "XPrinter XP-365", "protocol": "ESC/POS"},
        "label_size_mm": {"width": 58, "height": 40},
        "labels_total": len(results),
        "labels_sent": sent,
        "labels_failed": failed,
        "jobs": results,
    }


def list_print_jobs_for_order(order_id: str) -> list[dict]:
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, order_id, job_type, printer_host, printer_port, status,
                   attempts, created_at, sent_at, last_error, payload_json, rendered_label
            FROM print_jobs
            WHERE order_id = ?
            ORDER BY created_at DESC
            """,
            (order_id,),
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except Exception:
            payload = {}
        unit = payload.get("unit_label") or {}
        result.append(
            {
                "id": row["id"],
                "order_id": row["order_id"],
                "job_type": row["job_type"],
                "printer_host": row["printer_host"],
                "printer_port": row["printer_port"],
                "status": row["status"],
                "attempts": row["attempts"],
                "created_at": row["created_at"],
                "sent_at": row["sent_at"],
                "last_error": row["last_error"],
                "label_no": unit.get("label_no"),
                "label_count": unit.get("label_count"),
                "item_name": unit.get("name"),
                "preview": row["rendered_label"],
            }
        )
    return result


def require_order_exists(order_id: str):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
