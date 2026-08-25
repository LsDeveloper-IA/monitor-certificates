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

        certificado["email"] = "novo@example.com"
        atualizada = self.enviar([certificado])
        self.assertEqual(atualizada.status_code, 200)
        self.assertEqual(atualizada.json["atualizados"], 1)

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
        listagem = self.cliente.get("/api/certificados")
        self.assertEqual(len(listagem.json), 1)
        self.assertEqual(listagem.json[0]["arquivo_drive_id"], "atual.pfx")


if __name__ == "__main__":
    unittest.main()
