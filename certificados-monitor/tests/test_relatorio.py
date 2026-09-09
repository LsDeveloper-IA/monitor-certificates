import os
import json
import unittest
from unittest.mock import patch

from flask import Flask

from src.models.user import db
from src.routes.relatorio import relatorio_bp
from src.routes.relatorio import _consolidar_categorias, _carregar_base_empresas_sieg


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
        leitor_auto_nc = patch("src.routes.relatorio._carregar_empresas_sem_certificado", return_value=[])
        leitor_auto_nc.start()
        self.addCleanup(leitor_auto_nc.stop)
        leitor_sieg = patch("src.routes.relatorio._carregar_base_empresas_sieg", return_value=None)
        leitor_sieg.start()
        self.addCleanup(leitor_sieg.stop)
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

        sucessos = _consolidar_categorias({
            "empresas_com_sucesso": empresas_drive,
            "empresas_com_falha": [empresa(2)],
        })["empresas_com_sucesso"]

        self.assertEqual(
            [item["nome"] for item in sucessos],
            ["Empresa 1", "Empresa 3"],
        )

    def test_extrai_cnpj_do_nome_da_empresa_do_drive(self):
        empresas_drive = [{
            "cnpj": "",
            "nome": "12.345.678/0001-90 - Empresa Exemplo",
        }]

        sucessos = _consolidar_categorias({
            "empresas_com_sucesso": empresas_drive,
        })["empresas_com_sucesso"]

        self.assertEqual(len(sucessos), 1)
        self.assertEqual(sucessos[0]["cnpj"], "12345678000190")
        self.assertEqual(sucessos[0]["nome"], "Empresa Exemplo")

    def test_compara_automacao_e_drive_para_preencher_cnpj_e_nome(self):
        empresas_drive = [{
            "cnpj": "",
            "nome": "12.345.678/0001-90 - Empresa Exemplo",
        }]
        sucessos_explicitos = [{
            "cnpj": "12345678000190",
            "nome": "Empresa Exemplo",
        }]

        sucessos = _consolidar_categorias({
            "empresas_com_sucesso": [*empresas_drive, *sucessos_explicitos],
        })["empresas_com_sucesso"]

        self.assertEqual(len(sucessos), 1)
        self.assertEqual(sucessos[0]["cnpj"], "12345678000190")
        self.assertEqual(sucessos[0]["nome"], "Empresa Exemplo")

    def test_aceita_dados_da_automacao_com_campo_empresa(self):
        empresas_drive = [{
            "cnpj": "",
            "nome": "2WV CONSTRUCOES E REFORMAS LTDA",
        }]
        sucessos_explicitos = [{
            "empresa": "2WV CONSTRUCOES E REFORMAS LTDA",
            "cnpj": "12345678000190",
        }]

        sucessos = _consolidar_categorias({
            "empresas_com_sucesso": [*empresas_drive, *sucessos_explicitos],
        })["empresas_com_sucesso"]

        self.assertEqual(len(sucessos), 1)
        self.assertEqual(sucessos[0]["nome"], "2WV CONSTRUCOES E REFORMAS LTDA")
        self.assertEqual(sucessos[0]["cnpj"], "12345678000190")

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
        self.assertEqual(resposta.json["resumo"]["total_processado"], 1)
        self.assertEqual(len(resposta.json["empresas_com_falha"]), 0)
        self.assertEqual(len(resposta.json["empresas_com_sucesso"]), 1)

    @patch("src.routes.relatorio.listar_relatorios_json", return_value=[])
    @patch("src.routes.relatorio.conectar_google_drive")
    def test_informa_quando_json_nao_existe(self, conectar, listar):
        resposta = self.cliente.get("/api/relatorios/certificados-vencidos")
        self.assertEqual(resposta.status_code, 404)

    @patch("src.routes.relatorio.ler_relatorio_json")
    @patch("src.routes.relatorio.listar_relatorios_json")
    @patch("src.routes.relatorio.conectar_google_drive")
    def test_ignorada_identificada_substitui_sucesso_anterior_sem_aumentar_total(self, conectar, listar, ler):
        listar.return_value = [
            {"id": "a", "modifiedTime": "2026-08-28T10:00:00Z"},
            {"id": "b", "modifiedTime": "2026-08-28T11:00:00Z"},
        ]
        ignorada = relatorio(executado_em="2026-08-28T11:00:00")
        ignorada["resumo"]["ignorados"] = 10
        ignorada["empresas_ignoradas"] = [empresa(1), empresa(1)]
        ler.side_effect = [relatorio(sucessos=[empresa(1)]), ignorada]
        resposta = self.cliente.get("/api/relatorios/certificados-vencidos")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["resumo"]["total_processado"], 1)
        self.assertEqual(resposta.json["resumo"]["ignorados"], 1)
        self.assertEqual(resposta.json["resumo"]["sucessos"], 0)

    @patch("src.routes.relatorio._carregar_empresas_sem_certificado")
    @patch("src.routes.relatorio.sincronizar_relatorios_drive")
    def test_endpoint_remove_sobreposicao_da_auto_nc_com_sucessos(self, sincronizar, carregar):
        sincronizar.return_value = relatorio(sucessos=[empresa(1), empresa(2)])
        carregar.return_value = [empresa(1)]
        resposta = self.cliente.get("/api/relatorios/certificados-vencidos")
        self.assertEqual(resposta.json["resumo"]["total_processado"], 2)
        self.assertEqual(resposta.json["resumo"]["sucessos"], 1)
        self.assertEqual(resposta.json["resumo"]["sem_certificado"], 1)

    @patch("src.routes.relatorio._carregar_base_empresas_sieg")
    @patch("src.routes.relatorio.ler_relatorio_json")
    @patch("src.routes.relatorio.listar_relatorios_json")
    @patch("src.routes.relatorio.conectar_google_drive")
    def test_endpoint_identifica_relatorio_sem_cnpj_pela_base_sieg(self, conectar, listar, ler, base):
        base.return_value = {"empresas": [{**empresa(1), "ativo_sieg": True},
                                          {**empresa(2), "ativo_sieg": True}]}
        listar.return_value = [{"id": "a", "modifiedTime": "2026-09-08T12:00:00Z"}]
        ler.return_value = relatorio(sucessos=[{"nome": "Empresa 1"}])
        resposta = self.cliente.get("/api/relatorios/certificados-vencidos")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["resumo"]["total_processado"], 2)
        self.assertEqual(resposta.json["resumo"]["sucessos"], 1)
        self.assertEqual(resposta.json["resumo"]["sem_resultado"], 1)
        self.assertEqual(resposta.json["fonte_total"], "sieg_cnpj_ativos")


class ContagemUnicaTestCase(unittest.TestCase):
    def test_total_de_586_empresas_nao_soma_categorias_sobrepostas(self):
        dados = {
            "resumo": {"sucessos": 900, "falhas": 900, "ignorados": 900, "sem_certificado": 900},
            "empresas_com_sucesso": [empresa(n) for n in range(1, 587)],
            "empresas_ignoradas": [empresa(n) for n in range(1, 31)],
            "empresas_com_falha": [empresa(n) for n in range(31, 51)],
            "empresas_sem_certificado": [empresa(n) for n in range(51, 61)],
        }
        resultado = _consolidar_categorias(dados)
        resumo = resultado["resumo"]
        self.assertEqual(resumo["total_processado"], 586)
        self.assertEqual(resumo["sucessos"], 526)
        self.assertEqual(resumo["ignorados"], 30)
        self.assertEqual(resumo["falhas"], 20)
        self.assertEqual(resumo["sem_certificado"], 10)
        documentos = [item["cnpj"] for campo, lista in resultado.items()
                      if campo.startswith("empresas_") for item in lista]
        self.assertEqual(len(documentos), len(set(documentos)))

    def test_empresa_nas_quatro_categorias_aparece_apenas_sem_certificado(self):
        dados = {campo: [empresa(1), empresa(1)] for campo in (
            "empresas_com_sucesso", "empresas_ignoradas",
            "empresas_com_falha", "empresas_sem_certificado",
        )}
        resultado = _consolidar_categorias(dados)
        self.assertEqual(resultado["resumo"]["total_processado"], 1)
        self.assertEqual(resultado["resumo"]["sem_certificado"], 1)
        self.assertEqual(resultado["empresas_com_sucesso"], [])
        self.assertEqual(resultado["empresas_com_falha"], [])
        self.assertEqual(resultado["empresas_ignoradas"], [])

    def test_normaliza_cnpj_e_nome_sem_documento_entre_categorias(self):
        resultado = _consolidar_categorias({
            "empresas_com_sucesso": [{"cnpj": "12.345.678/0001-90", "nome": "12.345.678/0001-90 - Comércio Exemplo LTDA"}],
            "empresas_com_falha": [{"cnpj": "12345678000190", "nome": "Comércio Exemplo Ltda"}],
            "empresas_sem_certificado": [{"nome": "COMERCIO EXEMPLO LTDA"}],
        })
        self.assertEqual(resultado["resumo"]["total_processado"], 1)
        self.assertEqual(resultado["empresas_sem_certificado"][0]["cnpj"], "12345678000190")

    def test_mesmo_nome_com_cnpjs_distintos_preserva_duas_empresas(self):
        resultado = _consolidar_categorias({
            "empresas_com_sucesso": [{"cnpj": "12345678000190", "nome": "Empresa Exemplo"}],
            "empresas_com_falha": [{"cnpj": "12345678000270", "nome": "Empresa Exemplo"}],
        })
        self.assertEqual(resultado["resumo"]["total_processado"], 2)
        self.assertEqual(resultado["resumo"]["sucessos"], 1)
        self.assertEqual(resultado["resumo"]["falhas"], 1)

    def test_contadores_sem_empresas_identificadas_nao_inflam_total(self):
        resultado = _consolidar_categorias({
            "resumo": {"sucessos": 100, "ignorados": 100, "falhas": 100, "sem_certificado": 100},
            "empresas_com_sucesso": [{}, None, {"nome": ""}],
        })
        self.assertEqual(resultado["resumo"]["total_processado"], 0)

    def test_total_da_base_inclui_pendentes_e_exclui_cpf_inativos_e_documento_incompleto(self):
        cpf = {"nome": "Pessoa Fisica", "cnpj": "123.456.789-01", "ativo_sieg": True}
        incompleta = {"nome": "Cadastro incompleto", "cnpj": "12345", "ativo_sieg": True}
        base = {"atualizado_em": "2026-09-08T12:00:00", "empresas": [
            *[{**empresa(n), "ativo_sieg": True} for n in range(1, 6)],
            {**empresa(1), "ativo_sieg": True},
            {**empresa(6), "ativo_sieg": False}, cpf, incompleta,
        ]}
        resultado = _consolidar_categorias({
            "empresas_com_sucesso": [empresa(1), empresa(2), empresa(3), empresa(4), empresa(6), empresa(7), cpf],
            "empresas_ignoradas": [empresa(2), cpf],
            "empresas_com_falha": [empresa(3), cpf, incompleta],
            "empresas_sem_certificado": [empresa(4), cpf],
        }, base)
        self.assertEqual(resultado["resumo"], {"sucessos": 1, "certas": 1, "ignorados": 1,
                                               "falhas": 1, "sem_certificado": 1,
                                               "sem_resultado": 1, "total_processado": 5})
        self.assertEqual(resultado["empresas_sem_resultado"][0]["cnpj"], empresa(5)["cnpj"])
        self.assertEqual(resultado["base_atualizada_em"], base["atualizado_em"])

    def test_sem_base_tambem_exclui_cpf_e_documento_incompleto(self):
        resultado = _consolidar_categorias({"empresas_com_falha": [
            empresa(1), {"nome": "Pessoa", "cnpj": "12345678901"},
            {"nome": "Sem documento"}, {"nome": "Incompleto", "cnpj": "12345"},
        ]})
        self.assertEqual(resultado["resumo"]["total_processado"], 1)
        self.assertEqual(resultado["fonte_total"], "relatorios")

    def test_base_vazia_completa_nao_reutiliza_totais_historicos(self):
        resultado = _consolidar_categorias(relatorio(sucessos=[empresa(1)]), {"empresas": []})
        self.assertEqual(resultado["resumo"]["total_processado"], 0)
        self.assertEqual(resultado["empresas_com_sucesso"], [])
        self.assertEqual(resultado["fonte_total"], "sieg_cnpj_ativos")

    def test_nome_ambiguo_nao_atribui_resultado_a_uma_filial_ao_acaso(self):
        base = {"empresas": [{**empresa(n), "nome": "Matriz e filial", "ativo_sieg": True}
                             for n in (1, 2)]}
        resultado = _consolidar_categorias({
            "empresas_com_sucesso": [{"nome": "Matriz e filial"}],
        }, base)
        self.assertEqual(resultado["resumo"]["total_processado"], 2)
        self.assertEqual(resultado["resumo"]["sucessos"], 0)
        self.assertEqual(resultado["resumo"]["sem_resultado"], 2)

    def test_sem_resultado_exclui_correspondencias_por_nome_e_cnpj_em_todas_categorias(self):
        base = {"empresas": [{**empresa(n), "ativo_sieg": True} for n in range(1, 6)]}
        base["empresas"][0]["nome"] = "Comércio Exemplo Ltda."
        dados = {
            "empresas_com_sucesso": [{"nome": " COMERCIO EXEMPLO LTDA "}],
            "empresas_ignoradas": [{"nome": "EMPRESA-2"}],
            "empresas_com_falha": [{"cnpj": empresa(3)["cnpj"], "nome": "Outro nome cadastrado"}],
            "empresas_sem_certificado": [{"nome": "Empresa 4"}, {"nome": "empresa-4"}],
        }
        resultado = _consolidar_categorias(dados, base)
        self.assertEqual([item["cnpj"] for item in resultado["empresas_sem_resultado"]],
                         [empresa(5)["cnpj"]])
        documentos = [item["cnpj"] for campo in (*dados, "empresas_sem_resultado")
                      for item in resultado[campo]]
        self.assertEqual(len(documentos), len(set(documentos)))
        self.assertEqual(len(documentos), resultado["resumo"]["total_processado"])
        dados["empresas_com_sucesso"].append({"nome": "EMPRESA 5"})
        atualizado = _consolidar_categorias(dados, base)
        self.assertEqual(atualizado["empresas_sem_resultado"], [])
        self.assertEqual(atualizado["resumo"]["total_processado"], 5)


class BaseSiegTestCase(unittest.TestCase):
    @patch("src.routes.relatorio.Path.read_text")
    def test_apenas_inventario_completo_e_utilizado(self, ler):
        for conteudo in ("{}", "[]", "null", "invalido", '{"completo": false, "empresas": []}'):
            with self.subTest(conteudo=conteudo):
                ler.return_value = conteudo
                self.assertIsNone(_carregar_base_empresas_sieg())
        base = {"completo": True, "empresas": []}
        ler.return_value = json.dumps(base)
        self.assertEqual(_carregar_base_empresas_sieg(), base)

    @patch("src.routes.relatorio.Path.read_text", side_effect=FileNotFoundError)
    def test_arquivo_ausente_nao_e_uma_base_vazia(self, ler):
        self.assertIsNone(_carregar_base_empresas_sieg())


if __name__ == "__main__":
    unittest.main()
