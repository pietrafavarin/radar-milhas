"""Compara cada oferta com o histórico e monta o JSON que o painel lê."""
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from .parser import BRT
from .places import PLACES

JANELA_HISTORICO = 365     # dias usados para calcular a média
JANELA_PAINEL = 120        # dias de passagens exibidas no painel
DIAS_DESTAQUE = 3          # "melhores do dia" olha os posts das últimas 72h
VALIDADE_PADRAO = 3        # promoção de transferência sem data-limite: considerada ativa por 3 dias
MIN_AMOSTRAS = 3
PROGRAMAS_FOCO = ("Livelo", "Esfera")


def _dt(s):
    return datetime.fromisoformat(s) if s else None


def media_aparada(valores):
    """Média sem os 10% mais altos e mais baixos (evita distorção por erro de leitura)."""
    v = sorted(valores)
    corte = int(len(v) * 0.1)
    if corte:
        v = v[corte:-corte]
    return statistics.fmean(v)


def transfer_ativa(t, agora):
    fim = _dt(t.get("valido_ate"))
    if fim:
        return fim >= agora
    return _dt(t["publicado"]) >= agora - timedelta(days=VALIDADE_PADRAO)


def build(posts: dict, agora: datetime | None = None) -> dict:
    agora = agora or datetime.now(BRT)
    todos = sorted(posts.values(), key=lambda p: p["publicado"])
    passagens = [p for p in todos if p["tipo"] == "passagem"]
    transfers = [p for p in todos if p["tipo"] == "transferencia"]
    outras = [p for p in todos if p["tipo"] == "outra"]

    # ---------- bônus de transferência ----------
    bonus_hist = defaultdict(list)
    for t in transfers:
        for o in t["origens_pontos"]:
            for prog in t["programas"]:
                bonus_hist[(o, prog)].append(t["bonus_pct"])
    for t in transfers:
        t["ativa"] = transfer_ativa(t, agora)
        t["foco"] = any(o in PROGRAMAS_FOCO for o in t["origens_pontos"])
        comps = [bonus_hist[(o, p)] for o in t["origens_pontos"] for p in t["programas"]]
        amostra = [b for c in comps for b in c]
        if len(amostra) >= MIN_AMOSTRAS:
            t["bonus_medio"] = round(media_aparada(amostra))
            t["acima_da_media"] = t["bonus_pct"] > t["bonus_medio"]

    ativas_foco = defaultdict(list)  # programa aéreo -> promoções Livelo/Esfera ativas
    for t in transfers:
        if t["ativa"]:
            for o in t["origens_pontos"]:
                if o in PROGRAMAS_FOCO:
                    for prog in t["programas"]:
                        ativas_foco[prog].append({"origem": o, "bonus_pct": t["bonus_pct"],
                                                  "valido_ate": t.get("valido_ate"), "link": t["link"],
                                                  "titulo": t["titulo"]})

    # ---------- passagens vs. média ----------
    por_chave = defaultdict(list)
    por_regiao = defaultdict(list)
    for p in passagens:
        por_chave[(p["destino"], p["programa"], p["cabine"])].append(p)
        por_regiao[(p["regiao"], p["programa"], p["cabine"])].append(p)

    def comparar(p, grupo, nivel):
        inicio = _dt(p["publicado"]) - timedelta(days=JANELA_HISTORICO)
        # compara com as outras ofertas (antes e depois), exceto ela mesma
        valores = [q["milhas"] for q in grupo if q["id"] != p["id"] and _dt(q["publicado"]) >= inicio]
        if len(valores) < (2 if nivel == "destino" else 5):
            return False
        media = media_aparada(valores)
        p["media"] = round(media)
        p["amostras"] = len(valores)
        p["base_media"] = nivel
        p["desconto_pct"] = round((1 - p["milhas"] / media) * 100, 1)
        p["abaixo_da_media"] = p["milhas"] < media
        return True

    for p in passagens:
        p.pop("media", None), p.pop("desconto_pct", None), p.pop("abaixo_da_media", None)
        if not comparar(p, por_chave[(p["destino"], p["programa"], p["cabine"])], "destino"):
            comparar(p, por_regiao[(p["regiao"], p["programa"], p["cabine"])], "regiao")
        promos = ativas_foco.get(p["programa"], [])
        p["transferencias_ativas"] = promos
        if promos:
            melhor = max(promos, key=lambda x: x["bonus_pct"])
            # assume paridade 1:1 (Livelo e Esfera -> Smiles/LATAM/Azul)
            p["pontos_banco_necessarios"] = math.ceil(p["milhas"] / (1 + melhor["bonus_pct"] / 100))
            p["melhor_transferencia"] = melhor

    # ---------- ranking do dia ----------
    corte = agora - timedelta(days=DIAS_DESTAQUE)
    recentes = [p for p in passagens if _dt(p["publicado"]) >= corte]

    def score(p):
        s = p.get("desconto_pct", 0) or 0
        if p["sai_de_sp"]:
            s += 15
        elif not p["origem_informada"]:
            s += 5
        if p.get("melhor_transferencia"):
            s += min(p["melhor_transferencia"]["bonus_pct"], 100) / 5
        if p["cabine"] in ("Executiva", "Primeira"):
            s += 5
        return round(s, 1)

    for p in recentes:
        p["score"] = score(p)
    destaques = sorted([p for p in recentes if p.get("desconto_pct", 0) >= 0],
                       key=lambda p: -p["score"])[:12]

    # ---------- resumo por destino ----------
    inicio_painel = agora - timedelta(days=JANELA_PAINEL)
    exibidas = [p for p in passagens if _dt(p["publicado"]) >= inicio_painel]
    destinos = {}
    for p in exibidas:
        d = destinos.setdefault(p["destino"], {
            "codigo": p["destino"], "nome": p["destino_nome"], "pais": p["pais"],
            "regiao": p["regiao"], "ofertas": 0, "ultima": None, "melhor_desconto": None,
            "programas": {}})
        d["ofertas"] += 1
        d["ultima"] = max(d["ultima"] or "", p["publicado"])
        if p.get("desconto_pct") is not None:
            d["melhor_desconto"] = max(d["melhor_desconto"] if d["melhor_desconto"] is not None else -999,
                                       p["desconto_pct"])
        chave = f'{p["programa"]} · {p["cabine"]}'
        grupo = por_chave[(p["destino"], p["programa"], p["cabine"])]
        hist = [q["milhas"] for q in grupo if _dt(q["publicado"]) >= agora - timedelta(days=JANELA_HISTORICO)]
        atual = d["programas"].get(chave)
        if not atual or p["milhas"] < atual["menor"]:
            d["programas"][chave] = {"menor": p["milhas"], "link": p["link"], "data": p["publicado"],
                                     "media": round(media_aparada(hist)) if len(hist) >= 2 else None,
                                     "amostras": len(hist)}

    # ---------- estatísticas por país e por região (12 meses), para a seção "Minha viagem" ----------
    def sai_do_brasil(p, aceita_sem_origem):
        if not p["origens"]:
            return aceita_sem_origem
        return any(PLACES.get(o, {}).get("pais") == "Brasil" for o in p["origens"])

    def stats(chave):
        # só voos saindo do Brasil (região: exige origem informada, para não misturar voos internos da Europa)
        grupos = defaultdict(list)
        for p in passagens:
            if _dt(p["publicado"]) >= agora - timedelta(days=JANELA_HISTORICO) and \
                    sai_do_brasil(p, aceita_sem_origem=(chave == "pais")) and p["regiao"] != "Nacional":
                grupos[(p[chave], f'{p["programa"]}|{p["cabine"]}')].append(p["milhas"])
        out = defaultdict(dict)
        for (k, pc), vals in grupos.items():
            out[k][pc] = {"media": round(media_aparada(vals)), "menor": min(vals), "n": len(vals)}
        return out

    bonus_usual, bonus_ativo = {}, {}
    for (o, prog), vals in bonus_hist.items():
        if o in PROGRAMAS_FOCO:
            bonus_usual[f"{o}|{prog}"] = {"media": round(media_aparada(vals)), "n": len(vals), "max": max(vals)}
    for t in transfers:
        if t["ativa"]:
            for o in t["origens_pontos"]:
                for prog in t["programas"]:
                    k = f"{o}|{prog}"
                    if o in PROGRAMAS_FOCO and t["bonus_pct"] > bonus_ativo.get(k, {}).get("bonus_pct", -1):
                        bonus_ativo[k] = {"bonus_pct": t["bonus_pct"], "valido_ate": t.get("valido_ate"),
                                          "link": t["link"], "titulo": t["titulo"]}

    # ---------- custo do milheiro (compra de milhas/pontos) ----------
    milheiro = {}
    janela_cpm = agora - timedelta(days=90)
    com_cpm = [p for p in todos if p.get("cpm") and _dt(p["publicado"]) >= janela_cpm]
    for prog in sorted({p["cpm_programa"] for p in com_cpm}):
        lista = sorted([p for p in com_cpm if p["cpm_programa"] == prog], key=lambda p: p["publicado"], reverse=True)
        livres = [p["cpm"] for p in lista if not p["cpm_requer"]]

        def resumo(p):
            return {"cpm": p["cpm"], "titulo": p["titulo"], "link": p["link"], "publicado": p["publicado"],
                    "valido_ate": p.get("valido_ate"), "requer": p["cpm_requer"]}

        ativos = [resumo(p) for p in lista if transfer_ativa(p, agora)]
        milheiro[prog] = {
            "tipico": round(statistics.median(livres), 2) if livres else None,
            "menor": min(livres) if livres else None,
            "n": len(livres),
            "ativos": sorted(ativos, key=lambda a: a["cpm"]),
            "recentes": [resumo(p) for p in lista[:6]],
        }

    return {
        "milheiro": milheiro,
        "stats_pais": stats("pais"),
        "stats_regiao": stats("regiao"),
        "bonus_usual": bonus_usual,
        "bonus_ativo": bonus_ativo,
        "gerado_em": agora.isoformat(timespec="minutes"),
        "destaques": destaques,
        "passagens": sorted(exibidas, key=lambda p: p["publicado"], reverse=True),
        "transferencias": sorted([t for t in transfers if _dt(t["publicado"]) >= agora - timedelta(days=120)],
                                 key=lambda t: (not t["ativa"], not t["foco"], t["publicado"]), reverse=False),
        "outras": sorted([o for o in outras if _dt(o["publicado"]) >= agora - timedelta(days=JANELA_PAINEL)],
                         key=lambda o: o["publicado"], reverse=True),
        "destinos": sorted(destinos.values(), key=lambda d: d["ultima"], reverse=True),
        "totais": {"posts_lidos": len(todos), "passagens": len(passagens),
                   "transferencias": len(transfers)},
    }
