from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from operacoes.models import Aplicacao, EventoTitulo, OperacaoCessao, Titulo, TipoAplicacao, TipoEventoTitulo
from usuarios.models import Empresa
from .models import Fundo, InformeMensal, TipoFundo
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


def _criar_operacao_cessao(fundo, numero_contrato, **overrides):
    dados = dict(
        fundo=fundo,
        cedente_cnpj='99999999000100',
        cedente_nome='Cedente Teste',
        numero_contrato=numero_contrato,
        data_contrato=date(2025, 1, 1),
        data_aquisicao=date(2025, 1, 1),
        valor_total_nominal=Decimal('0'),
        valor_total_aquisicao=Decimal('0'),
    )
    dados.update(overrides)
    return OperacaoCessao.objects.create(**dados)


def _criar_titulo(fundo, operacao, numero_titulo, sacado_nome, saldo_devedor, **overrides):
    """Cria um Titulo + seu EventoTitulo(AQUISICAO) inicial -- do jeito que
    processar_cessao faz de verdade (operacoes/services/cessao.py:90-108).
    Sem o evento, _carteira_ativos/_status_enquadramento (que agora
    reconstroem o estado via replay -- ver operacoes/services/
    carteira_historica.py) tratariam o título como se nunca tivesse
    existido em nenhuma data."""
    dados = dict(
        operacao_cessao=operacao,
        fundo=fundo,
        numero_titulo=numero_titulo,
        sacado_nome=sacado_nome,
        sacado_cpf_cnpj='11122233344',
        valor_nominal=saldo_devedor,
        valor_aquisicao=saldo_devedor,
        data_emissao=date(2025, 1, 1),
        data_vencimento=date(2025, 6, 1),
        saldo_devedor=saldo_devedor,
        ativo=True,
    )
    dados.update(overrides)
    titulo = Titulo.objects.create(**dados)
    EventoTitulo.objects.create(
        titulo=titulo,
        tipo_evento=TipoEventoTitulo.AQUISICAO,
        data_evento=dados['data_emissao'],
        valor_evento=titulo.valor_aquisicao,
    )
    return titulo


def _criar_aplicacao(fundo, tipo_aplicacao, valor, **overrides):
    dados = dict(
        fundo=fundo,
        tipo_aplicacao=tipo_aplicacao,
        descricao='Aplicação teste',
        valor=valor,
        data_aplicacao=date(2025, 1, 1),
    )
    dados.update(overrides)
    return Aplicacao.objects.create(**dados)


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
    """
    Testes de _carteira_ativos e _status_enquadramento (3º estado 'Não
    avaliado', A5.1).

    _carteira_ativos passou a ler operacoes.Titulo/Aplicacao (a carteira
    administrada na plataforma) em vez de InformeMensalCarteira (segmentos
    do informe CVM) -- decisão revisada pelo cliente depois de ver a lâmina
    real, ver plano "AJUSTE — Fonte da Carteira de Ativos".
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(nome='Empresa Teste', cnpj='00000000000100')

    def test_carteira_agrupa_a_partir_do_9o_ativo(self):
        fundo = _criar_fundo(self.empresa)
        operacao = _criar_operacao_cessao(fundo, 'CONTRATO-1')
        # 9 sacados distintos com valores decrescentes -- os 8 primeiros
        # aparecem individualmente, o 9º (menor) vira "Outros ativos".
        for i in range(9):
            _criar_titulo(
                fundo, operacao, numero_titulo=f'TIT-{i}', sacado_nome=f'Sacado {i}',
                saldo_devedor=Decimal('1000.00') - Decimal(i) * 10,
            )
        ativos = _carteira_ativos(fundo, date(2025, 12, 31))

        self.assertEqual(len(ativos), 9)  # 8 individuais + 1 "Outros ativos"
        self.assertEqual(ativos[0]['valor'], Decimal('1000.00'))  # maior primeiro
        self.assertEqual(ativos[-1]['descricao'], 'Outros ativos')
        self.assertEqual(ativos[-1]['valor'], Decimal('920.00'))  # só o 9º sobra pro "Outros"

    def test_carteira_combina_direito_creditorio_e_liquidez(self):
        fundo = _criar_fundo(self.empresa, cnpj='22222222000188')
        operacao = _criar_operacao_cessao(fundo, 'CONTRATO-2')
        _criar_titulo(fundo, operacao, 'TIT-A', 'Sacado A', Decimal('600.00'))
        _criar_titulo(fundo, operacao, 'TIT-B', 'Sacado B', Decimal('300.00'))
        _criar_aplicacao(fundo, TipoAplicacao.TESOURO, Decimal('100.00'))

        ativos = _carteira_ativos(fundo, date(2025, 12, 31))

        self.assertEqual(len(ativos), 3)  # poucos itens, sem "Outros ativos"
        self.assertEqual(
            [a['descricao'] for a in ativos],
            ['Direito Creditório — Sacado A', 'Direito Creditório — Sacado B', 'Liquidez — Tesouro Direto'],
        )
        self.assertEqual([a['percentual'] for a in ativos], [Decimal('60'), Decimal('30'), Decimal('10')])

    def test_status_nao_avaliado_quando_fundo_sem_limites(self):
        fundo = _criar_fundo(self.empresa, cnpj='33333333000177')  # limites ficam None (default)
        _, status = _status_enquadramento(fundo, date(2025, 12, 31))
        self.assertEqual(status, 'Não avaliado')

    def test_titulo_liquidado_apos_a_competencia_ainda_aparece_nela(self):
        # Espelha o caso real encontrado no Canoa FIDC: título adquirido em
        # jan/2026, liquidado em 30/03/2026. A lâmina de fevereiro (gerada
        # HOJE, muito depois da liquidação) tem que continuar mostrando o
        # título -- é exatamente o cenário que motivou a reconstrução
        # histórica (ver plano "AJUSTE 2").
        fundo = _criar_fundo(self.empresa, cnpj='55555555000144')
        operacao = _criar_operacao_cessao(fundo, 'CONTRATO-3', data_aquisicao=date(2026, 1, 1))
        titulo = _criar_titulo(
            fundo, operacao, 'TIT-LIQ', 'Sacado Liquidado', Decimal('1000.00'),
            data_emissao=date(2026, 1, 1),
        )
        EventoTitulo.objects.create(
            titulo=titulo, tipo_evento=TipoEventoTitulo.LIQUIDACAO_TOTAL,
            data_evento=date(2026, 3, 30), valor_evento=Decimal('1000.00'),
        )

        self.assertEqual(len(_carteira_ativos(fundo, date(2026, 2, 28))), 1)  # ainda ativo em fev
        self.assertEqual(_carteira_ativos(fundo, date(2026, 3, 31)), [])  # liquidado até o corte de março


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
