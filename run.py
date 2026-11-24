"""Roda o radar: coleta os blogs, atualiza o histórico e gera docs/data.json.

Uso:
    py run.py               # coleta diária (2 páginas por feed)
    py run.py --paginas 25  # primeira carga: puxa ~meses de histórico
    py run.py --offline     # só reprocessa o histórico salvo (útil após mudar o extrator)
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from radar import notify
from radar.analyze import build
from radar.collect import fetch_items
from radar.enrich import enriquecer
from radar.ppv import enriquecer_ppv, rotas_para_ofertas
from radar.parser import parse_post

RAIZ = Path(__file__).parent
BRUTO = RAIZ / "data" / "posts.json"     # texto original de cada post (permite reprocessar)
SAIDA = RAIZ / "docs" / "data.json"
ALERTADOS = RAIZ / "data" / "alertados.json"  # ids já avisados (para não repetir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paginas", type=int, default=2)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--periodos", type=int, default=40, help="máx. de posts para ler o período de viagem (0 = não ler)")
    ap.add_argument("--sem-alertas", action="store_true", help="não envia Telegram")
    ap.add_argument("--simular-alertas", action="store_true", help="mostra os alertas sem enviar")
    ap.add_argument("--testar-alerta", action="store_true", help="envia uma mensagem de teste e sai")
    ap.add_argument("--descobrir-chat", action="store_true", help="mostra seu TELEGRAM_CHAT_ID e sai")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if args.descobrir_chat:
        return notify.descobrir_chat()
    if args.testar_alerta:
        notify.enviar("🧪 Teste do Radar de Milhas: os alertas estão funcionando.")
        return print("Mensagem de teste enviada.")

    brutos = json.loads(BRUTO.read_text(encoding="utf-8")) if BRUTO.exists() else {}
    # formato antigo (já processado) não tem "descricao": descarta
    brutos = {k: v for k, v in brutos.items() if "descricao" in v}
    antes = len(brutos)

    if not args.offline:
        print(f"Coletando {args.paginas} página(s) por feed…")
        for item in fetch_items(args.paginas):
            brutos[item["link"]] = {**item, "publicado": item["publicado"].isoformat()}

    def parse(b):
        return parse_post(b["titulo"], b["descricao"], b["link"], datetime.fromisoformat(b["publicado"]), b["fonte"])

    if not args.offline and args.periodos:
        # ofertas de passagem sem período no resumo: ler a página completa (só Melhores Destinos)
        def precisa(b):
            r = parse(b)
            return bool(r and r["tipo"] == "passagem" and not r["periodo"])
        enriquecer(brutos, precisa, limite=args.periodos)
        # tabelas com datas dos Alertas PPV (Pontos pra Voar)
        enriquecer_ppv(brutos, limite=args.periodos)

    BRUTO.parent.mkdir(exist_ok=True)
    BRUTO.write_text(json.dumps(brutos, ensure_ascii=False, indent=0), encoding="utf-8")

    posts = {}
    for b in brutos.values():
        rec = parse(b)
        if rec and rec["tipo"] == "passagem" and b.get("rotas"):
            rec = None  # o alerta já virou ofertas linha a linha; não contar o título de novo
        if rec:
            if rec["tipo"] == "passagem" and b.get("periodo_artigo"):
                rec["periodo"] = sorted(set(rec["periodo"]) | set(b["periodo_artigo"]))
            posts[rec["id"]] = rec
        # cada linha das tabelas do PPV vira uma oferta com data
        for oferta in rotas_para_ofertas(b):
            posts[oferta["id"]] = oferta

    data = build(posts)
    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    t = data["totais"]
    print(f"Histórico: {len(brutos)} posts ({len(brutos) - antes} novos) · "
          f"{t['passagens']} passagens · {t['transferencias']} promoções de transferência")
    print(f"Destaques de hoje: {len(data['destaques'])}")
    for p in data["destaques"][:5]:
        d = p.get("desconto_pct")
        desc = "sem histórico" if d is None else (f"{d:.0f}% abaixo da média" if d > 0 else f"{-d:.0f}% acima da média")
        print(f"  {p['destino_nome']:18} {p['milhas']:>7,} {str(p['programa']):16} {p['cabine']:10} {desc}")

    if args.simular_alertas:
        notify.notificar(data, ALERTADOS, datetime.fromisoformat(data["gerado_em"]), simular=True)
    elif not args.sem_alertas:
        try:
            notify.notificar(data, ALERTADOS, datetime.fromisoformat(data["gerado_em"]))
        except Exception as e:  # noqa: BLE001  (falha no Telegram não pode derrubar a atualização do painel)
            print(f"Alertas: erro ao enviar ({e})")


if __name__ == "__main__":
    main()
