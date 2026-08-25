"""Executa os agentes de Instagram do Vera.Fidei.

O padrão é gerar uma prévia local auditável. ``--publish`` apenas solicita a
etapa remota; ela ainda exige template aprovado, flag de produção, credenciais
rotacionadas e pacote íntegro.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.dispatcher import PipelineDispatcher  # noqa: E402
from app.social.instagram_publish import validate_instagram_connection  # noqa: E402
from app.social.ledger import SocialLedger  # noqa: E402
from app.social.package import (  # noqa: E402
    approve_current_style,
    publish_package,
    style_is_approved,
)
from core.config import settings  # noqa: E402
from app.social.scheduled_run import publication_readiness, run_scheduled_post  # noqa: E402


def _print_pipeline(ctx) -> None:
    print(f"execution_id: {ctx.execution_id}")
    print("processo:")
    for result in ctx.history:
        print(f"  - {result.agent_name}: {result.status}")
        for note in result.notes:
            print(f"      {note}")
        for warning in result.warnings:
            print(f"      AVISO: {warning}")
    package = ctx.findings.get("social_package")
    if package:
        print(f"prévia: {Path(package).resolve()}")
        for index in range(1, 4):
            print(f"  slide {index}: {(Path(package) / f'slide_{index}.png').resolve()}")
        print(f"  legenda: {(Path(package) / 'caption.txt').resolve()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author", help="autor canônico; sem isso, usa o rodízio seguro")
    parser.add_argument("--day", type=int, help="dia do ano para reprodução determinística")
    parser.add_argument("--publish", action="store_true", help="solicita publicação após todas as travas")
    parser.add_argument("--approve-style", metavar="PACKAGE", help="aprova o estilo visto nesse pacote")
    parser.add_argument("--check-api", action="store_true", help="teste somente leitura das credenciais")
    parser.add_argument("--status", action="store_true", help="mostra se o estilo atual está aprovado")
    parser.add_argument("--readiness", action="store_true", help="mostra as travas sem exibir segredos")
    parser.add_argument("--scheduled", action="store_true", help="executa a rotina diária idempotente")
    parser.add_argument("--publish-package", metavar="PACKAGE", help="publica um pacote já aprovado")
    args = parser.parse_args()

    if args.approve_style:
        approval = approve_current_style(args.approve_style)
        print(json.dumps(approval, ensure_ascii=False, indent=2))
        return 0
    if args.check_api:
        print(json.dumps(validate_instagram_connection(), ensure_ascii=False, indent=2))
        return 0
    if args.status:
        print(json.dumps({"style_approved": style_is_approved()}, indent=2))
        return 0
    if args.readiness:
        readiness = publication_readiness()
        print(json.dumps(readiness, ensure_ascii=False, indent=2))
        return 0 if readiness["ready"] else 2
    if args.scheduled:
        outcome = run_scheduled_post()
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
        return 0 if outcome["status"] in {"published", "already_published_today"} else 2
    if args.publish_package:
        media_id = publish_package(
            args.publish_package,
            SocialLedger(settings.social_ledger_path),
        )
        print(json.dumps({"status": "published", "remote_media_id": media_id}, indent=2))
        return 0

    ctx = PipelineDispatcher().run(
        "Gerar carrossel rastreável para o Instagram do Vera.Fidei",
        initial_findings={
            "social_options": {
                "author": args.author,
                "day": args.day,
                "publish_requested": args.publish,
            }
        },
    )
    _print_pipeline(ctx)
    failed = any(result.status in {"error", "blocked"} for result in ctx.history[:-1])
    publish_result = ctx.reports.get("social_publish_agent") or {}
    if args.publish and not publish_result.get("remote_media_id"):
        return 2
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
