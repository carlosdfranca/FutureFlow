# Plano de Implementação — Cobrança (XML NF-e + CNAB 400)

> Este documento consolida as decisões tomadas em conversa com o usuário sobre
> `docs/plano_comparacao_cobranca.md` e define a sequência de implementação.
> Nada foi codificado ainda — este é o plano para a próxima rodada de trabalho.

## 1. Decisões tomadas

| # | Tema | Decisão |
|---|---|---|
| 1 | Deságio de 0,6% (`× 0,994`) no valor do título | **Não aplicar.** Manter `valor_nominal` cheio no CNAB. Confirmado no `Módulo3.bas:23` (`CalcularDesconto = Round(valor * 0.994, 2)`) que a macro aplica esse desconto, mas o usuário decidiu **não replicar** essa regra. |
| 2 | Persistir `chave_nfe`, `sacado_endereco`, `sacado_cep` | **Sim, corrigir** — bug claro na view, sem regra de negócio em disputa. |
| 3 | Comprimento da linha CNAB (444 vs 400) | **444 está correto.** Documentação que diz "400" deve ser corrigida. |
| 4 | Colunas BASE 19/20 (`TIPO DE JUROS`/`TAXA DE JUROS`) | Identificadas na planilha real (`GERADOR_OPERAÇÕES_ESTOQUE.xlsm`, aba BASE, cabeçalhos S1/T1). Confirmado em **315/315 linhas de produção** que nunca são preenchidas. **Replicar exatamente o comportamento da macro**, inclusive no caso vazio (ver §3.3 — a macro gera zeros na posição 11-20, não espaços). |
| 5 | Data de emissão por título | **Usar `dhEmi` da NF-e** (nível da nota) para todos os títulos daquela NF-e, corrigindo o fallback atual para `data_aquisicao`. |
| 6 | Import em lote | **Sim, implementar.** Múltiplos XML por upload; cada NF-e continua virando **uma `OperacaoCessao` separada** (não agrupar em um lote único). |
| 7 | Duplicidade de `chave_nfe` | **Apenas avisar, não bloquear.** Checagem contra **todo o banco de dados** (todos os fundos/operações). Sem `unique`, sem migration. |
| 8 | Fluxo legado (`core/views_cessao.py` → `fundos.Recebiveis`) | **Fora de escopo.** Não mexer. |
| 9 | `CDO`/`OCORRENCIA` do CNAB | Tirar do formulário manual. **Campos no modelo `Fundo`** (requer migration). `DTL` (data de liquidação) continua vindo do formulário a cada geração, pois muda por remessa. |
| 10 | `VL_PAGO` vs `VALOR_PAGO_TITULO` | Na planilha real, as colunas 9 e 18 **sempre têm o mesmo valor** (confirmado pelo usuário com quem enviou o arquivo). **Unificar**: calcular o valor liquidado uma vez e usar para os dois campos do CNAB, em vez de somar eventos para um (`VL_PAGO`) e usar `valor_aquisicao` estático para o outro (`VALOR_PAGO_TITULO`). |
| 11 | Ajustes de baixo risco aprovados | Sanitizar nomes (acentos/especiais), corrigir contagem do trailer, corrigir bug `{{*}}` no parser, atualizar documentação 400→444. |

## 2. Achado adicional da investigação da planilha

Ao abrir `docs/legado_vba/GERADOR_OPERAÇÕES_ESTOQUE.xlsm` (abas MENU, Plan5, BASE)
para identificar as colunas 19/20, confirmei em `Módulo1.bas:40-41` que mesmo com
essas colunas vazias, a macro gera na posição 11-20 (campo monetário "taxa de
juros") a sequência `"0000000000"` (10 zeros), não espaços — porque o formato é o
mesmo dos demais campos monetários (zero-fill), independente de haver valor. O
sistema atual gera **espaços** nas posições 2-20 inteiras. Esse é um ajuste
posicional real, não apenas uma lacuna de dado — ver item 3.3.

## 3. Sequência de implementação

### P0 — Bloqueantes / correção de dados essenciais

**3.1 — Persistir `chave_nfe`, `sacado_endereco`, `sacado_cep`, `data_emissao`**
- Arquivo: `operacoes/views.py:131-141` (`titulos_dados` na ação `confirmar`).
- Ajuste: incluir `chave_nfe`, `sacado_endereco`, `sacado_cep` no dict (já vêm
  preenchidos em `titulos_iniciais`, só faltam ser repassados). `processar_cessao`
  já lê esses campos via `.get()` (`operacoes/services/cessao.py:64,65,73`) —
  **sem migration**.
- Para `data_emissao` (decisão #5): garantir que o valor de `dhEmi` extraído a
  nível de nota (`core/services/cessao_xml.py`, no bloco de `PartesCessao`/nota)
  seja propagado para cada título individual (`TituloCessao`) antes de chegar à
  view, e que a conversão trate o formato ISO com componente de hora/timezone
  (`YYYY-MM-DDTHH:MM:SS-03:00`) extraindo somente a data — hoje isso não é feito
  de forma robusta. Local provável do ajuste: `core/services/cessao_xml.py`
  (montagem de cada `TituloCessao`) e/ou `operacoes/views.py` (linhas 59-71 e
  131-141).
- Risco: baixo. Impacto: CNAB pos 395-438 passa a sair com a chave; posições
  275-314 e 327-334 deixam de sair vazias; `data_emissao` reflete a NF-e real.

**3.2 — Unificar `VL_PAGO` e `VALOR_PAGO_TITULO`**
- Arquivo: `operacoes/views.py:435-493` (`download_cnab_cessao`).
- Hoje: `VL_PAGO` = soma de eventos `LIQUIDACAO_*` (`views.py:~455-460`);
  `VALOR_PAGO_TITULO` = `titulo.valor_aquisicao` (`views.py:480`) — **duas fontes
  diferentes**.
- Ajuste: calcular `valor_liquidado` uma única vez (soma de eventos, `0` se
  título não liquidado) e usar esse mesmo valor para **ambos** os campos
  (`VL_PAGO` e `VALOR_PAGO_TITULO`) no `base_data`.
- Risco: baixo/médio — muda o conteúdo de um campo do arquivo bancário
  (`VALOR_PAGO_TITULO`, campo X, ~pos 74-83) que hoje sai com o valor de
  aquisição e passará a sair com o valor liquidado (0 se ainda não liquidado).
  Testar com título liquidado e não liquidado.

### P1 — Relevantes (conteúdo/qualidade do arquivo)

**3.3 — Zero-fill nas posições 11-20 (em vez de espaços)**
- Arquivo: `operacoes/utils/cnab_generator.py:64` (`gerar_linha_detalhe`, variável `x`).
- Hoje: `rep(" ", 19)` para as posições 2-20 inteiras.
- Ajuste: como o sistema não tem dado de tipo/taxa de juros (colunas nunca
  usadas, decisão #4), substituir por: `rep(" ", 9) + pad_left_zeros(format_valor(""), 10)`
  — reproduz exatamente a saída da macro no caso vazio (posições 2-8 e 9-10
  como espaço, posição 11-20 como `"0000000000"`).
- Risco: baixo — puramente posicional, sem novo dado de entrada necessário.

**3.4 — Sanitizar nomes para CNAB**
- Portar `RemoverCaracteresEspeciais` (translitera acentos, filtra caracteres)
  e `RemoverPontos` (remove pontos) do `Módulo3.bas:60-113,383-391` como
  helpers em `operacoes/utils/cnab_utils.py`.
- Aplicar a `NM_SACADO` e `NOME_CEDENTE` na montagem do `base_data`
  (`operacoes/views.py`, pontos onde esses campos são lidos, ~464-470).
- Risco: baixo.

**3.5 — Data de emissão robusta** — coberto em 3.1 (é pré-requisito da decisão #5).

**3.6 — Corrigir contagem do trailer**
- Arquivos: `operacoes/utils/cnab_service.py` (`gerar_cnab_stream`) e
  `operacoes/utils/cnab_generator.py:188` (`gerar_cnab`, código morto — ajustar
  por consistência, embora não esteja no caminho ativo).
- Ajuste: contar linhas de detalhe **efetivamente escritas** (respeitando o
  corte por `SEU_NUMERO` vazio) em vez de `len(base_data)+2` fixo.
- Risco: baixo.

**3.7 — Import em lote (múltiplos XML)**
- Arquivos: `operacoes/templates/operacoes/workflow_cessao.html:46` (input
  `xml_file` → adicionar atributo `multiple`); `operacoes/views.py:27-96`
  (`workflow_cessao`, ação `parse_xml`).
- Ajuste: iterar `request.FILES.getlist('xml_file')`, processando cada arquivo
  **sincronamente** (lotes de 50-200 esperados, sem Celery); cada XML gera sua
  própria prévia de títulos e, na confirmação, sua própria `OperacaoCessao`
  (decisão #6 — não agrupar). Precisa de tela/fluxo que suporte múltiplas
  prévias antes da confirmação (mudança de UX, não só de backend) — detalhar
  layout do template `workflow_cessao.html` durante a implementação.
- Risco: médio (maior mudança de fluxo/UX desta rodada).

**3.8 — Aviso de NF-e duplicada**
- Arquivo: `operacoes/views.py` (ação `parse_xml` ou `confirmar`).
- Ajuste: antes de confirmar, checar `Titulo.objects.filter(chave_nfe=chave).exists()`
  em todo o banco (decisão #7); se existir, exibir aviso (`messages.warning` ou
  alerta na tela de confirmação) mas permitir prosseguir. Sem alteração de
  modelo/migration.
- Risco: baixo.

**3.9 — `CDO`/`OCORRENCIA` como campo do `Fundo`**
- Arquivo: `fundos/models.py` — adicionar `codigo_originador_cnab` (CDO) e
  `ocorrencia_cnab_padrao` (default `'01'`) ao model `Fundo`. **Requer migration.**
- Arquivos: `operacoes/forms.py:262-277` (`CnabParametrosForm` — remover campos
  `cdo`/`ocorrencia`, manter só `dtl`); `operacoes/views.py:424-493`
  (`cnab_parametros`, `download_cnab_cessao` — ler `operacao.fundo.codigo_originador_cnab`
  e `.ocorrencia_cnab_padrao` em vez do form).
- Risco: médio (migration + mudança de formulário; cadastrar CDO nos fundos
  existentes antes de ativar).

### P2 — Menores / higiene

**3.10 — Corrigir bug `{{*}}` no parser**
- Arquivo: `core/services/cessao_xml.py:263`.
- Ajuste: `root.find(".//{{*}}infProt")` é sintaxe inválida do
  `xml.etree.ElementTree` (mascarada pelo fallback funcional `infProt/@Id`).
  Corrigir a sintaxe (`.//{*}infProt` para wildcard de namespace) ou remover a
  branch redundante, já que o fallback por `@Id` já cobre o caso sem namespace.
- Risco: baixo.

**3.11 — Reconciliar documentação 400→444**
- Arquivos: docstrings em `operacoes/utils/cnab_generator.py` (linhas 20, 56),
  `CLAUDE.md` e qualquer outra menção a "400 caracteres" no projeto.
- Puramente documental. Risco: nenhum.

## 4. Itens explicitamente fora de escopo desta rodada

- Deságio de 0,6% — decisão #1: não implementar.
- Bloqueio de duplicata de `chave_nfe` (`unique=True`) — decisão #7: só aviso, sem migration de unicidade.
- Fluxo legado `core/views_cessao.py`/`fundos.Recebiveis` — decisão #8: não mexer.
- Agrupamento de múltiplos XML em uma única `OperacaoCessao` — decisão #6: mantém 1 NF-e = 1 operação.

## 5. Ordem sugerida de execução

1. 3.1 (persistir chave_nfe/endereço/CEP/data_emissao) — base para tudo mais.
2. 3.2 (unificar VL_PAGO/VALOR_PAGO_TITULO).
3. 3.3 (zero-fill posições 11-20).
4. 3.4 (sanitizar nomes).
5. 3.6 (contagem do trailer).
6. 3.10 (bug `{{*}}`).
7. 3.11 (docs 400→444).
8. 3.9 (CDO/OCORRENCIA no Fundo — migration).
9. 3.8 (aviso de duplicata).
10. 3.7 (import em lote — maior mudança de UX, por último).

Itens 1-7 são de baixo risco e não tocam schema. Itens 8-10 envolvem migration
(8) ou mudança de fluxo/UX (10) e merecem revisão própria antes de seguir.

## 6. Verificação

- Subir um XML de NF-e real, confirmar a cessão, checar no shell que
  `Titulo.chave_nfe`, `sacado_endereco`, `sacado_cep` e `data_emissao` (= `dhEmi`
  da nota) ficaram preenchidos corretamente.
- Gerar o CNAB e validar por script: toda linha com 444 chars; posição 395-438
  com a chave real; posição 11-20 com `0000000000` (não espaços); `VL_PAGO` e
  `VALOR_PAGO_TITULO` (X e Y) com o mesmo valor liquidado.
- Testar upload de múltiplos XML de uma vez; confirmar que cada um gera sua
  própria `OperacaoCessao` e que uma chave_nfe repetida dispara aviso (sem
  bloquear).
- Cadastrar CDO em pelo menos um `Fundo` de teste e gerar CNAB confirmando que
  o valor vem do modelo, não mais do formulário.
