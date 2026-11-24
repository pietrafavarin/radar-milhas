"""Baixa os feeds RSS dos blogs de milhas."""
import time
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEEDS = [
    ("Melhores Destinos", "https://www.melhoresdestinos.com.br/milhas/feed"),
    ("Melhores Destinos", "https://www.melhoresdestinos.com.br/feed"),
    ("Passageiro de Primeira", "https://passageirodeprimeira.com/categorias/passagens-aereas/feed/"),
    ("Passageiro de Primeira", "https://passageirodeprimeira.com/categorias/promocoes/feed/"),
    ("Passageiro de Primeira", "https://passageirodeprimeira.com/feed/"),
]

UA = "Mozilla/5.0 (compatible; RadarMilhas/1.0; uso pessoal)"
PAUSA = 1.5  # segundos entre pedidos


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml"})
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if getattr(e, "code", None) == 404:
                raise
            if tentativa == 2:
                raise
            time.sleep(3 * (tentativa + 1))
    return b""


def fetch_items(pages: int = 1, log=print):
    """Gera dicts {titulo, descricao, link, publicado, fonte} de todos os feeds."""
    vistos = set()
    for fonte, url in FEEDS:
        for page in range(1, pages + 1):
            page_url = url if page == 1 else f"{url}{'&' if '?' in url else '?'}paged={page}"
            try:
                raw = _get(page_url)
                root = ET.fromstring(raw)
            except Exception as e:  # noqa: BLE001
                log(f"  ! {page_url}: {e}")
                break
            items = root.findall(".//item")
            if not items:
                break
            for it in items:
                link = (it.findtext("link") or "").strip()
                if not link or link in vistos:
                    continue
                vistos.add(link)
                try:
                    pub = parsedate_to_datetime(it.findtext("pubDate"))
                except Exception:  # noqa: BLE001
                    continue
                yield {
                    "titulo": it.findtext("title") or "",
                    "descricao": it.findtext("description") or "",
                    "link": link,
                    "publicado": pub,
                    "fonte": fonte,
                }
            log(f"  {fonte} p{page}: {len(items)} posts")
            time.sleep(PAUSA)
