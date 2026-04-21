import json
import socket
import uuid
from contextlib import closing
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.core.config import LABEL_PRINTER_HOST, LABEL_PRINTER_PORT, LABEL_SIZE_MM
from app.core.db import get_conn
from app.modules.orders.service import build_order_response
from app.modules.settings.service import get_effective_settings


class LabelLine(BaseModel):
    text: str = Field(min_length=1, max_length=120)


class LabelPayload(BaseModel):
    order_id: str
    order_number: str
    service_mode: str
    created_at: str
    target_prep_seconds: int
    items: list[dict[str, Any]]
    lines: list[LabelLine]


class PrinterAdapter:
    def send(self, rendered_label: str, host: str, port: int) -> None:
        raise NotImplementedError


class RawTcpPrinterAdapter(PrinterAdapter):
    def send(self, rendered_label: str, host: str, port: int) -> None:
        data = rendered_label.encode("utf-8", errors="replace")
        with socket.create_connection((host, port), timeout=4.0) as sock:
            sock.sendall(data)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def format_service_mode(service_mode: str) -> str:
    return "TAKEAWAY" if service_mode == "takeaway" else "DINE IN"


def build_label_payload(order: dict) -> LabelPayload:
    lines: list[LabelLine] = [
        LabelLine(text="=" * 24),
        LabelLine(text=f"JOJO'S 58x40 LABEL"),
        LabelLine(text=f"ORDER #{order['number']}"),
        LabelLine(text=f"MODE: {format_service_mode(order.get('service_mode') or 'dine_in')}"),
        LabelLine(text=f"CREATED: {order['created_at'][:19].replace('T', ' ')}"),
        LabelLine(text=f"TARGET: {int(order.get('target_prep_seconds') or 0) // 60} min"),
        LabelLine(text="-" * 24),
    ]

    for item in order.get("items", []):
        lines.append(LabelLine(text=f"{item.get('qty', 1)}x {item.get('display_name') or item.get('name') or 'Item'}"))
        for mod in item.get("modifier_lines", []):
            lines.append(LabelLine(text=f"  {mod}"[:42]))

    lines.extend([LabelLine(text="-" * 24), LabelLine(text="KITCHEN COPY"), LabelLine(text="\n\n")])

    return LabelPayload(
        order_id=order["id"],
        order_number=order["number"],
        service_mode=order.get("service_mode") or "dine_in",
        created_at=order["created_at"],
        target_prep_seconds=int(order.get("target_prep_seconds") or 0),
        items=order.get("items", []),
        lines=lines,
    )


def render_label_58x40(payload: LabelPayload) -> str:
    # Generic plain-text rendering over raw TCP (9100).
    # Adapter boundary allows swapping to ZPL/TSPL/EPL without business-logic changes.
    content = "\n".join(line.text for line in payload.lines)
    width_mm, height_mm = LABEL_SIZE_MM
    header = f"#SIZE:{width_mm}x{height_mm}mm\n"
    return f"{header}{content}\n"


def _resolve_printer_endpoint() -> tuple[str, int]:
    settings = get_effective_settings()
    printer = settings.get("printer") if isinstance(settings.get("printer"), dict) else {}

    host = str(printer.get("label_host") or LABEL_PRINTER_HOST).strip()
    port = int(printer.get("label_port") or LABEL_PRINTER_PORT)
    return host, port


def _insert_job(order_id: str, payload: LabelPayload, rendered_label: str, printer_host: str, printer_port: int) -> str:
    job_id = str(uuid.uuid4())
    now = utc_now_iso()

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
                "kitchen_label_58x40",
                printer_host,
                printer_port,
                "queued",
                0,
                payload.model_dump_json(ensure_ascii=False),
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
    order = build_order_response(order_id)
    payload = build_label_payload(order)
    rendered = render_label_58x40(payload)
    host, port = _resolve_printer_endpoint()

    job_id = _insert_job(order_id, payload, rendered, host, port)

    active_adapter = adapter or RawTcpPrinterAdapter()
    attempts = 1
    try:
        active_adapter.send(rendered, host=host, port=port)
        _update_job(job_id, status="sent", attempts=attempts)
        return {"job_id": job_id, "status": "sent", "printer": {"host": host, "port": port}}
    except Exception as exc:
        _update_job(job_id, status="failed", attempts=attempts, error=str(exc))
        return {"job_id": job_id, "status": "failed", "printer": {"host": host, "port": port}, "error": str(exc)}


def list_print_jobs_for_order(order_id: str) -> list[dict]:
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, order_id, job_type, printer_host, printer_port, status,
                   attempts, created_at, sent_at, last_error
            FROM print_jobs
            WHERE order_id = ?
            ORDER BY created_at DESC
            """,
            (order_id,),
        )
        rows = cur.fetchall()

    return [
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
        }
        for row in rows
    ]


def require_order_exists(order_id: str):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
