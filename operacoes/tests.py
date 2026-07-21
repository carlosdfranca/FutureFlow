import re
from datetime import date
from pathlib import Path

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from fundos.models import Fundo, TipoFundo
from usuarios.models import Empresa
from .models import OperacaoCessao, Titulo


XML_PATH = Path(
    r"c:\Users\carlo\OneDrive\Trampo\Projetos\Cinnamon\Future Flow\CNAB\Exemplo Import CNAB.xml"
)


class WorkflowCessaoXmlTest(TestCase):
    """
    Cobertura de regressão para o fluxo de importação de XML + geração de
    CNAB, criada durante a implementação do plano de correção descrito em
    docs/plano_implementacao_cobranca.md. Garante que chave_nfe, endereço,
    CEP e data de emissão do sacado sobrevivem do parse até a persistência
    e chegam corretamente ao arquivo CNAB gerado.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Teste", cnpj="00000000000100")
        self.fundo = Fundo.objects.create(
            empresa=self.empresa,
            cnpj="11111111000199",
            razao_social="Fundo Teste FIDC",
            tipo_fundo=TipoFundo.FIDC,
            data_constituicao=date(2020, 1, 1),
        )
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="senha123")
        self.client = Client()
        self.client.force_login(self.user)

    def _parse_xml(self):
        with open(XML_PATH, "rb") as f:
            response = self.client.post(
                reverse("operacoes:workflow_cessao"),
                {"acao": "parse_xml", "xml_file": f},
            )
        self.assertEqual(response.status_code, 200)
        return response

    def test_parse_xml_preenche_campos_ocultos_no_formset(self):
        """O HTML retornado após o parse deve conter os campos ocultos
        (chave_nfe, sacado_endereco, sacado_cep, data_emissao) já
        preenchidos com os dados do XML — regressão para o bug em que
        esses campos eram descartados por não estarem no template."""
        response = self._parse_xml()
        html = response.content.decode("utf-8")

        self.assertIn("35260502455462000129550010001545861100956966", html)  # chave_nfe
        self.assertIn("ROD SANTOS DUMONT", html)  # sacado_endereco
        self.assertIn("13012100", html)  # sacado_cep
        self.assertIn("2026-05-11", html)  # data_emissao (value="YYYY-MM-DD")

    def test_confirmar_persiste_chave_nfe_endereco_cep_e_data_emissao(self):
        self._parse_xml()

        post_data = {
            "acao": "confirmar",
            "fundo": str(self.fundo.pk),
            "numero_contrato": "NF-154586",
            "data_contrato": "2026-07-21",
            "data_aquisicao": "2026-07-21",
            "cedente_cnpj": "02455462000129",
            "cedente_nome": "PROTURBO USINAGEM DE PRECISAO LTDA.",
            "cedente_endereco": "",
            "observacoes": "",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-numero_titulo": "001",
            "form-0-sacado_nome": "VALEO SISTEMAS AUTOMOTIVOS LTDA",
            "form-0-sacado_cpf_cnpj": "57010662001212",
            "form-0-sacado_endereco": "ROD SANTOS DUMONT KM 64",
            "form-0-sacado_cep": "13012100",
            "form-0-valor_nominal": "80911.50",
            "form-0-valor_aquisicao": "80911.50",
            "form-0-data_vencimento": "2026-07-10",
            "form-0-chave_nfe": "35260502455462000129550010001545861100956966",
            "form-0-data_emissao": "2026-05-11",
        }
        response = self.client.post(reverse("operacoes:workflow_cessao"), post_data)

        self.assertEqual(OperacaoCessao.objects.count(), 1, response.content.decode("utf-8")[:2000])
        operacao = OperacaoCessao.objects.get()
        self.assertEqual(response.status_code, 302)

        titulo = operacao.titulos.get()
        self.assertEqual(titulo.chave_nfe, "35260502455462000129550010001545861100956966")
        self.assertEqual(titulo.sacado_endereco, "ROD SANTOS DUMONT KM 64")
        self.assertEqual(titulo.sacado_cep, "13012100")
        self.assertEqual(titulo.data_emissao, date(2026, 5, 11))

        return operacao

    def test_cnab_gerado_com_chave_nfe_e_layout_444(self):
        operacao = self.test_confirmar_persiste_chave_nfe_endereco_cep_e_data_emissao()

        response = self.client.post(
            reverse("operacoes:download_cnab_cessao", args=[operacao.pk]),
            {"dtl": "2026-07-21", "cdo": "15555601", "ocorrencia": "01"},
        )
        self.assertEqual(response.status_code, 200)
        conteudo = response.content.decode("utf-8")
        linhas = conteudo.splitlines()

        self.assertEqual(len(linhas), 3)  # header + 1 detalhe + trailer
        for linha in linhas:
            self.assertEqual(len(linha), 444, msg=f"linha com tamanho errado: {len(linha)}")

        detalhe = linhas[1]
        self.assertIn("35260502455462000129550010001545861100956966", detalhe)  # NFE (não mais zeros)
        self.assertEqual(detalhe[10:20], "0000000000")  # taxa de juros vazia -> zero-fill
        self.assertEqual(linhas[2][-6:], "000003")  # trailer count correto
