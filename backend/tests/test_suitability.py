# Talentum — backend/tests/test_suitability.py
# Responsabilidade: Protege a pontuação, a matriz de carteiras e o contrato das rotas de suitability.
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.suitability import build_financial_situation_snapshot, respond_to_my_suitability
from app.schemas.suitability import SuitabilityAssessmentCreate, SuitabilityClientResponseUpdate
from app.services.suitability import (
    build_knowledge_review_flags,
    build_recommendation,
    build_recommended_actions,
    questionnaire_definition,
    score_answers,
)


def test_suitability_routes_are_registered() -> None:
    from app.main import app

    assert {
        "/clients/me/suitability/questionnaire",
        "/clients/me/suitability",
        "/clients/{client_id}/suitability",
        "/clients/{client_id}/suitability/{assessment_id}/review",
        "/clients/me/suitability/{assessment_id}/response",
    }.issubset(app.openapi()["paths"])


def test_questionnaire_has_requested_objectives_and_questions() -> None:
    definition = questionnaire_definition()

    assert {item["value"] for item in definition["objectives"]} == {
        "longevity",
        "dividends",
        "long_term",
        "short_term",
    }
    assert len(definition["questions"]) == 12
    questions = {question["key"]: question for question in definition["questions"]}
    assert questions["product_familiarity"]["selection_mode"] == "multiple"
    assert questions["operation_products"]["selection_mode"] == "multiple"


def test_assessment_contract_requires_all_twelve_answers() -> None:
    payload = SuitabilityAssessmentCreate(
        objective="long_term",
        answers=complete_suitability_answers(),
        financial_data_version="a" * 64,
        confirm_financial_situation=True,
    )
    assert len(payload.answers) == 12


def complete_suitability_answers(**overrides: str) -> dict[str, str]:
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
    answers.update(overrides)
    return answers


def test_financial_snapshot_aggregates_data_and_flags_near_term_capacity() -> None:
    now = datetime.now(timezone.utc)
    profile = SimpleNamespace(
        client_id=42,
        monthly_income=Decimal("5000.00"),
        monthly_expenses=Decimal("5200.00"),
        updated_at=now,
    )
    assets = [
        SimpleNamespace(id=1, category="investimentos", value=Decimal("12000.00"), updated_at=now),
        SimpleNamespace(id=2, category="investimentos", value=Decimal("3000.00"), updated_at=now),
    ]
    goals = [
        SimpleNamespace(
            id=3,
            title="Entrada do imóvel",
            target_value=Decimal("50000.00"),
            current_value=Decimal("10000.00"),
            target_date=date.today() + timedelta(days=365),
            updated_at=now,
        )
    ]
    db = Mock()
    db.get.return_value = profile
    db.scalars.side_effect = [SimpleNamespace(all=lambda: assets), SimpleNamespace(all=lambda: goals)]

    snapshot = build_financial_situation_snapshot(42, db)

    assert snapshot["monthly_surplus"] == "-200.00"
    assert snapshot["patrimony_total"] == "15000.00"
    assert snapshot["patrimony_by_category"] == [{"category": "investimentos", "value": "15000.00"}]
    assert snapshot["active_goals"][0]["title"] == "Entrada do imóvel"
    assert set(snapshot["capacity_flags"]) == {
        "liabilities_not_recorded",
        "monthly_surplus_not_positive",
        "active_goal_within_2_years",
    }
    assert len(snapshot["data_version"]) == 64


def test_recommendation_carries_financial_review_flags_and_guardrails() -> None:
    recommendation = build_recommendation(
        "long_term",
        "moderate",
        {"capacity_flags": ["monthly_surplus_not_positive", "liabilities_not_recorded"]},
    )

    assert recommendation["financial_review_flags"] == [
        "monthly_surplus_not_positive",
        "liabilities_not_recorded",
    ]
    assert any("renda mensal" in item for item in recommendation["guardrails"])
    assert any("passivos" in item for item in recommendation["guardrails"])


def test_recommended_actions_adapt_to_reserve_goals_cash_flow_and_frequency() -> None:
    answers = complete_suitability_answers(
        emergency_reserve="no", operation_frequency="weekly_or_more"
    )
    financial = {
        "capacity_flags": ["active_goal_within_2_years", "monthly_surplus_not_positive"]
    }

    actions = build_recommended_actions("long_term", answers, financial, [])
    keys = {action["key"] for action in actions}

    assert {
        "build_emergency_reserve",
        "earmark_near_term_goals",
        "review_monthly_cash_flow",
        "review_transaction_costs",
        "advisor_confirm_allocation",
    }.issubset(keys)


def test_high_score_generates_aggressive_long_term_model_summing_one_hundred() -> None:
    score, risk = score_answers(
        "long_term",
        complete_suitability_answers(),
    )
    recommendation = build_recommendation("long_term", risk)

    assert score == 13
    assert risk == "aggressive"
    assert sum(item["percentage"] for item in recommendation["allocations"]) == 100
    equities = next(item for item in recommendation["allocations"] if item["asset_class"] == "dividend_equities_br")
    fiis = next(item for item in recommendation["allocations"] if item["asset_class"] == "real_estate_funds")
    assert sum(item["percentage"] for item in equities["suballocations"]) == equities["percentage"]
    assert sum(item["percentage"] for item in fiis["suballocations"]) == fiis["percentage"]
    assert {"ITUB4", "BBAS3"}.issubset(set(equities["suballocations"][0]["examples"]))
    assert {"KNCR11", "KNIP11"}.issubset(set(fiis["suballocations"][0]["examples"]))


def test_short_term_horizon_caps_an_aggressive_score_to_conservative() -> None:
    score, risk = score_answers(
        "short_term",
        complete_suitability_answers(investment_horizon="under_2_years"),
    )

    assert score == 10
    assert risk == "conservative"


def test_knowledge_history_is_recorded_without_changing_risk_score() -> None:
    score, profile = score_answers("long_term", complete_suitability_answers())
    less_experienced = complete_suitability_answers(
        product_familiarity="none",
        operation_products="none",
        operation_period="none",
        operation_frequency="none",
        monthly_operation_volume="none",
        financial_education="none",
    )
    novice_score, novice_profile = score_answers("long_term", less_experienced)

    assert (score, profile) == (novice_score, novice_profile)

    recommendation = build_recommendation("long_term", profile)
    flags = build_knowledge_review_flags(less_experienced, recommendation)
    assert "no_prior_market_operations_reported" in flags
    assert "review_familiarity_with_recommended_products" in flags
    assert "no_financial_education_or_professional_experience_reported" in flags


@pytest.mark.parametrize(
    "product_selection",
    ["none,fiis", "none,fixed_income", "fixed_income,fixed_income", "unknown", ""],
)
def test_product_familiarity_multiselect_rejects_invalid_combinations(
    product_selection: str,
) -> None:
    with pytest.raises(ValueError, match="conhecimento e experiência"):
        score_answers(
            "long_term",
            complete_suitability_answers(product_familiarity=product_selection),
        )


def test_short_term_model_has_no_equity_or_fii_allocation_for_any_risk_profile() -> None:
    for risk in ("conservative", "moderate", "aggressive"):
        recommendation = build_recommendation("short_term", risk)
        by_class = {item["asset_class"]: item["percentage"] for item in recommendation["allocations"]}
        assert sum(item["percentage"] for item in recommendation["allocations"]) == 100
        assert by_class.get("dividend_equities_br", 0) == 0
        assert by_class.get("global_equities", 0) == 0
        assert by_class.get("real_estate_funds", 0) == 0
        assert any("curto prazo" in item.lower() for item in recommendation["guardrails"])


def test_all_model_combinations_and_suballocations_sum_to_one_hundred() -> None:
    for objective in ("longevity", "dividends", "long_term", "short_term"):
        for risk in ("conservative", "moderate", "aggressive"):
            recommendation = build_recommendation(objective, risk)
            assert sum(item["percentage"] for item in recommendation["allocations"]) == 100
            for allocation in recommendation["allocations"]:
                if allocation.get("suballocations"):
                    assert sum(
                        item["percentage"] for item in allocation["suballocations"]
                    ) == allocation["percentage"]


def test_long_term_models_have_profile_specific_br_equity_and_fii_weights() -> None:
    expected = {
        "conservative": {"fixed_income_liquidity": 50, "fixed_income_inflation": 30, "dividend_equities_br": 5, "global_equities": 5, "real_estate_funds": 5, "cash": 5},
        "moderate": {"fixed_income_liquidity": 20, "fixed_income_inflation": 35, "dividend_equities_br": 15, "global_equities": 15, "real_estate_funds": 15},
        "aggressive": {"fixed_income_liquidity": 10, "fixed_income_inflation": 25, "dividend_equities_br": 30, "global_equities": 20, "real_estate_funds": 15},
    }
    for risk, expected_weights in expected.items():
        recommendation = build_recommendation("long_term", risk)
        actual = {item["asset_class"]: item["percentage"] for item in recommendation["allocations"]}
        assert actual == expected_weights


def test_client_can_respond_after_advisor_approval_and_response_is_audited() -> None:
    now = datetime.now(timezone.utc)
    assessment = SimpleNamespace(
        id=17,
        client_id=42,
        objective="long_term",
        risk_profile="moderate",
        score=8,
        answers={},
        recommendation=build_recommendation("long_term", "moderate"),
        status="approved",
        client_response="pending",
        client_response_note=None,
        client_response_at=None,
        created_at=now,
        expires_at=now + timedelta(days=365),
        reviewed_at=now,
        reviewed_by_user_id=9,
    )
    db = Mock()
    db.scalar.return_value = assessment
    db.refresh.side_effect = lambda value: None

    result = respond_to_my_suitability(
        assessment_id=17,
        payload=SuitabilityClientResponseUpdate(
            response="adjustment_requested", note="Prefiro reduzir a parcela de FIIs."
        ),
        current_user=SimpleNamespace(id=42, role="client"),
        db=db,
    )

    assert result.client_response == "adjustment_requested"
    assert result.client_response_note == "Prefiro reduzir a parcela de FIIs."
    assert result.client_response_at is not None
    audit_log = db.add.call_args.args[0]
    assert audit_log.action == "respond"
    assert audit_log.details["response"] == "adjustment_requested"


@pytest.mark.parametrize(
    ("assessment_status", "client_response"),
    [("pending_review", "pending"), ("approved", "accepted")],
)
def test_client_cannot_respond_before_approval_or_change_a_saved_response(
    assessment_status: str, client_response: str
) -> None:
    db = Mock()
    db.scalar.return_value = SimpleNamespace(
        id=17,
        client_id=42,
        status=assessment_status,
        client_response=client_response,
    )

    with pytest.raises(HTTPException) as error:
        respond_to_my_suitability(
            assessment_id=17,
            payload=SuitabilityClientResponseUpdate(response="declined"),
            current_user=SimpleNamespace(id=42, role="client"),
            db=db,
        )

    assert error.value.status_code == 409
    db.commit.assert_not_called()
