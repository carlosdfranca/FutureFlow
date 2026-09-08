# Fixture: lote Atrivion 09-09 (30 títulos)

Evidência do comportamento da macro legada, usada pelo teste golden do CNAB de cessão.

## Arquivos

| Arquivo | O que é |
|---|---|
| `xml/*.xml` (30) | NF-e originais do lote, cedente PROTURBO (`02455462000129`). Cópia de `docs/legado_vba/Notas Antecipada Atrivion 09-09/Notas Antecipada Atrivion 08-09/`. Só os XMLs — os 30 PDFs de DANFE (5,4 MB) ficaram fora. |
| `antecipacao_atrivion_09-09.xls` | Planilha da operação, autoria Ariane Veloso da Silva (metadado OLE), salva em 08/09/2026 16:45. Traz os **vencimentos negociados** e os valores já líquidos de IOF. |
| `referencia_legado.txt` | CNAB gerado pela macro legada (`GERADOR_OPERAÇÕES_ESTOQUE.xlsm`) para este lote, com DTL 09/09/2026. **Não editar.** |
| `golden.txt` | O esperado pelo teste. Derivado de `referencia_legado.txt` por `gerar_golden.py`. |
| `gerar_golden.py` | Reproduz o `golden.txt`. Rode se precisar reconferir. |

## A cascata do legado

```
vDup (cobr/dup/vDup)                      ex. 14.979,22
  ↓ ARRED(× (1 − 0,6%) ; 2)   IOF         ← Módulo3.bas:23, Round(valor * 0.994, 2)
"Valor da Duplicata"                      ex. 14.889,34  → CNAB pos. 127-139
  ↓ ARRED(× (1 − 2,88%) ; 2)  deságio     ← fórmula da BASE col 9
"Valor de Aquisição"                      ex. 14.445,64  → CNAB pos. 193-205
```

Confirmado nos 30 títulos, 444 colunas. Totais: 1.139.249,52 (bruto) →
**1.132.413,99** (`VL_NOMINAL`) → **1.098.668,05** (`VL_PRESENTE`, a 2,88%).

Três evidências independentes de que o `VL_NOMINAL` do legado é o valor **já líquido de
IOF**, e não o valor cheio da nota:

1. `MENU!J2` se chama literalmente **"Valor Duplicata"** e guarda os valores líquidos;
   `MENU!F4` ("Valor Total Recebíveis") soma essa coluna e dá 1.132.413,99.
2. A aba `DESPESA FINANCEIRA` tem `Valor Aquisição = Valor Recebíveis × (1 − 2,98%)`,
   exato até a 10ª casa na linha 15 (a única não arredondada).
3. `Módulo3.bas:194` lê o `ICMSTot/vNF` numa variável (`strValorNominal_XML`) que **nunca
   é usada**. A fonte do valor é `cobr/dup/vDup` (`Módulo3.bas:193`).

## As duas edições sobre o arquivo do legado

O golden é 100% legado **exceto** nestes dois pontos, que são divergências decididas:

**1. `VL_PRESENTE` da nota 158477 (1ª linha de detalhe)** — `0000001444564` →
`0000001446053`. A planilha saiu com deságio de **2,98%** só nessa linha e **2,88%** nas
outras 29: a fórmula da coluna I foi editada à mão numa célula. O golden usa 2,88%
uniforme, que é a taxa que o teste informa. `VL_NOMINAL` não muda.

**2. CEP em 21 linhas** — `'9680900 '` → `'09680900'`. `Módulo3.bas:228` escreve o CEP sem
`NumberFormat = "@"` (compare com as colunas 5, 6 e 14, que a macro protege), então o Excel
converte para número e come o zero à esquerda. **Decidimos não replicar esse bug** — o
sistema manda o CEP correto do XML. As 9 linhas da VALEO (`13012100`) não são afetadas
porque o CEP não começa com zero.

> A mesma classe de bug atinge **qualquer** coluna sem `"@"`: CPF de sacado começando com
> zero (col 7) e `nFat` com zero à esquerda (cols 3/4) também divergiriam. Não ocorre neste
> lote — todos os sacados são CNPJ e os `nFat` têm 6 dígitos.

## Pré-condições do teste

- **Vencimentos vêm do `dVenc` do XML**, sem override do operador. Na operação real os 9
  títulos da VALEO foram renegociados (a planilha da Ariane traz 25/10 e 10/11 no lugar de
  20/10–25/10); o teste isola o cálculo e não exercita esse caminho.
- **Nenhum evento além de `AQUISICAO`** — `download_cnab_cessao` filtra `ativo=True` e soma
  liquidações no `VALOR_PAGO_TITULO` (pos. 83-92), que aqui é zero.
- **Um único bloco** na tela de import: os 30 XMLs compartilham o cedente, então o
  agrupamento por CNPJ tem que produzir 1 `OperacaoCessao` com 30 `Titulo`.
- **Ordem por `numero_titulo`**: a ordem do legado é a alfabética de nome de arquivo
  (= chave NF-e), que aqui coincide com o `nFat` crescente porque todos têm 6 dígitos.

## Parâmetros usados na geração do arquivo legado

| | |
|---|---|
| DTL (data de liquidação) | 09/09/2026 |
| CDO (código originador) | `15555601` |
| Ocorrência | `01` |
| Coobrigação | `02` (sem coobrigação — `Módulo3.bas:232` crava `2`) |
| Identificação do cedente | `02` (pessoa jurídica) |
| Tipo de título | `01` |
