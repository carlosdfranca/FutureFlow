from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
import xml.etree.ElementTree as ET
from typing import Any


# ============================================================
# Helpers
# ============================================================

_RE_DIGITS = re.compile(r"\D+")


def _digits(value: str | None) -> str:
    if value is None:
        return ""
    return _RE_DIGITS.sub("", str(value))


def _to_decimal(value: str | None) -> Decimal:
    """
    Converte string para Decimal aceitando:
      - "15000.75"
      - "15.000,75"
      - "15000,75"
      - ""
    """
    if value is None:
        return Decimal("0")
    s = str(value).strip()
    if not s:
        return Decimal("0")

    # remove espaços
    s = s.replace(" ", "")

    # se tiver vírgula e ponto, assume pt-BR "15.000,75"
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    # se só tiver vírgula, assume decimal com vírgula
    elif "," in s and "." not in s:
        s = s.replace(",", ".")

    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def _find_first_text(elem: ET.Element, paths: list[str], ns: dict[str, str]) -> str:
    """
    Procura o primeiro texto existente em uma lista de XPaths (relativos ao elem).
    Retorna "" se não achar.
    """
    for p in paths:
        found = elem.find(p, ns)
        if found is not None and (found.text or "").strip():
            return (found.text or "").strip()
    return ""


def _all(elem: ET.Element, path: str, ns: dict[str, str]) -> list[ET.Element]:
    return list(elem.findall(path, ns))


def _safe_find(elem: ET.Element, tag_name: str, ns: dict[str, str]) -> ET.Element | None:
    """
    Busca elemento tentando primeiro sem namespace, depois com namespace se disponível.
    """
    # Primeiro tenta sem namespace
    found = elem.find(tag_name)
    if found is not None:
        return found
    
    # Se tem namespace available, tenta com prefixo
    if ns and 'nfe' in ns:
        found = elem.find(f"nfe:{tag_name}", ns)
        if found is not None:
            return found
    
    return None


def _safe_findall(elem: ET.Element, tag_name: str, ns: dict[str, str]) -> list[ET.Element]:
    """
    Busca todos os elementos tentando primeiro sem namespace, depois com namespace se disponível.
    """
    # Primeiro tenta sem namespace
    found = elem.findall(tag_name)
    if found:
        return found
    
    # Se tem namespace available, tenta com prefixo
    if ns and 'nfe' in ns:
        found = elem.findall(f"nfe:{tag_name}", ns)
        if found:
            return found
    
    return []


def _safe_find_text(elem: ET.Element, tag_name: str, ns: dict[str, str]) -> str:
    """
    Busca texto de um elemento tentando primeiro sem namespace, depois com namespace.
    """
    found = _safe_find(elem, tag_name, ns)
    if found is not None and found.text:
        return found.text.strip()
    return ""


def _infer_namespace(root: ET.Element) -> dict[str, str]:
    """
    NF-e normalmente usa namespace como:
      {http://www.portalfiscal.inf.br/nfe}
    Este helper tenta capturar e retornar um dict pro ElementTree.
    """
    # Primeiro, tenta pela tag do root
    m = re.match(r"\{(.+)\}", root.tag)
    if m:
        return {"nfe": m.group(1)}
    
    # Se não encontrou, procura recursivamente por elementos com namespace
    for elem in root.iter():
        m = re.match(r"\{(.+)\}", elem.tag)
        if m:
            return {"nfe": m.group(1)}
    
    return {}


@dataclass(frozen=True)
class CpvTitulo:
    sacado_nome: str
    sacado_doc: str  # CPF/CNPJ apenas dígitos
    valor: Decimal
    vencimento_iso: str  # "YYYY-MM-DD"
    tipo_credito: str = "Duplicata"
    numero_titulo: str = ""  # opcional


@dataclass(frozen=True)
class CpvPartes:
    cedente_nome: str
    cedente_doc: str  # CNPJ apenas dígitos
    sacado_nome: str
    sacado_doc: str  # CPF/CNPJ apenas dígitos
    numero_nota: str = ""     # nNF
    data_emissao_iso: str = ""  # dhEmi / dEmi


@dataclass(frozen=True)
class CpvParseResult:
    partes: CpvPartes
    titulos: list[CpvTitulo]
    total: Decimal


# ============================================================
# Parser principal
# ============================================================

def parse_nfe_xml(xml_bytes: bytes) -> CpvParseResult:
    """
    Lê XML NF-e (vários formatos comuns) e extrai:
      - emit/xNome + emit/CNPJ
      - dest/xNome + dest/CNPJ ou dest/CPF
      - duplicatas: cobr/dup (dVenc e (vDup opcional))
      - fallback de valor: somar det/prod/vProd

    Não salva nada em disco. Só retorna dados.
    """
    root = ET.fromstring(xml_bytes)
    ns = _infer_namespace(root)

    # Achar o nó infNFe (pode estar em nfeProc/NFe/infNFe etc.)
    infnfe = root.find(".//infNFe")
    if infnfe is None and ns and 'nfe' in ns:
        infnfe = root.find(".//nfe:infNFe", ns)

    if infnfe is None:
        raise ValueError("XML não contém infNFe (não parece ser uma NF-e válida).")

    # nós principais usando funções seguras
    emit = _safe_find(infnfe, "emit", ns)
    dest = _safe_find(infnfe, "dest", ns)
    ide = _safe_find(infnfe, "ide", ns)
    cobr = _safe_find(infnfe, "cobr", ns)

    if emit is None or dest is None:
        raise ValueError("XML NF-e sem tags emit/dest.")

    cedente_nome = _safe_find_text(emit, "xNome", ns)
    cedente_cnpj = _digits(_safe_find_text(emit, "CNPJ", ns))

    sacado_nome = _safe_find_text(dest, "xNome", ns)
    # Tenta CNPJ primeiro, depois CPF
    sacado_doc = (_digits(_safe_find_text(dest, "CNPJ", ns)) or 
                  _digits(_safe_find_text(dest, "CPF", ns)))

    numero_nota = ""
    data_emissao = ""
    if ide is not None:
        numero_nota = _safe_find_text(ide, "nNF", ns)
        # dhEmi é comum, mas algumas versões usam dEmi
        data_emissao = (_safe_find_text(ide, "dhEmi", ns) or 
                       _safe_find_text(ide, "dEmi", ns))
        data_emissao = data_emissao.strip()

    # Total por produtos (fallback)
    # somar det/prod/vProd
    det_nodes = _safe_findall(infnfe, "det", ns)
    soma_vprod = Decimal("0")
    for det in det_nodes:
        prod = _safe_find(det, "prod", ns)
        if prod is None:
            continue
        vprod = _safe_find_text(prod, "vProd", ns)
        soma_vprod += _to_decimal(vprod)

    # Duplicatas (cobr/dup)
    dup_nodes: list[ET.Element] = []
    if cobr is not None:
        dup_nodes = _safe_findall(cobr, "dup", ns)

    titulos: list[CpvTitulo] = []

    if dup_nodes:
        for dup in dup_nodes:
            d_venc = _safe_find_text(dup, "dVenc", ns)
            # valor da duplicata pode ser vDup; se não existir, deixa 0 e a tela decide
            v_dup = _to_decimal(_safe_find_text(dup, "vDup", ns))
            n_dup = _safe_find_text(dup, "nDup", ns)

            titulos.append(
                CpvTitulo(
                    sacado_nome=sacado_nome,
                    sacado_doc=sacado_doc,
                    valor=v_dup,
                    vencimento_iso=d_venc,  # geralmente já vem YYYY-MM-DD
                    tipo_credito="Duplicata",
                    numero_titulo=n_dup or numero_nota,
                )
            )

        # Se todas vieram com valor 0 (comum em alguns XMLs), distribui proporcionalmente ou joga soma total?
        # Aqui, por simplicidade, se TODOS forem 0 e existir soma_vprod, coloca tudo no primeiro título.
        if soma_vprod > 0 and all(t.valor == 0 for t in titulos):
            first = titulos[0]
            titulos[0] = CpvTitulo(
                sacado_nome=first.sacado_nome,
                sacado_doc=first.sacado_doc,
                valor=soma_vprod,
                vencimento_iso=first.vencimento_iso,
                tipo_credito=first.tipo_credito,
                numero_titulo=first.numero_titulo,
            )

    else:
        # Sem duplicata no XML: cria 1 título padrão com vencimento vazio.
        # A tela vai permitir editar vencimento/valor.
        titulos.append(
            CpvTitulo(
                sacado_nome=sacado_nome,
                sacado_doc=sacado_doc,
                valor=soma_vprod,
                vencimento_iso="",
                tipo_credito="Duplicata",
                numero_titulo=numero_nota,
            )
        )

    total = sum((t.valor for t in titulos), Decimal("0"))

    partes = CpvPartes(
        cedente_nome=cedente_nome,
        cedente_doc=cedente_cnpj,
        sacado_nome=sacado_nome,
        sacado_doc=sacado_doc,
        numero_nota=numero_nota,
        data_emissao_iso=data_emissao,
    )

    return CpvParseResult(partes=partes, titulos=titulos, total=total)


# ============================================================
# Utilitário opcional para sua view
# ============================================================

def parse_nfe_uploaded_file(uploaded_file) -> CpvParseResult:
    """
    Aceita request.FILES['xml'] (UploadedFile do Django).
    """
    return parse_nfe_xml(uploaded_file.read())
