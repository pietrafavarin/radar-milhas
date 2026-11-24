"""Lê a página completa das ofertas do Melhores Destinos para descobrir o período de viagem.

O resumo do feed raramente traz as datas; o texto completo do post traz ("para viajar em junho de 2027").
Cada post é lido uma única vez e só o período fica guardado (campo "periodo_artigo" em data/posts.json).
O Passageiro de Primeira mostra as datas só em imagem, então não é consultado.
"""
import html
import re
import time
from datetime import datetime

from .collect import PAUSA, _get
from .parser import clean, periodo_viagem


def _texto_do_artigo(page: str, resumo: str) -> str | None:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"\s+", " ", t)
    # o corpo começa onde está o resumo do feed; dali pegamos ~3.000 caracteres (evita barra lateral e anúncios)
    ancora = re.sub(r"\s+", " ", resumo)[:60].strip()
    i = t.find(ancora) if ancora else -1
    return t[i:i + 3000] if i >= 0 else None


def enriquecer(brutos: dict, precisa, limite: int = 40, log=print) -> int:
    """Busca o período nas páginas de até `limite` posts ainda não lidos. `precisa(bruto)` diz quais ler."""
    feitos = 0
    pendentes = sorted((b for b in brutos.values()
                        if b["fonte"] == "Melhores Destinos" and "periodo_artigo" not in b and precisa(b)),
                       key=lambda b: b["publicado"], reverse=True)
    for b in pendentes[:limite]:
        try:
            page = _get(b["link"]).decode("utf-8", "replace")
            corpo = _texto_do_artigo(page, clean(b["descricao"]))
            b["periodo_artigo"] = periodo_viagem(corpo, datetime.fromisoformat(b["publicado"])) if corpo else []
            feitos += 1
        except Exception as e:  # noqa: BLE001
            log(f"  ! {b['link']}: {e}")
        time.sleep(PAUSA)
    if pendentes:
        log(f"Períodos de viagem: {feitos} posts lidos ({max(0, len(pendentes) - limite)} ficam para a próxima)")
    return feitos
