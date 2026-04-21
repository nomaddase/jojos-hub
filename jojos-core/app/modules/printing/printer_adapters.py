import socket


class PrinterAdapter:
    def send(self, rendered_label: str, host: str, port: int) -> None:
        raise NotImplementedError


class RawTcpTextAdapter(PrinterAdapter):
    """
    Production adapter for current 58x40 label printer using raw TCP text on port 9100.
    Keep all protocol/model assumptions centralized in this adapter.
    """

    def send(self, rendered_label: str, host: str, port: int) -> None:
        data = rendered_label.encode("utf-8", errors="replace")
        with socket.create_connection((host, port), timeout=4.0) as sock:
            sock.sendall(data)
