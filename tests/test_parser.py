"""Casos reais de títulos/resumos dos blogs. Rode com: py -m unittest discover -s tests"""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar.parser import BRT, parse_post  # noqa: E402

PUB = datetime(2026, 11, 23, 10, 0, tzinfo=BRT)


def p(title, desc=""):
    return parse_post(title, desc, "https://x/" + title[:20], PUB, "teste")


class Passagens(unittest.TestCase):
    def test_smiles_nova_york_rota_explicita(self):
        r = p("Ótimo preço! Voe para Nova York a partir de 66 mil milhas Smiles + taxas",
              "Encontramos disponibilidade de bilhetes ida e volta entre São Paulo (GRU) e Nova York (JFK). "
              "Os voos são operados pela American Airlines e a emissão pode ser feita a partir de 66.800 milhas Smiles + taxas por trecho.")
        self.assertEqual(r["tipo"], "passagem")
        self.assertEqual((r["milhas"], r["programa"], r["destino"], r["cabine"]), (66800, "Smiles", "NYC", "Econômica"))
        self.assertTrue(r["sai_de_sp"])

    def test_avios_maiusculo(self):
        r = p("Voe de Recife para Madri a partir de 16 mil Avios Iberia Club + taxas")
        self.assertEqual((r["milhas"], r["programa"], r["destino"], r["origens"]), (16000, "Iberia (Avios)", "MAD", ["REC"]))

    def test_executiva_latam(self):
        r = p("Executiva da Aeromexico de São Paulo para Tóquio a partir de R$ 6.783 ou 285 mil milhas LATAM Pass + taxas")
        self.assertEqual((r["milhas"], r["programa"], r["destino"], r["cabine"]), (285000, "LATAM Pass", "TYO", "Executiva"))
        self.assertTrue(r["sai_de_sp"])

    def test_azul_pontos_com_origem(self):
        r = p("Nordeste com a Azul! Voos para João Pessoa saindo de Campinas a partir de 8 mil pontos o trecho",
              "voos para João Pessoa a partir de 8.400 pontos Azul o trecho")
        self.assertEqual((r["milhas"], r["programa"], r["destino"], r["origens"]), (8400, "Azul Fidelidade", "JPA", ["VCP"]))
        self.assertTrue(r["sai_de_sp"])

    def test_bonus_de_milhas_nao_vira_preco(self):
        r = p("Voe para Gramado na Páscoa a partir de R$ 117 ou 4 mil milhas LATAM + taxas",
              "A partir de 4.159 milhas. Ganhe 2.000 milhas extras na primeira transferência.")
        self.assertEqual(r["milhas"], 4159)
        self.assertEqual(r["destino"], "CXJ")

    def test_companhia_nao_e_destino(self):
        r = p("Singapore Airlines oferece 30% de desconto em trechos selecionados no KrisFlyer")
        self.assertNotEqual((r or {}).get("destino"), "SIN")

    def test_cartao_nao_e_passagem(self):
        self.assertIsNone(p("Bom demais! Peça o cartão Latam Pass Itaú e ganhe até 80 mil milhas bônus"))

    def test_natal_feriado_nao_e_cidade(self):
        r = p("Voos para o Natal a partir de 9 mil milhas Smiles para Salvador")
        self.assertEqual(r["destino"], "SSA")


class MesesDeViagem(unittest.TestCase):
    def test_intervalo(self):
        from radar.parser import months_mentioned
        self.assertEqual(months_mentioned("poucas datas disponiveis entre os meses de marco e maio de 2027"), [3, 4, 5])
        self.assertEqual(months_mentioned("datas entre marco e maio de 2027"), [3, 4, 5])
        self.assertEqual(months_mentioned("voos de novembro a fevereiro"), [1, 2, 11, 12])
        self.assertEqual(months_mentioned("voos entre o rio de janeiro (gig) e milao"), [])

    def test_prazo_nao_e_viagem(self):
        from radar.parser import months_mentioned
        self.assertEqual(months_mentioned("promocao valida ate 30 de novembro para voos em junho"), [6])
        self.assertEqual(months_mentioned("ate dezembro"), [])

    def test_abreviado(self):
        from radar.parser import months_mentioned
        self.assertEqual(months_mentioned("datas em jun/27 e jul/27"), [6, 7])


class PeriodoComAno(unittest.TestCase):
    def per(self, txt):
        from radar.parser import periodo_viagem
        return periodo_viagem(txt, datetime(2026, 11, 13, tzinfo=BRT))

    def test_frases_reais(self):
        self.assertEqual(self.per("O menor preço é para viajar em junho de 2027, por 16.800 pontos ida e volta."), ["2027-06"])
        self.assertEqual(self.per("com datas para viajar principalmente em agosto de 2027 ."), ["2027-08"])
        self.assertEqual(self.per("São oportunidades para viajar entre novembro de 2026 e setembro de 2027 ."),
                         ["2026-11", "2026-12"] + [f"2027-{m:02d}" for m in range(1, 10)])
        self.assertEqual(self.per("bons preços saindo de Brasília e do Rio de Janeiro, para viajar entre fevereiro e março de 2027."),
                         ["2027-02", "2027-03"])

    def test_prazo_da_promocao_nao_conta(self):
        self.assertEqual(self.per("A campanha é válida para contas abertas até às 23h59 de 6 de janeiro de 2027."), [])

    def test_sem_datas(self):
        self.assertEqual(self.per("Encontramos disponibilidade entre o Rio de Janeiro (GIG) e Milão (MXP)."), [])


class Transferencias(unittest.TestCase):
    def test_livelo_latam(self):
        r = p("LATAM FRIDAY! Ganhe 27% de bônus nas transferências de pontos Livelo",
              "O LATAM Pass está oferecendo 27% de milhas bônus nas transferências da Livelo até amanhã (24).")
        self.assertEqual(r["tipo"], "transferencia")
        self.assertEqual((r["bonus_pct"], r["origens_pontos"], r["programas"]), (27, ["Livelo"], ["LATAM Pass"]))
        self.assertTrue(r["valido_ate"].startswith("2026-11-24"))

    def test_esfera_smiles_data(self):
        r = p("Smiles oferece até 90% de bônus na transferência de pontos Esfera",
              "Promoção válida até 30/11 para clientes Santander.")
        self.assertEqual((r["bonus_pct"], r["programas"]), (90, ["Smiles"]))
        self.assertIn("Esfera", r["origens_pontos"])
        self.assertTrue(r["valido_ate"].startswith("2026-11-30"))

    def test_transfira_no_titulo(self):
        r = p("Milheiro LATAM a partir de R$ 23,55! Transfira pontos Livelo para o LATAM Pass",
              "Ganhe até 25% de bônus ao transferir até 2 de dezembro.")
        self.assertEqual(r["tipo"], "transferencia")
        self.assertTrue(r["valido_ate"].startswith("2026-12-02"))

    def test_conta_nomad_nao_e_transferencia(self):
        r = p("Abra a conta Nomad e ganhe até 30 mil pontos Azul e 50% de bônus na transferência")
        self.assertNotEqual((r or {}).get("tipo"), "transferencia")


if __name__ == "__main__":
    unittest.main()
