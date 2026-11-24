"""Dicionário de destinos: nome canônico, código, país, região e variações de escrita."""
import re
import unicodedata

NACIONAL = "Nacional"

# nome | código | país | região | apelidos (separados por ;)
_RAW = """
São Paulo|SAO|Brasil|Nacional|sao paulo;sampa;guarulhos;congonhas;gru;cgh
Campinas|VCP|Brasil|Nacional|viracopos;vcp
Rio de Janeiro|RIO|Brasil|Nacional|rio;galeao;santos dumont;gig;sdu
Belo Horizonte|CNF|Brasil|Nacional|bh;confins;cnf
Brasília|BSB|Brasil|Nacional|brasilia;bsb
Salvador|SSA|Brasil|Nacional|ssa
Recife|REC|Brasil|Nacional|rec;porto de galinhas
Fortaleza|FOR|Brasil|Nacional|
Natal|NAT|Brasil|Nacional|
João Pessoa|JPA|Brasil|Nacional|joao pessoa
Maceió|MCZ|Brasil|Nacional|maceio
Aracaju|AJU|Brasil|Nacional|
São Luís|SLZ|Brasil|Nacional|sao luis;lencois maranhenses
Teresina|THE|Brasil|Nacional|
Belém|BEL|Brasil|Nacional|belem
Manaus|MAO|Brasil|Nacional|
Macapá|MCP|Brasil|Nacional|macapa
Boa Vista|BVB|Brasil|Nacional|
Porto Velho|PVH|Brasil|Nacional|
Rio Branco|RBR|Brasil|Nacional|
Palmas|PMW|Brasil|Nacional|jalapao
Cuiabá|CGB|Brasil|Nacional|cuiaba;chapada dos guimaraes
Campo Grande|CGR|Brasil|Nacional|
Bonito|BYO|Brasil|Nacional|
Goiânia|GYN|Brasil|Nacional|goiania
Vitória|VIX|Brasil|Nacional|vitoria
Curitiba|CWB|Brasil|Nacional|
Florianópolis|FLN|Brasil|Nacional|florianopolis;floripa
Porto Alegre|POA|Brasil|Nacional|
Foz do Iguaçu|IGU|Brasil|Nacional|foz do iguacu;foz;cataratas
Navegantes|NVT|Brasil|Nacional|balneario camboriu;camboriu;beto carrero
Gramado|CXJ|Brasil|Nacional|caxias do sul;serra gaucha;canela
Porto Seguro|BPS|Brasil|Nacional|trancoso;arraial d'ajuda
Ilhéus|IOS|Brasil|Nacional|ilheus
Fernando de Noronha|FEN|Brasil|Nacional|noronha
Jericoacoara|JJD|Brasil|Nacional|jeri;jericoacoara
Uberlândia|UDI|Brasil|Nacional|uberlandia
Ribeirão Preto|RAO|Brasil|Nacional|ribeirao preto
Londrina|LDB|Brasil|Nacional|
Maringá|MGF|Brasil|Nacional|maringa
Joinville|JOI|Brasil|Nacional|
Chapecó|XAP|Brasil|Nacional|chapeco
Petrolina|PNZ|Brasil|Nacional|
Juazeiro do Norte|JDO|Brasil|Nacional|
Imperatriz|IMP|Brasil|Nacional|
Santarém|STM|Brasil|Nacional|santarem;alter do chao
Montes Claros|MOC|Brasil|Nacional|
Nordeste|NE|Brasil|Nacional|
Buenos Aires|BUE|Argentina|América do Sul|ezeiza;aeroparque;eze;aep
Bariloche|BRC|Argentina|América do Sul|
Mendoza|MDZ|Argentina|América do Sul|
Córdoba|COR|Argentina|América do Sul|cordoba
Ushuaia|USH|Argentina|América do Sul|
El Calafate|FTE|Argentina|América do Sul|calafate
Salta|SLA|Argentina|América do Sul|
Argentina|AR|Argentina|América do Sul|
Santiago|SCL|Chile|América do Sul|santiago do chile;scl
Punta Arenas|PUQ|Chile|América do Sul|
Puerto Natales|PNT|Chile|América do Sul|torres del paine
Atacama|CJC|Chile|América do Sul|san pedro de atacama;calama
Chile|CL|Chile|América do Sul|
Montevidéu|MVD|Uruguai|América do Sul|montevideu;montevideo
Punta del Este|PDP|Uruguai|América do Sul|
Uruguai|UY|Uruguai|América do Sul|
Lima|LIM|Peru|América do Sul|
Cusco|CUZ|Peru|América do Sul|cuzco;machu picchu
Peru|PE|Peru|América do Sul|
Bogotá|BOG|Colômbia|América do Sul|bogota
Medellín|MDE|Colômbia|América do Sul|medellin
Cartagena|CTG|Colômbia|América do Sul|
San Andrés|ADZ|Colômbia|América do Sul|san andres
Colômbia|CO|Colômbia|América do Sul|colombia
Quito|UIO|Equador|América do Sul|
Galápagos|GPS|Equador|América do Sul|galapagos
Assunção|ASU|Paraguai|América do Sul|assuncao;asuncion
La Paz|LPB|Bolívia|América do Sul|
Santa Cruz de la Sierra|VVI|Bolívia|América do Sul|santa cruz de la sierra
Cancún|CUN|México|Caribe e América Central|cancun;riviera maya;playa del carmen;tulum
Cidade do México|MEX|México|Caribe e América Central|cidade do mexico;mexico city
México|MX|México|Caribe e América Central|mexico
Punta Cana|PUJ|República Dominicana|Caribe e América Central|
Santo Domingo|SDQ|República Dominicana|Caribe e América Central|
Aruba|AUA|Aruba|Caribe e América Central|
Curaçao|CUR|Curaçao|Caribe e América Central|curacao
Havana|HAV|Cuba|Caribe e América Central|
Panamá|PTY|Panamá|Caribe e América Central|panama;cidade do panama
San José|SJO|Costa Rica|Caribe e América Central|costa rica
San Juan|SJU|Porto Rico|Caribe e América Central|porto rico
Caribe|CAR|Caribe|Caribe e América Central|
Nova York|NYC|EUA|América do Norte|nova york;nova iorque;new york;ny;jfk;newark;ewr
Miami|MIA|EUA|América do Norte|
Orlando|MCO|EUA|América do Norte|disney
Fort Lauderdale|FLL|EUA|América do Norte|fort lauderdale
Boston|BOS|EUA|América do Norte|
Washington|WAS|EUA|América do Norte|
Chicago|CHI|EUA|América do Norte|
Atlanta|ATL|EUA|América do Norte|
Dallas|DFW|EUA|América do Norte|
Houston|IAH|EUA|América do Norte|
Los Angeles|LAX|EUA|América do Norte|
San Francisco|SFO|EUA|América do Norte|sao francisco
Las Vegas|LAS|EUA|América do Norte|
Seattle|SEA|EUA|América do Norte|
Denver|DEN|EUA|América do Norte|
Nova Orleans|MSY|EUA|América do Norte|new orleans
Honolulu|HNL|EUA|América do Norte|havai;hawaii
Estados Unidos|US|EUA|América do Norte|eua;estados unidos
Toronto|YTO|Canadá|América do Norte|
Montreal|YUL|Canadá|América do Norte|
Vancouver|YVR|Canadá|América do Norte|
Canadá|CA|Canadá|América do Norte|canada
Lisboa|LIS|Portugal|Europa|
Porto|OPO|Portugal|Europa|cidade do porto
Faro|FAO|Portugal|Europa|algarve
Funchal|FNC|Portugal|Europa|madeira
Ponta Delgada|PDL|Portugal|Europa|acores;azores
Portugal|PT|Portugal|Europa|
Madri|MAD|Espanha|Europa|madrid
Barcelona|BCN|Espanha|Europa|
Sevilha|SVQ|Espanha|Europa|sevilla
Málaga|AGP|Espanha|Europa|malaga
Palma de Mallorca|PMI|Espanha|Europa|mallorca;maiorca
Espanha|ES|Espanha|Europa|
Paris|PAR|França|Europa|
Nice|NCE|França|Europa|
França|FR|França|Europa|franca
Londres|LON|Reino Unido|Europa|london;heathrow
Edimburgo|EDI|Reino Unido|Europa|edinburgh
Dublin|DUB|Irlanda|Europa|
Roma|ROM|Itália|Europa|
Milão|MIL|Itália|Europa|milao;milan
Veneza|VCE|Itália|Europa|veneza;venice
Florença|FLR|Itália|Europa|florenca
Nápoles|NAP|Itália|Europa|napoles
Itália|IT|Itália|Europa|italia
Frankfurt|FRA|Alemanha|Europa|
Munique|MUC|Alemanha|Europa|munich
Berlim|BER|Alemanha|Europa|berlin
Alemanha|DE|Alemanha|Europa|
Amsterdã|AMS|Holanda|Europa|amsterda;amsterdam;amsterda
Bruxelas|BRU|Bélgica|Europa|
Zurique|ZRH|Suíça|Europa|zurich
Genebra|GVA|Suíça|Europa|
Suíça|CH|Suíça|Europa|suica
Viena|VIE|Áustria|Europa|
Praga|PRG|República Tcheca|Europa|
Budapeste|BUD|Hungria|Europa|
Atenas|ATH|Grécia|Europa|
Santorini|JTR|Grécia|Europa|
Grécia|GR|Grécia|Europa|grecia
Istambul|IST|Turquia|Europa|istanbul
Copenhague|CPH|Dinamarca|Europa|
Estocolmo|STO|Suécia|Europa|
Oslo|OSL|Noruega|Europa|
Helsinque|HEL|Finlândia|Europa|
Reykjavik|REK|Islândia|Europa|islandia
Varsóvia|WAW|Polônia|Europa|varsovia
Croácia|HR|Croácia|Europa|croacia;dubrovnik;split
Europa|EU|Europa|Europa|
Dubai|DXB|Emirados Árabes|Oriente Médio|
Abu Dhabi|AUH|Emirados Árabes|Oriente Médio|
Doha|DOH|Catar|Oriente Médio|
Tel Aviv|TLV|Israel|Oriente Médio|
Cairo|CAI|Egito|África|
Marrakech|RAK|Marrocos|África|marraquexe
Casablanca|CMN|Marrocos|África|
Cidade do Cabo|CPT|África do Sul|África|cape town
Joanesburgo|JNB|África do Sul|África|johannesburgo;johannesburg
Luanda|LAD|Angola|África|
Ilhas Maurício|MRU|Maurício|África|mauricio
Tóquio|TYO|Japão|Ásia|toquio;tokyo
Osaka|OSA|Japão|Ásia|
Japão|JP|Japão|Ásia|japao
Seul|SEL|Coreia do Sul|Ásia|seoul
Pequim|BJS|China|Ásia|beijing
Xangai|SHA|China|Ásia|shanghai
Hong Kong|HKG|Hong Kong|Ásia|
Singapura|SIN|Singapura|Ásia|singapore
Bangkok|BKK|Tailândia|Ásia|bangcoc
Phuket|HKT|Tailândia|Ásia|
Tailândia|TH|Tailândia|Ásia|tailandia
Bali|DPS|Indonésia|Ásia|denpasar
Maldivas|MLE|Maldivas|Ásia|male
Nova Délhi|DEL|Índia|Ásia|nova delhi;delhi
Índia|IN|Índia|Ásia|india
Sydney|SYD|Austrália|Oceania|sidney
Melbourne|MEL|Austrália|Oceania|
Austrália|AU|Austrália|Oceania|australia
Auckland|AKL|Nova Zelândia|Oceania|
Papeete|PPT|Polinésia Francesa|Oceania|taiti;tahiti;bora bora
"""


def norm(text: str) -> str:
    """minúsculas e sem acentos, para comparação."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


PLACES = {}  # código -> dados
_ALIASES = []  # (alias_normalizado, código)

for _line in _RAW.strip().splitlines():
    _name, _code, _country, _region, _al = _line.split("|")
    PLACES[_code] = {"nome": _name, "codigo": _code, "pais": _country, "regiao": _region}
    names = {norm(_name)} | {a.strip() for a in _al.split(";") if a.strip()}
    for a in names:
        _ALIASES.append((a, _code))

# Mais longos primeiro, para "Santiago do Chile" vencer "Santiago" e "Porto Seguro" vencer "Porto".
_ALIASES.sort(key=lambda x: -len(x[0]))
_SHORT_CODES = {a for a, _ in _ALIASES if len(a) <= 3}  # códigos IATA: só em maiúsculas no texto original
_PATTERN = re.compile(r"(?<![\w])(" + "|".join(re.escape(a) for a, _ in _ALIASES) + r")(?![\w])")
_LOOKUP = dict((a, c) for a, c in reversed(_ALIASES))
_LOOKUP.update({a: c for a, c in _ALIASES})


def find_places(text: str):
    """Lista de (posição, código) dos lugares citados no texto, sem sobreposição."""
    n = norm(text)
    out = []
    for m in _PATTERN.finditer(n):
        alias = m.group(1)
        orig = text[m.start():m.end()]
        # nomes próprios: precisam começar com maiúscula ("bonito", "natal" no meio da frase não contam)
        if not orig[0].isupper():
            continue
        # códigos curtos (GRU, NY, BH): precisam estar todos em maiúsculas; "Rio" é exceção
        if alias in _SHORT_CODES and alias != "rio" and orig != orig.upper():
            continue
        # "Singapore Airlines", "Qatar Airways", "Turkish Airlines": é a companhia, não o destino
        if re.match(r"\s+(airlines|airways|air\b)", n[m.end():m.end() + 10]):
            continue
        if alias == "natal":
            before = n[max(0, m.start() - 7):m.start()]
            after = n[m.end():m.end() + 12]
            if re.search(r"\b(o|no|do|neste|este|pro|pelo|ao|de)\s+$", before) and not re.search(r"\b(saindo|partindo|saidas)\s+de\s+$", n[max(0, m.start() - 15):m.start()]):
                continue
            if re.match(r"\s+e\s+(ano novo|reveillon)", after):
                continue
        out.append((m.start(), _LOOKUP[alias]))
    return out


# aeroporto -> código da cidade usado aqui (quando diferente)
AIRPORTS = {
    "GRU": "SAO", "CGH": "SAO", "GIG": "RIO", "SDU": "RIO", "PLU": "CNF", "EZE": "BUE", "AEP": "BUE",
    "JFK": "NYC", "EWR": "NYC", "LGA": "NYC", "IAD": "WAS", "DCA": "WAS", "ORD": "CHI", "MDW": "CHI",
    "YYZ": "YTO", "CDG": "PAR", "ORY": "PAR", "LHR": "LON", "LGW": "LON", "STN": "LON",
    "FCO": "ROM", "CIA": "ROM", "MXP": "MIL", "LIN": "MIL", "BGY": "MIL", "ARN": "STO", "KEF": "REK",
    "NRT": "TYO", "HND": "TYO", "KIX": "OSA", "ICN": "SEL", "PEK": "BJS", "PKX": "BJS", "PVG": "SHA",
    "SAW": "IST", "CJC": "CJC", "BER": "BER", "TXL": "BER",
}


def place_from_airport(text: str):
    """'Roma (FCO)' -> código conhecido (ROM) ou None."""
    m = re.search(r"\(([A-Z]{3})\)", text)
    if m:
        iata = m.group(1)
        code = AIRPORTS.get(iata, iata)
        if code in PLACES:
            return code
    found = find_places(text)
    return found[0][1] if found else None


def is_sao_paulo(code: str) -> bool:
    return code in {"SAO", "VCP"}
