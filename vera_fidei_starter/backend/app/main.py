"""
Runner standalone do pipeline Vera.Fidei.

Uso:
    cd vera_fidei_starter/backend
    python -m app.main

Verifica que todos os agentes executam corretamente e exibe
o relatório consolidado para o exemplo padrão de São Cipriano.
"""
from pprint import pprint

from app.pipelines.citation_pipeline import run_citation_pipeline


if __name__ == "__main__":
    task = (
        'Verifique esta citação atribuída a São Cipriano: '
        '"Não pode ter Deus por Pai quem não tem a Igreja por Mãe."'
    )

    print("=" * 60)
    print("VERA.FIDEI — Pipeline de Verificação")
    print("=" * 60)
    print(f"Tarefa: {task}\n")

    report = run_citation_pipeline(task)

    print(f"execution_id : {report['execution_id']}")
    print(f"Veredito final: {report['final_verdict'].upper()}")
    print(f"Nível de segurança: {report['safety_level']}")
    print()
    print("Agentes executados:")
    for step in report["history"]:
        print(f"  [{step['status'].upper()}] {step['agent']} — {', '.join(step['notes'])}")
    print()
    print("Relatório completo:")
    pprint(report, sort_dicts=False)
