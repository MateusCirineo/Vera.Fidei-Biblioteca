"""
Gerador de cupons Stripe para o Vera.Fidei.

Uso rapido:
    python create_test_coupons.py sk_test_SUACHAVE

Padrao do uso rapido:
    codigos aleatorios com prefixo COLEGIO
    30% de desconto
    desconto recorrente para sempre enquanto a assinatura continuar ativa
    uso unico por codigo

Uso avancado:
    python create_test_coupons.py sk_test_SUACHAVE --prefix COLEGIO --percent 30 --forever --count 5
    python create_test_coupons.py sk_test_SUACHAVE --prefix PROMO --percent 20 --months 3 --count 10
"""

from __future__ import annotations

import argparse
import csv
import secrets
import string
import sys
from datetime import datetime
from pathlib import Path

import stripe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gerador de cupons Vera.Fidei")
    parser.add_argument("api_key", help="Chave secreta Stripe: sk_test_... ou sk_live_...")
    parser.add_argument("--prefix", default="COLEGIO", help="Prefixo dos codigos. Padrao: COLEGIO")
    parser.add_argument("--percent", type=int, default=30, help="Percentual de desconto. Padrao: 30")
    parser.add_argument("--forever", action="store_true", help="Desconto permanente enquanto assinatura ativa")
    parser.add_argument("--months", type=int, default=None, help="Desconto por N meses")
    parser.add_argument("--count", type=int, default=5, help="Quantidade de codigos. Padrao: 5")
    parser.add_argument("--name", default=None, help="Nome descritivo do coupon no Stripe")
    parser.add_argument("--sequential", action="store_true", help="Gerar COLEGIO01, COLEGIO02... em vez de aleatorio")
    parser.add_argument("--out", default=None, help="Arquivo CSV de saida. Padrao: coupons/coupons_<prefix>_<data>.csv")
    return parser.parse_args()


def build_coupon_args(args: argparse.Namespace) -> tuple[dict, str]:
    if not (1 <= args.percent <= 100):
        raise ValueError("--percent deve estar entre 1 e 100.")
    if not (1 <= args.count <= 500):
        raise ValueError("--count deve estar entre 1 e 500.")
    if args.forever and args.months is not None:
        raise ValueError("Use --forever OU --months N, nao os dois.")

    # Sem flags de duracao, o padrao do Vera.Fidei e desconto recorrente.
    if args.forever or args.months is None:
        duration_label = "recorrente para sempre"
        coupon_args = {
            "percent_off": args.percent,
            "duration": "forever",
            "currency": "brl",
        }
    elif args.months == 1:
        duration_label = "primeiro mes"
        coupon_args = {
            "percent_off": args.percent,
            "duration": "once",
            "currency": "brl",
        }
    else:
        if not (2 <= args.months <= 24):
            raise ValueError("--months deve estar entre 1 e 24.")
        duration_label = f"{args.months} meses"
        coupon_args = {
            "percent_off": args.percent,
            "duration": "repeating",
            "duration_in_months": args.months,
            "currency": "brl",
        }

    coupon_args["name"] = args.name or f"Vera.Fidei - {args.percent}% off {duration_label} [{args.prefix.upper()}]"
    return coupon_args, duration_label


def generate_codes(prefix: str, count: int, sequential: bool) -> list[str]:
    prefix = prefix.strip().upper()
    if sequential:
        return [f"{prefix}{index:02d}" for index in range(1, count + 1)]

    alphabet = string.ascii_uppercase + string.digits
    codes: set[str] = set()
    while len(codes) < count:
        token = "".join(secrets.choice(alphabet) for _ in range(8))
        codes.add(f"{prefix}-{token}")
    return sorted(codes)


def main() -> None:
    args = parse_args()
    api_key = args.api_key.strip()
    stripe.api_key = api_key

    is_test = api_key.startswith("sk_test_")
    is_live = api_key.startswith("sk_live_")
    if not is_test and not is_live:
        print("Chave invalida. Use uma Secret key do Stripe começando com sk_test_ ou sk_live_.")
        sys.exit(1)

    try:
        coupon_args, duration_label = build_coupon_args(args)
    except ValueError as exc:
        print(f"Erro: {exc}")
        sys.exit(1)

    mode_label = "TESTE" if is_test else "PRODUCAO"
    prefix = args.prefix.strip().upper()

    print(f"\n{mode_label} - Criando coupon no Stripe...")
    print(f"  Desconto : {args.percent}%")
    print(f"  Duracao  : {duration_label}")
    mode = "sequenciais" if args.sequential else "aleatorios"
    print(f"  Codigos  : {args.count} codigos {mode} com prefixo {prefix}")
    print("  Uso      : 1 vez por codigo\n")

    coupon = stripe.Coupon.create(**coupon_args)
    print(f"Coupon criado: {coupon['id']}\n")

    output_path = Path(args.out) if args.out else Path("coupons") / f"coupons_{prefix.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    print("Promotion Codes criados:")
    print("-" * 45)
    for code in generate_codes(prefix, args.count, args.sequential):
        promo = stripe.PromotionCode.create(
            coupon=coupon["id"],
            code=code,
            max_redemptions=1,
        )
        rows.append(
            {
                "code": promo["code"],
                "promotion_code_id": promo["id"],
                "coupon_id": coupon["id"],
                "percent_off": args.percent,
                "duration": duration_label,
                "max_redemptions": 1,
                "mode": mode_label,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        print(f"  {promo['code']} -> {promo['id']}")

    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    discounted = round(9999 * (1 - args.percent / 100))
    print("-" * 45)
    print("\nPronto.")
    print(f"Magisterio: R$ 99,99 -> R$ {discounted / 100:.2f}/mes ({duration_label}).")
    print("Cada codigo so pode ser usado uma vez.")
    print(f"Lista salva em: {output_path}")


if __name__ == "__main__":
    main()
