from typing import Protocol

from app.conference.models import AgentOpinion
from app.market_data.models import MarketContext


class LLMProvider(Protocol):
    async def generate_opinion(
        self,
        *,
        role: str,
        context: MarketContext,
        requested_action: str | None = None,
    ) -> AgentOpinion: ...

    async def summarize(self, opinions: list[AgentOpinion]) -> str: ...
