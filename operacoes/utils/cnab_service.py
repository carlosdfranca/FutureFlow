import io
from .cnab_generator import gerar_linha_header, gerar_linha_detalhe, gerar_linha_trailer


def gerar_cnab_stream(base_data: list, menu_data: dict) -> io.StringIO:
    buffer = io.StringIO()
    buffer.write(gerar_linha_header(menu_data) + "\n")
    for index, record in enumerate(base_data, start=2):
        if not record.get("SEU_NUMERO", "").strip():
            break
        buffer.write(gerar_linha_detalhe(record, index, menu_data) + "\n")
    total = len(base_data) + 2
    buffer.write(gerar_linha_trailer(total) + "\n")
    buffer.seek(0)
    return buffer
