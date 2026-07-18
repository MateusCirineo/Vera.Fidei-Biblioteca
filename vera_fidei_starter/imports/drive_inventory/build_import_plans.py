import json
from pathlib import Path

base = Path('vera_fidei_starter/imports/drive_inventory')
out = base / 'plans'
out.mkdir(parents=True, exist_ok=True)

folder_meta = {
    '18LHL3KL3suwXDAwUdwVeX0AtqRv0HpzH': {'top': 'Santo Tomás de Aquino', 'mode': 'catena'},
    '1IFAexOFxlpSu9FnR5Rd20iqzrsyKTilK': {'top': 'Santo Tomás de Aquino', 'mode': 'all'},
    '16f8UdiT23M-JAtRTt6R_7tAkl1ZWlH7o': {'top': 'Santo Tomás de Aquino', 'mode': 'thomas'},
    '1BHuETeWAdlt93HlH73unH3v9pTN_M_75': {'top': 'São Boaventura', 'mode': 'all'},
    '1mq7IG_ZFc-tEBM_uUQ9xo2JY2L_vbx_Z': {'top': None, 'mode': 'trivium'},
}

trivium_import_terms = [
    'Patrística Vol. 17 - A Doutrina Cristã - Santo Agostinho',
    'Sobre a Música - Santo Agostinho',
    'De Institutione Arithmetica - Boécio',
    'Fundamentals of Music - Boécio',
]
thomas_review_terms = [
    'Santo Tomás e a Crise Contemporânea',
    'traduzido via software',
    'Selected Writings',
    'Saint Thomas Aquinas Collection',
]
thomas_skip_terms = [
    'Suma Teológica - Santo Tomás de Aquino.pdf',
    'Suma teológica - volume 04.pdf',
]

def display_name(item):
    name = item.get('Name') or Path(item.get('Path') or '').name
    mime = item.get('MimeType') or ''
    if mime == 'application/pdf' and not name.lower().endswith('.pdf'):
        return name + '.pdf'
    return name

def first_segment(path):
    return path.split('/', 1)[0] if '/' in path else ''

def author_top_for_path(path, fallback):
    if 'Santo Agostinho' in path:
        return 'Santo Agostinho'
    if 'Boécio' in path or 'Boecio' in path:
        return 'Boécio'
    return fallback

summary = {}
for folder_id, meta in folder_meta.items():
    data = json.loads((base / f'{folder_id}.json').read_text(encoding='utf-8'))
    rows = []
    for item in data:
        path = item.get('Path') or item.get('Name') or ''
        name = display_name(item)
        top = meta['top'] or first_segment(path) or '<root>'
        mode = meta['mode']
        action = 'importar'
        if mode == 'catena' and 'Tradução boa/' in path:
            action = 'revisar'
        elif mode == 'trivium':
            top = author_top_for_path(path, top)
            action = 'importar' if any(term in path for term in trivium_import_terms) else 'revisar'
        elif mode == 'thomas':
            if any(term in path for term in thomas_skip_terms):
                action = 'revisar'
            if any(term in path for term in thomas_review_terms):
                action = 'revisar'
        rows.append({
            'path': path,
            'name': name,
            'top_folder': top,
            'size': item.get('Size') or 0,
            'action': action,
            'duplicate': False,
        })
    result = {
        'source_folder_id': folder_id,
        'total_pdfs': len(rows),
        'rows': rows,
    }
    (out / f'{folder_id}.analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    summary[folder_id] = {
        'total': len(rows),
        'importar': sum(1 for r in rows if r['action'] == 'importar'),
        'revisar': sum(1 for r in rows if r['action'] == 'revisar'),
        'mb_importar': round(sum(r['size'] for r in rows if r['action'] == 'importar') / 1024 / 1024, 2),
    }

print(json.dumps(summary, ensure_ascii=False, indent=2))
