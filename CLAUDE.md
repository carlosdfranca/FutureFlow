# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development server
python manage.py runserver

# Migrations
python manage.py makemigrations
python manage.py migrate

# Celery worker (requires Redis running)
celery -A fidc_gestao worker --loglevel=info

# Celery Beat (periodic tasks scheduler)
celery -A fidc_gestao beat --loglevel=info

# Flower (Celery monitoring UI)
celery -A fidc_gestao flower

# Django shell
python manage.py shell
```

Environment variables are loaded via `python-dotenv` (`load_dotenv()` in `settings.py`). Requires a `.env` file at the project root — minimum required vars: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_*`.

## Architecture

### Stack
Django 5.2 · MySQL (`mysqlclient`) · Redis/Celery · `python-dotenv` · `docxtpl` (DOCX generation) · `lxml` (XML parsing)

### URL routing
```
/             → core.urls        (shell pages: home, limites, risco, etc.)
/usuarios/    → usuarios.urls    (login, perfil)
/fundos/      → fundos.urls      (fundos, cotas, informes)
/operacoes/   → operacoes.urls   (cessões, títulos, aplicações)
/admin/       → Django admin
```

### Multi-tenancy (`usuarios` app)
- `Empresa` is the tenant. `CustomUser` (extends `AbstractUser`) belongs to one or more `Empresa` via `UserEmpresa`.
- `EmpresaRole` holds boolean permission flags per empresa (e.g. `pode_ver_fundos`, `pode_importar_informes`).
- `EmpresaAtivaMiddleware` (`core/middleware.py`) reads `request.session["empresa_ativa"]` and injects `request.empresa_ativa` (an `Empresa` instance). Always available for authenticated users — auto-selects the first empresa if session is empty.
- Two context processors in `core/context_processors.py` inject `empresas_todas` and `empresas_disponiveis` into every template.

### `fundos` app
- `Fundo` (FIDC/FII/FIP) → `Cotista` → `MovimentacaoCota` → `CotaHistorico`
- Cota history is populated by importing the **Informe Mensal XML** (CVM format) via `fundos/services/importar_informe.py` + `fundos/services/informe_xml.py`. The old `calcular_cotas_diarias` task is deprecated — do not re-enable it in Celery Beat.
- Tributo calculation (IR/IOF on resgate) lives in `fundos/services/tributos.py`.

### `operacoes` app — Cessões (main active system)
Three-level model with event sourcing:
```
OperacaoCessao (contrato/lote)
  └── Titulo (recebível individual)
        └── EventoTitulo (immutable history)
```
`TipoEventoTitulo` integer values intentionally match CNAB OCORRENCIA codes (e.g. LIQUIDACAO_TOTAL = 6, LIQUIDACAO_PARCIAL = 14).

XML batch import (`workflow_cessao` view, action `parse_xml`) groups títulos **by cedente CNPJ** extracted from the XML: N XMLs from the same cedente in one upload become 1 `OperacaoCessao` with N `Titulo` rows (not N separate operações) — `OperacaoCessao` only stores one cedente, so different cedentes in the same upload still produce separate blocos. See `docs/plano_agrupamento_cessao_e_cnab.md`.

Business logic goes through the service layer (`operacoes/services/cessao.py`):
- `processar_cessao()` — creates `OperacaoCessao` + `Titulo` list + initial `EventoTitulo(AQUISICAO)` in one `@transaction.atomic`. Always recalculates `Titulo.valor_aquisicao` (valor presente) server-side from `valor_nominal` and `OperacaoCessao.taxa_desconto` — never trusts the value posted from the form.
- `calcular_valor_presente(valor_nominal, taxa_desconto_pct)` — `ARRED(nominal - nominal*taxa; 2)` with `ROUND_HALF_UP`; taxa is % (e.g. `0.60` = 0,6%). See `docs/plano_valor_presente_cessao.md`.
- `criar_evento_titulo()` — creates the event and mutates `Titulo.saldo_devedor` / `Titulo.ativo` as a side effect.

CNAB detail line (`download_cnab_cessao` → `cnab_generator.gerar_linha_detalhe`) has `VL_NOMINAL` (pos. 127-139, `Titulo.valor_nominal`, full value) and `VL_PRESENTE` (pos. 193-205, `Titulo.valor_aquisicao`, discounted) as **separate** fields — do not conflate them. `VALOR_PAGO_TITULO` (pos. 83-92) is the sum of liquidation events, unrelated to either. See `docs/plano_agrupamento_cessao_e_cnab.md`.

### `core` app
- Shell/stub views for sections not yet implemented (limites, risco, conformidade, etc.).
- `core/services/cessao_xml.py` — parses NF-e XML files uploaded in the cessão workflow.
- `core/services/cessao_doc.py` — generates DOCX documents (termo de cessão, confirmação) using `docxtpl` from templates in `doc_templates/`.

### CNAB generation (`operacoes/utils/`)
- `cnab_utils.py` — low-level formatters ported from VBA (`rep`, `rp`, `format_valor`, `pad_*`). `format_valor()` expects a **string with comma** as decimal separator (BR format).
- `cnab_generator.py` — builds header (type 0), detail (type 1), and trailer (type 9) lines.
- `cnab_service.py` — `gerar_cnab_stream(base_data, menu_data)` wraps the generator to write to `io.StringIO` instead of a file, returning a buffer ready for `HttpResponse`.

When building `base_data` from Django `DecimalField` values, convert with `str(decimal_value).replace('.', ',')` before passing to the CNAB functions. CPF/CNPJ identification: `"1"` = CPF (≤11 digits after stripping punctuation), `"2"` = CNPJ.

### Templates
- Base layout: `core/templates/base.html`
- App templates: `<app>/templates/<app>/<template>.html`
- Release notes rendered as Markdown on the home page from `static/docs/release_notes.md`.
- DOCX source templates: `doc_templates/`.
