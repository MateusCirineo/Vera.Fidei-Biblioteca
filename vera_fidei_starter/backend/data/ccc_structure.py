"""
Estrutura dos artigos do Catecismo da Igreja Católica (CCC).
Mapeia intervalos de artigos → título da seção e temas para busca no acervo.
"""
from __future__ import annotations

# (artigo_início, artigo_fim, título_pt, temas_para_busca)
CCC_SECTIONS: list[tuple[int, int, str, list[str]]] = [
    # PRÓLOGO
    (1, 25, "Prólogo — A vida em Cristo", [
        "beatitude", "vocação cristã", "Deus", "Cristo", "fim do homem",
    ]),

    # PARTE I — SEÇÃO I: "Creio" / "Cremos"
    (26, 49, "A capacidade do homem para Deus", [
        "Deus", "desejo de Deus", "razão", "religião", "ateísmo", "dignidade humana",
    ]),
    (50, 73, "A Revelação de Deus", [
        "revelação divina", "palavra de Deus", "profeta", "Escritura", "Aliança",
    ]),
    (74, 100, "Transmissão da Revelação — Tradição e Magistério", [
        "Tradição", "Magistério", "apóstolos", "sucessão apostólica", "depósito da fé",
    ]),
    (101, 141, "Sagrada Escritura — inspiração e interpretação", [
        "Sagrada Escritura", "Bíblia", "inspiração", "cânon", "sentido literal",
        "sentido espiritual", "Antigo Testamento", "Novo Testamento",
    ]),
    (142, 184, "A resposta do homem a Deus — A Fé", [
        "fé", "credo", "obediência da fé", "Abraão", "liberdade",
    ]),

    # PARTE I — SEÇÃO II: Profissão da Fé Cristã
    (185, 197, "Os símbolos da fé — Credo Niceno-Constantinopolitano", [
        "credo", "símbolo da fé", "Niceia", "batismo",
    ]),
    (198, 231, "Creio em Deus — Deus Uno e Único", [
        "Deus", "monoteísmo", "nomes de Deus", "Jahvé", "onipotência divina",
    ]),
    (232, 267, "A Santíssima Trindade", [
        "Trindade", "Pai", "Filho", "Espírito Santo", "pessoa divina", "consubstancial",
        "processão", "missão divina",
    ]),
    (268, 327, "O Pai Todo-Poderoso — A Criação", [
        "criação", "Criador", "céu e terra", "providência divina", "mal", "livre-arbítrio",
    ]),
    (328, 354, "Os Anjos", [
        "anjos", "seres espirituais", "querubins", "serafins", "anjo guardião", "demônios",
    ]),
    (355, 384, "O homem criado à imagem de Deus", [
        "imagem de Deus", "alma", "corpo", "dignidade humana", "unidade do homem",
        "inteligência", "vontade",
    ]),
    (385, 421, "A queda — O pecado original", [
        "pecado original", "Adão", "queda", "concupiscência", "tentação", "diabo",
        "consequências do pecado",
    ]),

    # Encarnação e vida de Cristo
    (422, 483, "O Filho de Deus se fez homem — Encarnação", [
        "Encarnação", "Verbo encarnado", "Filho de Deus", "natureza divina", "natureza humana",
        "hipostática", "Emmanuel",
    ]),
    (484, 534, "Maria e o nascimento de Cristo", [
        "Maria", "Virgem Maria", "Imaculada Conceição", "Mãe de Deus", "Anunciação",
        "Theotokos", "virgindade", "nascimento de Cristo",
    ]),
    (535, 570, "Batismo e vida pública de Jesus", [
        "batismo de Jesus", "Transfiguração", "milagres de Jesus", "tentação de Jesus",
        "pregação do Reino", "parábolas",
    ]),
    (571, 630, "A Paixão e morte de Cristo", [
        "Paixão", "crucificação", "morte de Cristo", "redenção", "expiação",
        "sacrifício", "sofrimento redentor", "cruz",
    ]),
    (631, 658, "A Ressurreição de Cristo", [
        "Ressurreição", "sepulcro vazio", "aparições do Ressuscitado", "vida nova",
        "primeiro nascido dos mortos",
    ]),
    (659, 682, "A Ascensão e segunda vinda de Cristo", [
        "Ascensão", "glória de Cristo", "julgamento final", "segunda vinda", "Parusia",
        "Cristo Rei",
    ]),

    # Espírito Santo e Igreja
    (683, 747, "O Espírito Santo", [
        "Espírito Santo", "Paráclito", "dons do Espírito", "Pentecostes",
        "frutos do Espírito", "carismas",
    ]),
    (748, 810, "A Igreja — origem e natureza", [
        "Igreja", "povo de Deus", "corpo de Cristo", "sacramento universal de salvação",
        "missão da Igreja",
    ]),
    (811, 870, "A Igreja — hierarquia, Papa e bispos", [
        "Papa", "episcopado", "sucessão apostólica", "primado de Pedro", "infalibilidade",
        "concílio ecumênico", "colegialidade",
    ]),
    (871, 945, "Os fiéis — leigos e vida consagrada", [
        "laicado", "vida religiosa", "consagrados", "missão dos leigos", "sacerdócio comum",
    ]),
    (946, 962, "A comunhão dos santos", [
        "comunhão dos santos", "intercessão dos santos", "méritos", "oração pelos mortos",
    ]),
    (963, 975, "Maria — Mãe da Igreja", [
        "Maria", "Mãe de Deus", "Assunção de Maria", "Medianeira", "invocação de Maria",
    ]),
    (976, 987, "O perdão dos pecados", [
        "perdão dos pecados", "absolvição", "conversão", "reconciliação", "chaves do Reino",
    ]),
    (988, 1065, "A ressurreição dos mortos e a vida eterna", [
        "ressurreição da carne", "céu", "inferno", "purgatório", "juízo final",
        "vida eterna", "bem-aventuranças eternas", "escatologia",
    ]),

    # PARTE II — SACRAMENTOS
    (1066, 1112, "A Liturgia — celebração do mistério pascal", [
        "liturgia", "culto cristão", "mistério pascal", "celebração", "ação litúrgica",
    ]),
    (1113, 1209, "Os sacramentos em geral", [
        "sacramentos", "graça sacramental", "sinais sagrados", "ex opere operato",
        "matéria e forma", "ministro do sacramento",
    ]),
    (1210, 1284, "O Batismo", [
        "batismo", "renascimento pela água", "purificação do pecado original",
        "fé batismal", "catecumenato", "incorporação à Igreja",
    ]),
    (1285, 1321, "A Confirmação", [
        "confirmação", "crisma", "Espírito Santo", "dons do Espírito", "selo do Espírito",
        "madureza cristã",
    ]),
    (1322, 1419, "A Eucaristia", [
        "eucaristia", "missa", "transubstanciação", "corpo e sangue de Cristo",
        "sacrifício eucarístico", "comunhão", "presença real", "ceia do Senhor",
        "memorial", "pão eucarístico",
    ]),
    (1420, 1498, "Penitência e Reconciliação", [
        "confissão", "penitência", "absolvição", "arrependimento", "contrição",
        "satisfação", "sacramento da reconciliação", "conversão",
    ]),
    (1499, 1532, "Unção dos Enfermos", [
        "unção dos enfermos", "doentes", "sofrimento", "cura", "viatico",
        "extrema-unção",
    ]),
    (1533, 1600, "A Ordem Sacerdotal", [
        "sacerdócio", "ordem sagrada", "presbítero", "diácono", "bispo", "ordenação",
        "ministério ordenado", "celibato sacerdotal",
    ]),
    (1601, 1666, "O Matrimônio", [
        "matrimônio", "casamento", "família", "amor conjugal", "fidelidade",
        "indissolubilidade", "fecundidade",
    ]),
    (1667, 1690, "Sacramentais e piedade popular", [
        "sacramentais", "bênçãos", "morte cristã", "exéquias", "piedade popular",
    ]),

    # PARTE III — VIDA EM CRISTO (SEÇÃO I)
    (1691, 1756, "A dignidade da pessoa humana e a liberdade", [
        "dignidade humana", "liberdade", "ato humano", "imputabilidade", "intenção",
    ]),
    (1757, 1802, "A moralidade dos atos humanos e a consciência moral", [
        "consciência moral", "atos morais", "objeto moral", "circunstâncias",
        "lei moral", "norma objetiva",
    ]),
    (1803, 1845, "As virtudes cardinais e teologais", [
        "virtudes", "prudência", "justiça", "fortaleza", "temperança",
        "fé", "esperança", "caridade", "dons do Espírito", "beatitudes",
    ]),
    (1846, 1876, "O pecado — espécies e consequências", [
        "pecado", "pecado mortal", "pecado venial", "vícios capitais", "conversão",
        "ofensa a Deus",
    ]),
    (1877, 1948, "A comunidade humana e o bem comum", [
        "bem comum", "justiça social", "solidariedade", "autoridade civil",
        "princípio de subsidiariedade",
    ]),
    (1949, 2051, "A lei moral e a graça salvífica", [
        "lei moral", "lei natural", "lei antiga", "lei nova", "graça",
        "justificação", "mérito", "santificação", "santos",
    ]),

    # PARTE III — OS DEZ MANDAMENTOS (SEÇÃO II)
    (2052, 2082, "Os Dez Mandamentos em geral", [
        "decálogo", "mandamentos", "lei divina", "obrigação moral",
    ]),
    (2083, 2141, "Primeiro mandamento — adoração e fé em Deus", [
        "adoração", "idolatria", "fé", "esperança", "magia", "superstição",
        "ateísmo prático", "religião",
    ]),
    (2142, 2167, "Segundo mandamento — o nome de Deus", [
        "nome de Deus", "blasfêmia", "juramento falso", "promessa", "respeito ao sagrado",
    ]),
    (2168, 2195, "Terceiro mandamento — santificação do domingo", [
        "domingo", "descanso", "Sabbath", "culto dominical", "santificação do dia do Senhor",
    ]),
    (2196, 2257, "Quarto mandamento — família e autoridade", [
        "família", "pais e filhos", "autoridade dos pais", "obediência", "estado",
        "deveres cívicos",
    ]),
    (2258, 2330, "Quinto mandamento — a vida humana", [
        "vida humana", "homicídio", "guerra justa", "pena de morte", "aborto",
        "eutanásia", "suicídio", "legítima defesa",
    ]),
    (2331, 2400, "Sexto mandamento — castidade e sexualidade", [
        "castidade", "sexualidade humana", "pureza", "amor conjugal", "virgindade",
        "fidelidade conjugal", "contracepção",
    ]),
    (2401, 2463, "Sétimo mandamento — propriedade e justiça social", [
        "propriedade", "roubo", "justiça distributiva", "pobreza", "solidariedade",
        "trabalho", "doutrina social",
    ]),
    (2464, 2513, "Oitavo mandamento — verdade e testemunho", [
        "verdade", "mentira", "testemunho falso", "segredo profissional",
        "arte cristã", "meios de comunicação",
    ]),
    (2514, 2533, "Nono mandamento — pureza do coração", [
        "pureza do coração", "concupiscência", "modéstia", "pudor", "batalha espiritual",
    ]),
    (2534, 2557, "Décimo mandamento — desapego e pobreza espiritual", [
        "cobiça", "desapego dos bens", "pobreza espiritual", "inveja",
        "bem-aventurança dos pobres",
    ]),

    # PARTE IV — ORAÇÃO CRISTÃ
    (2558, 2649, "A oração cristã", [
        "oração", "contemplação", "meditação", "louvor", "súplica", "ação de graças",
        "adoração", "oração vocal",
    ]),
    (2650, 2758, "Tradição da oração — formas e obstáculos", [
        "tradição da oração", "liturgia das horas", "lectio divina", "distrações",
        "aridez espiritual", "oração litúrgica",
    ]),
    (2759, 2865, "O Pai-Nosso — a oração do Senhor", [
        "Pai-Nosso", "oração dominical", "Pai celeste", "Reino de Deus",
        "vontade de Deus", "pão de cada dia", "perdão das ofensas",
        "tentação", "mal",
    ]),
]


def find_ccc_section(article: int) -> dict | None:
    """Retorna os metadados da seção do CCC que contém o artigo dado."""
    for start, end, title, themes in CCC_SECTIONS:
        if start <= article <= end:
            return {
                "title": title,
                "themes": themes,
                "start": start,
                "end": end,
            }
    return None
