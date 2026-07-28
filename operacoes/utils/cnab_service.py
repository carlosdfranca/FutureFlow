import io
from .cnab_generator import gerar_linha_header, gerar_linha_detalhe, gerar_linha_trailer


def gerar_cnab_stream(base_data: list, menu_data: dict) -> io.StringIO:
    buffer = io.StringIO()
    buffer.write(gerar_linha_header(menu_data) + "\n")
    detalhes_escritos = 0
    for index, record in enumerate(base_data, start=2):
        if not record.get("SEU_NUMERO", "").strip():
            break
        buffer.write(gerar_linha_detalhe(record, index, menu_data) + "\n")
        detalhes_escritos += 1
    # Contagem reflete header + detalhes realmente escritos + trailer,
    # respeitando o corte por SEU_NUMERO vazio acima.
    total = detalhes_escritos + 2
    buffer.write(gerar_linha_trailer(total) + "\n")
    buffer.seek(0)
    return buffer
