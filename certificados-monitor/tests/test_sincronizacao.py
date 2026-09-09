import os
import unittest

from flask import Flask

from src.models.user import db
from src.routes.certificado import certificado_bp


class SincronizacaoTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["INTEGRACAO_API_KEY"] = "chave-de-teste"
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.app.register_blueprint(certificado_bp, url_prefix="/api")
        with self.app.app_context():
            db.create_all()
        self.cliente = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.environ.pop("INTEGRACAO_API_KEY", None)

    def enviar(self, certificados, chave="chave-de-teste"):
        return self.cliente.post(
            "/api/certificados/sincronizar",
            json={"certificados": certificados},
            headers={"X-API-Key": chave},
        )

    def test_bloqueia_chave_invalida(self):
        resposta = self.enviar([], chave="incorreta")
        self.assertEqual(resposta.status_code, 401)

    def test_bloqueia_criacao_sem_chave(self):
        resposta = self.cliente.post(
            "/api/certificados",
            json={
                "nome_empresa": "Empresa Teste",
                "cpf_cnpj": "12345678000190",
                "tipo": "PJ",
                "data_vencimento": "2027-05-05",
            },
        )
        self.assertEqual(resposta.status_code, 401)

    def test_mantem_consulta_sem_chave(self):
        resposta = self.cliente.get("/api/certificados")
        self.assertEqual(resposta.status_code, 200)

    def test_cria_e_atualiza_sem_duplicar_cnpj(self):
        certificado = {
            "empresa": "Empresa Teste",
            "cnpj": "12.345.678/0001-90",
            "vencimento": "2027-05-05",
            "email": "teste@example.com",
            "arquivo": "empresa.pfx",
        }
        criada = self.enviar([certificado])
        self.assertEqual(criada.status_code, 200)
        self.assertEqual(criada.json["criados"], 1)
        self.assertTrue(criada.json["primeira_carga"])
        self.assertEqual(criada.json["alteracoes_certificados"], [])

        certificado["email"] = "novo@example.com"
        atualizada = self.enviar([certificado])
        self.assertEqual(atualizada.status_code, 200)
        self.assertEqual(atualizada.json["atualizados"], 1)
        self.assertEqual(atualizada.json["inalterados"], 0)
        self.assertEqual(atualizada.json["alteracoes_certificados"], [])

        inalterada = self.enviar([certificado])
        self.assertEqual(inalterada.status_code, 200)
        self.assertEqual(inalterada.json["atualizados"], 0)
        self.assertEqual(inalterada.json["inalterados"], 1)
        self.assertEqual(
            inalterada.json["criados"]
            + inalterada.json["atualizados"]
            + inalterada.json["inalterados"]
            + len(inalterada.json["rejeitados"]),
            inalterada.json["recebidos"],
        )

        listagem = self.cliente.get("/api/certificados")
        self.assertEqual(len(listagem.json), 1)
        self.assertEqual(listagem.json[0]["email_contato"], "novo@example.com")
        self.assertIn("dias_para_vencimento", listagem.json[0])

    def test_rejeita_item_invalido_sem_interromper_lote(self):
        resposta = self.enviar(
            [
                {
                    "empresa": "Sem documento",
                    "cnpj": "123",
                    "vencimento": "2027-05-05",
                }
            ]
        )
        self.assertEqual(resposta.status_code, 207)
        self.assertEqual(len(resposta.json["rejeitados"]), 1)

    def test_mesmo_cnpj_com_arquivos_diferentes_cria_dois_registros(self):
        primeiro = {
            "empresa": "Empresa com filiais",
            "cnpj": "12.345.678/0001-90",
            "vencimento": "2027-05-05",
            "arquivo": "matriz.pfx",
        }
        segundo = {**primeiro, "arquivo": "filial.pfx"}

        resposta = self.enviar([primeiro, segundo])

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["criados"], 2)
        listagem = self.cliente.get("/api/certificados")
        self.assertEqual(len(listagem.json), 2)

    def test_lista_completa_desativa_certificado_ausente(self):
        antigo = {
            "empresa": "Empresa antiga",
            "cnpj": "12.345.678/0001-90",
            "vencimento": "2027-05-05",
            "arquivo": "antigo.pfx",
        }
        atual = {**antigo, "arquivo": "atual.pfx"}
        self.enviar([antigo])

        resposta = self.cliente.post(
            "/api/certificados/sincronizar",
            json={"certificados": [atual], "substituir_lista": True},
            headers={"X-API-Key": "chave-de-teste"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["desativados"], 1)
        self.assertEqual(
            resposta.json["alteracoes_certificados"][0]["tipo"],
            "renovado",
        )
        listagem = self.cliente.get("/api/certificados")
        self.assertEqual(len(listagem.json), 1)
        self.assertEqual(listagem.json[0]["arquivo_drive_id"], "atual.pfx")
        self.assertEqual(
            resposta.json["alteracoes_certificados"][0]["tipo"], "renovado"
        )

    def test_renovacao_desativa_certificado_antigo_sem_substituir_lista(self):
        antigo = {
            "empresa": "Empresa renovada",
            "cnpj": "12.345.678/0001-90",
            "vencimento": "2026-05-05",
            "arquivo": "antigo.pfx",
        }
        novo = {
            **antigo,
            "vencimento": "2027-05-05",
            "arquivo": "renovado.pfx",
        }
        self.enviar([antigo])

        resposta = self.enviar([novo])

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["desativados"], 1)
        self.assertEqual(
            resposta.json["alteracoes_certificados"][0]["tipo"],
            "renovado",
        )
        self.assertEqual(
            resposta.json["alteracoes_certificados"][0]["arquivo_anterior"],
            "antigo.pfx",
        )
        listagem = self.cliente.get("/api/certificados")
        self.assertEqual(len(listagem.json), 1)
        self.assertEqual(listagem.json[0]["arquivo_drive_id"], "renovado.pfx")

    def test_informa_quando_o_vencimento_muda(self):
        certificado = {
            "empresa": "Empresa Teste",
            "cnpj": "12.345.678/0001-90",
            "vencimento": "2027-05-05",
            "arquivo": "empresa.pfx",
        }
        self.enviar([certificado])

        certificado["vencimento"] = "2028-06-10"
        resposta = self.enviar([certificado])

        alteracao = resposta.json["alteracoes_certificados"][0]
        self.assertEqual(alteracao["tipo"], "vencimento_alterado")
        self.assertEqual(alteracao["vencimento_anterior"], "2027-05-05")
        self.assertEqual(alteracao["vencimento_novo"], "2028-06-10")


if __name__ == "__main__":
    unittest.main()
