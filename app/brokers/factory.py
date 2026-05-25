from app.brokers.mock_provider import MockBrokerProvider
from app.brokers.webull_provider import WebullProvider
from app.core.config import Settings


def build_broker_provider(settings: Settings):
    if settings.broker_provider == "webull":
        return WebullProvider(settings)
    return MockBrokerProvider(settings.webull_account_id or "mock-account")
