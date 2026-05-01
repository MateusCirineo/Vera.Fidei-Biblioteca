"""
Benchmark de regressão do verificador Vera.Fidei.

Mede quatro categorias distintas para detectar regressões entre versões:
  - citações verdadeiras (acerto top-1 / top-3)
  - citações falsas inventadas (taxa de falso positivo)
  - citações falsas plausíveis (taxa de falso positivo)
  - citações parcialmente corretas / truncadas (taxa de falso positivo)

Uso:
    cd vera_fidei_starter/backend
    python scripts/benchmark.py [--verbose]
"""
from __future__ import annotations

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

TRUE_CITATIONS: list[dict] = [
    # Citações verdadeiras com fonte rastreável
    {
        "quote": "Habere iam non potest Deum patrem qui ecclesiam non habet matrem",
        "attributed_to": "São Cipriano de Cartago",
        "expected_author_fragment": "Cipriano",
        "description": "De Ecclesiae Catholicae Unitate — texto latino",
    },
    {
        "quote": "Quem não tem a Igreja por mãe não pode ter Deus por pai",
        "attributed_to": "São Cipriano",
        "expected_author_fragment": "Cipriano",
        "description": "De Unitate — tradução PT canônica",
    },
    {
        "quote": "Salus extra ecclesiam non est",
        "attributed_to": "São Cipriano",
        "expected_author_fragment": "Cipriano",
        "description": "Epístola ad Iubaianum — frase lapidar",
    },
    {
        "quote": "Tolle definitiones, tolle distinctiones, et quaecumque de fide dicuntur erunt absurda",
        "attributed_to": "Santo Tomás de Aquino",
        "expected_author_fragment": "Tomás",
        "description": "Texto escolástico sobre distinções",
    },
    {
        "quote": "Fecisti nos ad te et inquietum est cor nostrum donec requiescat in te",
        "attributed_to": "Santo Agostinho",
        "expected_author_fragment": "Agostinho",
        "description": "Confissões I,1 — latim",
    },
    {
        "quote": "Nosso coração está inquieto até que repousa em ti",
        "attributed_to": "Santo Agostinho",
        "expected_author_fragment": "Agostinho",
        "description": "Confissões I,1 — tradução PT",
    },
    {
        "quote": "Ama et fac quod vis",
        "attributed_to": "Santo Agostinho",
        "expected_author_fragment": "Agostinho",
        "description": "In Epistolam Ioannis — frase lapdar",
    },
    {
        "quote": "Dilige et quod vis fac",
        "attributed_to": "Santo Agostinho",
        "expected_author_fragment": "Agostinho",
        "description": "Variante latina de Ama et fac quod vis",
    },
    {
        "quote": "In necessariis unitas in dubiis libertas in omnibus caritas",
        "attributed_to": "Santo Agostinho",
        "expected_author_fragment": None,  # Atribuição histórica disputada — aceitar qualquer resultado
        "description": "Frase de autoria disputada — sistema deve ser conservador",
    },
    {
        "quote": "Gloria Dei vivens homo",
        "attributed_to": "Santo Ireneu de Lion",
        "expected_author_fragment": "Ireneu",
        "description": "Adversus Haereses IV — latim",
    },
]

FALSE_INVENTED: list[dict] = [
    # Citações completamente inventadas, sem base em texto real
    {
        "quote": "A fé sem inteligência é superstição; a inteligência sem fé é arrogância.",
        "attributed_to": "Santo Agostinho",
        "description": "Frase inventada — estrutura antitética moderna",
    },
    {
        "quote": "O amor é a ponte entre o coração e a eternidade divina.",
        "attributed_to": "São João da Cruz",
        "description": "Frase inventada com vocabulário espiritual genérico",
    },
    {
        "quote": "Deus não abandona aquele que o busca com sinceridade, mesmo no meio das trevas.",
        "attributed_to": "São Francisco de Assis",
        "description": "Paráfrase inventada, tema vago",
    },
    {
        "quote": "A verdade não precisa de defesa; ela se defende sozinha na luz da razão.",
        "attributed_to": "São Tomás de Aquino",
        "description": "Frase inventada com vocabulário iluminista",
    },
    {
        "quote": "O silêncio é a linguagem de Deus, tudo o mais é tradução imperfeita.",
        "attributed_to": "Santo Agostinho",
        "description": "Citação de Rumi frequentemente atribuída erroneamente a Agostinho",
    },
]

FALSE_PLAUSIBLE: list[dict] = [
    # Citações baseadas em texto real mas nunca escritas nessa forma exata
    {
        "quote": "Quem não tem a Igreja por mãe jamais alcançará a salvação eterna.",
        "attributed_to": "São Cipriano",
        "description": "Paráfrase de Cipriano — sentido ampliado, não é o texto real",
    },
    {
        "quote": "Nosso espírito encontra descanso somente quando repousa em Deus criador.",
        "attributed_to": "Santo Agostinho",
        "description": "Paráfrase das Confissões — sentido próximo mas formulação diferente",
    },
    {
        "quote": "A Igreja é mãe dos fiéis porque é esposa de Cristo.",
        "attributed_to": "São Cipriano",
        "description": "Síntese teológica plausível, mas não é citação direta",
    },
    {
        "quote": "Fora da unidade da Igreja não existe remissão dos pecados.",
        "attributed_to": "São Cipriano",
        "description": "Eco de Cipriano mas formulação não documentada",
    },
    {
        "quote": "O coração humano foi criado para Deus e não encontra paz em nenhuma criatura.",
        "attributed_to": "Santo Agostinho",
        "description": "Paráfrase das Confissões — conceito correto, texto diferente",
    },
]

PARTIALLY_CORRECT: list[dict] = [
    # Citações truncadas, remontadas ou com acréscimo
    {
        "quote": "Nosso coração está inquieto",
        "attributed_to": "Santo Agostinho",
        "description": "Confissões I,1 truncada — falta 'até que repousa em ti'",
    },
    {
        "quote": "Quem não tem a Igreja por mãe não pode ter Deus por pai — disse o mártir Cipriano em defesa da unidade",
        "attributed_to": "São Cipriano",
        "description": "Citação correta com acréscimo descritivo não presente no original",
    },
    {
        "quote": "Fecisti nos ad te, Domine, et inquietum est cor nostrum donec requiescat in te et in pace aeterna",
        "attributed_to": "Santo Agostinho",
        "description": "Confissões I,1 com acréscimo 'et in pace aeterna' não presente no original",
    },
    {
        "quote": "Habere non potest Deum patrem qui ecclesiam non habet matrem",
        "attributed_to": "São Cipriano",
        "description": "Variante de Cipriano sem 'iam' — pequena alteração textual",
    },
    {
        "quote": "Ama e faz o que queres, pois quem ama a Deus jamais pecará gravemente.",
        "attributed_to": "Santo Agostinho",
        "description": "Citação com acréscimo interpretativo — segunda cláusula não está no original",
    },
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

STATUS_POSITIVE = {"CONFIRMADA_EXATA", "CORRESPONDENCIA_FORTE", "TRADUCAO_FIEL", "TRADUCAO_IMPRECISA"}
STATUS_UNCERTAIN = {"PARAFRASE_PLAUSIVEL", "ATRIBUICAO_DUVIDOSA"}
STATUS_NEGATIVE = {"NAO_ENCONTRADA"}


def run_benchmark(verbose: bool = False) -> None:
    from services.verification_service import VerificationService
    from schemas.citation import VerifyCitationRequest

    svc = VerificationService()

    categories = [
        ("TRUE (verdadeiras)", TRUE_CITATIONS, "true"),
        ("FALSE_INVENTED (inventadas)", FALSE_INVENTED, "false_invented"),
        ("FALSE_PLAUSIBLE (plausíveis)", FALSE_PLAUSIBLE, "false_plausible"),
        ("PARTIALLY_CORRECT (truncadas/remontadas)", PARTIALLY_CORRECT, "partially_correct"),
    ]

    grand_times: list[float] = []
    context_confirms = 0
    context_total = 0

    for category_name, cases, category_type in categories:
        print(f"\n{'='*70}")
        print(f"  {category_name}")
        print(f"{'='*70}")

        results = []
        for case in cases:
            req = VerifyCitationRequest(
                quote=case["quote"],
                attributed_to=case.get("attributed_to", ""),
            )
            t0 = time.perf_counter()
            try:
                resp = svc.verify(req)
                elapsed = time.perf_counter() - t0
                status = resp.status_code
                author = resp.author or ""
                has_context = bool(resp.context_before or resp.context_after)
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                status = "ERROR"
                author = ""
                has_context = False
                if verbose:
                    print(f"  ERRO: {exc}")

            grand_times.append(elapsed)
            results.append((case, status, author, elapsed, has_context))

            # Context confirmation: did context_before/after exist for a match?
            if category_type == "true" and status in STATUS_POSITIVE:
                context_total += 1
                if has_context:
                    context_confirms += 1

            marker = "✓" if category_type == "true" and status in STATUS_POSITIVE else (
                "✗" if category_type != "true" and status in STATUS_POSITIVE else "~"
            )
            if verbose:
                print(f"  [{marker}] {case['description'][:55]:<55} → {status:<25} ({elapsed:.2f}s)")

        # Category stats
        if category_type == "true":
            top1 = sum(1 for _, s, _, _, _ in results if s in STATUS_POSITIVE)
            top3_uncertain = sum(1 for _, s, _, _, _ in results if s in STATUS_POSITIVE | STATUS_UNCERTAIN)
            print(f"\n  Acerto top-1 (positivo):      {top1}/{len(results)} ({top1/len(results):.0%})")
            print(f"  Acerto top-3 (incl. incerto): {top3_uncertain}/{len(results)} ({top3_uncertain/len(results):.0%})")
        else:
            fp = sum(1 for _, s, _, _, _ in results if s in STATUS_POSITIVE)
            fp_uncertain = sum(1 for _, s, _, _, _ in results if s in STATUS_UNCERTAIN)
            print(f"\n  Falso positivo (classificação positiva): {fp}/{len(results)} ({fp/len(results):.0%})")
            print(f"  Incerto (PARAFRASE/ATRIBUICAO):          {fp_uncertain}/{len(results)} ({fp_uncertain/len(results):.0%})")

    # Summary
    print(f"\n{'='*70}")
    print("  RESUMO GERAL")
    print(f"{'='*70}")
    avg_time = sum(grand_times) / len(grand_times) if grand_times else 0
    print(f"  Tempo médio por verificação: {avg_time:.2f}s")
    print(f"  Total de verificações:       {len(grand_times)}")
    if context_total:
        pct = context_confirms / context_total
        print(f"  Contexto adjacente confirmado: {context_confirms}/{context_total} ({pct:.0%})")
    print()
    print("  ⚠  Rodar antes e depois de cada mudança de feature para detectar regressão.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vera.Fidei regression benchmark")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mostrar resultado caso a caso")
    args = parser.parse_args()
    run_benchmark(verbose=args.verbose)
