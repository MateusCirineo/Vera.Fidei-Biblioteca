"""
Detecção de autores patrísticos e normalização de títulos canônicos.

O número exato de Padres da Igreja varia por tradição e critério de inclusão
(Católica Romana: ~70-80; Ortodoxa: ~88; Anglican: varia).
Esta lista segue o corpus patrístico clássico reconhecido pelo magistério católico,
organizado por período e tradição.

Limitações documentadas:
  - PDFs coletânea podem retornar o autor mais citado, não o principal
  - Nome de editor no título pode enviesar a detecção
  - Obras que citam muito outro Padre podem causar empate ou erro
  - detect_canonical_title usa regex — não unifica formas multilíngues
    (ex: "De Trinitate" ≠ "On the Trinity" até mapa multilíngue existir)
"""

from __future__ import annotations

import re


# ─── Banco de dados de autores ─────────────────────────────────────────────────
# Total: 69 autores organizados por período e tradição

PATRISTIC_AUTHORS: dict[str, dict] = {

    # ═══════════════════════════════════════════════════════════════════════════
    # PADRES APOSTÓLICOS (séc. I-II)
    # ═══════════════════════════════════════════════════════════════════════════

    "São Clemente de Roma": {
        "patterns": [r"clement.*roman", r"clemente.*roma", r"clemens\s+rom"],
        "works": [r"ad\s+corinthios.*clem", r"epistul.*clement.*rom"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Santo Inácio de Antioquia": {
        "patterns": [r"ignati[uo]", r"inácio.*antioch", r"ignace.*antioch"],
        "works": [r"ad\s+ephes.*ignati", r"ad\s+romanos.*ignati",
                  r"ad\s+smyrn", r"ad\s+polycarp.*ignati"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Policarpo de Esmirna": {
        "patterns": [r"polycarp", r"policarpo"],
        "works": [r"ad\s+philippens.*polycarp", r"martyrium.*polycarp"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Papias de Hierápolis": {
        "patterns": [r"papias", r"papías"],
        "works": [r"expositio.*papias", r"logion.*kyriakes.*papias"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Hermas": {
        "patterns": [r"\bhermas\b", r"pastor.*hermas"],
        "works": [r"pastor.*hermas", r"shepherd.*hermas", r"poimen.*herma"],
        "collection": "PG",
        "tradition": "grega",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # APOLOGISTAS GREGOS (séc. II)
    # ═══════════════════════════════════════════════════════════════════════════

    "São Justino Mártir": {
        "patterns": [r"justinus.*martyr", r"justino.*mártir", r"justin.*martyr"],
        "works": [r"apologia.*justin", r"dialogus.*tryph"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Atenágoras de Atenas": {
        "patterns": [r"athenagoras", r"atenágoras"],
        "works": [r"legatio.*christian", r"de\s+resurrectione.*athenag"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Melito de Sardes": {
        "patterns": [r"melito", r"melitão"],
        "works": [r"peri\s+pascha", r"homili.*pascha.*melit"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Teófilo de Antioquia": {
        "patterns": [r"theophil.*antioch", r"teófilo.*antioch"],
        "works": [r"ad\s+autolycum"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Taciano, o Sírio": {
        "patterns": [r"\btatian", r"\btaciano\b"],
        "works": [r"diatessaron", r"oratio.*graecos.*tati"],
        "collection": "PG",
        "tradition": "grega",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # PADRES ANTI-GNÓSTICOS E ALEXANDRINOS (séc. II-III)
    # ═══════════════════════════════════════════════════════════════════════════

    "Santo Ireneu de Lião": {
        "patterns": [r"irenaeus", r"ireneu", r"irén[eé]"],
        "works": [r"adversus\s+haereses", r"contra\s+haeres", r"demonstratio.*apostol"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Clemente de Alexandria": {
        "patterns": [r"clement\w*\s+alex", r"clemens\s+alex"],
        "works": [r"stromata", r"protrepticus", r"paedagogus"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Orígenes": {
        "patterns": [r"origen[es]?", r"[oó]rigenes"],
        "works": [r"de\s+principiis", r"contra\s+celsum", r"hexapla", r"peri\s+archon"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Hipólito de Roma": {
        "patterns": [r"hippolyt", r"hipólito.*roma"],
        "works": [r"refutatio.*omnium.*haeres", r"traditio.*apostolica", r"de\s+antichristo.*hippol"],
        "collection": "PG",
        "tradition": "grega",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # PADRES LATINOS (séc. II-III)
    # ═══════════════════════════════════════════════════════════════════════════

    "Minúcio Félix": {
        "patterns": [r"minucius\s+felix", r"minúcio\s+félix"],
        "works": [r"octavius"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Tertuliano": {
        "patterns": [r"tertullian", r"tertulian"],
        "works": [r"apologetic", r"de\s+praescriptione", r"adversus\s+praxean",
                  r"de\s+anima.*tertul", r"de\s+carne\s+christi"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Cipriano de Cartago": {
        "patterns": [r"cyprianus", r"cipriano", r"\bcartag"],
        "works": [r"de\s+unitate\s+eccles", r"de\s+lapsis",
                  r"de\s+dominica\s+oratione", r"de\s+mortalitate"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Novaciano": {
        "patterns": [r"novatian", r"novaciano"],
        "works": [r"de\s+trinitate.*novat"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Lactâncio": {
        "patterns": [r"lactanti[uo]", r"lactâncio"],
        "works": [r"divinae\s+institutiones", r"de\s+mortibus\s+persecutorum", r"de\s+ira\s+dei"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Arnóbio de Sica": {
        "patterns": [r"arnobius.*sic", r"arnóbio.*sica", r"arnobius.*senior"],
        "works": [r"adversus\s+nationes.*arnob"],
        "collection": "PL",
        "tradition": "latina",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # PADRES DO SÉC. III (ORIENTE)
    # ═══════════════════════════════════════════════════════════════════════════

    "São Dionísio de Alexandria": {
        "patterns": [r"dionys.*bishop.*alex", r"dionísio.*bispo.*alex",
                     r"dionysius\s+great"],
        "works": [r"epistul.*dionys.*alex"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Gregório Taumaturgo": {
        "patterns": [r"gregor.*thaumaturg", r"gregório.*taumaturgo", r"gregory.*wonder"],
        "works": [r"panegyricus.*origen", r"de\s+fide.*gregor.*thaumaturg"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Metódio de Olimpo": {
        "patterns": [r"methodius.*olymp", r"metódio.*olimpo"],
        "works": [r"symposium.*methodius", r"de\s+resurrectione.*methodius"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Afraates, o Persa": {
        "patterns": [r"aphrahat", r"afraates", r"afrahat", r"persian\s+sage"],
        "works": [r"demonstrationes.*aphrahat"],
        "collection": "PO",
        "tradition": "oriental",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # ERA DE OURO — SÉC. IV
    # ═══════════════════════════════════════════════════════════════════════════

    "Eusébio de Cesareia": {
        "patterns": [r"eusebius.*caes", r"eusébio.*cesar", r"eusebius\s+pamphili"],
        "works": [r"historia\s+ecclesiastica", r"praeparatio\s+evangelica",
                  r"vita\s+constantini"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Alexandre de Alexandria": {
        "patterns": [r"alexander\s+of\s+alex", r"alexandre.*bispo.*alex",
                     r"alexandr.*patriarc.*alex"],
        "works": [r"epistul.*alexandr.*alex"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Atanásio de Alexandria": {
        "patterns": [r"athanas", r"atan[aá]sio"],
        "works": [r"de\s+incarnatione", r"contra\s+arian", r"vita\s+antonii",
                  r"epistul\s+festales"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Cirilo de Jerusalém": {
        "patterns": [r"cyril.*jerus", r"cirilo.*jerusal"],
        "works": [r"catecheses.*cyril", r"mystagog.*cyril"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Hilário de Poitiers": {
        "patterns": [r"hilari[uo].*pictav", r"hilário.*poitiers", r"hilary.*poitiers"],
        "works": [r"de\s+trinitate.*hilar", r"in\s+matthaeum.*hilar"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Epifânio de Salamina": {
        "patterns": [r"epiphanius", r"epifânio"],
        "works": [r"panarion", r"ancoratus"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Basílio Magno": {
        "patterns": [r"basilius", r"bas[ií]lio", r"basil.*magn", r"basil.*caesare"],
        "works": [r"hexaemeron.*basil", r"de\s+spiritu\s+sancto",
                  r"contra\s+eunomium.*basil", r"regulae.*basil"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Gregório Nazianzeno": {
        "patterns": [r"gregor\w+\s+nazianzen", r"greg[oó]rio\s+nazianzeno",
                     r"gregory.*theolog"],
        "works": [r"orationes\s+theologicae", r"carmen.*gregor.*naz"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Gregório de Nissa": {
        "patterns": [r"gregor\w+\s+nyss", r"greg[oó]rio\s+de\s+nissa",
                     r"gregory.*nyssa"],
        "works": [r"de\s+vita\s+moysis", r"in\s+canticum.*gregor.*niss",
                  r"de\s+anima\s+et\s+resurrectione"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Ambrósio de Milão": {
        "patterns": [r"ambrosius", r"ambr[oó]sio", r"\bambrose\b"],
        "works": [r"de\s+officiis.*ambros", r"de\s+mysteriis",
                  r"de\s+sacramentis", r"hexaemeron.*ambros"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Efrém Sírio": {
        "patterns": [r"ephraem", r"ephrem", r"efr[eé]m"],
        "works": [r"hymni\s+de\s+fide", r"hymni\s+de\s+paradiso", r"sermo.*ephrem"],
        "collection": "PO",
        "tradition": "oriental",
    },
    "São João Crisóstomo": {
        "patterns": [r"chrysostom", r"cris[oó]stom", r"ioann.{0,5}chrysost"],
        "works": [r"homili.*antioch", r"de\s+sacerdot",
                  r"in\s+matth.*chrysost", r"in\s+johan.*chrysost"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Jerônimo": {
        "patterns": [r"hieronymus", r"\bjerome\b", r"jer[oô]nimo"],
        "works": [r"de\s+viris\s+illustr", r"adversus\s+jovinian",
                  r"hebraic", r"vulgatam"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Paulino de Nola": {
        "patterns": [r"paulinus.*nola", r"paulino.*nola"],
        "works": [r"carmina.*paulin.*nola", r"epistul.*paulin.*nola"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Santo Agostinho de Hipona": {
        "patterns": [r"august[iu]n", r"agostinho", r"\bhippo\b"],
        "works": [r"confessione", r"civitate\s+dei", r"de\s+trinitate",
                  r"enchirid", r"de\s+doctrina", r"retract",
                  r"de\s+libero\s+arbitrio"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Cromácio de Aquileia": {
        "patterns": [r"chromati[uo]", r"cromácio"],
        "works": [r"tractatus.*chromat", r"sermo.*chromat"],
        "collection": "PL",
        "tradition": "latina",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # SÉC. V
    # ═══════════════════════════════════════════════════════════════════════════

    "São Cirilo de Alexandria": {
        "patterns": [r"cyril.*alexandr", r"cirilo.*alexandr"],
        "works": [r"in\s+iohannem.*cyril", r"contra\s+nestor",
                  r"de\s+adoratione", r"dialogus.*trinitat.*cyril"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Teodoreto de Ciro": {
        "patterns": [r"theodoret", r"teodoreto"],
        "works": [r"historia\s+ecclesiastica.*theodoret",
                  r"haereticarum.*fabularium", r"de\s+providentia.*theodoret"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Proclo de Constantinopla": {
        "patterns": [r"proclus.*constanti", r"proclo.*constanti"],
        "works": [r"sermo.*procl", r"tomus.*procl"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Vicente de Lérins": {
        "patterns": [r"vincenti[uo].*lerin", r"vicente.*lérins", r"vincent.*lerins"],
        "works": [r"commonitorium"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Próspero de Aquitânia": {
        "patterns": [r"prosper.*aquitan", r"próspero.*aquitânia"],
        "works": [r"contra\s+collatorem", r"de\s+gratia.*prosper"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São João Cassiano": {
        "patterns": [r"cassian[uo]", r"john\s+cassian"],
        "works": [r"collationes", r"de\s+institutis"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Leão Magno": {
        "patterns": [r"leo\s+magn", r"le[aã]o\s+magno", r"\bleo\s+i\b", r"pope\s+leo"],
        "works": [r"tomus\s+ad\s+flavian", r"sermo.*leo.*magn"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Pedro Crisólogo": {
        "patterns": [r"petrus\s+chrysolog", r"pedro\s+crisólogo",
                     r"peter\s+chrysolog"],
        "works": [r"sermo.*chrysolog"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Sulpício Severo": {
        "patterns": [r"sulpici[uo].*sever", r"sulpício\s+severo"],
        "works": [r"vita\s+martini", r"chronica.*sulpic"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Quodvultdeus": {
        "patterns": [r"quodvultdeus"],
        "works": [r"de\s+promissionibus", r"sermo.*quodvult"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Máximo de Turim": {
        "patterns": [r"maxim[uo].*taur", r"máximo.*turim"],
        "works": [r"sermo.*maxim.*taur"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Salviano de Marselha": {
        "patterns": [r"salvian[uo].*massil", r"salviano.*marselha",
                     r"salvian.*marseill"],
        "works": [r"de\s+gubernatione\s+dei", r"epistul.*salvian"],
        "collection": "PL",
        "tradition": "latina",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # SÉC. V-VI (ORIENTAL)
    # ═══════════════════════════════════════════════════════════════════════════

    "São Tiago de Saruge": {
        "patterns": [r"jacob.*sarug", r"tiago.*saruge", r"james.*sarug"],
        "works": [r"memre.*jakob.*sarug", r"homili.*jakob.*sarug"],
        "collection": "PO",
        "tradition": "oriental",
    },
    "Filoxênio de Mabugue": {
        "patterns": [r"philoxen", r"filoxênio"],
        "works": [r"discours.*philoxen", r"epistul.*philoxen"],
        "collection": "PO",
        "tradition": "oriental",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # SÉC. VI
    # ═══════════════════════════════════════════════════════════════════════════

    "São Fulgêncio de Ruspe": {
        "patterns": [r"fulgenti[uo].*ruspe", r"fulgêncio.*ruspe"],
        "works": [r"de\s+fide.*fulgent", r"ad\s+monimum"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Cesário de Arles": {
        "patterns": [r"caesari[uo].*arles", r"cesário.*arles"],
        "works": [r"sermo.*caesar.*arles", r"regula.*caesari"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Boécio": {
        "patterns": [r"boeth[iu]", r"bo[eé]cio"],
        "works": [r"consolatio\s+philosophiae", r"contra\s+eutychen"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Cassiodoro": {
        "patterns": [r"cassiodor[uo]"],
        "works": [r"institutiones.*cassiodor", r"variae.*cassiodor",
                  r"expositio\s+psalmorum.*cassiodor"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Gregório Magno": {
        "patterns": [r"gregor\w+\s+magn", r"greg[oó]rio\s+magno",
                     r"gregory\s+great"],
        "works": [r"moralia\s+in\s+iob", r"regula\w*\s+pastoralis",
                  r"dialogu.*gregor", r"registrum\s+epistul"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Leandro de Sevilha": {
        "patterns": [r"leandrus.*hispal", r"leandro.*sevilha"],
        "works": [r"de\s+institutione\s+virginum.*leand"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Gregório de Tours": {
        "patterns": [r"gregor.*turon", r"gregório.*tours"],
        "works": [r"historia\s+francorum", r"de\s+gloria\s+martyrum"],
        "collection": "PL",
        "tradition": "latina",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # SÉC. VII
    # ═══════════════════════════════════════════════════════════════════════════

    "Santo Isidoro de Sevilha": {
        "patterns": [r"isidor[uo].*hispal", r"isidoro.*sevilha",
                     r"isidore.*seville"],
        "works": [r"etymologiae", r"sententiae.*isidor",
                  r"de\s+viris\s+illustr.*isidor"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Santo Ildefonso de Toledo": {
        "patterns": [r"ildefons[uo]", r"ildefonso.*toledo"],
        "works": [r"de\s+virginitate.*ildefons"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Máximo Confessor": {
        "patterns": [r"maxim[uo].*confessor", r"máximo.*confessor"],
        "works": [r"mystagogia.*maxim", r"centuria\s+de\s+caritate",
                  r"ambigua.*maxim"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Pseudo-Dionísio Areopagita": {
        "patterns": [r"dionysi[uo].*areopag", r"dionísio.*areopag",
                     r"pseudo.*dionysi"],
        "works": [r"de\s+caelesti\s+hierarchia", r"de\s+ecclesiastica\s+hierarchia",
                  r"de\s+mystica\s+theologia", r"de\s+divinis\s+nominibus"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Isaac de Nínive": {
        "patterns": [r"isaac.*niniv", r"isaac.*syri[ac]", r"isaac.*nínive"],
        "works": [r"de\s+perfectione\s+religiosa", r"asceticon.*isaac"],
        "collection": "PO",
        "tradition": "oriental",
    },
    "São Macário do Egito": {
        "patterns": [r"macari[uo].*aegypt", r"macário.*egito",
                     r"macarius.*egypt"],
        "works": [r"homiliae\s+spirituales", r"de\s+elevatione\s+mentis.*macari"],
        "collection": "PO",
        "tradition": "oriental",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # SÉC. VII-VIII
    # ═══════════════════════════════════════════════════════════════════════════

    "São André de Creta": {
        "patterns": [r"andrew.*cret", r"andré.*creta", r"andreas.*cret"],
        "works": [r"canon.*magnus.*andrea", r"sermo.*andrea.*cret"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Germano de Constantinopla": {
        "patterns": [r"germanus.*constanti", r"germano.*constanti"],
        "works": [r"historia.*mystica.*germa", r"sermo.*germa.*constanti"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São João Damasceno": {
        "patterns": [r"damascen", r"damasceno", r"john.*damasc"],
        "works": [r"de\s+fide\s+orthodoxa", r"fons\s+scientiae",
                  r"contra\s+imaginum"],
        "collection": "PG",
        "tradition": "oriental",
    },
    "São Beda, o Venerável": {
        "patterns": [r"beda.*venerab", r"bede.*venerable", r"\bbeda\b",
                     r"\bbede\b"],
        "works": [r"historia\s+ecclesiastica.*gentis\s+anglorum",
                  r"de\s+temporum\s+ratione", r"in\s+lucam.*beda"],
        "collection": "PL",
        "tradition": "latina",
    },
}


# ─── Títulos canônicos ────────────────────────────────────────────────────────

CANONICAL_TITLES: dict[str, str] = {
    # Agostinho
    r"confessio": "Confissões",
    r"civitate\s+dei": "A Cidade de Deus",
    r"de\s+trinitate.*august": "De Trinitate (Agostinho)",
    r"enchirid": "Enchirídio",
    r"de\s+doctrina\s+christiana": "Da Doutrina Cristã",
    r"de\s+libero\s+arbitrio": "Do Livre-arbítrio",
    r"retractationes": "Retratações",
    # Cipriano
    r"de\s+unitate\s+eccles": "Da Unidade da Igreja",
    r"de\s+lapsis": "Dos Lapsos",
    # Jerônimo
    r"de\s+viris\s+illustr": "Dos Homens Ilustres",
    # Gregório Magno
    r"moralia\s+in\s+iob": "Moralia in Job",
    r"regula\w*\s+pastoralis": "Regra Pastoral",
    r"dialogi.*gregor": "Diálogos",
    # Crisóstomo
    r"de\s+sacerdotio": "Do Sacerdócio",
    # Basílio
    r"de\s+spiritu\s+sancto": "Do Espírito Santo",
    r"hexaemeron": "Hexaemeron",
    # Atanásio
    r"de\s+incarnatione": "Da Encarnação",
    r"vita\s+antonii": "Vida de Santo Antão",
    # Orígenes
    r"de\s+principiis": "Dos Princípios",
    r"contra\s+celsum": "Contra Celso",
    # Boécio
    r"consolatio\s+philosophiae": "Consolação da Filosofia",
    # Efrém
    r"hymni\s+de\s+paradiso": "Hinos do Paraíso",
    # João Damasceno
    r"de\s+fide\s+orthodoxa": "A Fé Ortodoxa",
    # Ireneu
    r"adversus\s+haereses": "Contra as Heresias",
    # Isidoro
    r"etymologiae": "Etimologias",
    # Eusébio
    r"historia\s+ecclesiastica": "História Eclesiástica",
    # Lactâncio
    r"divinae\s+institutiones": "Instituições Divinas",
    # Tertuliano
    r"apologetic": "Apologético",
    r"de\s+praescriptione": "Da Prescrição dos Hereges",
    # Beda
    r"historia\s+ecclesiastica.*gentis\s+anglorum": "História Eclesiástica do Povo Inglês",
    # João Cassiano
    r"collationes": "Colações",
    # Vicente de Lérins
    r"commonitorium": "Commonitório",
    # Pseudo-Dionísio
    r"de\s+mystica\s+theologia": "Da Teologia Mística",
    r"de\s+divinis\s+nominibus": "Dos Nomes Divinos",
    r"de\s+caelesti\s+hierarchia": "Da Hierarquia Celeste",
    # Sulpício Severo
    r"vita\s+martini": "Vida de São Martinho",
}


# ─── Limiar de confiança ──────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD = 3  # score mínimo para retornar nome de autor


# ─── Funções públicas ─────────────────────────────────────────────────────────

def detect_author(
    title: str,
    content_sample: str = "",
    min_score: int = 2,
) -> tuple[str | None, int]:
    """
    Detecta o autor patrístico com base no título e amostra do conteúdo.

    Retorna (nome_canônico, score) com três níveis:
      score < min_score (default 2) → (None, 0)    — nenhum sinal
      min_score <= score < 3        → (None, score) — sinal fraco, não usar
      score >= 3                    → (autor, score) — confiança suficiente

    Pesos:
      +2 por padrão de nome encontrado (patterns)
      +1 por título de obra encontrado (works)

    Limitações conhecidas:
      - PDFs coletânea podem retornar o autor mais citado, não o principal
      - Nome de editor no título pode enviesar a detecção
      - Obras que citam muito outro Padre podem causar empate ou erro
      - (futuro) peso maior para primeiras linhas / metadados do PDF
    """
    combined = (title + " " + content_sample).lower()
    best_author: str | None = None
    best_score: int = 0

    for author, data in PATRISTIC_AUTHORS.items():
        score = 0
        for p in data["patterns"]:
            if re.search(p, combined, re.IGNORECASE):
                score += 2  # nome pesa mais
        for w in data["works"]:
            if re.search(w, combined, re.IGNORECASE):
                score += 1  # obra confirma
        if score > best_score:
            best_score = score
            best_author = author

    if best_score < min_score:
        return (None, 0)
    if best_score < CONFIDENCE_THRESHOLD:
        return (None, best_score)  # sinal fraco: preserva score mas não retorna autor
    return (best_author, best_score)


def detect_canonical_title(title: str, content_sample: str = "") -> str:
    """
    Normaliza o título para forma canônica via regex.
    Verifica título E amostra do conteúdo, pois muitos PDFs têm
    o título abreviado, traduzido ou ausente no nome do arquivo.

    Limitações conhecidas:
      - "De Trinitate", "Sobre a Trindade", "On the Trinity" → mesma obra,
        mas precisaria de mapa multilíngue ou embeddings para unificar
      - Títulos não mapeados em CANONICAL_TITLES retornam o título bruto
    """
    combined = title + " " + content_sample[:500]
    for pattern, canonical in CANONICAL_TITLES.items():
        if re.search(pattern, combined, re.IGNORECASE):
            return canonical
    return title  # fallback: título como está


def detect_patristic_tradition(author_name: str) -> str | None:
    """Retorna a tradição patrística do autor, ou None se não reconhecido."""
    data = PATRISTIC_AUTHORS.get(author_name)
    return data.get("tradition") if data else None
