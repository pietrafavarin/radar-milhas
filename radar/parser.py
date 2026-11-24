"""Transforma um post de blog em dados estruturados.

Três tipos de post interessam:
  - "passagem": resgate de passagem com milhas/pontos (programa, preço, origem, destino, cabine)
  - "transferencia": bônus para transferir pontos de banco/cartão para programa aéreo
  - "outra": outras promoções que citam Livelo ou Esfera (compra de pontos, clube etc.)
"""
import re
from datetime import datetime, timedelta, timezone

from .places import PLACES, find_places, is_sao_paulo, norm

BRT = timezone(timedelta(hours=-3))

# programa canônico -> padrões (texto já normalizado, sem acento)
PROGRAMS = [
    ("Smiles", r"smiles"),
    ("LATAM Pass", r"latam\s*pass|milhas\s+latam|latam"),
    ("Azul Fidelidade", r"azul\s+fidelidade|tudoazul|pontos\s+azul|azul"),
    ("Iberia (Avios)", r"avios\s+iberia|iberia\s+(club|plus)|iberia"),
    ("British Airways (Avios)", r"british\s+airways\s+club|avios\s+british|british"),
    ("Qatar (Avios)", r"privilege\s+club|avios\s+qatar|qatar"),
    ("TAP Miles&Go", r"miles\s*&?\s*go|tap"),
    ("Aeroplan", r"aeroplan|air\s+canada"),
    ("AAdvantage", r"aadvantage|american\s+airlines"),
    ("Flying Blue", r"flying\s+blue|air\s+france|klm"),
    ("LifeMiles", r"lifemiles|avianca"),
    ("ConnectMiles", r"connectmiles|copa\s+airlines"),
    ("KrisFlyer", r"krisflyer|singapore\s+airlines"),
    ("MileagePlus", r"mileageplus|united"),
    ("Emirates Skywards", r"skywards|emirates"),
    ("Etihad Guest", r"etihad"),
    ("Turkish Miles&Smiles", r"turkish"),
    ("Delta SkyMiles", r"skymiles|delta"),
    ("Aerolíneas Plus", r"aerolineas\s+plus|aerolineas\s+argentinas"),
    ("Livelo", r"livelo"),
    ("Esfera", r"esfera"),
]
_PROGRAM_RES = [(name, re.compile(r"\b(?:" + pat + r")\b")) for name, pat in PROGRAMS]
AIRLINE_PROGRAMS = [p for p, _ in PROGRAMS if p not in ("Livelo", "Esfera")]

# origens de pontos (bancos/cartões/varejo) que fazem promoções de transferência
SOURCES = [
    ("Livelo", r"livelo|bradesco|banco do brasil"),
    ("Esfera", r"esfera|santander"),
    ("Itaú", r"itau|iupp|ponto\s+itau"),
    ("C6 Átomos", r"atomos|c6"),
    ("Inter Loop", r"inter\s+loop|loop"),
    ("Nubank", r"nubank"),
    ("Caixa", r"caixa"),
    ("BTG", r"btg"),
    ("XP", r"\bxp\b"),
    ("Premmia", r"premmia"),
    ("Nomad", r"nomad"),
    ("Sicredi", r"sicredi"),
    ("BRB", r"brb|curtai"),
    ("Mercado Pago", r"mercado\s+pago"),
    ("Méliuz", r"meliuz"),
]
_SOURCE_RES = [(name, re.compile(r"\b(?:" + pat + r")\b")) for name, pat in SOURCES]

_MONTHS = {m: i + 1 for i, m in enumerate(
    "janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro".split())}

# número + unidade: "61.343 milhas", "16 mil Avios", "7 mil milhas", "4,5 mil pontos", "7.500 mil milhas"
_AMOUNT_RE = re.compile(
    r"(\d{1,3}(?:\.\d{3})+|\d+(?:,\d+)?)\s*(mil\s+)?(milhas|pontos|avios)\b((?:\s+[\w&]+){0,4})", re.I)
_PERCENT_RE = re.compile(r"(\d{2,3})\s*%")


def clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = (text.replace("&#8230;", "…").replace("&#8211;", "–").replace("&#160;", " ")
            .replace("&nbsp;", " ").replace("&amp;", "&").replace("&#8217;", "’"))
    text = re.sub(r"O post .{0,300}? apareceu primeiro em .*$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _to_int(num: str, has_mil: bool) -> int:
    if "." in num:  # separador de milhar ("61.343", "7.500 mil" = 7500)
        return int(num.replace(".", ""))
    value = float(num.replace(",", "."))
    return int(round(value * 1000)) if has_mil else int(value)


def amounts(text: str):
    """[(posição, valor, unidade, texto_seguinte_normalizado)]"""
    out = []
    for m in _AMOUNT_RE.finditer(text):
        val = _to_int(m.group(1), bool(m.group(2)))
        out.append((m.start(), val, norm(m.group(3)), norm(m.group(4) or "")))
    return out


def detect_program(snippet_norm: str):
    for name, rx in _PROGRAM_RES:
        if rx.search(snippet_norm):
            return name
    return None


def detect_cabin(text_norm: str) -> str:
    if re.search(r"primeira\s+classe|first\s+class|\bprimeira\b(?!\s+(vez|transferencia|compra|emissao))", text_norm) \
            and re.search(r"primeira\s+classe|first", text_norm):
        return "Primeira"
    if re.search(r"executiva|business|classe\s+premium\s+business", text_norm):
        return "Executiva"
    if re.search(r"economica\s+premium|premium\s+economy", text_norm):
        return "Premium Economy"
    return "Econômica"


def _places_with_roles(title: str, desc: str):
    """Descobre origem(ns) e destino a partir do título e da descrição."""
    origins, dest = [], None
    t = title
    tn = norm(t)

    # "entre São Paulo (GRU) e Nova York (JFK)" na descrição: rota explícita
    m = re.search(r"entre\s+(.{2,40}?)\s+e\s+(.{2,40}?)(?:[,.]|\s+(?:sao|os|com|a|operad))", norm(desc))
    route_origin = route_dest = None
    if m:
        a = find_places(desc[m.start(1):m.end(1)])
        b = find_places(desc[m.start(2):m.end(2)])
        if a and b:
            route_origin, route_dest = a[0][1], b[0][1]

    tp = find_places(t)
    # destino no título: o lugar logo após "para", "rumo a", "em" ...
    for pos, code in tp:
        before = tn[max(0, pos - 14):pos]
        if re.search(r"\b(para|pra|rumo a|a|ao|em|conhecer|visitar)\s+(o\s+|a\s+|os\s+|as\s+)?$", before):
            dest = code
            break
    if dest is None and route_dest:
        dest = route_dest
    if dest is None:
        # primeiro lugar do título que não esteja depois de "de/saindo de"
        for pos, code in tp:
            before = tn[max(0, pos - 14):pos]
            if not re.search(r"\b(de|saindo de|saidas de|partindo de|desde)\s+$", before):
                dest = code
                break

    # origens: "saindo de X", "saídas de X e Y", "de X para", rota explícita
    full = t + " . " + desc
    fn = norm(full)
    for m in re.finditer(r"(saindo|saidas|saida|partindo|partidas|embarques?|decolando)\s+(de|do|da|em)\s+", fn):
        window = full[m.end():m.end() + 70]
        cut = re.search(r"[.;:!?]|\s+(para|por|a partir|com|entre|em)\s", norm(window))
        window = window[:cut.start()] if cut else window
        for _, code in find_places(window):
            if code != dest and code not in origins:
                origins.append(code)
    for m in re.finditer(r"\bde\s+([A-ZÁ-Ú][^\s,]*(?:\s+[A-Za-zÁ-ú][^\s,]*){0,3})\s+(para|a|ao)\s", full):
        for _, code in find_places(m.group(1))[:1]:
            if code != dest and code not in origins:
                origins.append(code)
    if route_origin and route_origin != dest and route_origin not in origins:
        origins.insert(0, route_origin)
    return origins, dest


def _choose_price(title: str, desc: str):
    """Escolhe o preço principal (por trecho) e o programa do post."""
    ta, da = amounts(title), amounts(desc)
    # ignora valores que são bônus/brindes ("ganhe 2.000 milhas")
    def ok(text, pos):
        before = norm(text[max(0, pos - 30):pos])
        return not re.search(r"(ganhe|ganhar|bonus|extras?|adicionais|sortear|acumule)\s*(\w+\s+){0,3}$", before)

    ta = [a for a in ta if ok(title, a[0])]
    da = [a for a in da if ok(desc, a[0])]
    if not ta and not da:
        return None
    main = ta[0] if ta else da[0]
    value = main[1]
    # usa o valor exato da descrição quando o título arredonda ("61 mil" -> "61.343")
    main_desc = None
    if ta:
        for a in da:
            if value and abs(a[1] - value) / value < 0.12:
                value, main_desc = a[1], a
                break

    program = detect_program(main[3]) or (main_desc and detect_program(main_desc[3]))
    if not program:
        # "pontos" sem programa explícito: procurar no texto todo
        program = detect_program(norm(title)) or detect_program(norm(desc))
    if main[2] == "avios" and program not in ("Iberia (Avios)", "British Airways (Avios)", "Qatar (Avios)"):
        program = "Iberia (Avios)"

    # ida e volta -> por trecho
    context = norm(title[main[0]:main[0] + 80]) if ta else norm(desc[main[0]:main[0] + 80])
    if re.search(r"ida\s+e\s+volta", context) and not re.search(r"trecho", context):
        value //= 2
    return value, program


def parse_post(title: str, desc_html: str, link: str, pub: datetime, source: str):
    desc = clean(desc_html)
    title = clean(title)
    text_n = norm(title + " " + desc)
    title_n = norm(title)
    base = {
        "id": link,
        "titulo": title,
        "resumo": desc[:400],
        "link": link,
        "fonte": source,
        "publicado": pub.astimezone(BRT).isoformat(timespec="minutes"),
    }

    # 1) Bônus de transferência
    is_transfer = (re.search(r"bonus", title_n) and re.search(r"transfer", text_n)) or \
                  (re.search(r"transf(er|ir)", title_n) and re.search(r"bonus", text_n))
    # fora: cartão/conta nova, e o sentido inverso ("transferir pontos Azul para a ALL Accor")
    is_reverse = re.search(r"transfer\w*\s+(seus\s+)?pontos\s+(azul|smiles|latam)\s+para|para\s+(o|a)\s+all\b|accor", text_n)
    if is_transfer and not is_reverse and not re.search(r"\b(cartao|conta)\b", title_n):
        pct = [int(p) for p in _PERCENT_RE.findall(title + " " + desc[:250])]
        pct = [p for p in pct if 10 <= p <= 200]
        sources = [n for n, rx in _SOURCE_RES if rx.search(text_n)]
        # destino da transferência: programa aéreo citado (prioriza o título)
        targets = []
        for txt in (title_n, norm(desc[:300])):
            for n, rx in _PROGRAM_RES:
                if n in AIRLINE_PROGRAMS and rx.search(txt) and n not in targets:
                    targets.append(n)
        if pct and sources and targets:
            return {**base, "tipo": "transferencia",
                    "bonus_pct": max(pct),
                    "origens_pontos": sources,
                    "programas": targets,
                    "valido_ate": parse_deadline(title + " " + desc, pub)}

    # 2) Passagem com milhas
    is_trip = re.search(r"\b(voe|voos?|passagens?|trechos?|resgates?|emiss|bilhetes?|ida e volta|executiva|disponibilidade)\b", text_n)
    is_noise = re.search(r"\b(ganhe|cartao|assinatura|clube|sorte|sortear|compra de (milhas|pontos)|cupom de desconto na compra|status|cashback)\b", title_n)
    if is_trip and not is_noise and amounts(title + " " + desc):
        price = _choose_price(title, desc)
        origins, dest = _places_with_roles(title, desc)
        if price and dest and price[1]:
            value, program = price
            if 1500 <= value <= 600000:
                place = PLACES[dest]
                return {**base, "tipo": "passagem",
                        "milhas": value,
                        "programa": program,
                        "cabine": detect_cabin(text_n),
                        "destino": dest,
                        "destino_nome": place["nome"],
                        "pais": place["pais"],
                        "regiao": place["regiao"],
                        "origens": origins,
                        "sai_de_sp": any(is_sao_paulo(o) for o in origins),
                        "origem_informada": bool(origins)}

    # 3) Outras promoções Livelo/Esfera (citadas no título)
    if re.search(r"\b(livelo|esfera)\b", title_n):
        return {**base, "tipo": "outra",
                "origens_pontos": [n for n, rx in _SOURCE_RES[:2] if rx.search(text_n)],
                "valido_ate": parse_deadline(title + " " + desc, pub)}
    return None


def parse_deadline(text: str, pub: datetime):
    """Data-limite da promoção, quando o texto diz ("até amanhã (24)", "até 30/11", "até 2 de dezembro")."""
    n = norm(text)
    pub_brt = pub.astimezone(BRT)

    def mk(day, month=None):
        year = pub_brt.year
        if month is None:
            month = pub_brt.month
            if day < pub_brt.day - 3:  # dia menor que hoje -> mês seguinte
                month += 1
        if month > 12:
            month, year = 1, year + 1
        if month < pub_brt.month - 6:
            year += 1
        try:
            return datetime(year, month, day, 23, 59, tzinfo=BRT).isoformat(timespec="minutes")
        except ValueError:
            return None

    m = re.search(r"\bate\s+(?:o\s+dia\s+|dia\s+)?(\d{1,2})/(\d{1,2})", n)
    if m:
        return mk(int(m.group(1)), int(m.group(2)))
    m = re.search(r"\bate\s+(?:o\s+(?:proximo\s+)?dia\s+|dia\s+)?(\d{1,2})\s+de\s+(" + "|".join(_MONTHS) + ")", n)
    if m:
        return mk(int(m.group(1)), _MONTHS[m.group(2)])
    m = re.search(r"\bate\s+(?:hoje|amanha|esta|este|a\s+proxima|o\s+proximo|segunda|terca|quarta|quinta|sexta|sabado|domingo)[^(]{0,25}\((\d{1,2})(?:/(\d{1,2}))?\)", n)
    if m:
        return mk(int(m.group(1)), int(m.group(2)) if m.group(2) else None)
    if re.search(r"\b(so hoje|ate hoje|ultimo dia|termina hoje|acaba hoje)\b", n):
        return pub_brt.replace(hour=23, minute=59).isoformat(timespec="minutes")
    if re.search(r"\bate amanha\b", n):
        return (pub_brt + timedelta(days=1)).replace(hour=23, minute=59).isoformat(timespec="minutes")
    return None
