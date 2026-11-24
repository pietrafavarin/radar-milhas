import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar.notify import selecionar  # noqa: E402
from radar.parser import BRT  # noqa: E402

AGORA = datetime(2026, 11, 24, 12, 0, tzinfo=BRT)
CFG = {"desconto_min": 10, "so_sp": True}


def passagem(id_, desconto, origens, horas=5):
    pub = (AGORA - timedelta(hours=horas)).isoformat()
    return {"id": id_, "publicado": pub, "desconto_pct": desconto, "media": 10000, "milhas": 8000,
            "origens": origens, "origem_informada": bool(origens), "sai_de_sp": "SAO" in origens,
            "destino_nome": "X", "programa": "Smiles", "cabine": "Econômica", "link": "l", "titulo": "t"}


def transf(id_, pct, medio, ativa=True, foco=True):
    return {"id": id_, "ativa": ativa, "foco": foco, "bonus_pct": pct, "bonus_medio": medio,
            "origens_pontos": ["Livelo"], "programas": ["Smiles"], "valido_ate": None, "link": "l", "titulo": "t"}


class Selecao(unittest.TestCase):
    def test_regras(self):
        data = {"passagens": [
            passagem("sp-bom", 25, ["SAO"]),
            passagem("sem-origem", 15, []),
            passagem("rio", 40, ["RIO"]),          # fora: não sai de SP
            passagem("pouco", 5, ["SAO"]),         # fora: desconto pequeno
            passagem("velho", 30, ["SAO"], horas=80),  # fora: mais de 72h
        ], "transferencias": [
            transf("t-bom", 100, 80), transf("t-fraco", 60, 80), transf("t-fim", 100, 80, ativa=False),
            transf("t-itau", 100, 80, foco=False),
        ]}
        ids = {i for i, _, _ in selecionar(data, CFG, AGORA)}
        self.assertEqual(ids, {"sp-bom", "sem-origem", "t-bom"})


if __name__ == "__main__":
    unittest.main()
