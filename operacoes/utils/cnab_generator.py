"""
Gerador de arquivos CNAB a partir de dados estruturados.
Converte dados de cobrança para o formato CNAB padrão bancário brasileiro.
"""

from .cnab_utils import (
    rep, fd, rp, format_valor, format_date_ddmmyy,
    format_date_ddmmaaaa, pad_left_zeros, pad_right_spaces, pad_left_spaces
)


def gerar_linha_header(menu_data: dict) -> str:
    """
    Gera a linha de cabeçalho (tipo 0) do arquivo CNAB.

    Args:
        menu_data: Dicionário com dados do menu (DTL, CDO, OCORRENCIA)

    Returns:
        String com a linha de cabeçalho formatada (444 caracteres)
    """
    dtl = menu_data["DTL"]
    cdo = menu_data["CDO"]

    linha = (
        "0" +                                                    # Tipo de registro
        "1" +                                                    # Tipo de operação
        "REMESSA" +                                              # Literal REMESSA
        "01" +                                                   # Código de serviço
        "COBRANCA       " +                                      # Literal COBRANCA (15 chars)
        pad_left_zeros(cdo, 20) +                               # Código originador (20 chars)
        rep("W", 30) +                                           # Placeholder (30 chars)
        "001" +                                                  # Código do banco
        rep("B", 15) +                                           # Placeholder (15 chars)
        format_date_ddmmyy(dtl) +                               # Data de liquidação (DDMMYY)
        rep(" ", 8) +                                            # Espaços (8 chars)
        "MX" +                                                   # Identificação
        pad_left_zeros("1", 7) +                                # Número sequencial (7 chars)
        rep(" ", 321) +                                          # Espaços (321 chars)
        "000001"                                                 # Número da linha
    )

    return linha


def gerar_linha_detalhe(base_record: dict, index: int, menu_data: dict) -> str:
    """
    Gera uma linha de detalhe (tipo 1) do arquivo CNAB.

    Args:
        base_record: Dicionário com dados de um registro da BASE
        index: Índice do registro (usado para numeração sequencial)
        menu_data: Dicionário com dados do menu (DTL, OCORRENCIA)

    Returns:
        String com a linha de detalhe formatada (444 caracteres)
    """
    dtl = menu_data["DTL"]
    oco = menu_data["OCORRENCIA"]

    # Primeira parte da linha (X no VBA)
    x = (
        "1" +                                                    # Tipo de registro
        rep(" ", 9) +                                            # Espaços (posições 2-10: tipo de juros, não usado)
        pad_left_zeros(format_valor(""), 10) +                  # Taxa de juros (posições 11-20, não usada -> zero-fill)
        # COOBRIGACAO (coluna 15) - 2 chars + 15 zeros
        pad_left_zeros(base_record["COOBRIGACAO"][-2:], 2) + rep("0", 15) +
        # SEU_NUMERO (coluna 3) - 25 chars, alinhado à direita
        pad_left_spaces(base_record["SEU_NUMERO"].strip(), 25) +
        "001" +                                                  # Código
        rep("0", 5) +                                            # Zeros (5 chars)
        rep("0", 11) +                                           # Zeros (11 chars)
        "1" +                                                    # Flag
        # VALOR_PAGO_TITULO (coluna 18) - 10 chars, preenchido com zeros
        pad_left_zeros(format_valor(base_record["VALOR_PAGO_TITULO"]), 10) +
        "1" +                                                    # Flag
        "N" +                                                    # Flag
        format_date_ddmmyy(dtl) +                               # Data de liquidação (DDMMYY)
        rep(" ", 4) +                                            # Espaços (4 chars)
        " " +                                                    # Espaço (1 char)
        "1" +                                                    # Flag
        rep(" ", 2) +                                            # Espaços (2 chars)
        pad_left_zeros(oco, 2) +                                # Ocorrência (2 chars)
        # NU_DOCUMENTO (coluna 4) - últimos 10 chars, alinhado à direita
        pad_left_spaces(base_record["NU_DOCUMENTO"].strip()[-10:], 10) +
        # DT_VENCIMENTO (coluna 5) - DDMMYY
        format_date_ddmmyy(base_record["DT_VENCIMENTO"]) +
        # VL_NOMINAL (coluna 6) - 13 chars, preenchido com zeros
        pad_left_zeros(format_valor(base_record["VL_NOMINAL"]), 13) +
        rep("0", 3) +                                            # Zeros (3 chars)
        rep("0", 5) +                                            # Zeros (5 chars)
        # TP_TITULO (coluna 13) - últimos 2 chars, preenchido com zeros
        pad_left_zeros(base_record["TP_TITULO"].strip()[-2:], 2) +
        " " +                                                    # Espaço (1 char)
        # DT_EMISSAO_TITULO (coluna 14) - DDMMYY
        format_date_ddmmyy(base_record["DT_EMISSAO_TITULO"])
    )

    # Segunda parte da linha (Y no VBA)
    # Determina CPF/CNPJ do sacado
    identificacao_sacado = base_record["IDENTIFICACAO_CPF_CNPJ_SACADO"].strip()
    if identificacao_sacado == "1":
        cpf_cnpj_sacado = "000" + base_record["NU_CPF_CNPJ_SACADO"].strip()[-11:]
        cpf_cnpj_sacado = pad_left_zeros(cpf_cnpj_sacado, 14)
    else:
        cpf_cnpj_sacado = pad_left_zeros(base_record["NU_CPF_CNPJ_SACADO"].strip()[:14], 14)

    y = (
        rep("0", 2) +                                            # Zeros (2 chars)
        # IDENTIFICACAO_CPF_CNPJ_CEDENTE (coluna 16) - 1 zero + 2 chars
        rep("0", 1) + pad_left_zeros(base_record["IDENTIFICACAO_CPF_CNPJ_CEDENTE"].strip()[-2:], 2) +
        rep("0", 12) +                                           # Zeros (12 chars)
        rep("0", 6) +                                            # Zeros (6 chars)
        rep("0", 13) +                                           # Zeros (13 chars)
        # VL_PAGO (coluna 9) - 13 chars, preenchido com zeros
        pad_left_zeros(format_valor(base_record["VL_PAGO"]), 13) +
        rep("0", 13) +                                           # Zeros (13 chars)
        # IDENTIFICACAO_CPF_CNPJ_SACADO (coluna 10) - "01" ou "02"
        ("01" if identificacao_sacado == "1" else "02") +
        # NU_CPF_CNPJ_SACADO (coluna 7) - 14 chars, formatado acima
        cpf_cnpj_sacado +
        # NM_SACADO (coluna 8) - 40 chars, alinhado à esquerda
        pad_right_spaces(base_record["NM_SACADO"].strip()[:40], 40) +
        # ENDERECO (coluna 11) - 40 chars, alinhado à esquerda
        pad_right_spaces(base_record["ENDERECO"].strip()[:40], 40) +
        rep(" ", 12) +                                           # Espaços (12 chars)
        # CEP (coluna 12) - primeiros 8 chars, alinhado à esquerda
        pad_right_spaces(base_record["CEP"].strip()[:8], 8) +
        # NOME_CEDENTE (coluna 2) - 40 chars, alinhado à esquerda, depois 6 espaços extras
        pad_right_spaces(base_record["NOME_CEDENTE"].strip()[:40], 46) +
        # CNPJ_CEDENTE (coluna 1) - remove caracteres especiais, 14 chars
        pad_left_zeros(rp(base_record["CNPJ_CEDENTE"].strip()), 14) +
        # NFE (coluna 17) - últimos 44 chars, preenchido com zeros
        pad_left_zeros(base_record["NFE"].strip()[-44:], 44) +
        # Número sequencial - 6 chars
        pad_left_zeros(str(index), 6)
    )

    return x + y


def gerar_linha_trailer(total_records: int) -> str:
    """
    Gera a linha de rodapé (tipo 9) do arquivo CNAB.

    Args:
        total_records: Número total de registros (incluindo header)

    Returns:
        String com a linha de rodapé formatada
    """
    linha = (
        "9" +                                                    # Tipo de registro
        rep(" ", 437) +                                          # Espaços (437 chars)
        pad_left_zeros(str(total_records), 6)                   # Número sequencial
    )

    return linha


def gerar_cnab(base_data: list, menu_data: dict, output_path: str) -> str:
    """
    Gera um arquivo CNAB completo a partir dos dados fornecidos.

    Args:
        base_data: Lista de dicionários com dados dos registros (coluna BASE)
        menu_data: Dicionário com dados do menu (DTL, CDO, OCORRENCIA)
        output_path: Caminho do arquivo de saída

    Returns:
        Mensagem de sucesso ou erro
    """
    try:
        with open(output_path, "w", encoding="utf-8") as arquivo:
            # Linha 1: Header
            linha_header = gerar_linha_header(menu_data)
            arquivo.write(linha_header + "\n")

            # Linhas 2 a N+1: Detalhes
            for index, record in enumerate(base_data, start=2):
                # Verifica se SEU_NUMERO está vazio (condição de parada)
                if not record.get("SEU_NUMERO", "").strip():
                    break

                linha_detalhe = gerar_linha_detalhe(record, index, menu_data)
                arquivo.write(linha_detalhe + "\n")

            # Última linha: Trailer
            total_records = len(base_data) + 2  # +2 para incluir header e trailer
            linha_trailer = gerar_linha_trailer(total_records)
            arquivo.write(linha_trailer + "\n")

        return f"✓ Arquivo CNAB gerado com sucesso: {output_path}"

    except Exception as e:
        return f"✗ Erro ao gerar arquivo CNAB: {str(e)}"
