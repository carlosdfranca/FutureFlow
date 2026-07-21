"""
Funções utilitárias para geração de arquivos CNAB.
Equivalentes às funções helper do VBA.
"""


def rep(char: str, count: int) -> str:
    """
    Repete um caractere N vezes.
    Equivalente à função REP do VBA.

    Args:
        char: Caractere a ser repetido
        count: Número de repetições

    Returns:
        String com o caractere repetido
    """
    return char * count


def fd(string: str, char: str) -> int:
    """
    Verifica se um caractere existe em uma string.
    Equivalente à função FD do VBA.

    Args:
        string: String a ser verificada
        char: Caractere a ser procurado

    Returns:
        1 se o caractere existe, 0 caso contrário
    """
    return 1 if char in string else 0


_MAPA_ACENTOS = {
    "À": "A", "Á": "A", "Â": "A", "Ã": "A", "Ä": "A", "Å": "A",
    "à": "a", "á": "a", "â": "a", "ã": "a", "ä": "a", "å": "a",
    "È": "E", "É": "E", "Ê": "E", "Ë": "E",
    "è": "e", "é": "e", "ê": "e", "ë": "e",
    "Ì": "I", "Í": "I", "Î": "I", "Ï": "I",
    "ì": "i", "í": "i", "î": "i", "ï": "i",
    "Ò": "O", "Ó": "O", "Ô": "O", "Õ": "O", "Ö": "O",
    "ò": "o", "ó": "o", "ô": "o", "õ": "o", "ö": "o",
    "Ù": "U", "Ú": "U", "Û": "U", "Ü": "U",
    "ù": "u", "ú": "u", "û": "u", "ü": "u",
    "Ç": "C", "ç": "c",
    "Ñ": "N", "ñ": "n",
}


def remover_pontos(texto: str) -> str:
    """
    Remove pontos de uma string.
    Equivalente à função RemoverPontos do VBA (Módulo3.bas).
    """
    if not texto:
        return ""
    return texto.replace(".", "")


def remover_caracteres_especiais(texto: str) -> str:
    """
    Translitera acentos comuns do português para ASCII e mantém apenas
    dígitos, letras ASCII, espaço e vírgula.
    Equivalente à função RemoverCaracteresEspeciais do VBA (Módulo3.bas).

    Args:
        texto: Texto original (ex.: nome do sacado)

    Returns:
        Texto sem pontos, acentos ou caracteres especiais
    """
    if not texto:
        return ""

    sem_pontos = texto.replace(".", "")
    resultado = []
    for caractere in sem_pontos:
        caractere = _MAPA_ACENTOS.get(caractere, caractere)
        if caractere.isascii() and (caractere.isalnum() or caractere in (" ", ",")):
            resultado.append(caractere)

    return "".join(resultado)


def rp(string: str) -> str:
    """
    Remove caracteres especiais (/, ., -) de uma string.
    Equivalente à função RP do VBA.

    Args:
        string: String a ser processada

    Returns:
        String sem os caracteres especiais
    """
    return string.replace("/", "").replace(".", "").replace("-", "")


def format_valor(value_str: str) -> str:
    """
    Formata um valor monetário para o padrão CNAB.
    Remove vírgula, adiciona zeros se necessário para decimais.

    Args:
        value_str: Valor em formato string (ex: "51490,00" ou "51490")

    Returns:
        Valor formatado sem vírgula e com decimais completos
    """
    # Remove vírgula
    valor_sem_virgula = value_str.replace(",", "")

    # Se não tem vírgula no original, adiciona "00" no final (centavos)
    if fd(value_str, ",") == 0:
        valor_sem_virgula += "00"

    # Se tem vírgula mas só 1 decimal (ex: "51490,0"), adiciona mais um zero
    if "," in value_str and value_str.split(",")[1] and len(value_str.split(",")[1]) == 1:
        valor_sem_virgula += "0"

    return valor_sem_virgula


def format_date_ddmmyy(date_str: str) -> str:
    """
    Converte data de DD/MM/YYYY ou DD/MM/YY para DDMMYY.

    Args:
        date_str: Data em formato DD/MM/YYYY ou DD/MM/YY

    Returns:
        Data em formato DDMMYY
    """
    parts = date_str.split("/")
    dd = parts[0][:2]
    mm = parts[1][:2]
    yy = parts[2][-2:]  # Pega os últimos 2 dígitos do ano
    return dd + mm + yy


def format_date_ddmmaaaa(date_str: str) -> str:
    """
    Converte data de DD/MM/YYYY para DDMMAAAA.

    Args:
        date_str: Data em formato DD/MM/YYYY

    Returns:
        Data em formato DDMMAAAA
    """
    parts = date_str.split("/")
    dd = parts[0][:2]
    mm = parts[1][:2]
    aaaa = parts[2][:4] if len(parts[2]) == 4 else "20" + parts[2]  # Assume 20XX se ano de 2 dígitos
    return dd + mm + aaaa


def pad_left_zeros(value: str, width: int) -> str:
    """
    Preenche uma string com zeros à esquerda até atingir a largura especificada.

    Args:
        value: Valor a ser preenchido
        width: Largura final desejada

    Returns:
        String preenchida com zeros à esquerda
    """
    return rep("0", width - len(value)) + value


def pad_right_spaces(value: str, width: int) -> str:
    """
    Preenche uma string com espaços à direita até atingir a largura especificada.

    Args:
        value: Valor a ser preenchido
        width: Largura final desejada

    Returns:
        String preenchida com espaços à direita
    """
    return value + rep(" ", width - len(value))


def pad_left_spaces(value: str, width: int) -> str:
    """
    Preenche uma string com espaços à esquerda até atingir a largura especificada.

    Args:
        value: Valor a ser preenchido
        width: Largura final desejada

    Returns:
        String preenchida com espaços à esquerda
    """
    return rep(" ", width - len(value)) + value
