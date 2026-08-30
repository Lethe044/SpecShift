"""Dosyadan, URL'den veya ham metinden OpenAPI/Swagger spesifikasyonu yukler."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import requests
import yaml


class SpecLoadError(Exception):
    """Spesifikasyon yuklenemedigi zaman firlatilir."""


def _parse_text(text: str, hint: str = "") -> dict:
    """Metni once JSON, olmazsa YAML olarak ayristirmaya calisir."""
    stripped = text.strip()
    if not stripped:
        raise SpecLoadError(f"Bos icerik: {hint}")

    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    try:
        data = yaml.safe_load(stripped)
    except yaml.YAMLError as exc:
        raise SpecLoadError(f"YAML/JSON ayristirma hatasi ({hint}): {exc}") from exc

    if not isinstance(data, dict):
        raise SpecLoadError(f"Spesifikasyon bir obje (mapping) degil: {hint}")

    return data


def parse_spec_text(text: str, hint: str = "") -> dict:
    """Disaridan cagrilabilen genel metin ayristirma fonksiyonu."""
    return _parse_text(text, hint=hint)


def is_url(source: str) -> bool:
    return bool(re.match(r"^https?://", source.strip(), re.IGNORECASE))


def load_spec(source: str, timeout: int = 15) -> dict:
    """
    Bir OpenAPI/Swagger spesifikasyonunu yukler.

    source bir URL, bir dosya yolu veya dogrudan JSON/YAML metni olabilir.
    """
    source = source.strip()

    if is_url(source):
        return _load_from_url(source, timeout=timeout)

    path = Path(source)
    if path.exists() and path.is_file():
        return _load_from_file(path)

    if source.startswith("{") or "openapi:" in source or "swagger:" in source:
        return _parse_text(source, hint="satir ici metin")

    raise SpecLoadError(
        f"Kaynak bulunamadi veya taninmadi: '{source}'. "
        "Bir dosya yolu, http(s) URL veya JSON/YAML metni bekleniyor."
    )


def _load_from_url(url: str, timeout: int = 15) -> dict:
    try:
        response = requests.get(url, timeout=timeout, headers={"Accept": "application/json, text/yaml, */*"})
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SpecLoadError(f"URL alinamadi '{url}': {exc}") from exc

    return _parse_text(response.text, hint=url)


def _load_from_file(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecLoadError(f"Dosya okunamadi '{path}': {exc}") from exc

    return _parse_text(text, hint=str(path))


def resolve_ref(ref: str, root_spec: dict) -> dict:
    """
    '#/components/schemas/User' gibi bir JSON pointer referansini cozer.
    Cozulemezse bos bir sozluk doner.
    """
    if not ref.startswith("#/"):
        return {}

    parts = ref[2:].split("/")
    node: Any = root_spec
    for part in parts:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return {}

    return node if isinstance(node, dict) else {}


def resolve_schema(schema: dict, root_spec: dict, _depth: int = 0) -> dict:
    """Bir semadaki $ref alanini gerekirse takip ederek gercek semayi doner."""
    if _depth > 20 or not isinstance(schema, dict):
        return schema if isinstance(schema, dict) else {}

    if "$ref" in schema:
        resolved = resolve_ref(schema["$ref"], root_spec)
        return resolve_schema(resolved, root_spec, _depth + 1)

    return schema
