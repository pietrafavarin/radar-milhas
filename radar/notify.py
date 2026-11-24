"""Alertas no Telegram para ofertas abaixo da média e bônus Livelo/Esfera.

Configuração (variáveis de ambiente / secrets do GitHub):
    TELEGRAM_TOKEN       token do bot (do @BotFather)
    TELEGRAM_CHAT_ID     seu chat id (descubra com: py run.py --descobrir-chat)
    ALERTA_DESCONTO_MIN  % mínimo abaixo da média para avisar (padrão 10)
    ALERTA_SO_SP         1 = só saindo de SP ou origem não informada (padrão 1)
Sem token configurado, nada é enviado.
"""
import html
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from .places import PLACES

MAX_POR_EXECUCAO = 8
JANELA_HORAS = 72


def _cfg():
    return {
        "token": os.environ.get("TELEGRAM_TOKEN", "").strip(),
        "chat": os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
        "desconto_min": float(os.environ.get("ALERTA_DESCONTO_MIN", "10")),
        "so_sp": os.environ.get("ALERTA_SO_SP", "1") != "0",
    }


def _api(token, metodo, params):
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(url, data=data, timeout=20) as r:
        return json.loads(r.read())


def enviar(texto, cfg=None):
    cfg = cfg or _cfg()
    return _api(cfg["token"], "sendMessage", {
        "chat_id": cfg["chat"], "text": texto, "parse_mode": "HTML", "disable_web_page_preview": "true"})


def descobrir_chat():
    """Mostra o chat id de quem mandou mensagem para o bot."""
    cfg = _cfg()
    if not cfg["token"]:
        print("Defina TELEGRAM_TOKEN primeiro.")
        return
    res = _api(cfg["token"], "getUpdates", {})
    chats = {(u.get("message") or {}).get("chat", {}).get("id") for u in res.get("result", [])}
    chats.discard(None)
    print("Chat id(s):", ", ".join(map(str, chats)) if chats else
          "nenhum. Mande um 'oi' para o seu bot no Telegram e rode de novo.")


def _fmt(n):
    return f"{n:,}".replace(",", ".")


def _msg_passagem(p):
    e = html.escape
    origem = ", ".join(PLACES.get(o, {}).get("nome", o) for o in p["origens"]) or "origem não informada"
    linhas = [
        f"✈️ <b>{e(p['destino_nome'])}</b> · {_fmt(p['milhas'])} {e(p['programa'])}/trecho",
        f"🔻 {p['desconto_pct']:.0f}% abaixo da média ({_fmt(p['media'])})" if p.get("desconto_pct") is not None else "",
        f"💺 {e(p['cabine'])} · 🛫 {e(origem)}",
    ]
    t = p.get("melhor_transferencia")
    if t:
        linhas.append(f"💳 {e(t['origem'])} +{t['bonus_pct']}% ativo → ≈ {_fmt(p['pontos_banco_necessarios'])} pontos")
    linhas.append(f'<a href="{e(p["link"])}">{e(p["titulo"])}</a>')
    return "\n".join(l for l in linhas if l)


def _msg_transfer(t):
    e = html.escape
    prazo = f"até {datetime.fromisoformat(t['valido_ate']):%d/%m}" if t.get("valido_ate") else "prazo não informado"
    usual = f" (usual {t['bonus_medio']}%)" if t.get("bonus_medio") is not None else ""
    return (f"💳 <b>{e(' / '.join(t['origens_pontos']))} → {e(', '.join(t['programas']))}: +{t['bonus_pct']}%</b>{usual}\n"
            f"⏰ {prazo}\n<a href=\"{e(t['link'])}\">{e(t['titulo'])}</a>")


def selecionar(data, cfg, agora):
    """Retorna [(id, mensagem, score)] candidatos a alerta."""
    corte = agora - timedelta(hours=JANELA_HORAS)
    out = []
    for p in data["passagens"]:
        if datetime.fromisoformat(p["publicado"]) < corte:
            continue
        if p.get("desconto_pct") is None or p["desconto_pct"] < cfg["desconto_min"]:
            continue
        if cfg["so_sp"] and p["origem_informada"] and not p["sai_de_sp"]:
            continue
        out.append((p["id"], _msg_passagem(p), p["desconto_pct"] + 20))
    for t in data["transferencias"]:
        if not (t["ativa"] and t["foco"]):
            continue
        if t.get("bonus_medio") is not None and t["bonus_pct"] < t["bonus_medio"]:
            continue
        out.append((t["id"], _msg_transfer(t), t["bonus_pct"]))
    return sorted(out, key=lambda x: -x[2])


def notificar(data, estado_path: Path, agora: datetime, simular=False, log=print):
    cfg = _cfg()
    if not simular and not (cfg["token"] and cfg["chat"]):
        log("Alertas: Telegram não configurado (pulei).")
        return
    enviados = set(json.loads(estado_path.read_text(encoding="utf-8"))) if estado_path.exists() else None
    candidatos = selecionar(data, cfg, agora)

    if enviados is None and not simular:
        # primeira execução: não despeja o passado, só avisa que ligou
        topo = "\n\n".join(m for _, m, _ in candidatos[:3])
        enviar("✅ <b>Radar de Milhas ativado.</b> Vou avisar quando surgir oferta boa.\n\n" +
               (f"Destaques de agora:\n\n{topo}" if topo else "Nada acima do limite agora."), cfg)
        estado_path.write_text(json.dumps(sorted(i for i, _, _ in candidatos)), encoding="utf-8")
        log(f"Alertas: primeira execução, {len(candidatos)} ofertas marcadas como vistas.")
        return

    enviados = enviados or set()
    novos = [c for c in candidatos if c[0] not in enviados][:MAX_POR_EXECUCAO]
    for id_, msg, _ in novos:
        if simular:
            log("---\n" + msg)
        else:
            enviar(msg, cfg)
        enviados.add(id_)
    if not simular:
        estado_path.write_text(json.dumps(sorted(enviados)), encoding="utf-8")
    log(f"Alertas: {len(novos)} {'simulados' if simular else 'enviados'}.")
