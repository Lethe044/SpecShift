"""
DiffResult uzerinden dogal dilde bir ozet uretir.

Bu modul tamamen istege baglidir. GROQ_API_KEY veya GEMINI_API_KEY ortam
degiskeni tanimli degilse, hicbir aga cikmadan sablon tabanli (rule-based)
bir ozet uretilir. Boylece proje hicbir ucretli servise bagimli olmadan
tam calisir durumda kalir.
"""

from __future__ import annotations

import os
from typing import Optional

import requests

from specshift.models import DiffResult, Severity

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

GEMINI_API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"

OPENAI_COMPATIBLE_URL_ENV = "SPECSHIFT_OPENAI_BASE_URL"


class AISummaryError(Exception):
    """AI ozeti uretilirken bir sorun olustugunda firlatilir."""


def generate_summary(
    result: DiffResult,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 30,
) -> str:
    """
    Mumkunse yapilandirilmis bir AI saglayicisi kullanarak, degilse sablon
    tabanli olarak dogal dilde bir ozet dondurur. Hicbir zaman istisna
    firlatarak calismayi durdurmaz; basarisiz olursa sablon ozete duser.
    """
    prompt = _build_prompt(result)

    chosen_provider = provider or _detect_provider()

    if chosen_provider == "groq" and os.environ.get("GROQ_API_KEY"):
        try:
            return _call_groq(prompt, model or GROQ_DEFAULT_MODEL, timeout)
        except AISummaryError:
            pass

    if chosen_provider == "gemini" and os.environ.get("GEMINI_API_KEY"):
        try:
            return _call_gemini(prompt, model or GEMINI_DEFAULT_MODEL, timeout)
        except AISummaryError:
            pass

    if chosen_provider == "openai_compatible" and os.environ.get("SPECSHIFT_API_KEY"):
        try:
            return _call_openai_compatible(prompt, model, timeout)
        except AISummaryError:
            pass

    return build_template_summary(result)


def _detect_provider() -> Optional[str]:
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("SPECSHIFT_API_KEY") and os.environ.get(OPENAI_COMPATIBLE_URL_ENV):
        return "openai_compatible"
    return None


def _build_prompt(result: DiffResult) -> str:
    counts = result.summary_counts()
    lines = [
        "Asagida bir API'nin iki surumu arasinda tespit edilen sozlesme "
        "(contract) degisikliklerinin listesi bulunuyor. Bu listeyi okuyup "
        "bu API'yi tuketen bir gelistiricinin anlayacagi, kisa, net ve "
        "profesyonel bir Turkce ozet yaz. Once en onemli kirici degisiklikleri "
        "vurgula, sonra dikkat edilmesi gerekenleri, en sonda onemsiz "
        "eklemeleri kisaca belirt. Liste veya baslik kullanma, akici paragraflar "
        "halinde yaz. Uydurma bilgi ekleme, sadece verilen degisikliklere dayan.",
        "",
        f"Toplam: {counts['breaking']} kirici, {counts['warning']} uyari, {counts['info']} bilgi amacli degisiklik.",
        "",
    ]
    for change in result.sorted_changes()[:60]:
        lines.append(f"- [{change.severity.value}] {change.location}: {change.message}")

    return "\n".join(lines)


def _call_groq(prompt: str, model: str, timeout: int) -> str:
    api_key = os.environ["GROQ_API_KEY"]
    try:
        response = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 700,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise AISummaryError(f"Groq istegi basarisiz oldu: {exc}") from exc


def _call_gemini(prompt: str, model: str, timeout: int) -> str:
    api_key = os.environ["GEMINI_API_KEY"]
    url = GEMINI_API_URL_TEMPLATE.format(model=model, key=api_key)
    try:
        response = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 700},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise AISummaryError(f"Gemini istegi basarisiz oldu: {exc}") from exc


def _call_openai_compatible(prompt: str, model: Optional[str], timeout: int) -> str:
    api_key = os.environ["SPECSHIFT_API_KEY"]
    base_url = os.environ[OPENAI_COMPATIBLE_URL_ENV].rstrip("/")
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or "default",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 700,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise AISummaryError(f"Ozel uc nokta istegi basarisiz oldu: {exc}") from exc


def build_template_summary(result: DiffResult) -> str:
    """API anahtari olmadan calisan, kural tabanli, deterministik ozet."""
    counts = result.summary_counts()

    if result.is_empty:
        return "Iki spesifikasyon arasinda herhangi bir fark tespit edilmedi."

    parts: list[str] = []

    if counts["breaking"] > 0:
        top_breaking = result.breaking_changes[:5]
        breaking_desc = "; ".join(f"{c.location} ({c.message.rstrip('.')})" for c in top_breaking)
        extra = counts["breaking"] - len(top_breaking)
        extra_note = f" ve {extra} kirici degisiklik daha" if extra > 0 else ""
        parts.append(
            f"Bu guncelleme {counts['breaking']} kirici degisiklik iceriyor ve mevcut API "
            f"tuketicilerini etkileyebilir. Ozellikle: {breaking_desc}{extra_note}. "
            "Bu API'yi kullanan istemcilerin gecis yapmadan once bu noktalari gozden gecirmesi onerilir."
        )
    else:
        parts.append(
            "Bu guncelleme herhangi bir kirici degisiklik icermiyor, mevcut istemciler "
            "ek bir aksiyon almadan calismaya devam edebilir."
        )

    if counts["warning"] > 0:
        parts.append(
            f"Ayrica {counts['warning']} adet dikkat edilmesi gereken degisiklik var; "
            "bunlar dogrudan kirici olmasa da bazi kullanim senaryolarinda davranis "
            "farkliligina yol acabilir."
        )

    if counts["info"] > 0:
        parts.append(
            f"Geriye kalan {counts['info']} degisiklik ise yeni ozellik veya iyilestirme "
            "niteliginde olup mevcut entegrasyonlar icin risk tasimiyor."
        )

    return " ".join(parts)
