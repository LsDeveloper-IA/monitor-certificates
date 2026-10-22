import io
import os
import unittest
from datetime import date, datetime
from unittest.mock import patch

from flask import Flask
from PIL import Image
from src.models.certificado import Certificado, db
from src.routes.historico import historico_bp, RegistroCertificado
from src.routes.certificado import certificado_bp


class HistoricoTestCase(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, AUTOMACAO_EXECUTION_KEY='teste-historico', INTEGRACAO_API_KEY='teste-sync')
        self.env.start()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(self.app)
        self.app.register_blueprint(historico_bp, url_prefix='/api')
        self.app.register_blueprint(certificado_bp, url_prefix='/api')
        with self.app.app_context():
            db.create_all()
            db.session.add(Certificado(nome_empresa='Empresa teste', cpf_cnpj='12345678000190', tipo='PJ', data_vencimento=date(2027, 1, 1), arquivo_drive_id='teste.pfx'))
            db.session.commit()
        self.client = self.app.test_client()
        self.headers = {'X-Automation-Key': 'teste-historico'}
        self.url = '/api/historico/certificados/1'

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.env.stop()

    def salvar(self, **dados):
        return self.client.post(self.url, headers=self.headers, data={'autor': 'Gabriel', 'texto': 'Contato sem retorno.\nTentar amanhã.', **dados})

    def listar(self, pagina=1):
        return self.client.get(self.url + f'?pagina={pagina}', headers=self.headers)

    def test_autenticacao_e_restricao_loopback(self):
        for caminho in [self.url, '/api/historico/imagens/1']:
            self.assertEqual(self.client.get(caminho).status_code, 401)
            self.assertEqual(self.client.get(caminho, headers={'X-Automation-Key': 'errada'}).status_code, 401)
            self.assertEqual(self.client.get(caminho, headers=self.headers, environ_overrides={'REMOTE_ADDR': '192.168.1.10'}).status_code, 401)
        self.assertEqual(self.client.post(self.url, data={'texto': 'X'}).status_code, 401)

    def test_salva_e_lista_com_data_e_autor(self):
        self.assertEqual(self.salvar().status_code, 201)
        r = self.listar().json
        self.assertEqual(len(r['registros']), 1)
        item = r['registros'][0]
        self.assertEqual(item['autor'], 'Gabriel')
        self.assertIn('\n', item['texto'])
        self.assertIsNotNone(datetime.fromisoformat(item['criado_em']).tzinfo)
        self.assertEqual(item['imagens'], [])
        self.assertFalse(r['tem_mais'])

    def test_texto_e_autor_obrigatorios_e_limitados(self):
        for dados in [{'texto': ' '}, {'autor': ' '}, {'texto': 'x' * 5001}, {'autor': 'x' * 101}]:
            self.assertEqual(self.salvar(**dados).status_code, 400)
        self.assertEqual(self.listar().json['registros'], [])

    def test_editar_preserva_autor_data_e_valida_texto(self):
        self.salvar()
        antes = self.listar().json['registros'][0]
        url = f"/api/historico/registros/{antes['id']}"
        self.assertEqual(self.client.put(url, headers=self.headers, json={'texto': ' '}).status_code, 400)
        self.assertEqual(self.client.put(url, json={'texto': 'X'}).status_code, 401)
        self.assertEqual(self.client.put(url, headers=self.headers, json={'texto': 'Consegui contato.'}).status_code, 200)
        depois = self.listar().json['registros'][0]
        self.assertEqual(depois['texto'], 'Consegui contato.')
        self.assertEqual(depois['criado_em'], antes['criado_em'])
        self.assertEqual(depois['autor'], antes['autor'])
        self.assertIsNotNone(depois['editado_em'])

    def test_excluir_remove_registro_e_anexos(self):
        arquivo = io.BytesIO()
        Image.new('RGB', (10, 10)).save(arquivo, format='PNG')
        arquivo.seek(0)
        self.salvar(imagens=(arquivo, 'teste.png'))
        antes = self.listar().json['registros'][0]
        url = f"/api/historico/registros/{antes['id']}"
        self.client.put(url, headers=self.headers, json={'texto': 'Editado'})
        self.assertEqual(self.client.delete(url).status_code, 401)
        self.assertEqual(self.client.delete(url, headers=self.headers).status_code, 200)
        self.assertEqual(self.listar().json['registros'], [])
        self.assertEqual(self.client.get(f"/api/historico/imagens/{antes['imagens'][0]}", headers=self.headers).status_code, 404)
        self.assertEqual(self.client.delete(url, headers=self.headers).status_code, 404)

    def test_certificado_inexistente(self):
        self.assertEqual(self.client.get('/api/historico/certificados/999', headers=self.headers).status_code, 404)

    def test_imagem_sanitizada_e_protegida(self):
        arquivo = io.BytesIO()
        Image.new('RGB', (10, 10), 'red').save(arquivo, format='PNG')
        arquivo.seek(0)
        self.assertEqual(self.salvar(imagens=(arquivo, 'foto.png')).status_code, 201)
        imagem_id = self.listar().json['registros'][0]['imagens'][0]
        caminho = f'/api/historico/imagens/{imagem_id}'
        self.assertEqual(self.client.get(caminho).status_code, 401)
        r = self.client.get(caminho, headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'image/jpeg')
        self.assertEqual(r.headers['Cache-Control'], 'private, no-store')
        self.assertEqual(Image.open(io.BytesIO(r.data)).format, 'JPEG')

    def test_rejeita_arquivo_falso_sem_salvar_registro(self):
        self.assertEqual(self.salvar(imagens=(io.BytesIO(b'nao e imagem'), 'foto.png')).status_code, 400)
        self.assertEqual(self.listar().json['registros'], [])

    def test_limite_quantidade_e_tamanho(self):
        self.assertEqual(self.salvar(imagens=[(io.BytesIO(b'x'), f'{n}.png') for n in range(4)]).status_code, 400)
        self.assertEqual(self.salvar(imagens=(io.BytesIO(b'x' * (5 * 1024 * 1024 + 1)), 'grande.png')).status_code, 400)

    def test_paginacao_e_isolamento_por_certificado(self):
        with self.app.app_context():
            db.session.add_all([RegistroCertificado(certificado_id=1, autor='Teste', texto=str(i)) for i in range(21)])
            db.session.add(Certificado(nome_empresa='Outra', cpf_cnpj='22345678000190', tipo='PJ', data_vencimento=date(2027, 1, 1)))
            db.session.commit()
        primeiro = self.listar().json
        self.assertEqual(len(primeiro['registros']), 20)
        self.assertEqual(primeiro['registros'][0]['texto'], '20')
        self.assertTrue(primeiro['tem_mais'])
        self.assertEqual(len(self.listar(2).json['registros']), 1)
        self.assertEqual(self.client.get('/api/historico/certificados/2', headers=self.headers).json['registros'], [])

    def test_sincronizacao_nao_apaga_historico(self):
        self.salvar()
        r = self.client.post('/api/certificados/sincronizar', headers={'X-API-Key': 'teste-sync'}, json={'certificados': [{'empresa': 'Empresa teste', 'cnpj': '12345678000190', 'arquivo': 'teste.pfx', 'vencimento': '2027-01-01', 'observacoes': 'Atualizado pela automacao'}]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(self.listar().json['registros']), 1)


if __name__ == '__main__':
    unittest.main()
