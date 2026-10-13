# Talentum — backend/app/services/antivirus.py
# Responsabilidade: Concentra regras de negócio e integrações reutilizáveis, mantendo as rotas mais simples.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import socket
import struct
from pathlib import Path

from app.core.config import get_settings


class AntivirusUnavailable(RuntimeError):
    """Sinaliza que a verificação obrigatória não pôde ser realizada."""

    pass


class MalwareDetected(RuntimeError):
    """Sinaliza que o serviço antivírus rejeitou o arquivo analisado."""

    pass


def scan_file(path: Path) -> None:
    """Envia o arquivo ao ClamAV e aplica a política configurada de falhas."""
    settings = get_settings()
    if not settings.clamav_host:
        if settings.clamav_required:
            raise AntivirusUnavailable("O serviço antivírus obrigatório não está configurado")
        return
    try:
        # O ClamAV INSTREAM recebe blocos com prefixo de tamanho e termina com um bloco vazio.
        with socket.create_connection((settings.clamav_host, settings.clamav_port), timeout=10) as client:
            client.sendall(b"zINSTREAM\0")
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    client.sendall(struct.pack(">I", len(chunk)))
                    client.sendall(chunk)
            client.sendall(struct.pack(">I", 0))
            # O modo z termina a resposta em NUL; recv único e strip não normalizam esse terminador (achado 145).
            response = client.recv(4096).decode("utf-8", errors="replace").strip()
    except (OSError, struct.error) as exc:
        # Em modo obrigatório, indisponibilidade impede o upload; no modo opcional, segue sem varredura.
        if settings.clamav_required:
            raise AntivirusUnavailable("O serviço antivírus não está disponível") from exc
        return
    # Só aceita uma confirmação explícita OK; malware ou resposta inesperada bloqueia o envio.
    if "FOUND" in response or not response.endswith("OK"):
        raise MalwareDetected("O arquivo foi rejeitado pela verificação antivírus")
