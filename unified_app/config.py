from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Literal, Optional, Dict, Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "unified_config.json"


ProviderType = Literal["openai", "ollama", "lmstudio"]


@dataclass
class OpenAIConfig:
    api_key: str = ""
    model: str = "gpt-4o"


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    model: str = "ollama/llama3.2"


@dataclass
class LMStudioConfig:
    base_url: str = "http://192.168.2.129:1234/v1"
    model: str = "qwen/qwen3-4b-2507"
    api_key: str = ""  # LM Studio usually accepts any string


@dataclass
class AppConfig:
    provider: ProviderType = "openai"
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    lmstudio: LMStudioConfig = field(default_factory=LMStudioConfig)

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        if not path.exists():
            return cls()

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return cls()

        def _load_section(section_cls, key: str):
            data = raw.get(key, {}) or {}
            return section_cls(**{**asdict(section_cls()), **data})

        return cls(
            provider=raw.get("provider", "openai"),
            openai=_load_section(OpenAIConfig, "openai"),
            ollama=_load_section(OllamaConfig, "ollama"),
            lmstudio=_load_section(LMStudioConfig, "lmstudio"),
        )

    def save(self, path: Path = CONFIG_PATH) -> None:
        data: Dict[str, Any] = {
            "provider": self.provider,
            "openai": asdict(self.openai),
            "ollama": asdict(self.ollama),
            "lmstudio": asdict(self.lmstudio),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_graph_config(app_config: AppConfig) -> Dict[str, Any]:
    """
    Build a SmartScraperGraph-compatible config dict based on current provider.
    """
    provider = app_config.provider

    if provider == "openai":
        return {
            "llm": {
                "model_provider": "openai",
                "api_key": app_config.openai.api_key,
                "model": app_config.openai.model,
            },
            "verbose": True,
        }

    if provider == "ollama":
        return {
            "llm": {
                "model_provider": "ollama",
                "model": app_config.ollama.model,
                "temperature": 0,
                "format": "json",
                "base_url": app_config.ollama.base_url,
            },
            "embeddings": {
                "model": "ollama/nomic-embed-text",
                "base_url": app_config.ollama.base_url,
            },
            "verbose": True,
        }

    if provider == "lmstudio":
        return {
            "llm": {
                # LM Studio 暴露的是 OpenAI 兼容接口，在 ScrapeGraph 中按 openai 处理
                "model_provider": "openai",
                "api_key": app_config.lmstudio.api_key or "lm-studio",
                "model": f"openai/{app_config.lmstudio.model}",
                "base_url": app_config.lmstudio.base_url,
                "temperature": 0,
            },
            "verbose": True,
        }

    # Fallback – should not happen
    return {}



