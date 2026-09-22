import socket
import struct
from pathlib import Path

from app.core.config import get_settings


class AntivirusUnavailable(RuntimeError):
    pass


class MalwareDetected(RuntimeError):
    pass


def scan_file(path: Path) -> None:
    settings = get_settings()
    if not settings.clamav_host:
        return
    try:
        with socket.create_connection((settings.clamav_host, settings.clamav_port), timeout=10) as client:
            client.sendall(b"zINSTREAM\0")
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    client.sendall(struct.pack(">I", len(chunk)))
                    client.sendall(chunk)
            client.sendall(struct.pack(">I", 0))
            response = client.recv(4096).decode("utf-8", errors="replace").strip()
    except (OSError, struct.error) as exc:
        if settings.clamav_required:
            raise AntivirusUnavailable("O serviço antivírus não está disponível") from exc
        return
    if "FOUND" in response or not response.endswith("OK"):
        raise MalwareDetected("O arquivo foi rejeitado pela verificação antivírus")
