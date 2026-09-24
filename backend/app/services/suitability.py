# Talentum — backend/app/services/suitability.py
# Responsabilidade: Centraliza as perguntas, a pontuação de risco e as carteiras modelo.
# As regras são determinísticas e explícitas para facilitar auditoria, testes e revisão pelo Advisor.
from typing import Any


OBJECTIVES = (
    {
        "value": "longevity",
        "label": "Longevidade e aposentadoria",
        "description": "Construir patrimônio para sustentar o futuro e a aposentadoria.",
    },
    {
        "value": "dividends",
        "label": "Renda com dividendos",
        "description": "Priorizar geração de renda recorrente, mantendo diversificação.",
    },
    {
        "value": "long_term",
        "label": "Crescimento de longo prazo",
        "description": "Buscar crescimento patrimonial em um horizonte superior a cinco anos.",
    },
    {
        "value": "short_term",
        "label": "Objetivo de curto prazo",
        "description": "Preservar o capital e manter liquidez para um objetivo próximo.",
    },
)

RISK_PROFILES = {
    "conservative": {
        "label": "Conservador",
        "description": "Prioriza preservação do capital, liquidez e menor oscilação.",
    },
    "moderate": {
        "label": "Moderado",
        "description": "Equilibra segurança, renda e crescimento com oscilações controladas.",
    },
    "aggressive": {
        "label": "Agressivo",
        "description": "Aceita oscilações relevantes em busca de maior crescimento no longo prazo.",
    },
}

QUESTION_DEFINITIONS = (
    {
        "key": "investment_horizon",
        "label": "Quando pretende utilizar a maior parte deste dinheiro?",
        "description": "O prazo influencia quanto tempo a carteira pode suportar oscilações.",
        "options": (
            {"value": "under_2_years", "label": "Em até 2 anos"},
            {"value": "2_to_5_years", "label": "Entre 2 e 5 anos"},
            {"value": "5_to_10_years", "label": "Entre 5 e 10 anos"},
            {"value": "over_10_years", "label": "Em mais de 10 anos"},
        ),
    },
    {
        "key": "liquidity_need",
        "label": "Quanto você precisa de liquidez para imprevistos?",
        "description": "Liquidez é a facilidade de transformar um investimento em dinheiro.",
        "options": (
            {"value": "high", "label": "Preciso acessar rapidamente"},
            {"value": "medium", "label": "Posso esperar alguns meses"},
            {"value": "low", "label": "Não devo precisar no curto prazo"},
        ),
    },
    {
        "key": "loss_reaction",
        "label": "Se sua carteira caísse temporariamente 20%, o que faria?",
        "description": "A resposta mede sua tolerância emocional a perdas temporárias.",
        "options": (
            {"value": "sell", "label": "Venderia para evitar novas perdas"},
            {"value": "hold", "label": "Manteria os investimentos"},
            {"value": "buy_more", "label": "Avaliaria investir mais"},
        ),
    },
    {
        "key": "experience",
        "label": "Como você avalia seu conhecimento sobre investimentos?",
        "description": "Conhecimento e experiência ajudam a compreender riscos e produtos.",
        "options": (
            {"value": "beginner", "label": "Estou começando"},
            {"value": "intermediate", "label": "Tenho alguma experiência"},
            {"value": "advanced", "label": "Tenho experiência ampla"},
        ),
    },
    {
        "key": "emergency_reserve",
        "label": "Você já possui uma reserva de emergência separada?",
        "description": "A reserva reduz a necessidade de resgatar investimentos em momentos ruins.",
        "options": (
            {"value": "no", "label": "Ainda não"},
            {"value": "yes", "label": "Sim, está formada"},
        ),
    },
    {
        "key": "risk_tolerance",
        "label": "Qual afirmação representa melhor sua relação com risco?",
        "description": "Risco maior pode gerar retornos maiores, mas também perdas maiores.",
        "options": (
            {"value": "low", "label": "Prefiro estabilidade"},
            {"value": "medium", "label": "Aceito alguma oscilação"},
            {"value": "high", "label": "Aceito oscilações significativas"},
        ),
    },
)

_SCORES = {
    "investment_horizon": {
        "under_2_years": 0,
        "2_to_5_years": 1,
        "5_to_10_years": 2,
        "over_10_years": 3,
    },
    "liquidity_need": {"high": 0, "medium": 1, "low": 2},
    "loss_reaction": {"sell": 0, "hold": 1, "buy_more": 2},
    "experience": {"beginner": 0, "intermediate": 1, "advanced": 2},
    "emergency_reserve": {"no": 0, "yes": 1},
    "risk_tolerance": {"low": 0, "medium": 2, "high": 3},
}

OBJECTIVE_LABELS = {item["value"]: item["label"] for item in OBJECTIVES}

# Percentuais por objetivo, risco e classe de ativo. Cada linha soma 100%.
_PORTFOLIO_MATRIX = {
    "longevity": {
        "conservative": (30, 40, 10, 10, 5, 5),
        "moderate": (20, 30, 15, 20, 10, 5),
        "aggressive": (10, 20, 20, 30, 15, 5),
    },
    "dividends": {
        "conservative": (35, 25, 20, 5, 10, 5),
        "moderate": (20, 20, 25, 15, 15, 5),
        "aggressive": (10, 15, 30, 25, 15, 5),
    },
    "long_term": {
        "conservative": (30, 35, 10, 10, 10, 5),
        "moderate": (15, 25, 20, 25, 10, 5),
        "aggressive": (10, 15, 25, 35, 10, 5),
    },
    "short_term": {
        "conservative": (50, 30, 5, 0, 5, 10),
        "moderate": (45, 25, 10, 5, 5, 10),
        "aggressive": (40, 20, 15, 10, 5, 10),
    },
}

_ASSET_CLASSES = (
    (
        "fixed_income_liquidity",
        "Renda fixa pós-fixada e com liquidez",
        "Parcela voltada à liquidez e à estabilidade da carteira.",
    ),
    (
        "fixed_income_inflation",
        "Renda fixa indexada à inflação",
        "Ajuda a preservar o poder de compra em objetivos de médio e longo prazo.",
    ),
    (
        "dividend_equities_br",
        "Ações brasileiras de empresas maduras",
        "Parcela de renda variável brasileira, com foco em empresas sólidas e dividendos.",
    ),
    (
        "global_equities",
        "ETFs e ações globais diversificadas",
        "Amplia a diversificação geográfica e a exposição a crescimento global.",
    ),
    (
        "real_estate_funds",
        "Fundos imobiliários",
        "Pode contribuir para renda recorrente e diversificação patrimonial.",
    ),
    (
        "cash",
        "Reserva de oportunidade",
        "Mantém recursos disponíveis para necessidades e novas oportunidades.",
    ),
)


def questionnaire_definition() -> dict[str, Any]:
    """Retorna perguntas e opções sem expor os pesos internos da pontuação."""

    return {
        "objectives": list(OBJECTIVES),
        "questions": [
            {
                "key": item["key"],
                "label": item["label"],
                "description": item["description"],
                "options": list(item["options"]),
            }
            for item in QUESTION_DEFINITIONS
        ],
        "disclaimer": (
            "Esta carteira é uma sugestão educativa baseada nas respostas e deve ser validada pelo Advisor "
            "antes de qualquer decisão ou operação."
        ),
    }


def score_answers(objective: str, answers: dict[str, str]) -> tuple[int, str]:
    """Valida as respostas, calcula a pontuação e limita risco incompatível com prazo curto."""

    if objective not in OBJECTIVE_LABELS:
        raise ValueError("Objetivo de investimento inválido")
    expected_keys = set(_SCORES)
    missing = expected_keys - set(answers)
    if missing:
        raise ValueError("Responda todas as perguntas do questionário")
    invalid = [
        key for key, value in answers.items() if key in _SCORES and value not in _SCORES[key]
    ]
    if invalid:
        raise ValueError("Uma ou mais respostas do questionário são inválidas")

    score = sum(_SCORES[key][answers[key]] for key in expected_keys)
    if score <= 4:
        profile = "conservative"
    elif score <= 8:
        profile = "moderate"
    else:
        profile = "aggressive"

    # Objetivos próximos não devem receber uma carteira agressiva automaticamente.
    if objective == "short_term" and answers["investment_horizon"] == "under_2_years":
        profile = "conservative" if profile == "aggressive" else profile
    return score, profile


def build_recommendation(objective: str, risk_profile: str) -> dict[str, Any]:
    """Monta uma carteira modelo por classes de ativos, sem indicar ativos específicos."""

    if objective not in _PORTFOLIO_MATRIX or risk_profile not in RISK_PROFILES:
        raise ValueError("Combinação de objetivo e perfil inválida")
    percentages = _PORTFOLIO_MATRIX[objective][risk_profile]
    allocations = [
        {
            "asset_class": asset_class,
            "label": label,
            "percentage": percentage,
            "rationale": rationale,
        }
        for (asset_class, label, rationale), percentage in zip(_ASSET_CLASSES, percentages)
        if percentage > 0
    ]
    return {
        "title": f"Carteira sugerida — {OBJECTIVE_LABELS[objective]}",
        "summary": (
            f"Modelo {RISK_PROFILES[risk_profile]['label'].lower()} para {OBJECTIVE_LABELS[objective].lower()}. "
            "Os percentuais são referências por classe e não representam uma ordem de investimento."
        ),
        "allocations": allocations,
        "guardrails": [
            "Manter uma reserva de emergência antes de aumentar a exposição a risco.",
            "Revisar o perfil pelo menos uma vez por ano ou após mudanças relevantes de vida.",
            "Validar produtos, custos, liquidez e adequação com o Advisor.",
        ],
    }
