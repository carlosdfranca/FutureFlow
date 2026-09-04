# Correção: agrupamento de XML por cedente + mapeamento VL_NOMINAL/VL_PRESENTE no CNAB

> Implementado em 2026-08-31. Investigação disparada por um relato do usuário: importar 59 XML
> criou 59 `OperacaoCessao` (uma por XML) em vez de 1 operação com 59 títulos. Reverte a
> decisão #6 (import em lote sem agrupar) e a decisão #10 (unificar VL_PAGO/VALOR_PAGO_TITULO)
> de `docs/plano_implementacao_cobranca.md`, e corrige a posição do CNAB descrita em
> `docs/plano_valor_presente_cessao.md`.

## Evidência

Analisada a planilha real `GERADOR_OPERAÇÕES_ESTOQUE.xlsm` (cópia com os 59 XMLs do usuário
na raiz do projeto; cópia mais antiga em `docs/legado_vba/`), abas MENU e BASE:

- Aba **MENU**: `H2:L61` lista as 59 duplicatas importadas (uma linha por XML), mas
  `E2:F7` ("Dados da Cessão": Valor Total Recebíveis, Preço de Aquisição) são **campos
  únicos**, agregando o lote inteiro.
- Aba **BASE**: as 59 linhas do lote têm **todas o mesmo CNPJ Cedente**
  (`02455462000129`), variando só o sacado (3 distintos).
- A macro `Sub arquivo()` (`docs/legado_vba/Módulo1.bas:2-94`) gera **um único arquivo CNAB**
  por execução: 1 header + 1 linha de detalhe por linha da BASE + 1 trailer.
- A aba BASE tem **duas colunas monetárias distintas** por título:

  | Coluna BASE | Cabeçalho | Fórmula/valor real (linha 2) |
  |---|---|---|
  | F (col 6) | `VL_NOMINAL - VIRGULA NA CASA DECIMAL` | `109531,60` (valor cheio, sem desconto) |
  | I (col 9) | `VL_PRESENTE - VIRGULA NA CASA DECIMAL` | `=ROUND((F2-(F2*0.0288)),2)` → `106377.09` |

  A fórmula da coluna I é literalmente `ARRED(nominal - nominal*taxa; 2)` — a mesma fórmula
  usada em `docs/plano_valor_presente_cessao.md` — com taxa 2,88% nesse lote real.
- Coluna R (18, "VALOR PAGO TÍTULO") estava **vazia** em todas as 59 linhas (títulos recém
  importados, ainda não liquidados) — comprovando que ela é conceitualmente diferente da
  coluna I (VL_PRESENTE, sempre preenchida com um valor calculado).

## Conclusão: dois bugs, não um

**Bug 1 — cardinalidade.** `1 lote de N XMLs do mesmo cedente = 1 OperacaoCessao com N
Titulo`, não N operações. O sistema fazia 1 bloco (= 1 futura OperacaoCessao) por arquivo
XML, sempre — decisão #6 de `docs/plano_implementacao_cobranca.md`, tomada sem uma amostra
real de uso em lote.

**Bug 2 — mapeamento CNAB.** `VL_NOMINAL` (pos. 127-139) e `VL_PRESENTE` (pos. 193-205) são
campos **separados** no CNAB. A rodada anterior (`docs/plano_valor_presente_cessao.md`) fez
`titulo.valor_aquisicao` (valor presente) sobrescrever `VL_NOMINAL` — errado, deveria
continuar sendo `titulo.valor_nominal`. E o campo que hoje é `VALOR_PAGO_TITULO`
recebia (por engano, decisão #10 de `docs/plano_implementacao_cobranca.md`) o mesmo valor de
uma OUTRA posição do CNAB (a que hoje chamamos `VL_PRESENTE`) — essa unificação partia de uma
amostra diferente e não vale para este lote real, onde os dois valores são claramente
distintos.

## O que mudou

### 1. Agrupamento por cedente — `operacoes/views.py`, ação `parse_xml`

Os títulos parseados de cada XML são agrupados por `parsed.partes.cedente_doc` (CNPJ do
cedente extraído do XML) antes de criar os blocos de revisão. XMLs do mesmo cedente no mesmo
upload viram 1 bloco (1 futura `OperacaoCessao`) com todos os títulos daquele cedente;
cedentes diferentes geram blocos separados (o modelo `OperacaoCessao` só guarda um
`cedente_cnpj/nome/endereco`, nunca por título — não dá pra misturar).

`numero_contrato` sugerido: quando o grupo resultante tem 1 único título (caso comum de 1
XML = 1 operação), mantém a sugestão `NF-{nNF}`; com vários títulos agrupados, fica em branco
(sem uma única nota fiscal para nomear o contrato) — usuário digita o número real antes de
confirmar.

### 2. CNAB — `operacoes/views.py` (`download_cnab_cessao`) e `operacoes/utils/cnab_generator.py`

```python
"VL_NOMINAL":  str(titulo.valor_nominal).replace('.', ',')     # pos. 127-139, valor cheio
"VL_PRESENTE": str(titulo.valor_aquisicao).replace('.', ',')   # pos. 193-205, valor descontado
"VALOR_PAGO_TITULO": valor_pago_str                             # pos. 83-92, soma de liquidações
```

A chave do dict que antes se chamava `VL_PAGO` (lida em `cnab_generator.py` na posição da
coluna BASE 9) foi renomeada para `VL_PRESENTE`, já que nunca representou valor pago.

## Verificação

Cobertura em `operacoes/tests.py`:
- `test_parse_xml_em_lote_mesmo_cedente_agrupa_em_um_bloco` — N XMLs do mesmo cedente viram 1
  bloco com N títulos (usa `INITIAL_FORMS` do formset para diferenciar títulos reais do form
  extra em branco que o formset sempre adiciona).
- `test_parse_xml_em_lote_cedentes_diferentes_gera_blocos_separados` — cedentes diferentes no
  mesmo upload não se misturam.
- `test_cnab_traz_vl_nominal_e_vl_presente_em_posicoes_separadas` — com taxa 0,6%, `VL_NOMINAL`
  (pos. 127-139) e `VL_PRESENTE` (pos. 193-205) saem com valores diferentes e corretos;
  `VALOR_PAGO_TITULO` (pos. 83-92) continua zerado para título não liquidado.
