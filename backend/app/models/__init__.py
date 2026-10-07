# Talentum — backend/app/models/__init__.py
# Responsabilidade: Define os modelos ORM que representam as entidades persistidas no banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from app.models.user import User
from app.models.session import UserSession
from app.models.client import AuditLog, ClientPermission, ClientProfile
from app.models.financial import FinancialProfile, Goal, PatrimonyItem
from app.models.action import ActionItem
from app.models.report import Report
from app.models.document import Document
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.market_alert import MarketAlert
from app.models.market_watchlist import MarketWatchlistItem
from app.models.investment_position import InvestmentPosition
from app.models.investment_transaction import InvestmentTransaction
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.suitability import SuitabilityAssessment

__all__ = [
    "AuditLog",
    "ActionItem",
    "ClientPermission",
    "ClientProfile",
    "Document",
    "Notification",
    "NotificationPreference",
    "MarketAlert",
    "MarketWatchlistItem",
    "InvestmentPosition",
    "InvestmentTransaction",
    "PortfolioSnapshot",
    "FinancialProfile",
    "Goal",
    "PatrimonyItem",
    "Report",
    "User",
    "UserSession",
    "SuitabilityAssessment",
]
