# -*- coding: utf-8 -*-
"""Deriva `golden.txt` a partir de `referencia_legado.txt`.

`referencia_legado.txt` é o CNAB gerado pela macro legada
(`GERADOR_OPERAÇÕES_ESTOQUE.xlsm`) para o lote Atrivion 09-09. O golden do teste
NÃO é gerado pelo nosso próprio código — senão o teste seria tautológico. Ele é o
arquivo do legado com exatamente duas edições, ambas decisões conscientes
registradas em PROVENIENCIA.md.

Rode com:  python operacoes/fixtures/cnab_atrivion_20260909/gerar_golden.py
"""

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

AQUI = Path(__file__).resolve().parent

# Posições 0-based (o layout tem 444 colunas 1-based).
VL_NOMINAL = slice(126, 139)   # pos. 127-139
VL_PRESENTE = slice(192, 205)  # pos. 193-205
CEP = slice(326, 334)          # pos. 327-334
SEU_NUMERO = slice(37, 62)     # pos. 38-62

# Edição 1: a planilha saiu com deságio de 2,98% na primeira linha de detalhe e
# 2,88% nas outras 29 (a fórmula da coluna I foi editada à mão só naquela
# célula). O golden usa 2,88% uniforme, que é a taxa que o teste informa.
TAXA_DESAGIO = Decimal("2.88")

# Edição 2: a macro escreve o CEP numa célula sem NumberFormat="@", então o Excel
# come o zero à esquerda (Módulo3.bas:228 — compare com as colunas 5, 6 e 14, que
# são protegidas). Decidimos NÃO replicar esse bug: o sistema manda o CEP correto.
CEPS_CORRIGIDOS = {"9680900 ": "09680900"}


def _substituir(linha, fatia, valor):
    assert len(valor) == fatia.stop - fatia.start, (valor, fatia)
    return linha[: fatia.start] + valor + linha[fatia.stop :]


def main():
    origem = (AQUI / "referencia_legado.txt").read_text(encoding="latin-1")
    saida, mudancas = [], []

    for linha in origem.splitlines():
        if not linha.startswith("1 "):  # header (0) e trailer (9) passam intactos
            saida.append(linha)
            continue

        nota = linha[SEU_NUMERO].strip()

        nominal = Decimal(linha[VL_NOMINAL]) / 100
        presente = (nominal - nominal * TAXA_DESAGIO / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        novo_presente = str(int(presente * 100)).zfill(13)
        if novo_presente != linha[VL_PRESENTE]:
            mudancas.append(
                "nota %s VL_PRESENTE %s -> %s (recomputado a %s%%)"
                % (nota, linha[VL_PRESENTE], novo_presente, TAXA_DESAGIO)
            )
            linha = _substituir(linha, VL_PRESENTE, novo_presente)

        if linha[CEP] in CEPS_CORRIGIDOS:
            novo_cep = CEPS_CORRIGIDOS[linha[CEP]]
            mudancas.append(
                "nota %s CEP %r -> %r (zero perdido pelo Excel)"
                % (nota, linha[CEP], novo_cep)
            )
            linha = _substituir(linha, CEP, novo_cep)

        assert len(linha) == 444, len(linha)
        saida.append(linha)

    (AQUI / "golden.txt").write_text("\n".join(saida) + "\n", encoding="latin-1")

    print("golden.txt escrito com %d linhas e %d edições:" % (len(saida), len(mudancas)))
    for m in mudancas:
        print("  -", m)


if __name__ == "__main__":
    main()
