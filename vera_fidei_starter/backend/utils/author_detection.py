"""
Detecção de autores patrísticos e normalização de títulos canônicos.

O corpus patrístico clássico reconhecido pelo magistério católico romano inclui
autores do séc. I ao VIII (Ocidente) e até João Damasceno (†749) no Oriente.
Alguns autores de ortodoxia contestada (Orígenes, Tertuliano, Evágrio Pôntico,
Teodoro de Mopsuéstia) são incluídos por fazerem parte integrante do corpus
patrístico estudado.

Limitações documentadas:
  - PDFs coletânea podem retornar o autor mais citado, não o principal
  - Nome de editor no título pode enviesar a detecção
  - Obras que citam muito outro Padre podem causar empate ou erro
  - detect_canonical_title usa regex — não unifica formas multilíngues
    (ex: "De Trinitate" ≠ "On the Trinity" até mapa multilíngue existir)
"""

from __future__ import annotations

import re


# ─── Banco de dados de autores (ordem alfabética) ─────────────────────────────

PATRISTIC_AUTHORS: dict[str, dict] = {

    "Afraates, o Persa": {
        "patterns": [r"aphrahat", r"afraates", r"afrahat", r"persian\s+sage"],
        "works": [r"demonstrationes.*aphrahat"],
        "collection": "PO",
        "tradition": "oriental",
    },
    "Aristides de Atenas": {
        "patterns": [r"aristid.*athen", r"aristides.*atenas"],
        "works": [r"apologi.*aristid"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Arnóbio de Sica": {
        "patterns": [r"arnobius.*sic", r"arnóbio.*sica", r"arnobius.*senior"],
        "works": [r"adversus\s+nationes.*arnob"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Atenágoras de Atenas": {
        "patterns": [r"athenagoras", r"atenágoras"],
        "works": [r"legatio.*christian", r"de\s+resurrectione.*athenag"],
        "collection": "PG",
        "tradition": "grega",
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
    "Clemente de Alexandria": {
        "patterns": [r"clement\w*\s+alex", r"clemens\s+alex"],
        "works": [r"stromata", r"protrepticus", r"paedagogus"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Dídimo, o Cego": {
        "patterns": [r"didymus.*blind", r"dídimo.*cego", r"didimus.*alex"],
        "works": [r"de\s+trinitate.*didym", r"in\s+genesim.*didym",
                  r"contra\s+manichaeos.*didym"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Ênodio de Pavia": {
        "patterns": [r"ennodius", r"ênodio.*pavia", r"ennodio.*pavia"],
        "works": [r"vita.*epiphanii.*ennod", r"opuscula.*ennod"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Eusébio de Cesareia": {
        "patterns": [r"eusebius.*caes", r"eusébio.*cesar", r"eusebius\s+pamphili"],
        "works": [r"historia\s+ecclesiastica", r"praeparatio\s+evangelica",
                  r"vita\s+constantini"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Evágrio Pôntico": {
        "patterns": [r"evagri[uo].*pont", r"evágrio.*pôntico",
                     r"evagrius.*pont"],
        "works": [r"practicus.*evagr", r"kephalaia.*evagr",
                  r"de\s+oratione.*evagr"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Filoxênio de Mabugue": {
        "patterns": [r"philoxen", r"filoxênio"],
        "works": [r"discours.*philoxen", r"epistul.*philoxen"],
        "collection": "PO",
        "tradition": "oriental",
    },
    "Hermas": {
        "patterns": [r"\bhermas\b", r"pastor.*hermas"],
        "works": [r"pastor.*hermas", r"shepherd.*hermas", r"poimen.*herma"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Hesíquio de Jerusalém": {
        "patterns": [r"hesychi[uo].*jerus", r"hesíquio.*jerusal",
                     r"hesychius.*jerus"],
        "works": [r"homili.*hesych", r"commentari.*hesych"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Lactâncio": {
        "patterns": [r"lactanti[uo]", r"lactâncio"],
        "works": [r"divinae\s+institutiones", r"de\s+mortibus\s+persecutorum",
                  r"de\s+ira\s+dei"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Marco, o Monge": {
        "patterns": [r"marcus.*monachus", r"marco.*monge",
                     r"mark.*monk", r"mark.*ascet"],
        "works": [r"de\s+lege\s+spirituali", r"de\s+his\s+qui\s+putant",
                  r"epistul.*marco.*monge"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Minúcio Félix": {
        "patterns": [r"minucius\s+felix", r"minúcio\s+félix"],
        "works": [r"octavius"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Nilo de Âncira": {
        "patterns": [r"nil[uo].*ancyr", r"nilo.*âncira", r"nilus.*ancyr"],
        "works": [r"de\s+oratione.*nil", r"epistul.*nili",
                  r"de\s+monastica.*exercit"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Novaciano": {
        "patterns": [r"novatian", r"novaciano"],
        "works": [r"de\s+trinitate.*novat"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Orígenes": {
        "patterns": [r"origen[es]?", r"[oó]rigenes"],
        "works": [r"de\s+principiis", r"contra\s+celsum", r"hexapla", r"peri\s+archon"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Papias de Hierápolis": {
        "patterns": [r"papias", r"papías"],
        "works": [r"expositio.*papias", r"logion.*kyriakes.*papias"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Pseudo-Dionísio Areopagita": {
        "patterns": [r"dionysi[uo].*areopag", r"dionísio.*areopag",
                     r"pseudo.*dionysi"],
        "works": [r"de\s+caelesti\s+hierarchia",
                  r"de\s+ecclesiastica\s+hierarchia",
                  r"de\s+mystica\s+theologia", r"de\s+divinis\s+nominibus"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Quodvultdeus": {
        "patterns": [r"quodvultdeus"],
        "works": [r"de\s+promissionibus", r"sermo.*quodvult"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Rufino de Aquileia": {
        "patterns": [r"rufin[uo].*aquilei", r"rufino.*aquileia",
                     r"rufinus.*aquil"],
        "works": [r"historia\s+ecclesiastica.*rufin",
                  r"de\s+principiis.*rufin"],
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
    "Santo Agostinho de Hipona": {
        "patterns": [r"august[iu]n", r"agostinho", r"\bhippo\b"],
        "works": [r"confessione", r"civitate\s+dei", r"de\s+trinitate",
                  r"enchirid", r"de\s+doctrina", r"retract",
                  r"de\s+libero\s+arbitrio"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Santo Antão do Egito": {
        "patterns": [r"antonius.*aegypt", r"antão.*egito", r"anthony.*great",
                     r"antony.*desert"],
        "works": [r"vita\s+antonii", r"epistulae.*antonii"],
        "collection": "PG",
        "tradition": "oriental",
    },
    "Santo Ildefonso de Toledo": {
        "patterns": [r"ildefons[uo]", r"ildefonso.*toledo"],
        "works": [r"de\s+virginitate.*ildefons"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Santo Inácio de Antioquia": {
        "patterns": [r"ignati[uo]", r"inácio.*antioch", r"ignace.*antioch"],
        "works": [r"ad\s+ephes.*ignati", r"ad\s+romanos.*ignati",
                  r"ad\s+smyrn", r"ad\s+polycarp.*ignati"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Santo Ireneu de Lião": {
        "patterns": [r"irenaeus", r"ireneu", r"irén[eé]"],
        "works": [r"adversus\s+haereses", r"contra\s+haeres", r"demonstratio.*apostol"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Santo Isidoro de Sevilha": {
        "patterns": [r"isidor[uo].*hispal", r"isidoro.*sevilha",
                     r"isidore.*seville"],
        "works": [r"etymologiae", r"sententiae.*isidor",
                  r"de\s+viris\s+illustr.*isidor"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Alexandre de Alexandria": {
        "patterns": [r"alexander\s+of\s+alex", r"alexandre.*bispo.*alex",
                     r"alexandr.*patriarc.*alex"],
        "works": [r"epistul.*alexandr.*alex"],
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
    "São Amfilóquio de Icônio": {
        "patterns": [r"amphilochi[uo]", r"amfilóquio"],
        "works": [r"iambi.*amphiloch", r"epistul.*amphiloch"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São André de Creta": {
        "patterns": [r"andrew.*cret", r"andré.*creta", r"andreas.*cret"],
        "works": [r"canon.*magnus.*andrea", r"sermo.*andrea.*cret"],
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
    "São Barnabé": {
        "patterns": [r"barnab[ae]", r"barnabé", r"pseudo.*barnab"],
        "works": [r"epistula.*barnab", r"epistle.*barnab"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Basílio Magno": {
        "patterns": [r"basilius", r"bas[ií]lio", r"basil.*magn",
                     r"basil.*caesare"],
        "works": [r"hexaemeron.*basil", r"de\s+spiritu\s+sancto",
                  r"contra\s+eunomium.*basil", r"regulae.*basil"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Beda, o Venerável": {
        "patterns": [r"beda.*venerab", r"bede.*venerable", r"\bbeda\b",
                     r"\bbede\b"],
        "works": [r"historia\s+ecclesiastica.*gentis\s+anglorum",
                  r"de\s+temporum\s+ratione", r"in\s+lucam.*beda"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Bento de Núrsia": {
        "patterns": [r"benedict.*nurs", r"bento.*núrsia", r"benedikt.*nurs"],
        "works": [r"regula.*benedicti", r"regula\s+monasteriorum"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Cesário de Arles": {
        "patterns": [r"caesari[uo].*arles", r"cesário.*arles"],
        "works": [r"sermo.*caesar.*arles", r"regula.*caesari"],
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
    "São Cirilo de Alexandria": {
        "patterns": [r"cyril.*alexandr", r"cirilo.*alexandr"],
        "works": [r"in\s+iohannem.*cyril", r"contra\s+nestor",
                  r"de\s+adoratione", r"dialogus.*trinitat.*cyril"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Cirilo de Jerusalém": {
        "patterns": [r"cyril.*jerus", r"cirilo.*jerusal"],
        "works": [r"catecheses.*cyril", r"mystagog.*cyril"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Clemente de Roma": {
        "patterns": [r"clement.*roman", r"clemente.*roma", r"clemens\s+rom"],
        "works": [r"ad\s+corinthios.*clem", r"epistul.*clement.*rom"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Columbano": {
        "patterns": [r"columban[uo]", r"columbanus", r"kolumban"],
        "works": [r"regula.*columban", r"instructiones.*columban",
                  r"epistul.*columban"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Cromácio de Aquileia": {
        "patterns": [r"chromati[uo]", r"cromácio"],
        "works": [r"tractatus.*chromat", r"sermo.*chromat"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Dionísio de Alexandria": {
        "patterns": [r"dionys.*bishop.*alex", r"dionísio.*bispo.*alex",
                     r"dionysius\s+great"],
        "works": [r"epistul.*dionys.*alex"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Efrém Sírio": {
        "patterns": [r"ephraem", r"ephrem", r"efr[eé]m"],
        "works": [r"hymni\s+de\s+fide", r"hymni\s+de\s+paradiso",
                  r"sermo.*ephrem"],
        "collection": "PO",
        "tradition": "oriental",
    },
    "São Epifânio de Salamina": {
        "patterns": [r"epiphanius", r"epifânio"],
        "works": [r"panarion", r"ancoratus"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Fulgêncio de Ruspe": {
        "patterns": [r"fulgenti[uo].*ruspe", r"fulgêncio.*ruspe"],
        "works": [r"de\s+fide.*fulgent", r"ad\s+monimum"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Gaudêncio de Bréscia": {
        "patterns": [r"gaudenti[uo].*bresci", r"gaudêncio.*bréscia",
                     r"gaudentius.*brix"],
        "works": [r"tractatus.*gaudent", r"sermo.*gaudent"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Germano de Constantinopla": {
        "patterns": [r"germanus.*constanti", r"germano.*constanti"],
        "works": [r"historia.*mystica.*germa", r"sermo.*germa.*constanti"],
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
    "São Gregório de Tours": {
        "patterns": [r"gregor.*turon", r"gregório.*tours"],
        "works": [r"historia\s+francorum", r"de\s+gloria\s+martyrum"],
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
    "São Gregório Nazianzeno": {
        "patterns": [r"gregor\w+\s+nazianzen", r"greg[oó]rio\s+nazianzeno",
                     r"gregory.*theolog"],
        "works": [r"orationes\s+theologicae", r"carmen.*gregor.*naz"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Gregório Taumaturgo": {
        "patterns": [r"gregor.*thaumaturg", r"gregório.*taumaturgo",
                     r"gregory.*wonder"],
        "works": [r"panegyricus.*origen", r"de\s+fide.*gregor.*thaumaturg"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Hilário de Arles": {
        "patterns": [r"hilari[uo].*arelat", r"hilário.*arles",
                     r"hilary.*arles"],
        "works": [r"vita\s+honorati", r"sermo.*hilar.*arles"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Hilário de Poitiers": {
        "patterns": [r"hilari[uo].*pictav", r"hilário.*poitiers",
                     r"hilary.*poitiers"],
        "works": [r"de\s+trinitate.*hilar", r"in\s+matthaeum.*hilar"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Hipólito de Roma": {
        "patterns": [r"hippolyt", r"hipólito.*roma"],
        "works": [r"refutatio.*omnium.*haeres", r"traditio.*apostolica",
                  r"de\s+antichristo.*hippol"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Isaac de Nínive": {
        "patterns": [r"isaac.*niniv", r"isaac.*syri[ac]", r"isaac.*nínive"],
        "works": [r"de\s+perfectione\s+religiosa", r"asceticon.*isaac"],
        "collection": "PO",
        "tradition": "oriental",
    },
    "São Isidoro de Pelúsio": {
        "patterns": [r"isidor[uo].*pelus", r"isidoro.*pelúsio",
                     r"isidore.*pelus"],
        "works": [r"epistul.*isidor.*pelus"],
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
    "São João Cassiano": {
        "patterns": [r"cassian[uo]", r"john\s+cassian"],
        "works": [r"collationes", r"de\s+institutis"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São João Crisóstomo": {
        "patterns": [r"chrysostom", r"cris[oó]stom", r"ioann.{0,5}chrysost"],
        "works": [r"homili.*antioch", r"de\s+sacerdot",
                  r"in\s+matth.*chrysost", r"in\s+johan.*chrysost"],
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
    "São Justino Mártir": {
        "patterns": [r"justinus.*martyr", r"justino.*mártir", r"justin.*martyr"],
        "works": [r"apologia.*justin", r"dialogus.*tryph"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Leandro de Sevilha": {
        "patterns": [r"leandrus.*hispal", r"leandro.*sevilha"],
        "works": [r"de\s+institutione\s+virginum.*leand"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Leão Magno": {
        "patterns": [r"leo\s+magn", r"le[aã]o\s+magno", r"\bleo\s+i\b",
                     r"pope\s+leo"],
        "works": [r"tomus\s+ad\s+flavian", r"sermo.*leo.*magn"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Macário do Egito": {
        "patterns": [r"macari[uo].*aegypt", r"macário.*egito",
                     r"macarius.*egypt", r"macarius.*magn"],
        "works": [r"homiliae\s+spirituales", r"apophthegmata.*macari"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Martinho de Braga": {
        "patterns": [r"martin[uo].*braccar", r"martinho.*braga",
                     r"martin.*braga"],
        "works": [r"formula\s+vitae\s+honestae", r"de\s+correctione\s+rusticorum"],
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
    "São Máximo de Turim": {
        "patterns": [r"maxim[uo].*taur", r"máximo.*turim"],
        "works": [r"sermo.*maxim.*taur"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Melito de Sardes": {
        "patterns": [r"melito", r"melitão"],
        "works": [r"peri\s+pascha", r"homili.*pascha.*melit"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Metódio de Olimpo": {
        "patterns": [r"methodius.*olymp", r"metódio.*olimpo"],
        "works": [r"symposium.*methodius", r"de\s+resurrectione.*methodius"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Pacômio": {
        "patterns": [r"pachomi[uo]", r"pacômio", r"pacomio"],
        "works": [r"regula.*pachom", r"vita.*pachom", r"praecepta.*pachom"],
        "collection": "PO",
        "tradition": "oriental",
    },
    "São Paládio de Galácia": {
        "patterns": [r"palladi[uo].*galat", r"paládio.*galácia",
                     r"palladius.*lausiac"],
        "works": [r"historia\s+lausiaca", r"dialogus.*chrysost.*pallad"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Paulino de Nola": {
        "patterns": [r"paulinus.*nola", r"paulino.*nola"],
        "works": [r"carmina.*paulin.*nola", r"epistul.*paulin.*nola"],
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
    "São Policarpo de Esmirna": {
        "patterns": [r"polycarp", r"policarpo"],
        "works": [r"ad\s+philippens.*polycarp", r"martyrium.*polycarp"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Proclo de Constantinopla": {
        "patterns": [r"proclus.*constanti", r"proclo.*constanti"],
        "works": [r"sermo.*procl", r"tomus.*procl"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Próspero de Aquitânia": {
        "patterns": [r"prosper.*aquitan", r"próspero.*aquitânia"],
        "works": [r"contra\s+collatorem", r"de\s+gratia.*prosper"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Sofrônio de Jerusalém": {
        "patterns": [r"sophronius.*jerus", r"sofrônio.*jerusal",
                     r"sophronios.*jerus"],
        "works": [r"synodica.*sophron", r"vita.*cyri.*ioann.*sophron"],
        "collection": "PG",
        "tradition": "grega",
    },
    "São Sulpício Severo": {
        "patterns": [r"sulpici[uo].*sever", r"sulpício\s+severo"],
        "works": [r"vita\s+martini", r"chronica.*sulpic"],
        "collection": "PL",
        "tradition": "latina",
    },
    "São Tiago de Saruge": {
        "patterns": [r"jacob.*sarug", r"tiago.*saruge", r"james.*sarug"],
        "works": [r"memre.*jakob.*sarug", r"homili.*jakob.*sarug"],
        "collection": "PO",
        "tradition": "oriental",
    },
    "São Vicente de Lérins": {
        "patterns": [r"vincenti[uo].*lerin", r"vicente.*lérins",
                     r"vincent.*lerins"],
        "works": [r"commonitorium"],
        "collection": "PL",
        "tradition": "latina",
    },
    "Taciano, o Sírio": {
        "patterns": [r"\btatian", r"\btaciano\b"],
        "works": [r"diatessaron", r"oratio.*graecos.*tati"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Teodoro de Mopsuéstia": {
        "patterns": [r"theodor.*mopsue", r"theodore.*mopsue",
                     r"teodoro.*mopsuéstia"],
        "works": [r"commentari.*theodor.*mops", r"catecheses.*theodor.*mops"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Teodoreto de Ciro": {
        "patterns": [r"theodoret", r"teodoreto"],
        "works": [r"historia\s+ecclesiastica.*theodoret",
                  r"haereticarum.*fabularium",
                  r"de\s+providentia.*theodoret"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Teófilo de Antioquia": {
        "patterns": [r"theophil.*antioch", r"teófilo.*antioch"],
        "works": [r"ad\s+autolycum"],
        "collection": "PG",
        "tradition": "grega",
    },
    "Tertuliano": {
        "patterns": [r"tertullian", r"tertulian"],
        "works": [r"apologetic", r"de\s+praescriptione", r"adversus\s+praxean",
                  r"de\s+anima.*tertul", r"de\s+carne\s+christi"],
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
    # Isidoro de Sevilha
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
    # Bento de Núrsia
    r"regula.*benedicti": "Regra de São Bento",
    # Paládio
    r"historia\s+lausiaca": "História Lausíaca",
    # Macário
    r"homiliae\s+spirituales": "Homilias Espirituais",
}


# ─── Aliases de autores e títulos de obras ───────────────────────────────────
# Permite que o usuário digite o nome do autor em formas alternativas (variantes
# ortográficas, grafias populares) ou o título de uma obra conhecida — e o sistema
# mapeia para o nome canônico presente em PATRISTIC_AUTHORS.

AUTHOR_ALIASES: dict[str, str] = {
    # Inácio de Antioquia — formas alternativas e títulos das cartas
    "inacio de antioquia":          "Santo Inácio de Antioquia",
    "inácio de antioquia":          "Santo Inácio de Antioquia",
    "ignacio de antioquia":         "Santo Inácio de Antioquia",
    "ignácio de antioquia":         "Santo Inácio de Antioquia",
    "inácio":                       "Santo Inácio de Antioquia",
    "ignacio":                      "Santo Inácio de Antioquia",
    "ignácio":                      "Santo Inácio de Antioquia",
    "inacio":                       "Santo Inácio de Antioquia",
    "inácio aos efésios":           "Santo Inácio de Antioquia",
    "inacio aos efesios":           "Santo Inácio de Antioquia",
    "carta aos efésios":            "Santo Inácio de Antioquia",
    "carta aos efesios":            "Santo Inácio de Antioquia",
    "inácio aos romanos":           "Santo Inácio de Antioquia",
    "inácio aos magnésios":         "Santo Inácio de Antioquia",
    "inácio aos tralianos":         "Santo Inácio de Antioquia",
    "inácio aos filadelfienses":    "Santo Inácio de Antioquia",
    "inácio aos esmirnenses":       "Santo Inácio de Antioquia",
    "carta a policarpo":            "Santo Inácio de Antioquia",
    # Ireneu de Lião — variantes ortográficas
    "ireneu de liao":               "Santo Ireneu de Lião",
    "ireneu de lião":               "Santo Ireneu de Lião",
    "irineu de liao":               "Santo Ireneu de Lião",
    "irineu de lião":               "Santo Ireneu de Lião",
    "ireneu":                       "Santo Ireneu de Lião",
    "irineu":                       "Santo Ireneu de Lião",
    "contra as heresias":           "Santo Ireneu de Lião",
    "adversus haereses":            "Santo Ireneu de Lião",
    # Policarpo de Esmirna
    "policarpo de esmirna":         "São Policarpo de Esmirna",
    "policarpo":                    "São Policarpo de Esmirna",
    "carta aos filipenses":         "São Policarpo de Esmirna",
    "martírio de policarpo":        "São Policarpo de Esmirna",
    # Clemente Romano
    "clemente romano":              "São Clemente de Roma",
    "clemente de roma":             "São Clemente de Roma",
    "primeira carta de clemente":   "São Clemente de Roma",
    "carta aos coríntios":          "São Clemente de Roma",
    # Hermas
    "pastor de hermas":             "Hermas",
    "o pastor de hermas":           "Hermas",
    "o pastor":                     "Hermas",
    # Barnabé
    "carta de barnabé":             "São Barnabé",
    "barnabé":                      "São Barnabé",
    "barnabe":                      "São Barnabé",
    # Papias
    "papias de hierapolis":         "Papias de Hierápolis",
    "papías de hierápolis":         "Papias de Hierápolis",
    "papias":                       "Papias de Hierápolis",
    # Justino
    "justino mártir":               "São Justino Mártir",
    "justino martir":               "São Justino Mártir",
    "justino":                      "São Justino Mártir",
    "são justino":                  "São Justino Mártir",
    # Apologistas
    "teofilo de antioquia":         "Teófilo de Antioquia",
    "teófilo de antioquia":         "Teófilo de Antioquia",
    "atenagoras de atenas":         "Atenágoras de Atenas",
    "atenágoras de atenas":         "Atenágoras de Atenas",
    "atenagoras":                   "Atenágoras de Atenas",
    "atenágoras":                   "Atenágoras de Atenas",
    "taciano":                      "Taciano, o Sírio",
    "taciano o sirio":              "Taciano, o Sírio",
    # Cipriano
    "cipriano de cartago":          "São Cipriano de Cartago",
    "sao cipriano":                 "São Cipriano de Cartago",
    "cipriano":                     "São Cipriano de Cartago",
    # Agostinho de Hipona
    "agostinho":                        "Santo Agostinho de Hipona",
    "santo agostinho":                  "Santo Agostinho de Hipona",
    "agostinho de hipona":              "Santo Agostinho de Hipona",
    "a trindade":                       "Santo Agostinho de Hipona",
    "de trinitate":                     "Santo Agostinho de Hipona",
    "o livre arbitrio":                 "Santo Agostinho de Hipona",
    "de libero arbitrio":               "Santo Agostinho de Hipona",
    "confissoes":                       "Santo Agostinho de Hipona",
    "cidade de deus":                   "Santo Agostinho de Hipona",
    # Ambrósio de Milão
    "ambrosio de milao":                "São Ambrósio de Milão",
    "sao ambrosio":                     "São Ambrósio de Milão",
    "santo ambrosio":                   "São Ambrósio de Milão",
    "ambrosio":                         "São Ambrósio de Milão",
    "sobre os sacramentos":             "São Ambrósio de Milão",
    "sobre os misterios":               "São Ambrósio de Milão",
    "sobre a penitencia":               "São Ambrósio de Milão",
    "explicacao dos simbolos":          "São Ambrósio de Milão",
    # Leão Magno
    "leao magno":                       "São Leão Magno",
    "sao leao magno":                   "São Leão Magno",
    "leao i":                           "São Leão Magno",
    "sermoes de leao magno":            "São Leão Magno",
    # João Crisóstomo
    "crisostomo":                       "São João Crisóstomo",
    "joao crisostomo":                  "São João Crisóstomo",
}


def _normalize_for_alias(text: str) -> str:
    """Normaliza texto para lookup em AUTHOR_ALIASES: remove acentos, lowercase, strip."""
    import unicodedata
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.strip()


def resolve_author_alias(attributed_to: str) -> str | None:
    """
    Resolve um nome de autor ou título de obra para o nome canônico em PATRISTIC_AUTHORS.
    Exemplo: "Inácio aos Efésios" → "Santo Inácio de Antioquia"
    Retorna None se não houver alias cadastrado.
    """
    key = _normalize_for_alias(attributed_to)
    return AUTHOR_ALIASES.get(key)


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
