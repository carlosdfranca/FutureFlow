from io import BytesIO
from decimal import Decimal
from datetime import datetime
from docxtpl import DocxTemplate


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _fmt_money(v: Decimal) -> str:
    s = f"{v:,.2f}"
    # 12,345.67 -> 12.345,67
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_doc(doc: str) -> str:
    if len(doc) == 14:
        return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
    if len(doc) == 11:
        return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    return doc


def _digits(v: str) -> str:
    """Remove caracteres não-numéricos de strings de documentos"""
    return "".join(c for c in str(v or "") if c.isdigit())


# -------------------------------------------------
# Render principal
# -------------------------------------------------

def render_termo_cessao_docx(
    template_path: str,
    *,
    partes,
    titulos,
    dados_operacao: dict
) -> bytes:

    doc = DocxTemplate(template_path)

    # =============================
    # Títulos → tabela
    # =============================

    total = sum(t.valor for t in titulos)

    tabela = []
    for t in titulos:
        tabela.append({
            "sacado_nome": t.sacado_nome,
            "sacado_doc": _fmt_doc(t.sacado_doc),
            "valor": _fmt_money(t.valor),
            "vencimento": t.vencimento_iso,
            "tipo": t.tipo_credito,
            "numero": t.numero_titulo,
        })

    # =============================
    # Base context — dados_operacao
    # =============================

    context = dict(dados_operacao)   # <<< pega TODOS campos do form

    # =============================
    # Data atual (quando clicou gerar)
    # =============================
    
    context["data_atual"] = datetime.now().strftime("%d/%m/%Y")

    # =============================
    # Formata campos conhecidos
    # =============================

    if context.get("preco_aquisicao"):
        context["preco_aquisicao"] = _fmt_money(context["preco_aquisicao"])

    # datas → string bonita
    for campo_data in [
        "data_aquisicao",
        "data_contrato"
    ]:
        if context.get(campo_data):
            context[campo_data] = context[campo_data].strftime("%d/%m/%Y")

    # docs - formatação automática dos novos campos
    campos_doc = [
        "cessionario_doc", "emitente_cnpj", "cessionario_cnpj", 
        "emitente_cpf", "cessionario_cpf", "testemunha1_cpf", "testemunha2_cpf"
    ]
    
    for campo in campos_doc:
        if context.get(campo):
            context[campo] = _fmt_doc(_digits(context[campo]))

    # =============================
    # Partes fixas
    # =============================

    context.update({
        "cedente_nome": partes.cedente_nome,
        "cedente_doc": _fmt_doc(partes.cedente_doc),
        "sacado_nome": partes.sacado_nome,
        "sacado_doc": _fmt_doc(partes.sacado_doc),

        "titulos": tabela,
        "valor_total": _fmt_money(total),
    })

    # =============================
    # Render
    # =============================

    doc.render(context)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)

    return buf.read()
