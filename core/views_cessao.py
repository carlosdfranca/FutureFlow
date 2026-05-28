from decimal import Decimal
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

from core.forms_cessao import (
    CessaoForm,
    TituloCessaoFormSet
)

from core.services.cessao_xml import parse_nfe_uploaded_file
from core.services.cessao_doc import render_termo_cessao_docx, render_termo_confirmacao_docx

from fundos.models import Recebiveis, Fundo


TEMPLATE_HTML = "workflow_cessao_cpv.html"
TEMPLATE_DOCX = str(settings.BASE_DIR / "doc_templates" / "termo_cessao.docx")
TEMPLATE_CONFIRMACAO_DOCX = str(settings.BASE_DIR / "doc_templates" / "termo_confirmacao.docx")


@login_required
def workflow_cessao_view(request):

    cessao_form = CessaoForm()
    titulos_formset = TituloCessaoFormSet()

    parsed_info = None

    if request.method == "POST":

        acao = request.POST.get("acao")

        # =====================================================
        # IMPORTAR XML → preencher títulos
        # =====================================================

        if acao == "parse_xml":

            xml_file = request.FILES.get("xml_file")

            if not xml_file:
                messages.error(request, "Selecione um XML.")
                return render(request, TEMPLATE_HTML, {
                    "cessao_form": CessaoForm(),
                    "titulos_formset": TituloCessaoFormSet(),
                })

            parsed = parse_nfe_uploaded_file(xml_file)

            iniciais = []
            for t in parsed.titulos:
                iniciais.append({
                    "numero": t.numero_titulo,
                    "sacado_nome": t.sacado_nome,
                    "sacado_doc": t.sacado_doc,
                    "valor": t.valor,
                    "vencimento": t.vencimento_iso,
                    "tipo": t.tipo_credito,
                })

            titulos_formset = TituloCessaoFormSet(initial=iniciais)

            return render(request, TEMPLATE_HTML, {
                "cessao_form": CessaoForm(),   # vazio — não valida
                "titulos_formset": titulos_formset,
            })

        # =====================================================
        # ADICIONAR LINHA MANUAL
        # =====================================================

        elif acao == "add_linha":

            titulos_formset = TituloCessaoFormSet(request.POST)

            total = int(request.POST["form-TOTAL_FORMS"])
            data = request.POST.copy()
            data["form-TOTAL_FORMS"] = total + 1

            titulos_formset = TituloCessaoFormSet(data)

            cessao_form = CessaoForm(request.POST)

        # =====================================================
        # GERAR — salvar + docx
        # =====================================================

        elif acao == "gerar":

            cessao_form = CessaoForm(request.POST)
            titulos_formset = TituloCessaoFormSet(request.POST)

            if not (cessao_form.is_valid() and titulos_formset.is_valid()):
                messages.error(request, "Corrija os campos.")
                return render(request, TEMPLATE_HTML, {
                    "cessao_form": cessao_form,
                    "titulos_formset": titulos_formset,
                })

            fundo = Fundo.objects.first()  # depois ligamos no form se quiser

            titulos_validos = []
            for f in titulos_formset:
                if f.cleaned_data:
                    titulos_validos.append(f.cleaned_data)

            if not titulos_validos:
                messages.error(request, "Nenhum título válido.")
                return render(request, TEMPLATE_HTML, {
                    "cessao_form": cessao_form,
                    "titulos_formset": titulos_formset, 
                })

            # ---------- salvar recebíveis ----------
            for t in titulos_validos:

                Recebiveis.objects.create(
                    fundo=fundo,
                    cedente_cnpj=_digits(t["sacado_doc"]),
                    cedente_nome=t["sacado_nome"],
                    sacado_cpf_cnpj=_digits(t["sacado_doc"]),
                    sacado_nome=t["sacado_nome"],
                    tipo_credito=t["tipo"],
                    numero_titulo=t["numero"],
                    data_vencimento=t["vencimento"],
                    valor_nominal=t["valor"],
                    valor_cessao=t["valor"],
                    status="A_ENVIAR"
                )

            # ---------- doc ----------
            class T:
                def __init__(self, d):
                    self.numero_titulo = d["numero"]
                    self.sacado_nome = d["sacado_nome"]
                    self.sacado_doc = d["sacado_doc"]
                    self.valor = d["valor"]
                    self.vencimento_iso = d["vencimento"].isoformat()
                    self.tipo_credito = d["tipo"]

            titulos_doc = [T(t) for t in titulos_validos]

            partes = type("P", (), {})()
            # Usar dados do cedente do formulário se disponível, senão usar fundo
            cedente_nome_form = cessao_form.cleaned_data.get('emitente_razao_social')
            cedente_cnpj_form = cessao_form.cleaned_data.get('emitente_cnpj')
            
            partes.cedente_nome = cedente_nome_form or fundo.nome or "CEDENTE"
            partes.cedente_doc = _digits(cedente_cnpj_form) if cedente_cnpj_form else getattr(fundo, 'cnpj', "00000000000000")
            partes.sacado_nome = titulos_doc[0].sacado_nome
            partes.sacado_doc = titulos_doc[0].sacado_doc

            doc_bytes = render_termo_cessao_docx(
                TEMPLATE_DOCX,
                partes=partes,
                titulos=titulos_doc,
                dados_operacao=cessao_form.cleaned_data
            )

            return HttpResponse(
                doc_bytes,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": 'attachment; filename="termo_cessao.docx"'}
            )

        # =====================================================
        # GERAR TERMO DE CONFIRMAÇÃO — mesma lógica
        # =====================================================

        elif acao == "gerar_confirmacao":

            cessao_form = CessaoForm(request.POST)
            titulos_formset = TituloCessaoFormSet(request.POST)

            if not (cessao_form.is_valid() and titulos_formset.is_valid()):
                messages.error(request, "Corrija os campos.")
                return render(request, TEMPLATE_HTML, {
                    "cessao_form": cessao_form,
                    "titulos_formset": titulos_formset,
                })

            fundo = Fundo.objects.first()  # depois ligamos no form se quiser

            titulos_validos = []
            for f in titulos_formset:
                if f.cleaned_data:
                    titulos_validos.append(f.cleaned_data)

            if not titulos_validos:
                messages.error(request, "Nenhum título válido.")
                return render(request, TEMPLATE_HTML, {
                    "cessao_form": cessao_form,
                    "titulos_formset": titulos_formset, 
                })

            # ---------- NÃO salva recebíveis (só gera doc) ----------

            # ---------- doc ----------
            class T:
                def __init__(self, d):
                    self.numero_titulo = d["numero"]
                    self.sacado_nome = d["sacado_nome"]
                    self.sacado_doc = d["sacado_doc"]
                    self.valor = d["valor"]
                    self.vencimento_iso = d["vencimento"].isoformat()
                    self.tipo_credito = d["tipo"]

            titulos_doc = [T(t) for t in titulos_validos]

            partes = type("P", (), {})()
            # Usar dados do cedente do formulário se disponível, senão usar fundo
            cedente_nome_form = cessao_form.cleaned_data.get('emitente_razao_social')
            cedente_cnpj_form = cessao_form.cleaned_data.get('emitente_cnpj')
            
            partes.cedente_nome = cedente_nome_form or fundo.nome or "CEDENTE"
            partes.cedente_doc = _digits(cedente_cnpj_form) if cedente_cnpj_form else getattr(fundo, 'cnpj', "00000000000000")
            partes.sacado_nome = titulos_doc[0].sacado_nome
            partes.sacado_doc = titulos_doc[0].sacado_doc

            doc_bytes = render_termo_confirmacao_docx(
                TEMPLATE_CONFIRMACAO_DOCX,
                partes=partes,
                titulos=titulos_doc,
                dados_operacao=cessao_form.cleaned_data
            )

            return HttpResponse(
                doc_bytes,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": 'attachment; filename="termo_confirmacao.docx"'}
            )

    return render(request, TEMPLATE_HTML, {
        "cessao_form": cessao_form,
        "titulos_formset": titulos_formset,
        "parsed_info": parsed_info
    })


def _digits(v):
    return "".join(c for c in str(v or "") if c.isdigit())
