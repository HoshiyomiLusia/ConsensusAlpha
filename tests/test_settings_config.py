from app.core.config import Settings


def test_webull_jp_region_uses_japan_openapi_endpoints():
    settings = Settings(webull_region="jp", webull_env="production")

    assert settings.webull_trading_endpoint == "api.webull.co.jp"
    assert settings.webull_market_data_endpoint == "api.webull.co.jp"


def test_webull_jp_region_uses_japan_uat_endpoint():
    settings = Settings(webull_region="jp", webull_env="test")

    assert settings.webull_trading_endpoint == "jp-openapi-alb.uat.webullbroker.com"
    assert settings.webull_market_data_endpoint == "jp-openapi-alb.uat.webullbroker.com"


def test_webull_custom_endpoint_override_is_preserved():
    settings = Settings(
        webull_region="jp",
        webull_env="production",
        webull_trading_endpoint_production="proxy.example.internal",
    )

    assert settings.webull_trading_endpoint == "proxy.example.internal"
