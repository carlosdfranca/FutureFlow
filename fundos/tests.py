from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from usuarios.models import Empresa
from .models import Fundo, InformeMensal, InformeMensalCarteira, SegmentoCarteira, TipoFundo
from .services.lamina import (
    _carteira_ativos,
    _classe_rentabilidade,
    _estatisticas,
    _grade_rentabilidade,
    _status_enquadramento,
    montar_dados_lamina,
)


def _criar_fundo(empresa, **overrides):
    dados = dict(
        empresa=empresa,
        cnpj='11111111000199',
        razao_social='Fundo Teste FIDC',
        tipo_fundo=TipoFundo.FIDC,
        data_constituicao=date(2025, 1, 15),
    )
    dados.update(overrides)
    return Fundo.objects.create(**dados)


def _criar_informe(fundo, competencia, **overrides):
    dados = dict(fundo=fundo, competencia=competencia)
    dados.update(overrides)
    return InformeMensal.objects.create(**dados)


class LaminaSerieEstatisticasTest(TestCase):
    """
    Testes unitários das funções puras de fundos/services/lamina.py que
    montam a tabela de rentabilidade (2 anos) e as 6 estatísticas do fundo
    (A2 + A3 do levantamento). Série pequena, com valores redondos, para
    poder conferir a matemática à mão (produto composto, meses positivos/
    negativos, cobertura).
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(nome='Empresa Teste', cnpj='00000000000100')
        # Fundo classe única (sem cotas sênior) -- igual ao caso real do
        # Canoa FIDC: rentabilidade_senior fica sempre 0, o dado de verdade
        # está em rentabilidade_subord.
        self.fundo = _criar_fundo(self.empresa, data_constituicao=date(2025, 1, 15))
        _criar_informe(self.fundo, date(2025, 1, 1), rentabilidade_subord=Decimal('1.00'), qt_cotas_senior=Decimal('0'))
        _criar_informe(self.fundo, date(2025, 2, 1), rentabilidade_subord=Decimal('-2.00'), qt_cotas_senior=Decimal('0'))
        self.informe_mar = _criar_informe(
            self.fundo, date(2025, 3, 1), rentabilidade_subord=Decimal('3.00'), qt_cotas_senior=Decimal('0')
        )

    def test_classe_escolhe_subordinada_quando_sem_cotas_senior(self):
        campo, rotulo = _classe_rentabilidade(self.informe_mar)
        self.assertEqual(campo, 'rentabilidade_subord')
        self.assertEqual(rotulo, 'Cota Única')

    def test_classe_escolhe_senior_quando_fundo_tem_cotas_senior(self):
        informe_senior = _criar_informe(
            self.fundo, date(2025, 4, 1),
            rentabilidade_senior=Decimal('0.50'), qt_cotas_senior=Decimal('1000'),
        )
        campo, rotulo = _classe_rentabilidade(informe_senior)
        self.assertEqual(campo, 'rentabilidade_senior')
        self.assertEqual(rotulo, 'Cota Sênior')

    def test_grade_pivota_por_mes_sem_preencher_com_zero(self):
        serie = InformeMensal.objects.filter(fundo=self.fundo).order_by('competencia')
        grade_ant, grade_atual = _grade_rentabilidade(serie, 'rentabilidade_subord', 2024, 2025)

        self.assertEqual(grade_ant, [None] * 12)  # nenhum informe em 2024
        self.assertEqual(grade_atual[0], Decimal('1.00'))   # Jan
        self.assertEqual(grade_atual[1], Decimal('-2.00'))  # Fev
        self.assertEqual(grade_atual[2], Decimal('3.00'))   # Mar
        self.assertIsNone(grade_atual[3])  # Abr — sem informe, não é 0

    def test_estatisticas_batem_com_calculo_manual(self):
        serie = list(InformeMensal.objects.filter(fundo=self.fundo).order_by('competencia'))
        stats = _estatisticas(serie, 'rentabilidade_subord', self.fundo, date(2025, 3, 1))

        self.assertEqual(stats.meses_pos, 2)  # Jan (+1), Mar (+3)
        self.assertEqual(stats.meses_neg, 1)  # Fev (-2)
        self.assertEqual(stats.maior_ret, Decimal('3.00'))
        self.assertEqual(stats.menor_ret, Decimal('-2.00'))
        # Produto composto (1.01 * 0.98 * 1.03 - 1) * 100 = 1.9494
        self.assertEqual(stats.ret_ini, Decimal('1.9494'))
        self.assertEqual(stats.ret_12m, Decimal('1.9494'))  # só há 3 meses, < 12
        self.assertEqual(stats.meses_disponiveis, 3)
        self.assertEqual(stats.meses_esperados, 3)  # jan/fev/mar 2025, fundo constituído em jan/2025
        self.assertTrue(stats.cobertura_completa)

    def test_cobertura_incompleta_quando_falta_informe(self):
        # Fundo constituído em nov/2024 mas só existem informes de 2025 ->
        # faltam nov e dez/2024 na série.
        fundo_com_buraco = _criar_fundo(
            self.empresa, cnpj='22222222000188', data_constituicao=date(2024, 11, 1),
        )
        informe = _criar_informe(fundo_com_buraco, date(2025, 1, 1), rentabilidade_subord=Decimal('1.00'))
        serie = [informe]
        stats = _estatisticas(serie, 'rentabilidade_subord', fundo_com_buraco, date(2025, 1, 1))

        self.assertEqual(stats.meses_disponiveis, 1)
        self.assertEqual(stats.meses_esperados, 3)  # nov/dez 2024 + jan 2025
        self.assertFalse(stats.cobertura_completa)


class LaminaCarteiraEEnquadramentoTest(TestCase):
    """Testes de _carteira_ativos (agrupamento 'Outros ativos') e
    _status_enquadramento (3º estado 'Não avaliado', A5.1)."""

    def setUp(self):
        self.empresa = Empresa.objects.create(nome='Empresa Teste', cnpj='00000000000100')

    def test_carteira_agrupa_a_partir_do_9o_ativo(self):
        fundo = _criar_fundo(self.empresa)
        informe = _criar_informe(fundo, date(2025, 1, 1))
        # 10 segmentos com valores decrescentes -- os 8 primeiros aparecem
        # individualmente, os 2 últimos viram 1 linha "Outros ativos".
        for i in range(10):
            InformeMensalCarteira.objects.create(
                informe=informe,
                segmento=SegmentoCarteira.OUTROS,
                subsegmento=f'SEG_{i}',
                valor=Decimal('1000.00') - i,
                percentual_carteira=Decimal('10.00') - i,
            )
        ativos = _carteira_ativos(informe)

        self.assertEqual(len(ativos), 9)  # 8 individuais + 1 "Outros ativos"
        self.assertEqual(ativos[-1]['descricao'], 'Outros ativos')
        # Os 2 últimos por valor (SEG_8 valor=992, SEG_9 valor=991) somam 1983.00
        self.assertEqual(ativos[-1]['valor'], Decimal('1983.00'))
        self.assertEqual(ativos[-1]['percentual'], Decimal('3.00'))  # (10-8)+(10-9) = 2+1

    def test_status_nao_avaliado_quando_fundo_sem_limites(self):
        fundo = _criar_fundo(self.empresa, cnpj='33333333000177')  # limites ficam None (default)
        _, status = _status_enquadramento(fundo)
        self.assertEqual(status, 'Não avaliado')


class LaminaViewTest(TestCase):
    """
    Teste de ponta a ponta da rota fundos:lamina_informe_pdf: renderiza um
    PDF de verdade (WeasyPrint) a partir de dados reais do banco de teste.

    NOTA: fundos/views.py::_check_pode_ver_informes hoje depende de
    `request.user_role`, que nenhum middleware do projeto seta -- na
    prática, só superusuário passa por essa checagem (bug pré-existente,
    documentado no plano da Fase 1+2, não corrigido aqui). Por isso o
    usuário de teste precisa ser superuser para exercitar a view.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(nome='Empresa Teste', cnpj='00000000000100')
        self.fundo = _criar_fundo(self.empresa)
        self.informe = _criar_informe(
            self.fundo, date(2025, 3, 1),
            rentabilidade_subord=Decimal('1.35'),
            vl_patrimonio_liquido=Decimal('1000000.00'),
            qt_total_cotistas=10,
        )
        User = get_user_model()
        self.user = User.objects.create_superuser(username='admin', password='senha123', email='a@a.com')
        self.client = Client()
        self.client.force_login(self.user)

    def test_gera_pdf_para_informe_valido(self):
        url = reverse('fundos:lamina_informe_pdf', args=[self.fundo.id, self.informe.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_404_para_informe_de_outro_fundo(self):
        outro_fundo = _criar_fundo(self.empresa, cnpj='44444444000166')
        outro_informe = _criar_informe(outro_fundo, date(2025, 3, 1))
        # informe existe, mas não pertence a self.fundo -- mesmo padrão de
        # tenant-safety de detalhe_informe (get_object_or_404(..., fundo=fundo))
        url = reverse('fundos:lamina_informe_pdf', args=[self.fundo.id, outro_informe.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_montar_dados_lamina_nao_quebra_com_fundo_minimo(self):
        # Fundo sem gestor/administrador/politica_investimento/classificacao_investidor
        # preenchidos -- garante que os campos "vazios" degradam graciosamente
        # (A7/A8 parciais) em vez de derrubar a página com erro.
        dados = montar_dados_lamina(self.fundo, self.informe)
        self.assertEqual(dados['publico_alvo'], '—')
        self.assertIsNone(dados['tese_investimento'])
