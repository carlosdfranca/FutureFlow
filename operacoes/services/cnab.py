"""
Service layer for montagem do registro de detalhe do CNAB.

Extraído de `views.py` (download_cnab_cessao) para ser reusado pela remessa
de baixa (`operacoes/services/cnab_baixa.py`) sem duplicar o dicionário de
18 chaves — que é verificado byte a byte por
`operacoes/tests.py::CnabGoldenAtrivionTest`.
"""
from decimal import Decimal

from ..utils.cnab_utils import rp, remover_pontos, remover_caracteres_especiais


def montar_registro_base(titulo, operacao, *, valor_pago: Decimal, ocorrencia: str = None) -> dict:
    """
    Monta as 18 chaves de um registro de detalhe do CNAB para um título.

    Única fonte de verdade para esse dicionário — usada tanto pela remessa de
    aquisição (`views.download_cnab_cessao`) quanto pela remessa de baixa
    (`operacoes/services/cnab_baixa.py`). Extração literal do que estava
    inline em `views.py`, sem alterar nenhum valor.

    Args:
        titulo: instância de Titulo
        operacao: OperacaoCessao do título (fornecida explicitamente, e não
            lida de `titulo.operacao_cessao`, para permitir prefetch/select
            eficiente quando o chamador itera muitos títulos)
        valor_pago: soma dos eventos de liquidação do título (Decimal),
            vira VALOR_PAGO_TITULO (pos. 83-92). Zero para título ainda não
            liquidado.
        ocorrencia: código de movimento (pos. 109-110) quando difere do
            padrão do fundo/menu_data — hoje só a remessa de baixa passa
            isso, um valor por título (`02` baixa/liquidação total, `14`
            liquidação parcial). `None` (padrão) deixa a chave OCORRENCIA de
            fora do dict, e `gerar_linha_detalhe` cai no valor do
            `menu_data`, igual ao comportamento antes desta função existir.

    Returns:
        dict com as 18 chaves esperadas por `cnab_generator.gerar_linha_detalhe`
    """
    cpf_cnpj_limpo = rp(titulo.sacado_cpf_cnpj)
    identificacao_sacado = "1" if len(cpf_cnpj_limpo) <= 11 else "2"

    # Coobrigação (pos. 21-22): resolvida aqui, e não no gerador, porque
    # `gerar_linha_detalhe` faz `base_record["COOBRIGACAO"][-2:]` e uma
    # string vazia sairia como '00' — um valor inválido, silenciosamente.
    coobrigacao = (
        titulo.coobrigacao or operacao.fundo.coobrigacao_cnab_padrao or '02'
    )

    registro = {
        "CNPJ_CEDENTE": operacao.cedente_cnpj,
        "NOME_CEDENTE": remover_pontos(operacao.cedente_nome),
        "SEU_NUMERO": titulo.numero_titulo,
        "NU_DOCUMENTO": titulo.numero_titulo,
        "DT_VENCIMENTO": titulo.data_vencimento.strftime('%d/%m/%Y'),
        # BASE col 6 / CNAB pos. 127-139: valor da duplicata líquido de IOF —
        # o primeiro passo da cascata, não o valor bruto do vDup.
        "VL_NOMINAL": str(titulo.valor_nominal).replace('.', ','),
        "NU_CPF_CNPJ_SACADO": titulo.sacado_cpf_cnpj,
        "NM_SACADO": remover_caracteres_especiais(titulo.sacado_nome),
        # BASE col 9 / CNAB pos. 193-205: valor presente (nominal descontado
        # pela taxa_desconto da operação). NÃO é valor pago/liquidado.
        "VL_PRESENTE": str(titulo.valor_aquisicao).replace('.', ','),
        "IDENTIFICACAO_CPF_CNPJ_SACADO": identificacao_sacado,
        "ENDERECO": titulo.sacado_endereco,
        "CEP": titulo.sacado_cep,
        "TP_TITULO": titulo.tipo_titulo,
        "DT_EMISSAO_TITULO": titulo.data_emissao.strftime('%d/%m/%Y'),
        "COOBRIGACAO": coobrigacao,
        "IDENTIFICACAO_CPF_CNPJ_CEDENTE": "02",
        "NFE": titulo.chave_nfe,
        "VALOR_PAGO_TITULO": str(valor_pago).replace('.', ','),
    }
    if ocorrencia is not None:
        registro["OCORRENCIA"] = ocorrencia
    return registro
