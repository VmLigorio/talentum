"""PostgreSQL-backed HTTP tests for the core client authorization flows."""

from contextlib import asynccontextmanager
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, or_, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_db
from app.core.security import hash_password
from app.db.database import Base
from app.main import app
from app.models import ClientPermission, ClientProfile, Document, FinancialProfile, User


PASSWORD = "Phase9-Test-Only-Password!"


@pytest.fixture(scope="session")
def phase9_session_factory():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Configure TEST_DATABASE_URL apontando para um PostgreSQL exclusivo de testes")

    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL precisa usar PostgreSQL; os modelos incluem tipos específicos do PostgreSQL")
    if not parsed_url.database or not parsed_url.database.endswith(("_test", "_testing")):
        pytest.fail("Por segurança, TEST_DATABASE_URL deve apontar para um banco cujo nome termine em _test ou _testing")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest.fixture
def phase9_users(phase9_session_factory):
    session = phase9_session_factory()
    suffix = uuid4().hex
    users = {
        "admin": User(
            name="Admin Fase 9",
            email=f"admin-{suffix}@example.test",
            password_hash=hash_password(PASSWORD),
            role="admin",
        ),
        "advisor_a": User(
            name="Advisor A",
            email=f"advisor-a-{suffix}@example.test",
            password_hash=hash_password(PASSWORD),
            role="advisor",
        ),
        "advisor_b": User(
            name="Advisor B",
            email=f"advisor-b-{suffix}@example.test",
            password_hash=hash_password(PASSWORD),
            role="advisor",
        ),
        "client_a": User(
            name="Cliente A",
            email=f"client-a-{suffix}@example.test",
            password_hash=hash_password(PASSWORD),
            role="client",
        ),
        "client_b": User(
            name="Cliente B",
            email=f"client-b-{suffix}@example.test",
            password_hash=hash_password(PASSWORD),
            role="client",
        ),
    }
    try:
        session.add_all(users.values())
        session.flush()
        session.add_all(
            [
                ClientProfile(user_id=users["client_a"].id, advisor_id=users["advisor_a"].id),
                ClientProfile(user_id=users["client_b"].id, advisor_id=users["advisor_b"].id),
                ClientPermission(client_id=users["client_a"].id),
                ClientPermission(client_id=users["client_b"].id),
            ]
        )
        session.commit()
        result = {key: {"id": user.id, "email": user.email} for key, user in users.items()}
        result["suffix"] = suffix
        yield result
    finally:
        user_ids = session.scalars(
            select(User.id).where(User.email.like(f"%-{suffix}@example.test"))
        ).all()
        if user_ids:
            session.execute(
                delete(Document).where(
                    or_(
                        Document.client_id.in_(user_ids),
                        Document.uploaded_by_user_id.in_(user_ids),
                    )
                )
            )
            session.execute(delete(User).where(User.id.in_(user_ids)))
            session.commit()
        session.close()


@pytest.fixture
def phase9_api_client(monkeypatch, phase9_session_factory):
    original_overrides = app.dependency_overrides.copy()

    @asynccontextmanager
    async def test_lifespan(_app):
        # Do not start market, snapshot, or document reminder monitors in HTTP tests.
        yield

    def override_get_db():
        session = phase9_session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(app.router, "lifespan_context", test_lifespan)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def _authorization(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
def test_admin_onboards_client_and_assigns_advisor(phase9_api_client, phase9_users) -> None:
    client = phase9_api_client
    users = phase9_users
    suffix = users["suffix"]
    admin_headers = _authorization(client, users["admin"]["email"])

    advisor = client.post(
        "/admin/users",
        headers=admin_headers,
        json={
            "name": "Advisor de Onboarding",
            "email": f"new-advisor-{suffix}@example.test",
            "password": PASSWORD,
            "role": "advisor",
        },
    )
    new_client = client.post(
        "/admin/users",
        headers=admin_headers,
        json={
            "name": "Cliente de Onboarding",
            "email": f"new-client-{suffix}@example.test",
            "password": PASSWORD,
            "role": "client",
        },
    )
    assert advisor.status_code == 201, advisor.text
    assert new_client.status_code == 201, new_client.text
    assert advisor.json()["role"] == "advisor"
    assert new_client.json()["role"] == "client"
    assert "password" not in advisor.json()
    assert "password_hash" not in advisor.json()

    assignment = client.put(
        f"/clients/{new_client.json()['id']}/assignment",
        headers=admin_headers,
        json={"advisor_id": advisor.json()["id"]},
    )
    assert assignment.status_code == 200
    assert assignment.json()["advisor_id"] == advisor.json()["id"]

    client_headers = _authorization(client, new_client.json()["email"])
    permissions = client.get(
        f"/clients/{new_client.json()['id']}/permissions", headers=client_headers
    )
    assert permissions.status_code == 200
    assert permissions.json()["can_edit_patrimony"] is False


@pytest.mark.integration
def test_advisor_only_lists_and_reads_assigned_clients(phase9_api_client, phase9_users) -> None:
    client = phase9_api_client
    users = phase9_users
    advisor_headers = _authorization(client, users["advisor_a"]["email"])

    listed = client.get("/clients", headers=advisor_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [users["client_a"]["id"]]

    assigned_client = client.get(
        f"/clients/{users['client_a']['id']}/dashboard", headers=advisor_headers
    )
    unassigned_client = client.get(
        f"/clients/{users['client_b']['id']}/dashboard", headers=advisor_headers
    )
    assert assigned_client.status_code == 200
    assert unassigned_client.status_code == 403


@pytest.mark.integration
def test_client_cannot_read_other_client_or_write_without_permission(
    phase9_api_client, phase9_users
) -> None:
    client = phase9_api_client
    users = phase9_users
    client_headers = _authorization(client, users["client_a"]["email"])

    own_patrimony = client.get(
        f"/clients/{users['client_a']['id']}/patrimony", headers=client_headers
    )
    another_patrimony = client.get(
        f"/clients/{users['client_b']['id']}/patrimony", headers=client_headers
    )
    forbidden_write = client.post(
        f"/clients/{users['client_a']['id']}/patrimony",
        headers=client_headers,
        json={
            "category": "Reserva",
            "description": "Reserva de emergência",
            "value": "1000.00",
        },
    )

    assert own_patrimony.status_code == 200
    assert another_patrimony.status_code == 403
    assert forbidden_write.status_code == 403


@pytest.mark.integration
def test_admin_can_grant_patrimony_edit_and_write_is_audited(
    phase9_api_client, phase9_users
) -> None:
    client = phase9_api_client
    users = phase9_users
    admin_headers = _authorization(client, users["admin"]["email"])
    client_headers = _authorization(client, users["client_a"]["email"])
    client_id = users["client_a"]["id"]

    permission_update = client.put(
        f"/clients/{client_id}/permissions",
        headers=admin_headers,
        json={"can_edit_patrimony": True},
    )
    assert permission_update.status_code == 200
    assert permission_update.json()["can_edit_patrimony"] is True

    created = client.post(
        f"/clients/{client_id}/patrimony",
        headers=client_headers,
        json={
            "category": "Reserva",
            "description": "Reserva de emergência",
            "value": "1000.00",
        },
    )
    assert created.status_code == 201, created.text

    audit = client.get(f"/clients/{client_id}/audit-log", headers=admin_headers)
    assert audit.status_code == 200
    assert any(
        item["resource"] == "patrimony_item" and item["action"] == "create"
        for item in audit.json()
    )


@pytest.mark.integration
def test_client_sees_only_published_reports(phase9_api_client, phase9_users) -> None:
    client = phase9_api_client
    users = phase9_users
    advisor_headers = _authorization(client, users["advisor_a"]["email"])
    client_headers = _authorization(client, users["client_a"]["email"])
    client_id = users["client_a"]["id"]
    report_payload = {
        "title": "Revisão patrimonial",
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "summary": "Resumo de teste para homologação.",
    }

    draft = client.post(
        f"/clients/{client_id}/reports",
        headers=advisor_headers,
        json={**report_payload, "status": "draft"},
    )
    published = client.post(
        f"/clients/{client_id}/reports",
        headers=advisor_headers,
        json={**report_payload, "title": "Relatório publicado", "status": "published"},
    )
    assert draft.status_code == 201, draft.text
    assert published.status_code == 201, published.text

    visible = client.get(f"/clients/{client_id}/reports", headers=client_headers)
    hidden_draft = client.get(
        f"/clients/{client_id}/reports/{draft.json()['id']}", headers=client_headers
    )
    assert visible.status_code == 200
    assert [report["id"] for report in visible.json()] == [published.json()["id"]]
    assert hidden_draft.status_code == 404


@pytest.mark.integration
def test_advisor_uploads_document_for_assigned_client_and_client_downloads_it(
    phase9_api_client, phase9_users, monkeypatch, tmp_path
) -> None:
    from app.api import documents as documents_api

    monkeypatch.setattr(documents_api.settings, "storage_dir", str(tmp_path))
    client = phase9_api_client
    users = phase9_users
    client_id = users["client_a"]["id"]
    advisor_headers = _authorization(client, users["advisor_a"]["email"])
    client_headers = _authorization(client, users["client_a"]["email"])
    other_advisor_headers = _authorization(client, users["advisor_b"]["email"])
    pdf_content = b"%PDF-1.7\nTalentum Phase 9 test document\n%%EOF"

    uploaded = client.post(
        f"/clients/{client_id}/documents",
        headers=advisor_headers,
        files={"file": ("comprovante.pdf", pdf_content, "application/pdf")},
        data={"kind": "income_proof", "description": "Documento sintético"},
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]

    listed = client.get(f"/clients/{client_id}/documents", headers=client_headers)
    downloaded = client.get(
        f"/clients/{client_id}/documents/{document_id}/download", headers=client_headers
    )
    denied = client.get(f"/clients/{client_id}/documents", headers=other_advisor_headers)
    admin_headers = _authorization(client, users["admin"]["email"])
    audit = client.get(f"/clients/{client_id}/audit-log", headers=admin_headers)

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [document_id]
    assert downloaded.status_code == 200
    assert downloaded.content == pdf_content
    assert denied.status_code == 403
    assert audit.status_code == 200
    assert any(
        item["resource"] == "document"
        and item["action"] == "create"
        and item["resource_id"] == str(document_id)
        for item in audit.json()
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("filename", "content", "content_type", "expected_status"),
    [
        ("comprovante.jpg", b"%PDF-1.7\nnot a JPEG", "application/pdf", 415),
        ("comprovante.pdf", b"not a PDF", "application/pdf", 415),
        (
            "grande.pdf",
            b"%PDF-1.7\n" + b"x" * (10 * 1024 * 1024),
            "application/pdf",
            413,
        ),
    ],
    ids=["extensao-incompativel", "assinatura-invalida", "acima-do-limite"],
)
def test_invalid_document_upload_leaves_no_file_or_record(
    phase9_api_client,
    phase9_users,
    monkeypatch,
    tmp_path,
    filename: str,
    content: bytes,
    content_type: str,
    expected_status: int,
) -> None:
    from app.api import documents as documents_api

    monkeypatch.setattr(documents_api.settings, "storage_dir", str(tmp_path))
    client = phase9_api_client
    users = phase9_users
    client_id = users["client_a"]["id"]
    advisor_headers = _authorization(client, users["advisor_a"]["email"])

    response = client.post(
        f"/clients/{client_id}/documents",
        headers=advisor_headers,
        files={"file": (filename, content, content_type)},
        data={"kind": "income_proof"},
    )
    documents = client.get(
        f"/clients/{client_id}/documents",
        headers=_authorization(client, users["client_a"]["email"]),
    )

    assert response.status_code == expected_status, response.text
    assert documents.status_code == 200
    assert documents.json() == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.integration
def test_suitability_snapshot_review_client_response_and_audit(
    phase9_api_client, phase9_users, phase9_session_factory
) -> None:
    client = phase9_api_client
    users = phase9_users
    client_id = users["client_a"]["id"]
    session = phase9_session_factory()
    try:
        session.add(
            FinancialProfile(
                client_id=client_id,
                monthly_income="8000.00",
                monthly_expenses="5000.00",
            )
        )
        session.commit()
    finally:
        session.close()

    client_headers = _authorization(client, users["client_a"]["email"])
    advisor_headers = _authorization(client, users["advisor_a"]["email"])
    other_advisor_headers = _authorization(client, users["advisor_b"]["email"])
    admin_headers = _authorization(client, users["admin"]["email"])

    questionnaire = client.get(
        "/clients/me/suitability/questionnaire", headers=client_headers
    )
    assert questionnaire.status_code == 200, questionnaire.text
    financial_situation = questionnaire.json()["financial_situation"]
    assert financial_situation["monthly_surplus"] == "3000.00"
    assert financial_situation["client_confirmed_at"] is None

    answers = {
        "investment_horizon": "over_10_years",
        "liquidity_need": "low",
        "loss_reaction": "buy_more",
        "experience": "advanced",
        "emergency_reserve": "yes",
        "risk_tolerance": "high",
        "product_familiarity": "fixed_income,funds,stocks_etfs,fiis",
        "operation_products": "fixed_income,stocks_etfs,fiis",
        "operation_period": "over_3_years",
        "operation_frequency": "monthly",
        "monthly_operation_volume": "1000_to_10000",
        "financial_education": "education",
    }
    payload = {
        "objective": "long_term",
        "answers": answers,
        "financial_data_version": financial_situation["data_version"],
        "confirm_financial_situation": True,
    }

    stale_snapshot = client.post(
        "/clients/me/suitability",
        headers=client_headers,
        json={**payload, "financial_data_version": "0" * 64},
    )
    assert stale_snapshot.status_code == 409
    assert client.get("/clients/me/suitability", headers=client_headers).json() is None

    created = client.post("/clients/me/suitability", headers=client_headers, json=payload)
    assert created.status_code == 201, created.text
    assessment = created.json()
    assessment_id = assessment["id"]
    assert assessment["status"] == "pending_review"
    assert assessment["financial_situation"]["client_confirmed_at"] is not None
    assert sum(
        allocation["percentage"] for allocation in assessment["recommendation"]["allocations"]
    ) == 100

    cross_advisor_read = client.get(
        f"/clients/{client_id}/suitability", headers=other_advisor_headers
    )
    pending_review = client.get(
        f"/clients/{client_id}/suitability", headers=advisor_headers
    )
    assert cross_advisor_read.status_code == 403
    assert pending_review.status_code == 200
    assert pending_review.json()["id"] == assessment_id

    reviewed = client.post(
        f"/clients/{client_id}/suitability/{assessment_id}/review",
        headers=advisor_headers,
        json={"approved": True},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"

    response = client.post(
        f"/clients/me/suitability/{assessment_id}/response",
        headers=client_headers,
        json={"response": "adjustment_requested", "note": "Revisar a parcela de FIIs."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["client_response"] == "adjustment_requested"
    assert response.json()["client_response_note"] == "Revisar a parcela de FIIs."

    audit = client.get(f"/clients/{client_id}/audit-log", headers=admin_headers)
    assert audit.status_code == 200
    actions = {
        item["action"]
        for item in audit.json()
        if item["resource"] == "suitability_assessment"
        and item["resource_id"] == str(assessment_id)
    }
    assert {"create", "review", "respond"}.issubset(actions)
