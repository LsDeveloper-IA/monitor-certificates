import os
import unittest
from unittest.mock import patch

from flask import Flask

from src.models.user import db
from src.routes.relatorio import relatorio_bp
from src.routes.relatorio import _sucessos_por_empresas_drive


def empresa(numero, motivo="Certificado não encontrado"):
    return {
        "cnpj": f"{numero:014d}",
        "nome": f"Empresa {numero}",
        "motivo": motivo,
    }


def relatorio(falhas=None, sucessos=None, certas=0, executado_em="2026-08-28T10:00:00"):
    return {
        "titulo": "RESUMO DA AUTOMAÇÃO SIEG",
        "executado_em": executado_em,
        "resumo": {
            "certas": certas,
            "ignorados": 0,
            "falhas": len(falhas or []),
        },
        "empresas_com_falha": falhas or [],
        "empresas_com_sucesso": sucessos or [],
    }


class RelatorioDriveTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["GOOGLE_DRIVE_PASTA_RELATORIOS_ID"] = "pasta-teste"
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.app.register_blueprint(relatorio_bp, url_prefix="/api")
        with self.app.app_context():
            db.create_all()
        self.cliente = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.environ.pop("GOOGLE_DRIVE_PASTA_RELATORIOS_ID", None)

    def test_empresas_do_drive_sem_falha_sao_listadas_como_sucesso(self):
        empresas_drive = [empresa(1), empresa(2), empresa(3)]

        sucessos = _sucessos_por_empresas_drive(
            empresas_drive,
            [empresa(2)],
            [],
        )

        self.assertEqual(
            [item["nome"] for item in sucessos],
            ["Empresa 1", "Empresa 3"],
        )

    @patch("src.routes.relatorio.ler_relatorio_json")
    @patch("src.routes.relatorio.listar_relatorios_json")
    @patch("src.routes.relatorio.conectar_google_drive")
    def test_acumula_sem_remover_empresas_ausentes(self, conectar, listar, ler):
        primeiro = {"id": "arquivo", "name": "resumo.json", "modifiedTime": "2026-08-28T10:00:00Z"}
        segundo = {"id": "arquivo", "name": "resumo.json", "modifiedTime": "2026-08-28T11:00:00Z"}
        falhas_iniciais = [empresa(numero) for numero in range(1, 62)]
        falhas_seguintes = [empresa(numero) for numero in range(1, 35)]
        listar.side_effect = [[primeiro], [primeiro, segundo]]
        ler.side_effect = [
            relatorio(falhas_iniciais, certas=289),
            relatorio(falhas_seguintes, certas=316, executado_em="2026-08-28T11:00:00"),
        ]

        resposta_inicial = self.cliente.get("/api/relatorios/certificados-vencidos")
        resposta_seguinte = self.cliente.get("/api/relatorios/certificados-vencidos")

        self.assertEqual(resposta_inicial.json["resumo"]["falhas"], 61)
        self.assertEqual(resposta_seguinte.json["resumo"]["falhas"], 61)
        self.assertEqual(len(resposta_seguinte.json["empresas_com_falha"]), 61)
        self.assertEqual(resposta_seguinte.json["historico"]["arquivos_processados"], 2)

    @patch("src.routes.relatorio.ler_relatorio_json")
    @patch("src.routes.relatorio.listar_relatorios_json")
    @patch("src.routes.relatorio.conectar_google_drive")
    def test_adiciona_novas_e_atualiza_sem_duplicar(self, conectar, listar, ler):
        primeiro = {"id": "a", "name": "1.json", "modifiedTime": "2026-08-28T10:00:00Z"}
        segundo = {"id": "b", "name": "2.json", "modifiedTime": "2026-08-28T11:00:00Z"}
        falhas_iniciais = [empresa(numero) for numero in range(1, 62)]
        falhas_novas = [empresa(numero, "Motivo atualizado") for numero in range(1, 30)]
        falhas_novas.extend(empresa(numero) for numero in range(62, 67))
        listar.return_value = [primeiro, segundo]
        ler.side_effect = [relatorio(falhas_iniciais), relatorio(falhas_novas)]

        resposta = self.cliente.get("/api/relatorios/certificados-vencidos")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["resumo"]["falhas"], 66)
        atualizada = next(
            item for item in resposta.json["empresas_com_falha"]
            if item["cnpj"] == "00000000000001"
        )
        self.assertEqual(atualizada["motivo"], "Motivo atualizado")
        self.assertEqual(atualizada["ocorrencias"], 2)

    @patch("src.routes.relatorio.ler_relatorio_json")
    @patch("src.routes.relatorio.listar_relatorios_json")
    @patch("src.routes.relatorio.conectar_google_drive")
    def test_releitura_do_mesmo_arquivo_e_idempotente(self, conectar, listar, ler):
        arquivo = {"id": "a", "name": "1.json", "modifiedTime": "2026-08-28T10:00:00Z"}
        listar.return_value = [arquivo]
        ler.return_value = relatorio([empresa(1)])

        primeira = self.cliente.get("/api/relatorios/certificados-vencidos")
        segunda = self.cliente.get("/api/relatorios/certificados-vencidos")

        self.assertEqual(primeira.json, segunda.json)
        ler.assert_called_once()

    @patch("src.routes.relatorio.ler_relatorio_json")
    @patch("src.routes.relatorio.listar_relatorios_json")
    @patch("src.routes.relatorio.conectar_google_drive")
    def test_sucesso_explicito_altera_status(self, conectar, listar, ler):
        primeiro = {"id": "a", "name": "1.json", "modifiedTime": "2026-08-28T10:00:00Z"}
        segundo = {"id": "b", "name": "2.json", "modifiedTime": "2026-08-28T11:00:00Z"}
        listar.return_value = [primeiro, segundo]
        ler.side_effect = [
            relatorio([empresa(1)]),
            relatorio([], [empresa(1)], certas=1, executado_em="2026-08-28T11:00:00"),
        ]

        resposta = self.cliente.get("/api/relatorios/certificados-vencidos")

        self.assertEqual(resposta.json["resumo"]["falhas"], 0)
        self.assertEqual(len(resposta.json["empresas_com_sucesso"]), 1)

    @patch("src.routes.relatorio.listar_relatorios_json", return_value=[])
    @patch("src.routes.relatorio.conectar_google_drive")
    def test_informa_quando_json_nao_existe(self, conectar, listar):
        resposta = self.cliente.get("/api/relatorios/certificados-vencidos")
        self.assertEqual(resposta.status_code, 404)


if __name__ == "__main__":
    unittest.main()
