import json

import httpx

from app.agents.mock_llm import MockLLMProvider
from app.agents.roles import CHAIRPERSON_ROLE
from app.conference.models import AgentOpinion
from app.core.config import AgentLLMConfig, Settings
from app.market_data.models import MarketSnapshot


class OpenAICompatibleLLMProvider:
    """Small OpenAI-compatible JSON client for optional real-agent mode."""

    def __init__(self, *, provider: str, model: str, api_key: str, base_url: str):
        if not api_key:
            raise ValueError("LLM_API_KEY is required when LLM_PROVIDER is not mock")
        if not model:
            raise ValueError("LLM_MODEL is required when LLM_PROVIDER is not mock")
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._usage_events: list[dict] = []

    @classmethod
    def from_settings(cls, settings: Settings):
        return cls(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    @classmethod
    def from_agent_config(cls, config: AgentLLMConfig):
        return cls(
            provider=config.provider,
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
        )

    async def generate_opinion(
        self,
        *,
        role: str,
        snapshot: MarketSnapshot,
        requested_action: str | None = None,
    ) -> AgentOpinion:
        system = (
            "You are an investment conference agent. Return strict JSON with keys: "
            "agent_id, role, symbol, action, confidence, thesis, concerns, "
            "blocking_concerns, suggested_max_position_pct, suggested_stop_loss_pct. "
            "The action must be BUY, SELL, or HOLD."
        )
        user = {
            "role": role,
            "snapshot": snapshot.model_dump(mode="json"),
            "requested_action": requested_action,
        }
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user)},
            ],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        self._record_usage(
            role=role,
            operation="opinion",
            usage=body.get("usage"),
            prompt=json.dumps(payload["messages"]),
            completion=content,
        )
        data = json.loads(content)
        data["role"] = role
        data["symbol"] = snapshot.symbol
        data.setdefault("agent_id", f"{self.provider}-{self.model}-{role}")
        raw_body = dict(data)
        data.setdefault(
            "raw_payload",
            {
                "provider": self.provider,
                "model": self.model,
                "body": raw_body,
                "usage": body.get("usage") or {},
            },
        )
        return AgentOpinion.model_validate(data)

    async def summarize(self, opinions: list[AgentOpinion]) -> str:
        votes = [opinion.model_dump(mode="json") for opinion in opinions]
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Summarize this investment conference in one concise paragraph.",
                },
                {"role": "user", "content": json.dumps(votes)},
            ],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        self._record_usage(
            role=CHAIRPERSON_ROLE,
            operation="summary",
            usage=body.get("usage"),
            prompt=json.dumps(payload["messages"]),
            completion=content,
        )
        return content

    def consume_usage_events(self) -> list[dict]:
        events = list(self._usage_events)
        self._usage_events.clear()
        return events

    def _record_usage(
        self,
        *,
        role: str,
        operation: str,
        usage: dict | None,
        prompt: str,
        completion: str,
    ) -> None:
        if usage:
            prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
            completion_tokens = int(
                usage.get("completion_tokens") or usage.get("output_tokens") or 0
            )
            total_tokens = int(usage.get("total_tokens") or prompt_tokens + completion_tokens)
            estimated = False
            raw_payload = usage
        else:
            prompt_tokens = self._estimate_tokens(prompt)
            completion_tokens = self._estimate_tokens(completion)
            total_tokens = prompt_tokens + completion_tokens
            estimated = True
            raw_payload = {"method": "character_estimate"}
        self._usage_events.append(
            {
                "role": role,
                "operation": operation,
                "provider": self.provider,
                "model": self.model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated": estimated,
                "raw_payload": raw_payload,
            }
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, (len(text) + 3) // 4)


class MultiAgentLLMProvider:
    def __init__(self, settings: Settings):
        self.providers = {
            config.role: self._provider_for_config(config, settings)
            for config in settings.effective_llm_agent_configs()
            if config.enabled
        }
        self.fallback = MockLLMProvider(settings.mock_agent_action or None)
        self._usage_events: list[dict] = []

    async def generate_opinion(
        self,
        *,
        role: str,
        snapshot: MarketSnapshot,
        requested_action: str | None = None,
    ) -> AgentOpinion:
        provider = self.providers.get(role, self.fallback)
        opinion = await provider.generate_opinion(
            role=role,
            snapshot=snapshot,
            requested_action=requested_action,
        )
        self._usage_events.extend(_consume_usage_events(provider))
        return opinion

    async def summarize(self, opinions: list[AgentOpinion]) -> str:
        provider = self.providers.get(CHAIRPERSON_ROLE, self.fallback)
        summary = await provider.summarize(opinions)
        self._usage_events.extend(_consume_usage_events(provider))
        return summary

    def consume_usage_events(self) -> list[dict]:
        events = list(self._usage_events)
        self._usage_events.clear()
        return events

    @staticmethod
    def _provider_for_config(config: AgentLLMConfig, settings: Settings):
        if config.provider.lower() == "mock":
            return MockLLMProvider(settings.mock_agent_action or None)
        return OpenAICompatibleLLMProvider.from_agent_config(config)


def build_llm_provider(settings: Settings):
    if settings.llm_agent_configs:
        return MultiAgentLLMProvider(settings)
    if settings.llm_provider.lower() == "mock":
        return MockLLMProvider(settings.mock_agent_action or None)
    return OpenAICompatibleLLMProvider.from_settings(settings)


def _consume_usage_events(provider) -> list[dict]:
    consume = getattr(provider, "consume_usage_events", None)
    if not consume:
        return []
    return consume()
