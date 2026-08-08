import socket


class PrinterAdapter:
    def send(self, rendered_label: bytes | str, host: str, port: int) -> None:
        raise NotImplementedError


class RawTcpEscPosAdapter(PrinterAdapter):
    """ESC/POS over RAW TCP (XPrinter XP-365 Wi-Fi, default port 9100)."""

    def send(self, rendered_label: bytes | str, host: str, port: int) -> None:
        data = rendered_label if isinstance(rendered_label, bytes) else rendered_label.encode("cp866", errors="replace")
        with socket.create_connection((host, port), timeout=4.0) as sock:
            sock.settimeout(4.0)
            sock.sendall(data)


# Compatibility alias for older imports.
RawTcpTextAdapter = RawTcpEscPosAdapter
