# Plano de Comparação — Cobrança (Importação XML NF-e + Geração CNAB 400) vs. Macros VBA Legadas

> Documento de investigação/planejamento. Nenhuma alteração de código ou migration foi feita
> nesta rodada — apenas leitura do código-fonte e das macros de referência em `docs/legado_vba/`.

## 1. Resumo executivo

O gerador CNAB do sistema é um **port posicional fiel** da macro `Sub arquivo()`:
header (tipo 0), detalhe (tipo 1) e trailer (tipo 9) têm o **mesmo layout de 444
caracteres** e as mesmas posições. As divergências não estão no “esqueleto” do
arquivo, mas em **quais dados chegam a algumas posições**:

- **Bloqueante — chave NF-e não é gravada.** O parser extrai `chave_nfe` e a tela
  exibe, mas a view descarta o campo antes de salvar (`operacoes/views.py:131-141`).
  No CNAB a posição 395-438 sai com **44 zeros** em vez da chave (a macro grava a
  chave real, BASE col 17).
- **Bloqueante/relevante — desconto de 0,6% não replicado.** A macro de import
  aplica `CalcularDesconto` (× 0,994) ao valor antes de gravá-lo na BASE col 6, que
  alimenta a posição 127-139 (valor do título) do CNAB. O sistema usa
  `valor_nominal` cheio, sem o deságio de 0,6%. → **valor cobrado diverge.**
- **Relevante — posições 8 e 11-20 do detalhe.** A macro grava BASE col 19 (pos 8)
  e BASE col 20 como monetário (pos 11-20); o sistema emite **espaços** nessas
  posições. A origem dessas colunas na macro **não está no import** (pergunta aberta).
- **Relevante — nomes sem sanitização.** A macro transliteria acentos e remove
  caracteres especiais (`RemoverCaracteresEspeciais`/`RemoverPontos`); o sistema
  grava nomes crus do XML, o que pode injetar acento/caractere não-ASCII em campo
  fixo do CNAB.
- **Relevante — import só aceita 1 arquivo.** A macro varre uma pasta inteira de
  `.xml` (lote); o sistema processa **um upload por vez**.
- **Cosmética/menor — pequenas trocas de fonte de dado** (COOBRIGACAO fixo “01” vs.
  col 15, tipo-inscrição do sacado calculado vs. constante da BASE, contagem do
  trailer) e um **bug latente no parser** (`{{*}}` inválido em `cessao_xml.py:263`,
  mascarado pelo fallback `@Id`).

Observação transversal: `valor nominal` da NF-e (`total/ICMSTot/vNF`) **não é usado
por nenhum dos dois** — macro e sistema usam `vDup`. A macro apenas lê `vNF` numa
variável que nunca é escrita.

---

## 2. Mapa do sistema atual

### 2.1 Fluxo de importação de XML (ativo, app `operacoes`)

| Camada | Arquivo:linha | Papel |
|---|---|---|
| Template upload | `operacoes/templates/operacoes/workflow_cessao.html:26,46,50,209` | form multipart, input `xml_file`, botões `parse_xml`/`confirmar` |
| View (entrada) | `operacoes/views.py:27` `workflow_cessao` | `parse_xml` → parseia; `confirmar` → salva |
| Parser | `core/services/cessao_xml.py:363` `parse_nfe_uploaded_file` → `parse_nfe_xml:180` | usa `xml.etree.ElementTree` (não `lxml`) |
| Namespace | `cessao_xml.py:115-132` `_infer_namespace` | `{"nfe":"http://www.portalfiscal.inf.br/nfe"}`, com fallback sem-namespace |
| Service (persistência) | `operacoes/services/cessao.py:11` `processar_cessao` (`@transaction.atomic`) | cria `OperacaoCessao`+`Titulo`+`EventoTitulo(AQUISICAO)` |

Modelos:
- `OperacaoCessao` (`operacoes/models.py:41-113`): `fundo` FK, `cedente_cnpj/nome/endereco`,
  `numero_contrato` (**unique**), datas, totais, `status`.
- `Titulo` (`operacoes/models.py:120-238`): `numero_titulo`, `sacado_nome/cpf_cnpj/endereco/cep`,
  `valor_nominal/valor_aquisicao`, `data_emissao/data_vencimento`, `ativo`,
  **`chave_nfe` CharField(44)** `:202` (não único), `tipo_titulo` default `'01'`,
  `coobrigacao` default `'01'`.
- `EventoTitulo` (`operacoes/models.py:245-304`): histórico imutável; soma de
  LIQUIDACAO alimenta `VL_PAGO` no CNAB.
- **Não existem** `ImportacaoNFe`, `LoteRemessa`, `TituloRemessa`, `RetornoBancario`.
- Caminho **legado** paralelo: `core/views_cessao.py:25` grava em `fundos.Recebiveis`
  (`fundos/models.py:308-362`) — **sem campo `chave_nfe`** e sem `try/except` no parse.
  O sistema ativo é o de `operacoes`.

### 2.2 Fluxo de geração CNAB (app `operacoes`)

| Camada | Arquivo:linha | Papel |
|---|---|---|
| Link UI | `operacoes/templates/operacoes/detalhe_cessao.html:34` | botão “Gerar CNAB” |
| View parâmetros | `operacoes/views.py:424` `cnab_parametros` | renderiza `CnabParametrosForm` |
| Form | `operacoes/forms.py:262-277` `CnabParametrosForm` | `dtl` (data), `cdo`, `ocorrencia` (init `'01'`) |
| View (entrada real) | `operacoes/views.py:435-493` `download_cnab_cessao` | monta `base_data`, chama gerador, devolve `.txt` |
| Gerador | `operacoes/utils/cnab_generator.py` | `gerar_linha_header/detalhe/trailer` |
| Service stream | `operacoes/utils/cnab_service.py:5` `gerar_cnab_stream` | escreve em `io.StringIO` (buffer, sem disco) |
| Helpers | `operacoes/utils/cnab_utils.py` | `rep`, `rp`, `format_valor`, `format_date_ddmmyy`, `pad_*` |

`base_data` sai de `OperacaoCessao` + `Titulo.filter(ativo=True)` + soma de eventos
LIQUIDACAO (`views.py:451-481`). Não há `gerar_cnab` em disco no fluxo web (o
`cnab_generator.py:160` é código morto). Valores Decimal são convertidos com
`str(x).replace('.', ',')` antes do gerador (`views.py:468,471,480`).

---

## 3. Tabela de divergências — fluxo XML

| Item | Sistema hoje | Macro (`Sub JPl`) | Tipo | Severidade |
|---|---|---|---|---|
| Chave NF-e (prefixo “NFe”) | Extrai de `infProt/chNFe`; fallback `infNFe/@Id` com `[3:]` se começa com `NFe` (`cessao_xml.py:263-270`) | `//nfe:infNFe/@Id` + `LimparPrefixoNFe` (drop 3 chars) | Alinhado (fonte 1ª difere) | Cosmética |
| **Persistência da chave** | **Parseada e exibida, mas descartada antes de salvar** (`views.py:131-141`); grava `''` | Grava chave na BASE col 17 | **Regra/dado ausente** | **Bloqueante** |
| Valor do título | `vDup` (`cessao_xml.py:294`); fallback Σ`vProd`; `valor_aquisicao = valor_nominal` | `vDup` via `FormatarValor` | Alinhado na fonte | — |
| **Deságio 0,6%** | **Nenhum** — valor cheio | `CalcularDesconto` × 0,994 grava na BASE col 6 | **Regra de negócio** | **Bloqueante/Relevante** |
| `vNF` (ICMSTot) | Não lê | Lê em variável, **não grava** | Alinhado (ambos ignoram) | Cosmética |
| Data emissão (`dhEmi`) | String ISO crua; conversão só no `DateField`; sufixo de hora `T..` não removido no parser | `ExtrairData` → `DD/MM/YYYY` (fatia `YYYY-MM-DD`, ignora hora) | Formatação | Relevante |
| Data vencimento (`dVenc`) | String crua → `DateField` | `ExtrairData` → `DD/MM/YYYY` | Formatação | Menor |
| **Sanitização de nomes** | Nomes crus do XML | Emitente: `RemoverPontos`; sacado: `RemoverCaracteresEspeciais` (translitera acento, filtra) | Regra/formatação | Relevante |
| Múltiplos arquivos | 1 upload por vez (`views.py:45`) | Varre pasta inteira (`Dir *.xml`) | Regra/UX | Relevante |
| XML inválido | View ativa: `try/except` → `messages.error` (`views.py:90`). Legado: **sem** try/except | MsgBox + contador, segue p/ próximo | Robustez | Menor (relevante no legado) |
| Duplicidade de NF-e | **Sem checagem**; `chave_nfe` não único | Sem checagem | Alinhado (ambos faltam) | Relevante |
| Bug parser | `root.find(".//{{*}}infProt")` — `{{*}}` inválido (`cessao_xml.py:263`) | n/a | Bug latente (mascarado por fallback) | Cosmética |
| Endereço/CEP sacado | Extraídos, mas **descartados** em `views.py:131-141` (não passados a `processar_cessao`) | Grava CEP na BASE col 12 | Dado ausente | Relevante (impacta CNAB) |

---

## 4. Tabela de divergências — fluxo CNAB (layout posicional 444 chars)

**Header (tipo 0)** e **Trailer (tipo 9)**: idênticos posição-a-posição entre
sistema e macro (`0/1/REMESSA/01/COBRANCA…/CDO(20)/W×30/001/B×15/DTL ddmmaa/…/000001`
e `9 + 437 espaços + contagem(6)`). Única ressalva no trailer: contagem.

**Detalhe (tipo 1)** — divergências (posições 1-based; “=” = igual):

| Pos | Len | Sistema | Macro (BASE col) | Tipo | Sev. |
|---|---|---|---|---|---|
| 1 | 1 | `"1"` | `"1"` | = | — |
| **2-20** | 19 | **19 espaços** (`cnab_generator.py:64`) | 6 esp + **col19@pos8** + 2 esp + **col20 monetário@11-20** | Dado ausente / posição | **Relevante** |
| 21-22 | 2 | `COOBRIGACAO[-2:]` → “01” default | BASE col 15 (constante 2) → “02” | Fonte/valor | Menor |
| 23-37 | 15 | 15 zeros | 15 zeros | = | — |
| 38-62 | 25 | `SEU_NUMERO` (numero_titulo) dir. | BASE col 3 (`nFat`) dir. | Fonte | Menor |
| 63-92 | — | `001`,zeros,flag,`VALOR_PAGO_TITULO`(10),… | idem, col 18 monetário(10) | = estrutura | — |
| 95-100 | 6 | `DTL` ddmmyy | `DTL` ddmmaa | = | — |
| 109-110 | 2 | `OCORRENCIA` | `OCO` (MENU) | = | — |
| 111-120 | 10 | `NU_DOCUMENTO` últ.10 dir. | col 4 últ.10 dir. | Fonte | Menor |
| 121-126 | 6 | `DT_VENCIMENTO` ddmmyy | col 5 ddmmaa | = | — |
| **127-139** | 13 | `VL_NOMINAL` **cheio** | col 6 = `vDup` **× 0,994** | **Regra (valor)** | **Bloqueante** |
| 148-149 | 2 | `TP_TITULO` “01” | col 13 (const 1)→“01” | = valor | — |
| 151-156 | 6 | `DT_EMISSAO` ddmmyy | col 14 ddmmaa | = | — |
| 159-161 | 3 | `0`+`ID_CEDENTE`=“002” | `0`+col16(“02”)=“002” | = | — |
| 193-205 | 13 | `VL_PAGO` (Σ liquidações) | col 9 (preenchida externamente) | Fonte | Menor |
| 219-220 | 2 | “01/02” por **len(doc)** | por **col 10** (const “02”) | Regra | Menor |
| 221-234 | 14 | doc sacado (CPF `000`+11 / CNPJ 14) | idem | = | — |
| 235-274 | 40 | `NM_SACADO` (cru, sem sanitizar) | col 8 (sanitizado) | Formatação | Relevante |
| 275-314 | 40 | `ENDERECO` (**vazio**, ver §3) | col 11 (vazio no import) | Dado ausente | Relevante |
| 327-334 | 8 | `CEP` (**vazio**, descartado) | col 12 | Dado ausente | Relevante |
| 335-380 | 46 | `NOME_CEDENTE` 40+6 esp | col 2 40+6 esp | = | — |
| 381-394 | 14 | `rp(CNPJ_CEDENTE)` zeros | `RP(col1)` zeros | = | — |
| **395-438** | 44 | `NFE` (**vazio → 44 zeros**, ver §3) | col 17 = chave real | **Dado ausente** | **Bloqueante** |
| 439-444 | 6 | sequência `index` | `i` | = | — |

**Comprimento total:** ambos = **444** (não 400). Os docstrings/`CLAUDE.md` dizem
“400” — **confirmar contra o layout do banco** (o banco rejeita arquivo com largura
de linha errada).

**Trailer — contagem:** sistema usa `len(base_data)+2` (`cnab_service.py:12`); a
macro usa `i` (último sequencial). Divergem se o `break` por `SEU_NUMERO` vazio
(`cnab_service.py:9`) descartar detalhes. Severidade: menor (edge case), mas pode
quebrar validação de fechamento no banco.

**Caveat dos `pad_*`:** `rep(" ", width-len)` sem guarda — valor maior que a largura
**não é truncado** (só campos com `[:N]` explícito truncam). Vale para sistema e
macro (`REP` idêntico). Risco de estouro de posição em nomes/documentos longos.

---

## 5. Plano de alteração (priorizado — não implementado nesta rodada)

> Restrições do projeto: manter **FBV**, **MySQL**, **Bootstrap 5**, processamento
> **síncrono** (sem Celery). Cada item abaixo é descrição de ajuste, não código.

**P0 — Bloqueantes (arquivo sai errado no banco)**

1. **Persistir `chave_nfe` (e endereço/CEP do sacado).**
   Arquivo: `operacoes/views.py:131-141`. Ajuste: incluir `chave_nfe`,
   `sacado_endereco`, `sacado_cep` (e, se desejado, `data_emissao`) no dict passado
   a `processar_cessao`. `processar_cessao` já lê esses campos via `.get()`
   (`cessao.py:64-73`) — sem migration. Impacto: CNAB pos 395-438 passa a sair com a
   chave; endereço/CEP do sacado deixam de sair vazios. Risco: baixo. Cobrir com o
   fluxo de teste (§ Verificação). Obs.: `data_emissao` está só em `PartesCessao`
   (nível nota), não em `TituloCessao` — decidir se replica a data da nota em todos
   os títulos (ver §6).

2. **Aplicar (ou confirmar ausência de) o deságio de 0,6% no valor do título.**
   Arquivos candidatos: `operacoes/views.py:468` (montagem de `VL_NOMINAL`) **ou**
   ponto de import (`operacoes/views.py:67-68` / `cessao.py`). Ajuste: se a regra
   atual das macros ainda vale, aplicar `× 0,994` (arredondado 2 casas) ao valor que
   alimenta a posição 127-139 — **mas só após decisão de negócio** (§6), pois muda o
   valor cobrado. Impacto: alto (valor financeiro). Risco: alto — **não fazer sem
   confirmação**.

**P1 — Relevantes (conteúdo/qualidade do arquivo)**

3. **Sanitizar nomes para CNAB.** Portar `RemoverCaracteresEspeciais`/`RemoverPontos`
   (translitera acentos → ASCII, remove especiais) como helper em
   `operacoes/utils/cnab_utils.py` e aplicá-lo a `NM_SACADO`/`NOME_CEDENTE` na
   montagem do `base_data` (`operacoes/views.py:464,470`). Impacto: evita byte
   não-ASCII em campo fixo. Risco: baixo.

4. **Preencher posições 8 e 11-20 do detalhe** conforme as macros atualizadas —
   **depende de identificar o que são BASE col 19 e col 20** (§6). Arquivo:
   `operacoes/utils/cnab_generator.py:62-64`. Impacto: alinhamento posicional.
   Risco: médio (mexe no layout). **Bloqueado por decisão.**

5. **Datas robustas.** Garantir que `dhEmi` com componente de hora (`...T..`) seja
   reduzido a data antes do `DateField`/formatação `ddmmyy`. Arquivo:
   `core/services/cessao_xml.py:256-258` (ou no ponto de conversão). Impacto: evita
   erro de parse/rejeição. Risco: baixo.

6. **Contagem do trailer = detalhes realmente escritos.** Arquivos:
   `operacoes/utils/cnab_service.py:9-12` e `cnab_generator.py:188`. Ajuste: contar
   linhas efetivamente emitidas (header+detalhes+trailer). Impacto: fechamento
   correto. Risco: baixo.

**P2 — Menores / higiene**

7. **Import em lote (múltiplos XML).** Permitir `multiple` no input e iterar
   `request.FILES.getlist('xml_file')` de forma **síncrona** (lotes de 50-200).
   Arquivos: `workflow_cessao.html:46`, `operacoes/views.py:44-96`. Impacto: UX
   alinhada à macro (varre pasta). Risco: médio (mudança de UX/agrupamento — ver §6).

8. **Dedup de NF-e.** Opcional: checar `chave_nfe` antes de inserir (aviso ou bloqueio).
   Requer decisão sobre unicidade (§6) — possivelmente `unique`/índice → **migration
   fica para rodada futura**. Risco: médio.

9. **Corrigir bug `{{*}}`** em `cessao_xml.py:263` para `{*}` (ou remover a branch).
   Risco: baixo (hoje mascarado pelo fallback).

10. **Reconciliar docstrings “400 vs 444”** em `cnab_generator.py`/`cnab_service.py`/
    `CLAUDE.md`. Puramente documental. Risco: nenhum.

Sequência sugerida: **1 → 5 → 3 → 6 → 9 → 10**, depois (após decisões) **2 → 4 → 7 → 8**.

---

## 6. Pontos que exigem decisão/confirmação antes de implementar

1. **Deságio de 0,6% (× 0,994):** a versão **atualizada** da macro ainda aplica esse
   desconto ao valor do título (pos 127-139)? É desconto concedido ao sacado,
   deságio de cessão, ou legado a descontinuar? Muda valor cobrado — não implemento
   sem sua confirmação. Confirmar também o **arredondamento** (a macro faz `Round(...,2)`).
2. **BASE col 19 (pos 8) e col 20 (pos 11-20):** o import não popula essas colunas.
   Qual a origem e o significado na macro atualizada (ex.: valor de abatimento, IOF,
   flag)? Sem isso não sei o que colocar nessas posições.
3. **`VL_PAGO`/`col 9` (pos 193-205):** hoje vem da soma de eventos LIQUIDACAO. Na
   macro a col 9 é preenchida externamente — confirmar se a semântica (valor pago
   acumulado) é a mesma.
4. **Comprimento 444 vs 400:** qual o layout oficial do banco/convênio (largura de
   linha e posições)? É o critério final de aceitação do arquivo.
5. **`data_emissao` por título:** o parser só tem a emissão no nível da nota
   (`PartesCessao`). Replico a mesma `dhEmi` para todos os títulos da NF, ou trato
   caso a caso? Hoje cai em `data_aquisicao` (`cessao.py:68`).
6. **Import em lote:** ao varrer vários XML, cada NF-e vira **uma `OperacaoCessao`
   separada** (como hoje, com `numero_contrato = NF-<nNF>` único) ou **um único lote**
   agregando vários títulos? Isso define o modelo de dados do lote.
7. **Dedup / unicidade de `chave_nfe`:** bloquear reimportação da mesma NF-e? Se sim,
   tornar `chave_nfe` único exige **migration** (rodada futura).
8. **Escopo do fluxo legado (`core/views_cessao.py` → `fundos.Recebiveis`):** entra
   nesta correção ou está descontinuado? Ele não guarda `chave_nfe` e não tem
   `try/except` no parse.
9. **OCORRENCIA/CDO padrão:** hoje vêm do form a cada geração. A macro lê de ranges
   fixos (MENU!OCORRENCIA/CDO). Manter entrada manual por operação?

---

## Verificação (para a rodada de implementação futura)

- **XML → persistência:** subir um XML de NF-e real pelo `workflow_cessao`,
  confirmar a cessão e inspecionar no shell que `Titulo.chave_nfe`, `sacado_endereco`
  e `sacado_cep` ficaram preenchidos (hoje ficam vazios). Base: `test_parser_xml.py`
  (chave esperada `35260502455462000129550010001545861100956966`).
- **CNAB posicional:** gerar o `.txt` via `download_cnab_cessao` e validar por script
  que **toda linha tem 444 chars**, que pos 395-438 traz a chave (não zeros), e que a
  contagem do trailer bate com o nº de detalhes. Comparar linha-a-linha com a saída
  da macro para o mesmo lote.
- **Regressão de valor:** após decisão sobre o deságio, conferir pos 127-139 contra o
  valor esperado (com/sem × 0,994).
