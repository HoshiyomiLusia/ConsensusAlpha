from app.market_data.models import AssetType


ETF_SYMBOLS = {"SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "TLT", "GLD"}

DEFAULT_MARKET_UNIVERSE = [
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLY",
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "META",
    "AMZN",
    "GOOGL",
    "AMD",
    "AVGO",
    "JPM",
    "UNH",
    "COST",
    "LLY",
]


def normalize_symbols(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    source = symbols or DEFAULT_MARKET_UNIVERSE
    for raw in source:
        for part in raw.replace("\n", ",").split(","):
            symbol = part.strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            normalized.append(symbol)
    return normalized


def infer_asset_type(symbol: str) -> AssetType:
    return "etf" if symbol.upper() in ETF_SYMBOLS else "equity"
