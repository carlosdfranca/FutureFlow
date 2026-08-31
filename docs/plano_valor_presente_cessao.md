# Valor Presente na Cessão — taxa de desconto informada antes do import do XML

> Implementado em 2026-08-31. Reverte a decisão #1 de `docs/plano_implementacao_cobranca.md`
> (que dizia para não replicar o deságio de 0,6% da macro legada), substituindo-a por uma
> taxa parametrizável por operação em vez de fixa em código.
>
> **Correção em 2026-08-31 (mesmo dia)**: a seção "CNAB" abaixo, como escrita originalmente,
> dizia que o valor presente saía na posição do `VL_NOMINAL` (127-139), sobrescrevendo o
> nominal. Isso estava **errado** — analisando a planilha real `GERADOR_OPERAÇÕES_ESTOQUE.xlsm`
> (ver `docs/plano_agrupamento_cessao_e_cnab.md`), ficou confirmado que `VL_NOMINAL` e
> `VL_PRESENTE` são **dois campos separados** no CNAB (posições 127-139 e 193-205). O texto
> abaixo foi atualizado para refletir a posição correta.

## Contexto

Antes desta mudança, o valor presente do título não existia — nem como campo, nem como
cálculo. O parser do XML lia apenas `cobr/dup/vDup` e a view gravava o mesmo número em
`valor_nominal` e `valor_aquisicao`. Ou seja, `Titulo.valor_aquisicao` ("valor pago pelo
fundo") sempre saía igual ao nominal, sem deságio.

A macro legada fazia esse cálculo com taxa fixa: `CalcularDesconto = Round(valor * 0.994, 2)`
(`docs/legado_vba/Módulo3.bas:23`), gravando o resultado na BASE col 6 → posição 127-139 do
CNAB. Essa regra volta agora, mas com a **taxa informada pelo usuário** por operação, em vez
de um valor fixo de 0,6%.

Fórmula (idêntica ao Excel do usuário):
`VL_PRESENTE = ARRED((VL_NOMINAL - (VL_NOMINAL * TAXA_DESCONTO)); 2)`

## Decisões

| # | Tema | Decisão |
|---|---|---|
| 1 | CNAB | `VL_PRESENTE` ganha posição própria (pos. 193-205), separada de `VL_NOMINAL` (pos. 127-139, que continua com o nominal cheio) — ver correção acima e `docs/plano_agrupamento_cessao_e_cnab.md` |
| 2 | Armazenamento | Reusa `Titulo.valor_aquisicao` como valor presente — sem campo novo em `Titulo` |
| 3 | Escopo da taxa | Única por operação (`OperacaoCessao.taxa_desconto`), travada — valor presente é somente-leitura na tela de revisão |
| 4 | Fórmula | Flat, sem pró-rata por prazo — literalmente a fórmula do Excel acima |
| 5 | Formato da taxa | Percentual (`0.60` = 0,6%), `DecimalField(max_digits=7, decimal_places=4)` |
| 6 | Arredondamento | `ROUND_HALF_UP` (via `Decimal.quantize`), reproduzindo o `ARRED()` do Excel — não o `round()` nativo do Python, que é bankers' rounding |

## Implementação

- **Modelo**: `OperacaoCessao.taxa_desconto` (`operacoes/models.py`), migration
  `operacoes/migrations/0005_add_taxa_desconto_cessao.py`, `default=0` (operações antigas
  mantêm valor presente = nominal, sem mudança de comportamento retroativa).
- **Cálculo**: `calcular_valor_presente(valor_nominal, taxa_desconto_pct)` em
  `operacoes/services/cessao.py` — função única, é a fonte de verdade.
- **Persistência**: `processar_cessao` sempre **recalcula** o valor presente no servidor a
  partir de `valor_nominal` e da `taxa_desconto` da operação — nunca confia no
  `valor_aquisicao` que vier do POST (o campo é somente-leitura na tela, mas a validação real
  é no backend).
- **Fluxo de import**: a taxa de desconto é obrigatória **antes** de importar o XML
  (`operacoes/views.py`, ação `parse_xml`) — sem ela, o import é bloqueado com mensagem de
  erro. A prévia de cada título já nasce com o valor presente calculado.
- **Formulário**: `CessaoOperacaoForm.taxa_desconto` (obrigatório);
  `TituloForm.valor_aquisicao` virou `required=False` + `readonly` (rótulo "Valor Presente").
- **CNAB**: `download_cnab_cessao` usa `titulo.valor_nominal` na chave `VL_NOMINAL` (posição
  127-139, valor cheio) e `titulo.valor_aquisicao` (valor presente) numa chave `VL_PRESENTE`
  separada (posição 193-205) — ver `docs/plano_agrupamento_cessao_e_cnab.md` para a
  investigação que corrigiu esse mapeamento.
- **UI**: campo de taxa na Etapa 1 (import) e na Etapa 2 (dados da operação) de
  `workflow_cessao.html`; recálculo em JS como conveniência visual (o servidor é quem manda).
- **Exibição**: `detalhe_cessao.html`/`detalhe_titulo.html` trocaram os rótulos
  "Valor de/Aquisição" por "Valor Presente"; o "Deságio %" mostrado agora vem direto de
  `operacao.taxa_desconto`, não mais derivado de `1 - aquisicao/nominal`.

## Verificação

Cobertura em `operacoes/tests.py`:
- `CalcularValorPresenteTest` — testes unitários da fórmula, incluindo o caso de
  meio-centavo que prova o `ROUND_HALF_UP`.
- `WorkflowCessaoXmlTest.test_parse_xml_sem_taxa_desconto_e_bloqueado` — import sem taxa é
  bloqueado.
- `WorkflowCessaoXmlTest.test_confirmar_calcula_valor_presente_com_taxa_da_operacao` —
  end-to-end com taxa 0,6%, provando que o servidor recalcula mesmo que o POST tente forçar
  outro valor.
- Testes antigos (`test_confirmar_persiste_...`, `test_fluxo_completo_com_xml_real_...`)
  ajustados para taxa `0` — comportamento idêntico ao anterior à mudança (valor presente =
  nominal), garantindo regressão nula para dados/CNAB de operações que não usam a taxa.
