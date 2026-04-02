"""
Model interface layer — unified API for talking to any LLM provider.

Supports: OpenAI, Anthropic, Google, local/ollama, and any OpenAI-compatible endpoint.
"""

from __future__ import annotations

import os
import json
import httpx
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel


class Message(BaseModel):
    """A single message in a conversation."""
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_calls: list[dict] = []
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class ToolDefinition(BaseModel):
    """A tool that an agent can call."""
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Optional[str] = None  # Python callable path


class ModelResponse(BaseModel):
    """Response from a model."""
    content: str
    tool_calls: list[dict] = []
    raw: dict = {}
    model: str = ""
    usage: dict = {}


class ModelProvider(ABC):
    """Abstract base class for model providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        ...

    @abstractmethod
    def name(self) -> str:
        ...


class OpenAIProvider(ModelProvider):
    """OpenAI-compatible provider (works with OpenAI, Azure, local endpoints)."""

    def __init__(self, model: str = "gpt-4o", base_url: str | None = None, api_key: str | None = None):
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def name(self) -> str:
        return f"openai:{self.model}"

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict = {
            "model": self.model,
            "messages": [m.model_dump(exclude_none=True, exclude={"tool_calls"} if not m.tool_calls else set()) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]

        return ModelResponse(
            content=msg.get("content", "") or "",
            tool_calls=msg.get("tool_calls", []),
            raw=data,
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
        )


class AnthropicProvider(ModelProvider):
    """Anthropic Claude provider."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def name(self) -> str:
        return f"anthropic:{self.model}"

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Separate system message
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_msg += m.content + "\n"
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        payload: dict = {
            "model": self.model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg:
            payload["system"] = system_msg.strip()

        if tools:
            payload["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in tools
            ]

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        # Extract content
        content_parts = []
        tool_calls = []
        for block in data.get("content", []):
            if block["type"] == "text":
                content_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block["input"]),
                    },
                })

        return ModelResponse(
            content="\n".join(content_parts),
            tool_calls=tool_calls,
            raw=data,
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
        )


class OllamaProvider(ModelProvider):
    """Local Ollama provider."""

    def __init__(self, model: str = "llama3.1", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def name(self) -> str:
        return f"ollama:{self.model}"

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return ModelResponse(
            content=data.get("message", {}).get("content", ""),
            raw=data,
            model=self.model,
        )


def parse_model_string(model_str: str) -> ModelProvider:
    """Parse a model string like 'openai:gpt-4o' or 'anthropic:claude-sonnet-4-20250514' into a provider.

    Formats:
        openai:model-name
        anthropic:model-name
        ollama:model-name
        local:model-name (alias for ollama)
        model-name (defaults to openai)
    """
    if ":" in model_str:
        provider, model = model_str.split(":", 1)
    else:
        provider = "openai"
        model = model_str

    provider = provider.lower()

    if provider == "openai":
        return OpenAIProvider(model=model)
    elif provider == "anthropic":
        return AnthropicProvider(model=model)
    elif provider in ("ollama", "local"):
        return OllamaProvider(model=model)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use openai, anthropic, or ollama.")
