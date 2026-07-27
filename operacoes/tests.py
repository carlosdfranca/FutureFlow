from datetime import date
from decimal import Decimal
from pathlib import Path

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from fundos.models import Fundo, TipoFundo
from usuarios.models import Empresa
from .models import OperacaoCessao
from .services.cessao import processar_cessao


XML_PATH = Path(
    r"c:\Users\carlo\OneDrive\Trampo\Projetos\Cinnamon\Future Flow\CNAB\Exemplo Import CNAB.xml"
)

# XML real (nfeProc completo, com protNFe/infProt) fornecido pelo usuário para
# validar o fluxo ponta a ponta. Fica dentro do repo (docs/legado_vba/), então
# funciona em qualquer máquina/CI, ao contrário do XML_PATH acima (OneDrive local).
XML_REAL_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs" / "legado_vba" / "35260602455462000129550010001557711769163725.xml"
)


def _bloco_post_data(idx, numero_contrato, fundo_pk, chave_nfe, data_emissao="2026-05-11"):
    """Monta o dict de POST (prefixado por bloco, como o template gera) para
    confirmar uma operação a partir de um único título."""
    op = f"op{idx}"
    tit = f"tit{idx}"
    return {
        f"{op}-fundo": str(fundo_pk),
        f"{op}-numero_contrato": numero_contrato,
        f"{op}-data_contrato": "2026-07-21",
        f"{op}-data_aquisicao": "2026-07-21",
        f"{op}-cedente_cnpj": "02455462000129",
        f"{op}-cedente_nome": "PROTURBO USINAGEM DE PRECISAO LTDA.",
        f"{op}-cedente_endereco": "",
        f"{op}-observacoes": "",
        f"{tit}-TOTAL_FORMS": "1",
        f"{tit}-INITIAL_FORMS": "1",
        f"{tit}-MIN_NUM_FORMS": "0",
        f"{tit}-MAX_NUM_FORMS": "1000",
        f"{tit}-0-numero_titulo": "001",
        f"{tit}-0-sacado_nome": "VALEO SISTEMAS AUTOMOTIVOS LTDA",
        f"{tit}-0-sacado_cpf_cnpj": "57010662001212",
        f"{tit}-0-sacado_endereco": "ROD SANTOS DUMONT KM 64",
        f"{tit}-0-sacado_cep": "13012100",
        f"{tit}-0-valor_nominal": "80911.50",
        f"{tit}-0-valor_aquisicao": "80911.50",
        f"{tit}-0-data_vencimento": "2026-07-10",
        f"{tit}-0-chave_nfe": chave_nfe,
        f"{tit}-0-data_emissao": data_emissao,
    }


class WorkflowCessaoXmlTest(TestCase):
    """
    Cobertura de regressão para o fluxo de importação de XML + geração de
    CNAB, criada durante a implementação do plano de correção descrito em
    docs/plano_implementacao_cobranca.md. Garante que chave_nfe, endereço,
    CEP e data de emissão do sacado sobrevivem do parse até a persistência
    e chegam corretamente ao arquivo CNAB gerado, e que o import em lote
    (múltiplos XML) gera uma OperacaoCessao por NF-e, sem agrupar.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Teste", cnpj="00000000000100")
        self.fundo = Fundo.objects.create(
            empresa=self.empresa,
            cnpj="11111111000199",
            razao_social="Fundo Teste FIDC",
            tipo_fundo=TipoFundo.FIDC,
            data_constituicao=date(2020, 1, 1),
            codigo_originador_cnab="15555601",
            ocorrencia_cnab_padrao="01",
        )
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="senha123")
        self.client = Client()
        self.client.force_login(self.user)

    def _parse_xml(self, n_arquivos=1, xml_path=None):
        from contextlib import ExitStack
        xml_path = xml_path or XML_PATH
        with ExitStack() as stack:
            arquivos = [stack.enter_context(open(xml_path, "rb")) for _ in range(n_arquivos)]
            response = self.client.post(
                reverse("operacoes:workflow_cessao"),
                {"acao": "parse_xml", "xml_file": arquivos},
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
        self.assertIn('name="op0-fundo"', html)  # prefixo do bloco único

    def test_botao_importar_xml_tem_formnovalidate(self):
        """O botão 'Importar XML' precisa de formnovalidate: como Etapa 1/2/3
        vivem no mesmo <form>, sem isso o navegador bloqueia o import exigindo
        os campos (obrigatórios) da Etapa 2/3, que essa ação nem usa."""
        response = self.client.get(reverse("operacoes:workflow_cessao"))
        html = response.content.decode("utf-8")
        self.assertIn('value="parse_xml" formnovalidate', html)

    def test_parse_xml_preserva_fundo_e_datas_ja_escolhidos(self):
        """Se o usuário já tinha escolhido um Fundo (e datas) na Etapa 2 antes
        de importar um XML, esses valores não podem ser descartados — fundo
        nunca vem do XML, então perdê-lo obriga reescolher toda vez."""
        with open(XML_PATH, "rb") as f:
            response = self.client.post(
                reverse("operacoes:workflow_cessao"),
                {
                    "acao": "parse_xml",
                    "xml_file": f,
                    "op0-fundo": str(self.fundo.pk),
                    "op0-data_contrato": "2026-01-15",
                    "op0-data_aquisicao": "2026-01-16",
                },
            )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        self.assertIn(f'value="{self.fundo.pk}" selected', html)
        self.assertIn('value="2026-01-15"', html)  # data_contrato preservada
        self.assertIn('value="2026-01-16"', html)  # data_aquisicao preservada

    def test_confirmar_persiste_chave_nfe_endereco_cep_e_data_emissao(self):
        self._parse_xml()

        post_data = {"acao": "confirmar", "total_blocos": "1"}
        post_data.update(_bloco_post_data(
            0, "NF-154586", self.fundo.pk,
            "35260502455462000129550010001545861100956966",
        ))
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
            {"dtl": "2026-07-21"},
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

    def test_cnab_bloqueado_se_fundo_sem_cdo(self):
        """Sem CDO cadastrado no fundo, a geração deve ser bloqueada com uma
        mensagem de erro em vez de gerar um CNAB com CDO vazio."""
        self.fundo.codigo_originador_cnab = ""
        self.fundo.save()
        operacao = self.test_confirmar_persiste_chave_nfe_endereco_cep_e_data_emissao()

        response = self.client.post(
            reverse("operacoes:download_cnab_cessao", args=[operacao.pk]),
            {"dtl": "2026-07-21"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Content-Type", "").split(";")[0], "text/html")
        self.assertNotIn("Content-Disposition", response)

    def test_confirmar_avisa_mas_nao_bloqueia_nfe_duplicada(self):
        """Reimportar uma chave_nfe já usada em outra operação deve gerar
        um aviso, mas não deve impedir a criação da nova operação."""
        chave_repetida = "35260502455462000129550010001545861100956966"
        processar_cessao(
            fundo=self.fundo,
            cedente_dados={"cnpj": "02455462000129", "nome": "OUTRO CEDENTE"},
            titulos_dados=[{
                "numero_titulo": "999",
                "sacado_nome": "OUTRO SACADO",
                "sacado_cpf_cnpj": "57010662001212",
                "valor_nominal": Decimal("100.00"),
                "valor_aquisicao": Decimal("100.00"),
                "data_vencimento": date(2026, 1, 1),
                "chave_nfe": chave_repetida,
            }],
            operacao_dados={
                "numero_contrato": "NF-JA-EXISTENTE",
                "data_contrato": date(2026, 1, 1),
                "data_aquisicao": date(2026, 1, 1),
            },
            usuario=self.user,
        )

        self._parse_xml()
        post_data = {"acao": "confirmar", "total_blocos": "1"}
        post_data.update(_bloco_post_data(0, "NF-154586", self.fundo.pk, chave_repetida))
        response = self.client.post(reverse("operacoes:workflow_cessao"), post_data, follow=True)

        # Não bloqueou: a nova operação foi criada normalmente.
        self.assertTrue(OperacaoCessao.objects.filter(numero_contrato="NF-154586").exists())

        mensagens = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("já haviam sido importadas" in m for m in mensagens),
            msg=f"Esperava aviso de duplicidade, mensagens recebidas: {mensagens}",
        )

    def test_confirmar_cadastro_manual_sem_xml(self):
        """Fluxo original (sem nunca chamar parse_xml): a tela inicial (GET)
        já tem 1 bloco padrão (op0/tit0) pronto para preenchimento manual."""
        get_response = self.client.get(reverse("operacoes:workflow_cessao"))
        self.assertEqual(get_response.status_code, 200)
        self.assertIn('name="op0-fundo"', get_response.content.decode("utf-8"))

        post_data = {"acao": "confirmar", "total_blocos": "1"}
        post_data.update(_bloco_post_data(0, "NF-MANUAL-1", self.fundo.pk, ""))
        response = self.client.post(reverse("operacoes:workflow_cessao"), post_data)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(OperacaoCessao.objects.filter(numero_contrato="NF-MANUAL-1").exists())

    def test_parse_xml_em_lote_gera_um_bloco_por_arquivo(self):
        """Upload de 2 XMLs no mesmo envio deve gerar 2 blocos de revisão
        independentes (op0/tit0 e op1/tit1), sem agrupar títulos."""
        response = self._parse_xml(n_arquivos=2)
        html = response.content.decode("utf-8")

        self.assertIn('name="op0-fundo"', html)
        self.assertIn('name="op1-fundo"', html)
        self.assertIn('name="tit0-0-numero_titulo"', html)
        self.assertIn('name="tit1-0-numero_titulo"', html)

    def test_confirmar_lote_cria_uma_operacao_por_bloco(self):
        """Confirmar um lote com 2 blocos deve criar 2 OperacaoCessao
        distintas, cada uma com seu próprio título — sem agrupar."""
        self._parse_xml(n_arquivos=2)

        post_data = {"acao": "confirmar", "total_blocos": "2"}
        post_data.update(_bloco_post_data(
            0, "NF-LOTE-1", self.fundo.pk,
            "35260502455462000129550010001545861100956966",
        ))
        post_data.update(_bloco_post_data(
            1, "NF-LOTE-2", self.fundo.pk,
            "35260502455462000129550010009999991100956966",
        ))
        response = self.client.post(reverse("operacoes:workflow_cessao"), post_data)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(OperacaoCessao.objects.filter(numero_contrato="NF-LOTE-1").exists())
        self.assertTrue(OperacaoCessao.objects.filter(numero_contrato="NF-LOTE-2").exists())
        self.assertEqual(OperacaoCessao.objects.count(), 2)
        # Cada operação com exatamente 1 título — nada foi agrupado.
        for numero in ("NF-LOTE-1", "NF-LOTE-2"):
            op = OperacaoCessao.objects.get(numero_contrato=numero)
            self.assertEqual(op.titulos.count(), 1)

    def test_fluxo_completo_com_xml_real_fornecido_pelo_usuario(self):
        """Ponta a ponta com o XML real (nfeProc + protNFe) que o usuário
        trouxe: parse -> confirmar -> gerar CNAB, sem editar nada na tela
        (fluxo padrão de quem só clica 'Importar' e depois 'Confirmar')."""
        response = self._parse_xml(xml_path=XML_REAL_PATH)
        html = response.content.decode("utf-8")

        # Dados que a tela deve mostrar pré-preenchidos, vindos direto do XML.
        self.assertIn("02455462000129", html)  # CNPJ cedente
        self.assertIn("value=\"NF-155771\"", html)  # numero_contrato sugerido (NF-{nNF})
        self.assertIn("35260602455462000129550010001557711769163725", html)  # chave_nfe
        self.assertIn("07180900", html)  # CEP do sacado
        self.assertIn("2026-06-15", html)  # data_emissao
        self.assertIn('value="155771"', html)  # numero_titulo vem de nFat, não de nDup ("001")

        post_data = {"acao": "confirmar", "total_blocos": "1"}
        post_data.update({
            "op0-fundo": str(self.fundo.pk),
            "op0-numero_contrato": "NF-155771",
            "op0-data_contrato": "2026-07-21",
            "op0-data_aquisicao": "2026-07-21",
            "op0-cedente_cnpj": "02455462000129",
            "op0-cedente_nome": "PROTURBO USINAGEM DE PRECISAO LTDA.",
            "op0-cedente_endereco": "",
            "op0-observacoes": "",
            "tit0-TOTAL_FORMS": "1",
            "tit0-INITIAL_FORMS": "1",
            "tit0-MIN_NUM_FORMS": "0",
            "tit0-MAX_NUM_FORMS": "1000",
            "tit0-0-numero_titulo": "155771",  # nFat (fatura), como a macro
            "tit0-0-sacado_nome": "CUMMINS BRASIL LTDA",
            "tit0-0-sacado_cpf_cnpj": "43201151000110",
            "tit0-0-sacado_endereco": "R JATI 310",
            "tit0-0-sacado_cep": "07180900",
            "tit0-0-valor_nominal": "21448.80",
            "tit0-0-valor_aquisicao": "21448.80",
            "tit0-0-data_vencimento": "2026-08-14",
            "tit0-0-chave_nfe": "35260602455462000129550010001557711769163725",
            "tit0-0-data_emissao": "2026-06-15",
        })
        response = self.client.post(reverse("operacoes:workflow_cessao"), post_data)
        self.assertEqual(response.status_code, 302, response.content.decode("utf-8")[:2000])

        operacao = OperacaoCessao.objects.get(numero_contrato="NF-155771")
        titulo = operacao.titulos.get()
        self.assertEqual(titulo.numero_titulo, "155771")
        self.assertEqual(titulo.chave_nfe, "35260602455462000129550010001557711769163725")
        self.assertEqual(titulo.sacado_endereco, "R JATI 310")
        self.assertEqual(titulo.sacado_cep, "07180900")
        self.assertEqual(titulo.data_emissao, date(2026, 6, 15))
        self.assertEqual(titulo.valor_nominal, Decimal("21448.80"))

        cnab_response = self.client.post(
            reverse("operacoes:download_cnab_cessao", args=[operacao.pk]),
            {"dtl": "2026-07-21"},
        )
        self.assertEqual(cnab_response.status_code, 200)
        linhas = cnab_response.content.decode("utf-8").splitlines()
        self.assertEqual(len(linhas), 3)
        for linha in linhas:
            self.assertEqual(len(linha), 444)
        detalhe = linhas[1]
        self.assertIn("35260602455462000129550010001557711769163725", detalhe)
