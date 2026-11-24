"""Lê as tabelas dos posts "Alerta PPV" do Pontos pra Voar.

Cada linha da tabela vira uma oferta com origem, destino, milhas e DATA do voo, por exemplo:
    Origem | Destino | Companhia | Trecho Clube/Diamante | Trecho Demais Clientes | Datas
    São Paulo (GRU) | Assunção (ASU) | GOL | 39.000 | 41.000 | 3 de dezembro
Cada post é lido uma única vez; as rotas ficam guardadas no histórico (campo "rotas" em data/posts.json).
"""
import html
import re
import time
from datetime import datetime

from .collect import PAUSA, _get
from .parser import BRT, _MONTHS, _MES_ABREV, AIRLINE_PROGRAMS, detect_cabin, detect_program, norm
from .places import PLACES, is_sao_paulo, place_from_airport

CATEGORIA = "https://pontospravoar.com/category/emissoes-com-pontos/"


def _cells(row_html):
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.S)]


def _num(txt):
    m = re.search(r"\d{1,3}(?:\.\d{3})+|\d{4,6}", txt or "")
    return int(m.group().replace(".", "")) if m else None


def _datas(txt, pub):
    """'24 de dezembro' / '3, 5 e 10 de junho' / 'junho' / '10/06' -> (primeira data ISO ou None, ['2027-06'])"""
    n = norm(txt)
    pub_ym = pub.year * 12 + pub.month - 1

    def ano_para(mes):
        return pub.year if pub.year * 12 + mes - 1 >= pub_ym else pub.year + 1

    out, primeira = [], None
    for dias, mes, ano in re.findall(r"((?:\d{1,2}\s*(?:,|e|a)\s*)*\d{1,2})?\s*(?:de\s+)?(" + "|".join(_MONTHS) + r")(?:\s+de\s+(20\d\d))?", n):
        mm = _MONTHS[mes]
        yy = int(ano) if ano else ano_para(mm)
        out.append(f"{yy}-{mm:02d}")
        if dias and not primeira:
            primeira = f"{yy}-{mm:02d}-{int(re.findall(r'\d{1,2}', dias)[0]):02d}"
    for d, mm in re.findall(r"\b(\d{1,2})/(\d{1,2})\b", n):
        mm = int(mm)
        if 1 <= mm <= 12:
            yy = ano_para(mm)
            out.append(f"{yy}-{mm:02d}")
            primeira = primeira or f"{yy}-{mm:02d}-{int(d):02d}"
    for ab, a2 in re.findall(r"\b(" + "|".join(_MES_ABREV) + r")\s*/\s*(\d{2})\b", n):
        out.append(f"20{a2}-{_MES_ABREV[ab]:02d}")
    return primeira, sorted(set(out))


def parse_alerta(page: str, titulo: str, pub: datetime):
    """Lista de rotas {origem, destino, milhas, cabine, companhia, data, periodo} do HTML de um Alerta PPV."""
    programa_post = detect_program(norm(titulo))
    rotas = []
    for tabela in re.findall(r"<table.*?</table>", page, re.S):
        linhas = [_cells(r) for r in re.findall(r"<tr.*?</tr>", tabela, re.S)]
        if len(linhas) < 2:
            continue
        cab = [norm(c) for c in linhas[0]]
        idx = lambda *nomes: next((i for i, c in enumerate(cab) if any(n in c for n in nomes)), None)  # noqa: E731
        i_o, i_d, i_dt, i_cia = idx("origem"), idx("destino"), idx("data"), idx("companhia", "cia")
        i_prog = idx("programa")
        if i_o is None or i_d is None:
            continue
        # colunas de preço: "Trecho Demais Clientes" é o preço para quem não é elite; colunas por cabine viram uma oferta cada
        precos = [i for i, c in enumerate(cab) if i not in (i_o, i_d, i_dt, i_cia, i_prog) and
                  re.search(r"trecho|milhas|pontos|avios|econ|exec|premium|primeira|tarifa|preco|valor", c)]
        por_cabine = [i for i in precos if re.search(r"econ|exec|premium|primeira", cab[i])]
        if por_cabine:
            colunas = [(i, detect_cabin(cab[i])) for i in por_cabine]
        else:
            demais = [i for i in precos if "demais" in cab[i]]
            escolha = demais[0] if demais else (precos[-1] if precos else None)
            colunas = [(escolha, detect_cabin(norm(titulo)))] if escolha is not None else []
        for ln in linhas[1:]:
            if len(ln) < len(cab) - 1:
                continue
            origem, destino = place_from_airport(ln[i_o]), place_from_airport(ln[i_d])
            nome_dest = re.sub(r"\s*\([A-Z]{3}\)", "", ln[i_d]).strip()
            iata = re.search(r"\(([A-Z]{3})\)", ln[i_d])
            data, periodo = _datas(ln[i_dt], pub) if i_dt is not None and i_dt < len(ln) else (None, [])
            for col, cabine in colunas:
                milhas = _num(ln[col]) if col < len(ln) else None
                if not milhas or not 1500 <= milhas <= 600000:
                    continue
                rotas.append({
                    "origem": origem, "origem_txt": ln[i_o], "destino": destino or (iata.group(1) if iata else nome_dest),
                    "destino_nome": PLACES[destino]["nome"] if destino else nome_dest,
                    "milhas": milhas, "cabine": cabine,
                    "programa": (detect_program(norm(ln[i_prog])) if i_prog is not None and i_prog < len(ln) else None) or programa_post,
                    "companhia": ln[i_cia] if i_cia is not None and i_cia < len(ln) else None,
                    "data": data, "periodo": periodo,
                })
    return rotas


def rotas_para_ofertas(bruto: dict):
    """Converte as rotas guardadas de um post em ofertas no mesmo formato das passagens dos blogs."""
    pub = datetime.fromisoformat(bruto["publicado"])
    titulo_n = norm(bruto["titulo"])
    out = []
    for i, r in enumerate(bruto.get("rotas", [])):
        dest = r["destino"]
        info = PLACES.get(dest)
        if info:
            pais, regiao = info["pais"], info["regiao"]
        elif re.search(r"\b(nacionais|nacional|brasil)\b", titulo_n):
            pais, regiao = "Brasil", "Nacional"
        else:
            continue  # destino desconhecido fora do Brasil: sem região não dá para comparar
        origens = [r["origem"]] if r["origem"] else []
        quando = f' em {datetime.fromisoformat(r["data"]):%d/%m/%Y}' if r.get("data") else ""
        out.append({
            "id": f'{bruto["link"]}#r{i}',
            "titulo": f'{r["origem_txt"]} → {r["destino_nome"]}{quando} · {bruto["titulo"]}',
            "resumo": "", "link": bruto["link"], "fonte": "Pontos pra Voar",
            "publicado": pub.astimezone(BRT).isoformat(timespec="minutes"),
            "tipo": "passagem", "milhas": r["milhas"], "programa": r["programa"], "cabine": r["cabine"],
            "destino": dest, "destino_nome": r["destino_nome"], "pais": pais, "regiao": regiao,
            "origens": origens, "sai_de_sp": any(is_sao_paulo(o) for o in origens), "origem_informada": True,
            "meses": [int(p[5:]) for p in r["periodo"]], "periodo": r["periodo"],
            "data_voo": r.get("data"), "companhia": r.get("companhia"), "de_tabela": True,
        })
    return out


def _e_alerta(b):
    return b["fonte"] == "Pontos pra Voar" and ("alerta-ppv" in b["link"] or norm(b["titulo"]).startswith("alerta ppv"))


def enriquecer_ppv(brutos: dict, limite=30, historico=True, log=print):
    """Lê as tabelas dos Alertas PPV ainda não lidos. Com historico=True, também busca os alertas
    listados na primeira página da categoria "Emissões com Pontos" (o feed só mostra os 20 posts mais recentes)."""
    lidos = 0
    if historico:
        try:
            cat = _get(CATEGORIA).decode("utf-8", "replace")
            for link in sorted(set(re.findall(r'href="(https://pontospravoar\.com/alerta-ppv[^"#?]+)"', cat))):
                if link not in brutos:
                    brutos[link] = {"link": link, "fonte": "Pontos pra Voar", "titulo": "", "descricao": "",
                                    "publicado": None}
            time.sleep(PAUSA)
        except Exception as e:  # noqa: BLE001
            log(f"  ! categoria PPV: {e}")

    pendentes = [b for b in brutos.values() if b["fonte"] == "Pontos pra Voar" and "rotas" not in b
                 and (_e_alerta(b) or not b.get("publicado"))]
    for b in pendentes[:limite]:
        try:
            page = _get(b["link"]).decode("utf-8", "replace")
            if not b.get("publicado"):  # veio da página da categoria: pegar título/data/resumo do próprio post
                meta = lambda p: re.search(r'<meta property="' + p + r'" content="([^"]*)"', page)  # noqa: E731
                b["titulo"] = html.unescape(meta("og:title").group(1)) if meta("og:title") else b["link"]
                b["descricao"] = html.unescape(meta("og:description").group(1)) if meta("og:description") else ""
                pt = meta("article:published_time")
                b["publicado"] = pt.group(1) if pt else datetime.now(BRT).isoformat()
            b["rotas"] = parse_alerta(page, b["titulo"], datetime.fromisoformat(b["publicado"]))
            lidos += 1
        except Exception as e:  # noqa: BLE001
            log(f"  ! {b['link']}: {e}")
        time.sleep(PAUSA)
    # remove entradas da categoria que não puderam ser lidas (sem data)
    for k in [k for k, b in brutos.items() if not b.get("publicado")]:
        del brutos[k]
    if pendentes:
        log(f"Alertas PPV: {lidos} lidos, {sum(len(b.get('rotas', [])) for b in brutos.values())} rotas com data no histórico")
    return lidos
