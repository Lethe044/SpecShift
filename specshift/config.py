"""'.specshift.yml' yapilandirma dosyasini okuyup varsayilan degerlerle birlestirir."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_CONFIG_FILENAMES = (".specshift.yml", ".specshift.yaml")


@dataclass
class SpecShiftConfig:
    spec_path: str = "openapi.yaml"
    base_ref: str = "main"
    fail_on: str = "breaking"  # breaking | warning | none
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    slack_webhook: Optional[str] = None
    discord_webhook: Optional[str] = None
    ignore_paths: list = field(default_factory=list)

    @classmethod
    def load(cls, path: Optional[str] = None) -> "SpecShiftConfig":
        candidates = [path] if path else list(DEFAULT_CONFIG_FILENAMES)

        for candidate in candidates:
            if not candidate:
                continue
            file_path = Path(candidate)
            if file_path.exists():
                data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
                return cls._from_dict(data)

        return cls()

    @classmethod
    def _from_dict(cls, data: dict) -> "SpecShiftConfig":
        return cls(
            spec_path=data.get("spec_path", cls.spec_path),
            base_ref=data.get("base_ref", cls.base_ref),
            fail_on=data.get("fail_on", cls.fail_on),
            ai_provider=data.get("ai_provider"),
            ai_model=data.get("ai_model"),
            slack_webhook=data.get("slack_webhook"),
            discord_webhook=data.get("discord_webhook"),
            ignore_paths=data.get("ignore_paths", []),
        )


def write_default_config(path: str = ".specshift.yml") -> None:
    content = """\
# specshift yapilandirma dosyasi
# Detayli aciklamalar icin: https://github.com/Lethe044/specshift

# Takip edilecek OpenAPI/Swagger dosyasinin yolu (repo kokune gore)
spec_path: openapi.yaml

# Karsilastirma yapilacak temel git referansi (branch, tag veya commit)
base_ref: main

# CI'da hangi seviyede build'in basarisiz sayilacagini belirler: breaking | warning | none
fail_on: breaking

# Istege bagli: dogal dil ozeti icin AI saglayicisi (groq | gemini | openai_compatible)
# API anahtari ortam degiskeni olarak verilmelidir: GROQ_API_KEY veya GEMINI_API_KEY
# ai_provider: groq
# ai_model: llama-3.3-70b-versatile

# Istege bagli: bildirim webhook adresleri
# slack_webhook: https://hooks.slack.com/services/...
# discord_webhook: https://discord.com/api/webhooks/...

# Diff sirasinda yok sayilacak path desenleri (opsiyonel)
ignore_paths: []
"""
    Path(path).write_text(content, encoding="utf-8")
