from pathlib import Path
import re
import unicodedata
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.database import get_db
from app.models import AuditLog, Document, User
from app.schemas.document import DocumentResponse
from app.services.authorization import require_client_manager, require_roles
from app.services.antivirus import AntivirusUnavailable, MalwareDetected, scan_file
from app.services.notifications import create_client_notification


router = APIRouter(prefix="/clients", tags=["documents"])
settings = get_settings()
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "text/plain",
}
FILE_SIGNATURES = {
    "application/pdf": b"%PDF",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}
ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".txt": "text/plain",
}
DOCUMENT_KINDS = {"income_proof", "address_proof", "other"}


def find_client(client_id: int, db: Session) -> User:
    client = db.scalar(select(User).where(User.id == client_id, User.role == "client"))
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


def find_document(client_id: int, document_id: int, db: Session) -> Document:
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.client_id == client_id)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return document


def storage_path(stored_name: str) -> Path:
    root = Path(settings.storage_dir).resolve()
    path = (root / stored_name).resolve()
    if path.parent != root:
        raise HTTPException(status_code=500, detail="Armazenamento de documentos inválido")
    return path


def safe_original_name(filename: str) -> str:
    name = Path(filename).name.replace("\r", "_").replace("\n", "_")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^A-Za-z0-9._ ()-]", "_", name).strip(" .")
    return (name or "documento")[:255]


@router.get("/{client_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    return list(
        db.scalars(
            select(Document)
            .where(Document.client_id == client_id)
            .order_by(Document.created_at.desc(), Document.id.desc())
        ).all()
    )


@router.post("/{client_id}/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    client_id: int,
    file: UploadFile = File(...),
    description: str | None = Form(default=None, max_length=500),
    kind: str = Form(default="other"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    find_client(client_id, db)
    if current_user.role not in {"admin", "advisor"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente o Advisor ou o administrador podem enviar documentos",
        )
    require_client_manager(client_id, current_user, db)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Selecione um arquivo")
    if kind not in DOCUMENT_KINDS:
        raise HTTPException(status_code=422, detail="Categoria de documento inválida")
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Tipo de arquivo não permitido. Use PDF, PNG, JPG ou TXT",
        )

    original_name = safe_original_name(file.filename)
    extension = Path(original_name).suffix.lower()
    expected_content_type = ALLOWED_EXTENSIONS.get(extension)
    if expected_content_type is None or expected_content_type != content_type:
        raise HTTPException(status_code=415, detail="A extensão do arquivo não corresponde ao tipo informado")
    stored_name = f"{uuid4().hex}{extension}"
    path = storage_path(stored_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    size_bytes = 0
    first_chunk = True
    try:
        with path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                if first_chunk and content_type in FILE_SIGNATURES and not chunk.startswith(FILE_SIGNATURES[content_type]):
                    raise HTTPException(status_code=415, detail="O conteúdo do arquivo não corresponde ao tipo informado")
                if first_chunk and content_type == "text/plain":
                    try:
                        chunk.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise HTTPException(status_code=415, detail="O arquivo de texto não está em UTF-8") from exc
                first_chunk = False
                size_bytes += len(chunk)
                if size_bytes > MAX_DOCUMENT_BYTES:
                    raise HTTPException(status_code=413, detail="O arquivo excede o limite de 10 MB")
                output.write(chunk)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    try:
        scan_file(path)
    except MalwareDetected as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AntivirusUnavailable as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    document = Document(
        client_id=client_id,
        uploaded_by_user_id=current_user.id,
        original_name=original_name,
        stored_name=stored_name,
        content_type=content_type,
        kind=kind,
        size_bytes=size_bytes,
        description=description.strip() if description and description.strip() else None,
    )
    try:
        db.add(document)
        db.flush()
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                client_user_id=client_id,
                action="create",
                resource="document",
                resource_id=str(document.id),
                details={"original_name": original_name, "size_bytes": size_bytes},
            )
        )
        create_client_notification(
            db,
            client_id=client_id,
            kind="document_uploaded",
            title="Novo documento",
            message=f'O documento "{original_name}" foi adicionado.',
            dedupe_key=f"document-uploaded:{document.id}",
        )
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return document


@router.get("/{client_id}/documents/{document_id}/download")
def download_document(
    client_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    document = find_document(client_id, document_id, db)
    path = storage_path(document.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo do documento não encontrado")
    return FileResponse(path, media_type=document.content_type, filename=document.original_name)


@router.delete("/{client_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    client_id: int,
    document_id: int,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> None:
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    document = find_document(client_id, document_id, db)
    path = storage_path(document.stored_name)
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="delete",
            resource="document",
            resource_id=str(document.id),
            details={"original_name": document.original_name},
        )
    )
    db.delete(document)
    db.commit()
    path.unlink(missing_ok=True)
