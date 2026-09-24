# Talentum — backend/tests/test_suitability.py
# Responsabilidade: Protege a pontuação, a matriz de carteiras e o contrato das rotas de suitability.
from app.services.suitability import build_recommendation, questionnaire_definition, score_answers


def test_suitability_routes_are_registered() -> None:
    from app.main import app

    assert {
        "/clients/me/suitability/questionnaire",
        "/clients/me/suitability",
        "/clients/{client_id}/suitability",
        "/clients/{client_id}/suitability/{assessment_id}/review",
    }.issubset(app.openapi()["paths"])


def test_questionnaire_has_requested_objectives_and_questions() -> None:
    definition = questionnaire_definition()

    assert {item["value"] for item in definition["objectives"]} == {
        "longevity",
        "dividends",
        "long_term",
        "short_term",
    }
    assert len(definition["questions"]) == 6


def test_high_score_generates_aggressive_long_term_model_summing_one_hundred() -> None:
    score, risk = score_answers(
        "long_term",
        {
            "investment_horizon": "over_10_years",
            "liquidity_need": "low",
            "loss_reaction": "buy_more",
            "experience": "advanced",
            "emergency_reserve": "yes",
            "risk_tolerance": "high",
        },
    )
    recommendation = build_recommendation("long_term", risk)

    assert score == 13
    assert risk == "aggressive"
    assert sum(item["percentage"] for item in recommendation["allocations"]) == 100


def test_short_term_horizon_caps_an_aggressive_score_to_conservative() -> None:
    score, risk = score_answers(
        "short_term",
        {
            "investment_horizon": "under_2_years",
            "liquidity_need": "low",
            "loss_reaction": "buy_more",
            "experience": "advanced",
            "emergency_reserve": "yes",
            "risk_tolerance": "high",
        },
    )

    assert score == 10
    assert risk == "conservative"
