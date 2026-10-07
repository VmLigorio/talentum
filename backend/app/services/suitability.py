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
    {
        "key": "product_familiarity",
        "label": "Com quais tipos de produto você tem familiaridade?",
        "description": "Marque todas as opções que conhece. Selecione “Nenhum” apenas se ainda não conhece esses produtos.",
        "selection_mode": "multiple",
        "options": (
            {"value": "none", "label": "Nenhum desses produtos"},
            {"value": "fixed_income", "label": "Renda fixa"},
            {"value": "funds", "label": "Fundos de investimento"},
            {"value": "stocks_etfs", "label": "Ações e ETFs"},
            {"value": "fiis", "label": "Fundos imobiliários (FIIs)"},
            {"value": "derivatives_structured", "label": "Derivativos e produtos estruturados"},
        ),
    },
    {
        "key": "operation_products",
        "label": "Em quais desses produtos você já investiu ou operou?",
        "description": "Marque todas as opções. A pergunta considera sua experiência real, não apenas o conhecimento teórico.",
        "selection_mode": "multiple",
        "options": (
            {"value": "none", "label": "Ainda não investi nesses produtos"},
            {"value": "fixed_income", "label": "Renda fixa"},
            {"value": "funds", "label": "Fundos de investimento"},
            {"value": "stocks_etfs", "label": "Ações e ETFs"},
            {"value": "fiis", "label": "Fundos imobiliários (FIIs)"},
            {"value": "derivatives_structured", "label": "Derivativos e produtos estruturados"},
        ),
    },
    {
        "key": "operation_period",
        "label": "Há quanto tempo você investe ou opera no mercado financeiro?",
        "description": "Considere o período total da sua experiência, mesmo que tenha feito pausas.",
        "options": (
            {"value": "none", "label": "Ainda não investi"},
            {"value": "under_1_year", "label": "Menos de 1 ano"},
            {"value": "1_to_3_years", "label": "De 1 a 3 anos"},
            {"value": "over_3_years", "label": "Mais de 3 anos"},
        ),
    },
    {
        "key": "operation_frequency",
        "label": "Com que frequência você costuma fazer operações de investimento?",
        "description": "Pense na frequência média dos últimos 12 meses.",
        "options": (
            {"value": "none", "label": "Não fiz operações"},
            {"value": "few_per_year", "label": "Algumas vezes por ano"},
            {"value": "monthly", "label": "Mensalmente"},
            {"value": "weekly_or_more", "label": "Semanalmente ou mais"},
        ),
    },
    {
        "key": "monthly_operation_volume",
        "label": "Qual foi o volume médio mensal das suas operações nos últimos 12 meses?",
        "description": "Informe uma faixa aproximada; não é necessário fornecer valores exatos.",
        "options": (
            {"value": "none", "label": "Não fiz operações"},
            {"value": "under_1000", "label": "Até R$ 1.000"},
            {"value": "1000_to_10000", "label": "De R$ 1.000 a R$ 10.000"},
            {"value": "over_10000", "label": "Acima de R$ 10.000"},
            {"value": "prefer_not_to_say", "label": "Prefiro não informar"},
        ),
    },
    {
        "key": "financial_education",
        "label": "Você tem formação ou experiência profissional relacionada a investimentos?",
        "description": "Considere cursos, formação acadêmica ou atuação profissional na área financeira.",
        "options": (
            {"value": "none", "label": "Não"},
            {"value": "education", "label": "Tenho curso ou formação relacionada"},
            {"value": "professional", "label": "Tenho experiência profissional na área"},
            {"value": "both", "label": "Tenho formação e experiência profissional"},
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

_CONTEXT_ANSWERS = {
    "product_familiarity": {"fixed_income", "funds", "stocks_etfs", "fiis", "derivatives_structured", "none"},
    "operation_products": {"fixed_income", "funds", "stocks_etfs", "fiis", "derivatives_structured", "none"},
    "operation_period": {"none", "under_1_year", "1_to_3_years", "over_3_years"},
    "operation_frequency": {"none", "few_per_year", "monthly", "weekly_or_more"},
    "monthly_operation_volume": {"none", "under_1000", "1000_to_10000", "over_10000", "prefer_not_to_say"},
    "financial_education": {"none", "education", "professional", "both"},
}

# Percentuais por objetivo, risco e classe de ativo. Cada linha soma 100%.
# Estes modelos são referências educativas de longo prazo; os exemplos de ativos
# abaixo são uma lista inicial para revisão do Advisor, sem indicação de compra.
_PORTFOLIO_MATRIX = {
    "longevity": {
        "conservative": (50, 30, 5, 5, 5, 5),
        "moderate": (20, 35, 15, 15, 15, 0),
        "aggressive": (10, 25, 30, 20, 15, 0),
    },
    "dividends": {
        "conservative": (40, 25, 20, 5, 5, 5),
        "moderate": (20, 25, 25, 10, 15, 5),
        "aggressive": (10, 25, 30, 20, 15, 0),
    },
    "long_term": {
        "conservative": (50, 30, 5, 5, 5, 5),
        "moderate": (20, 35, 15, 15, 15, 0),
        "aggressive": (10, 25, 30, 20, 15, 0),
    },
    "short_term": {
        # O prazo curto limita a exposição a ações e FIIs, mesmo para perfil arrojado.
        "conservative": (90, 0, 0, 0, 0, 10),
        "moderate": (90, 0, 0, 0, 0, 10),
        "aggressive": (90, 0, 0, 0, 0, 10),
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

_EQUITY_SEGMENTS = (
    {
        "asset_class": "brazilian_banks",
        "label": "Bancos",
        "examples": ["ITUB4", "BBAS3"],
        "rationale": "Revisar margem financeira, custo de crédito, inadimplência e capital.",
    },
    {
        "asset_class": "brazilian_power",
        "label": "Energia e serviços elétricos",
        "examples": ["TAEE11", "EGIE3", "EQTL3"],
        "rationale": "Combina negócios distintos; revisar regulação, dívida, concessões e exposição operacional.",
    },
    {
        "asset_class": "brazilian_market",
        "label": "Mercado brasileiro diversificado",
        "examples": ["ETF amplo de ações brasileiras"],
        "rationale": "Mantém exposição diversificada sem concentrar a parcela em poucos setores.",
    },
)

_FII_SEGMENTS = (
    {
        "asset_class": "fii_paper",
        "label": "Papel e CRI",
        "examples": ["KNCR11", "KNIP11"],
        "rationale": "Analisar risco de crédito, indexador, duration e concentração por devedor.",
    },
    {
        "asset_class": "fii_hybrid",
        "label": "Imóveis diversificados / híbrido",
        "examples": ["KNRI11"],
        "rationale": "Acompanhar vacância, qualidade dos imóveis, locatários e preço patrimonial.",
    },
    {
        "asset_class": "fii_shopping",
        "label": "Shopping centers",
        "examples": ["XPML11"],
        "rationale": "Acompanhar ocupação, vendas, concentração de ativos e condições do varejo.",
    },
    {
        "asset_class": "fii_logistics",
        "label": "Logística",
        "examples": ["BTLG11"],
        "rationale": "Acompanhar vacância, contratos, locatários e concentração geográfica.",
    },
)

_SEGMENT_WEIGHTS = {
    "equities": {
        "conservative": (40, 40, 20),
        "moderate": (33, 33, 34),
        "aggressive": (27, 33, 40),
    },
    "fiis": {
        "conservative": (40, 20, 20, 20),
        "moderate": (33, 27, 20, 20),
        "aggressive": (27, 20, 27, 26),
    },
}


def questionnaire_definition() -> dict[str, Any]:
    """Retorna perguntas e opções sem expor os pesos internos da pontuação."""

    return {
        "objectives": list(OBJECTIVES),
        "questions": [
            {
                "key": item["key"],
                "label": item["label"],
                "description": item["description"],
                "selection_mode": item.get("selection_mode", "single"),
                "options": list(item["options"]),
            }
            for item in QUESTION_DEFINITIONS
        ],
        "disclaimer": (
            "Esta carteira é educativa e baseada nas respostas. Ativos citados são exemplos para análise, não "
            "recomendação automática de compra. O Advisor deve validar a proposta; o aceite do cliente não "
            "executa operações."
        ),
    }


def score_answers(objective: str, answers: dict[str, str]) -> tuple[int, str]:
    """Valida as respostas, calcula a pontuação e limita risco incompatível com prazo curto."""

    if objective not in OBJECTIVE_LABELS:
        raise ValueError("Objetivo de investimento inválido")
    expected_keys = set(_SCORES) | set(_CONTEXT_ANSWERS)
    missing = expected_keys - set(answers)
    if missing:
        raise ValueError("Responda todas as perguntas do questionário")
    invalid = [
        key for key, value in answers.items() if key in _SCORES and value not in _SCORES[key]
    ]
    if invalid:
        raise ValueError("Uma ou mais respostas do questionário são inválidas")

    for key, valid_values in _CONTEXT_ANSWERS.items():
        raw_values = answers[key].split(",")
        selected_values = [value.strip() for value in raw_values if value.strip()]
        if (
            not selected_values
            or len(selected_values) != len(set(selected_values))
            or any(value not in valid_values for value in selected_values)
            or ("none" in selected_values and len(selected_values) > 1)
        ):
            raise ValueError("Uma ou mais respostas de conhecimento e experiência são inválidas")

    score = sum(_SCORES[key][answers[key]] for key in _SCORES)
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


def _split_percentage(total: int, weights: tuple[int, ...]) -> list[int]:
    """Divide um percentual inteiro por pesos e distribui arredondamentos sem perder pontos."""

    quotas = [total * weight / 100 for weight in weights]
    result = [int(quota) for quota in quotas]
    remaining = total - sum(result)
    order = sorted(range(len(weights)), key=lambda index: quotas[index] - result[index], reverse=True)
    for index in order[:remaining]:
        result[index] += 1
    return result


def _suballocations(total: int, risk_profile: str, kind: str) -> list[dict[str, Any]]:
    segments = _EQUITY_SEGMENTS if kind == "equities" else _FII_SEGMENTS
    weights = _SEGMENT_WEIGHTS[kind][risk_profile]
    percentages = _split_percentage(total, weights)
    return [
        {
            "asset_class": segment["asset_class"],
            "label": segment["label"],
            "percentage": percentage,
            "examples": list(segment["examples"]),
            "rationale": segment["rationale"],
        }
        for segment, percentage in zip(segments, percentages)
        if percentage > 0
    ]


def build_recommendation(
    objective: str,
    risk_profile: str,
    financial_situation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta um modelo por classe e detalha segmentos e exemplos para revisão humana."""

    if objective not in _PORTFOLIO_MATRIX or risk_profile not in RISK_PROFILES:
        raise ValueError("Combinação de objetivo e perfil inválida")
    percentages = _PORTFOLIO_MATRIX[objective][risk_profile]
    allocations = []
    for (asset_class, label, rationale), percentage in zip(_ASSET_CLASSES, percentages):
        if percentage <= 0:
            continue
        allocation = {
            "asset_class": asset_class,
            "label": label,
            "percentage": percentage,
            "rationale": rationale,
        }
        if asset_class == "dividend_equities_br":
            allocation["suballocations"] = _suballocations(percentage, risk_profile, "equities")
        elif asset_class == "real_estate_funds":
            allocation["suballocations"] = _suballocations(percentage, risk_profile, "fiis")
        allocations.append(allocation)

    is_short_term = objective == "short_term"
    guardrails = [
        "Separar a reserva de emergência antes de assumir risco de mercado.",
        "Revisar objetivo, perfil, custos, liquidez e adequação com o Advisor.",
        "Os ativos citados são exemplos para análise; não são ordens nem recomendação automática de compra.",
        "A resposta do cliente registra aceite ou recusa e não executa operações.",
    ]
    if is_short_term:
        guardrails.insert(
            0,
            "Para objetivo de curto prazo, o modelo prioriza liquidez e não aloca em ações ou FIIs, mesmo no perfil arrojado.",
        )
    financial_review_flags = list(
        (financial_situation or {}).get("capacity_flags", [])
    )
    if "monthly_surplus_not_positive" in financial_review_flags:
        guardrails.append(
            "A renda mensal declarada não supera as despesas; o Advisor deve revisar a capacidade financeira antes de aprovar."
        )
    if "active_goal_within_2_years" in financial_review_flags:
        guardrails.append(
            "Há uma meta financeira com prazo de até dois anos; reserve os recursos dessa meta antes de assumir risco de mercado."
        )
    if "no_patrimony_items_recorded" in financial_review_flags:
        guardrails.append(
            "Nenhum item patrimonial está cadastrado; confirme se a declaração está completa antes da aprovação."
        )
    if "liabilities_not_recorded" in financial_review_flags:
        guardrails.append(
            "O Talentum ainda não registra dívidas ou outros passivos; considere-os na revisão da situação financeira."
        )
    return {
        "title": f"Carteira sugerida — {OBJECTIVE_LABELS[objective]}",
        "summary": (
            f"Modelo {RISK_PROFILES[risk_profile]['label'].lower()} para {OBJECTIVE_LABELS[objective].lower()}. "
            "Os percentuais são referências por classe e não representam uma ordem de investimento."
        ),
        "allocations": allocations,
        "model_version": "4",
        "financial_review_flags": financial_review_flags,
        "guardrails": guardrails,
    }


def build_knowledge_review_flags(answers: dict[str, str], recommendation: dict[str, Any]) -> list[str]:
    """Highlights product mismatches for Advisor review without changing risk appetite."""
    familiar = set(answers["product_familiarity"].split(","))
    recommended_products = set()
    for allocation in recommendation["allocations"]:
        if allocation["asset_class"] in {"dividend_equities_br", "global_equities"}:
            recommended_products.add("stocks_etfs")
        elif allocation["asset_class"] == "real_estate_funds":
            recommended_products.add("fiis")

    flags = []
    if "none" in set(answers["operation_products"].split(",")):
        flags.append("no_prior_market_operations_reported")
    if recommended_products - familiar:
        flags.append("review_familiarity_with_recommended_products")
    if answers["financial_education"] == "none":
        flags.append("no_financial_education_or_professional_experience_reported")
    return flags


def build_recommended_actions(
    objective: str,
    answers: dict[str, str],
    financial_situation: dict[str, Any],
    knowledge_review_flags: list[str],
) -> list[dict[str, str]]:
    """Turns suitability signals into concrete review steps without inventing weights."""
    actions = []
    capacity_flags = set(financial_situation.get("capacity_flags", []))

    if objective == "short_term":
        actions.append(
            {
                "key": "protect_short_term_goal",
                "title": "Preservar o valor destinado ao objetivo próximo",
                "detail": "Confirme a data em que o recurso será usado e priorize liquidez e baixa oscilação para essa parcela.",
            }
        )
    if answers["emergency_reserve"] == "no":
        actions.append(
            {
                "key": "build_emergency_reserve",
                "title": "Formar ou completar a reserva de emergência",
                "detail": "Defina com o cliente a reserva necessária em instrumentos líquidos e de baixo risco antes de ampliar a exposição a ativos voláteis.",
            }
        )
    if "active_goal_within_2_years" in capacity_flags:
        actions.append(
            {
                "key": "earmark_near_term_goals",
                "title": "Separar recursos das metas próximas",
                "detail": "Revise as metas ativas com prazo de até dois anos e não misture os valores necessários com a parcela de longo prazo.",
            }
        )
    if "monthly_surplus_not_positive" in capacity_flags:
        actions.append(
            {
                "key": "review_monthly_cash_flow",
                "title": "Revisar o fluxo de caixa antes de definir aportes",
                "detail": "A renda cadastrada não supera as despesas; confirme o orçamento e não presuma capacidade de aporte recorrente.",
            }
        )
    if "no_prior_market_operations_reported" in knowledge_review_flags:
        actions.append(
            {
                "key": "explain_products_before_validation",
                "title": "Explicar riscos e funcionamento dos produtos",
                "detail": "O cliente não relatou operações anteriores. Revise liquidez, possibilidade de perda, custos e complexidade antes de validar cada classe.",
            }
        )
    elif "review_familiarity_with_recommended_products" in knowledge_review_flags:
        actions.append(
            {
                "key": "check_product_familiarity",
                "title": "Conferir familiaridade com as classes sugeridas",
                "detail": "Apresente como funcionam as classes sem familiaridade declarada e registre a compreensão do cliente antes da validação.",
            }
        )
    if answers["operation_frequency"] == "weekly_or_more":
        actions.append(
            {
                "key": "review_transaction_costs",
                "title": "Verificar custos das operações frequentes",
                "detail": "Compare custos diretos e indiretos e avalie se a frequência informada é necessária para o objetivo do cliente.",
            }
        )
    actions.append(
        {
            "key": "advisor_confirm_allocation",
            "title": "Validar a composição por classe e categoria",
            "detail": "Compare percentuais, liquidez, concentração, custos e riscos de cada categoria com o objetivo e as respostas do cliente; a carteira é um modelo para revisão.",
        }
    )
    return actions
