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

#### The two-step value cascade

Título values come from a **two-step cascade** mirroring the legacy spreadsheet. Getting this
wrong is what made the generated CNAB diverge from the legacy file by R$ 6.835,53 on a
30-título batch:

```
valor_face          cobr/dup/vDup from the XML (gross). NOT stored.
  ↓ ARRED(× (1 − taxa_iof); 2)          IOF, 0,6% by default
Titulo.valor_nominal    → CNAB VL_NOMINAL  (pos. 127-139), and saldo_devedor
  ↓ ARRED(× (1 − taxa_desconto); 2)     deságio, 2,98% in practice
Titulo.valor_aquisicao  → CNAB VL_PRESENTE (pos. 193-205)
```

- **`Titulo.valor_nominal` is net of IOF**, not the gross duplicata value. The gross value
  is not persisted (recoverable from the XML via `chave_nfe`); the sacado pays the net value,
  so `saldo_devedor`, carteira, lâmina and dashboards all follow it.
- **Round at every step.** Collapsing the two rates into one expression is off by cents:
  4.567,20 → 4.539,80 → 4.409,05, but 4.567,20 × 0,994 × 0,9712 rounds to 4.409,04.
- Both rates live on `OperacaoCessao` (`taxa_iof`, `taxa_desconto`), are percentages
  (`0.60` = 0,6%), default to `0` in the model (so pre-cascade operações keep their old
  behaviour), and are **required in the form** — `TAXA_IOF_PADRAO` supplies the initial value.

Business logic goes through the service layer (`operacoes/services/cessao.py`):
- `processar_cessao()` — creates `OperacaoCessao` + `Titulo` list + initial
  `EventoTitulo(AQUISICAO)` in one `@transaction.atomic`. Always derives `valor_nominal` and
  `valor_aquisicao` server-side from `titulos_dados[i]['valor_face']` and the two rates —
  never trusts the values posted from the form. Both rates are read with **hard key access**
  so a caller that forgets one raises `KeyError` instead of silently defaulting to 0.
- `calcular_valor_nominal(valor_face, taxa_iof_pct)` — step 1. Mirrors `CalcularDesconto`
  (`docs/legado_vba/Módulo3.bas:5-26`). Uses `ROUND_HALF_UP` where the VBA `Round()` is
  half-even — a deliberate R$ 0,01 divergence for gross values ending in X2,50 (~1 in 1.000).
- `calcular_valor_presente(valor_nominal, taxa_desconto_pct)` — step 2. Mirrors the formula
  in column I of the BASE sheet. See `docs/plano_valor_presente_cessao.md`.
- `criar_evento_titulo()` — creates the event and mutates `Titulo.saldo_devedor` /
  `Titulo.ativo` as a side effect.

CNAB detail line (`download_cnab_cessao` → `cnab_generator.gerar_linha_detalhe`) has
`VL_NOMINAL` (pos. 127-139, `Titulo.valor_nominal`, net of IOF) and `VL_PRESENTE`
(pos. 193-205, `Titulo.valor_aquisicao`, further discounted) as **separate** fields — do not
conflate them. `VALOR_PAGO_TITULO` (pos. 83-92) is the sum of liquidation events, unrelated to
either. `COOBRIGACAO` (pos. 21-22) resolves as
`titulo.coobrigacao or fundo.coobrigacao_cnab_padrao or '02'` **in the view**, before building
`base_data` — an empty string reaching the generator would silently become `'00'`. Detail
lines are ordered by `numero_titulo`, matching the legacy file and making the output
deterministic (the model's `Meta.ordering` by `data_vencimento` leaves ties unordered, and
ties are the norm in a cessão batch). See `docs/plano_agrupamento_cessao_e_cnab.md`.

`operacoes/tests.py::CnabGoldenAtrivionTest` compares the generated CNAB byte for byte
against the file the legacy macro produced for a real 30-título batch. Fixtures and the
evidence trail are in `operacoes/fixtures/cnab_atrivion_20260909/PROVENIENCIA.md`.

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
