import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar.parser import BRT  # noqa: E402
from radar.ppv import parse_alerta, rotas_para_ofertas  # noqa: E402

PUB = datetime(2026, 11, 23, 17, 30, tzinfo=BRT)

TABELA = """<table><tr><th>Origem</th><th>Destino</th><th>Companhia Aérea</th><th>Trecho Clube/Diamante</th>
<th>Trecho Demais Clientes</th><th>Datas</th><th>Reservas</th></tr>
<tr><td>São Paulo (GRU)</td><td>Assunção (ASU)</td><td>GOL</td><td>39.000</td><td>41.000</td><td>3 de dezembro</td><td><a>Reserve aqui</a></td></tr>
<tr><td>Rio de Janeiro (GIG)</td><td>Roma (FCO)</td><td>ITA</td><td>80.000</td><td>85.000</td><td>10 e 12 de junho</td><td>Reserve aqui</td></tr>
<tr><td>Rio de Janeiro (GIG)</td><td>Rosário (ROS)</td><td>GOL</td><td>28.000</td><td>29.000</td><td>12 de janeiro</td><td>Reserve aqui</td></tr>
</table>"""

TABELA_CABINES = """<table><tr><td>Origem</td><td>Destino</td><td>Econômica</td><td>Executiva</td><td>Datas</td></tr>
<tr><td>São Paulo (GRU)</td><td>Milão (MXP)</td><td>62.000</td><td>190.000</td><td>junho</td></tr></table>"""


class Alertas(unittest.TestCase):
    def test_tabela_com_demais_clientes(self):
        rotas = parse_alerta(TABELA, "Alerta PPV! Confira voos internacionais a partir de 22 mil milhas Smiles + taxas", PUB)
        self.assertEqual(len(rotas), 3)
        asu, roma, _ = rotas
        self.assertEqual((asu["origem"], asu["destino"], asu["milhas"], asu["data"], asu["programa"]),
                         ("SAO", "ASU", 41000, "2026-12-03", "Smiles"))
        self.assertEqual((roma["destino"], roma["data"], roma["periodo"]), ("ROM", "2027-06-10", ["2027-06"]))

    def test_colunas_por_cabine(self):
        rotas = parse_alerta(TABELA_CABINES, "Alerta PPV: Europa com milhas LATAM Pass", PUB)
        self.assertEqual([(r["cabine"], r["milhas"]) for r in rotas], [("Econômica", 62000), ("Executiva", 190000)])
        self.assertEqual(rotas[0]["periodo"], ["2027-06"])

    def test_vira_oferta(self):
        bruto = {"link": "https://pontospravoar.com/alerta-ppv-x/", "titulo": "Alerta PPV! Voos internacionais Smiles",
                 "publicado": PUB.isoformat(), "rotas": parse_alerta(TABELA, "Alerta PPV Smiles", PUB)}
        ofertas = rotas_para_ofertas(bruto)
        # Rosário não está no dicionário e o post não é nacional: fica de fora
        self.assertEqual([o["destino"] for o in ofertas], ["ASU", "ROM"])
        roma = ofertas[1]
        self.assertEqual((roma["pais"], roma["periodo"], roma["data_voo"]), ("Itália", ["2027-06"], "2027-06-10"))
        self.assertFalse(roma["sai_de_sp"])


if __name__ == "__main__":
    unittest.main()
