"""SpecShift komut satiri arayuzu."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Optional

from specshift import __version__
from specshift.ai_summary import generate_summary
from specshift.config import SpecShiftConfig, write_default_config
from specshift.differ import diff_specs
from specshift.git_utils import GitError, load_spec_from_git
from specshift.models import DiffResult
from specshift.notifier import NotifyError, notify_discord, notify_slack
from specshift.reporter import print_console_report, render_json_report, render_markdown_report
from specshift.spec_loader import SpecLoadError, load_spec

CACHE_DIR = Path(".specshift_cache")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="specshift",
        description="OpenAPI/Swagger spesifikasyonlarindaki degisiklikleri tespit eder ve siniflandirir.",
    )
    parser.add_argument("--version", action="version", version=f"specshift {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    diff_parser = subparsers.add_parser("diff", help="Iki spesifikasyonu karsilastir")
    diff_parser.add_argument("old", help="Eski spesifikasyon: dosya yolu veya URL")
    diff_parser.add_argument("new", help="Yeni spesifikasyon: dosya yolu veya URL")
    _add_common_diff_args(diff_parser)

    check_parser = subparsers.add_parser(
        "check", help="CI icin: mevcut spesifikasyonu bir git referansiyla karsilastirir"
    )
    check_parser.add_argument("--spec", help="Spesifikasyon dosyasinin yolu (config'i gecersiz kilar)")
    check_parser.add_argument("--base-ref", help="Karsilastirilacak git referansi (config'i gecersiz kilar)")
    check_parser.add_argument("--config", default=None, help="Yapilandirma dosyasinin yolu")
    _add_common_diff_args(check_parser)

    watch_parser = subparsers.add_parser(
        "watch", help="Bir URL'yi periyodik olarak izler, degisiklik oldugunda bildirim gonderir"
    )
    watch_parser.add_argument("url", help="Izlenecek OpenAPI spesifikasyonu URL'si")
    watch_parser.add_argument("--interval", type=int, default=300, help="Kontrol araligi (saniye), varsayilan 300")
    watch_parser.add_argument("--once", action="store_true", help="Sadece bir kez kontrol et ve cik")
    watch_parser.add_argument("--slack-webhook", help="Slack webhook URL'si")
    watch_parser.add_argument("--discord-webhook", help="Discord webhook URL'si")
    watch_parser.add_argument("--ai", action="store_true", help="Bildirimlere AI ozeti ekle")
    watch_parser.add_argument("--ai-provider", choices=["groq", "gemini", "openai_compatible"], default=None)

    init_parser = subparsers.add_parser("init", help="Ornek .specshift.yml yapilandirma dosyasi olusturur")
    init_parser.add_argument("--path", default=".specshift.yml", help="Olusturulacak dosyanin yolu")
    init_parser.add_argument("--force", action="store_true", help="Var olan dosyanin uzerine yaz")

    return parser


def _add_common_diff_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format", choices=["console", "markdown", "json"], default="console", help="Cikti formati"
    )
    parser.add_argument("--output", help="Ciktiyi bir dosyaya yazar (verilmezse stdout'a yazilir)")
    parser.add_argument("--ai", action="store_true", help="Yapay zeka ile dogal dil ozeti uret")
    parser.add_argument(
        "--ai-provider", choices=["groq", "gemini", "openai_compatible"], default=None, help="AI saglayicisi"
    )
    parser.add_argument("--ai-model", default=None, help="Kullanilacak AI model adi")
    parser.add_argument(
        "--fail-on",
        choices=["breaking", "warning", "none"],
        default="breaking",
        help="Hangi seviyede sifir olmayan cikis kodu donulecegini belirler",
    )
    parser.add_argument("--quiet", action="store_true", help="Sadece ozet satirini yazdir")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "diff":
            return _run_diff(args)
        if args.command == "check":
            return _run_check(args)
        if args.command == "watch":
            return _run_watch(args)
        if args.command == "init":
            return _run_init(args)
    except (SpecLoadError, GitError) as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nDurduruldu.")
        return 130

    parser.print_help()
    return 1


def _run_diff(args: argparse.Namespace) -> int:
    old_spec = load_spec(args.old)
    new_spec = load_spec(args.new)
    result = diff_specs(old_spec, new_spec)
    return _emit_result(result, args)


def _run_check(args: argparse.Namespace) -> int:
    config = SpecShiftConfig.load(args.config)
    spec_path = args.spec or config.spec_path
    base_ref = args.base_ref or config.base_ref

    old_spec = load_spec_from_git(spec_path, base_ref)
    new_spec = load_spec(spec_path)

    result = diff_specs(old_spec, new_spec)

    if not args.ai_provider and config.ai_provider:
        args.ai_provider = config.ai_provider
    if not args.ai_model and config.ai_model:
        args.ai_model = config.ai_model
    if args.fail_on == "breaking" and config.fail_on != "breaking":
        args.fail_on = config.fail_on

    exit_code = _emit_result(result, args)

    if config.slack_webhook or config.discord_webhook:
        ai_summary = None
        if args.ai:
            ai_summary = generate_summary(result, provider=args.ai_provider, model=args.ai_model)
        _send_notifications(result, config.slack_webhook, config.discord_webhook, ai_summary)

    return exit_code


def _emit_result(result: DiffResult, args: argparse.Namespace) -> int:
    ai_summary = None
    if args.ai:
        ai_summary = generate_summary(result, provider=args.ai_provider, model=args.ai_model)

    output_text: str
    if args.format == "json":
        output_text = render_json_report(result, ai_summary=ai_summary)
    elif args.format == "markdown":
        output_text = render_markdown_report(result, ai_summary=ai_summary)
    else:
        output_text = None  # console formati dogrudan yazdirilir

    if args.format == "console":
        if args.output:
            from specshift.reporter import render_plain_text_report

            Path(args.output).write_text(render_plain_text_report(result), encoding="utf-8")
            if not args.quiet:
                print(f"Rapor yazildi: {args.output}")
        else:
            print_console_report(result, verbose=not args.quiet)
            if ai_summary:
                print(f"\nYapay Zeka Ozeti:\n{ai_summary}")
    else:
        if args.output:
            Path(args.output).write_text(output_text, encoding="utf-8")
            print(f"Rapor yazildi: {args.output}")
        else:
            print(output_text)

    return _exit_code_for(result, args.fail_on)


def _exit_code_for(result: DiffResult, fail_on: str) -> int:
    if fail_on == "none":
        return 0
    if fail_on == "warning":
        return 1 if (result.has_breaking_changes or result.warnings) else 0
    return 1 if result.has_breaking_changes else 0


def _run_init(args: argparse.Namespace) -> int:
    target = Path(args.path)
    if target.exists() and not args.force:
        print(f"'{target}' zaten mevcut. Uzerine yazmak icin --force kullanin.", file=sys.stderr)
        return 1

    write_default_config(str(target))
    print(f"Yapilandirma dosyasi olusturuldu: {target}")
    return 0


def _run_watch(args: argparse.Namespace) -> int:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_key = hashlib.sha256(args.url.encode("utf-8")).hexdigest()[:16]
    cache_file = CACHE_DIR / f"{cache_key}.json"

    while True:
        try:
            current_spec = load_spec(args.url)
        except SpecLoadError as exc:
            print(f"Uyari: spesifikasyon alinamadi ({exc}), tekrar denenecek.", file=sys.stderr)
            if args.once:
                return 2
            time.sleep(args.interval)
            continue

        if cache_file.exists():
            previous_spec = json.loads(cache_file.read_text(encoding="utf-8"))
            result = diff_specs(previous_spec, current_spec)

            if not result.is_empty:
                print_console_report(result)
                ai_summary = None
                if args.ai:
                    ai_summary = generate_summary(result, provider=args.ai_provider)

                _send_notifications(result, args.slack_webhook, args.discord_webhook, ai_summary)
            else:
                print("Degisiklik bulunamadi.")
        else:
            print(f"Ilk anlik goruntu kaydedildi: {args.url}")

        cache_file.write_text(json.dumps(current_spec), encoding="utf-8")

        if args.once:
            return 0

        time.sleep(args.interval)


def _send_notifications(
    result: DiffResult, slack_webhook: Optional[str], discord_webhook: Optional[str], ai_summary: Optional[str]
) -> None:
    if result.is_empty:
        return

    if slack_webhook:
        try:
            notify_slack(slack_webhook, result, ai_summary=ai_summary)
        except NotifyError as exc:
            print(f"Slack bildirimi gonderilemedi: {exc}", file=sys.stderr)

    if discord_webhook:
        try:
            notify_discord(discord_webhook, result, ai_summary=ai_summary)
        except NotifyError as exc:
            print(f"Discord bildirimi gonderilemedi: {exc}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
