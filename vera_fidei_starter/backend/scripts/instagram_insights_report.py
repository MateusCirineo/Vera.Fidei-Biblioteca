"""Relatório de métricas do Instagram do Vera.Fidei — só leitura.

Lista os posts recentes com alcance/curtidas/comentários/salvamentos, pra
ajudar a decidir que tipo de conteúdo continuar fazendo. Não publica nem
modifica nada.

Uso:
    python scripts/instagram_insights_report.py
    python scripts/instagram_insights_report.py --limit 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from app.social.insights import account_summary, build_report  # noqa: E402
from app.social.instagram_publish import PublicationBlocked  # noqa: E402


def _fmt_caption(caption: str | None, width: int = 40) -> str:
    text = (caption or "(sem legenda)").replace("\n", " ").strip()
    return text[:width] + "…" if len(text) > width else text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=25, help="Quantos posts recentes buscar (padrão: 25).")
    args = parser.parse_args()

    try:
        account = account_summary()
    except PublicationBlocked as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    print(f"@{account.get('username', '?')} — {account.get('followers_count', '?')} seguidores, "
          f"{account.get('media_count', '?')} posts\n")

    report = build_report(limit=args.limit)
    if not report:
        print("Nenhum post encontrado.")
        return 0

    def score(item: dict) -> int:
        insights = item.get("insights") or {}
        return int(insights.get("total_interactions") or insights.get("reach") or 0)

    report.sort(key=score, reverse=True)

    header = f"{'Data':<12} {'Tipo':<10} {'Alcance':>8} {'Curtidas':>9} {'Coment.':>8} {'Salvos':>7}  Legenda"
    print(header)
    print("-" * len(header))
    for item in report:
        insights = item.get("insights") or {}
        if "error" in insights:
            print(f"{item.get('timestamp', '')[:10]:<12} {item.get('media_type', ''):<10} "
                  f"(sem métricas: {insights['error'][:60]})")
            continue
        print(
            f"{item.get('timestamp', '')[:10]:<12} "
            f"{item.get('media_type', ''):<10} "
            f"{insights.get('reach', 0):>8} "
            f"{insights.get('likes', 0):>9} "
            f"{insights.get('comments', 0):>8} "
            f"{insights.get('saved', 0):>7}  "
            f"{_fmt_caption(item.get('caption'))}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
