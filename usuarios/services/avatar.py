"""Normalização da foto de perfil.

O upload bruto (que pode ter vários MB) nunca é gravado: a imagem é recortada
no centro, reduzida e re-codificada em WEBP antes de chegar ao storage. Sobra
um único arquivo de algumas dezenas de KB por usuário.
"""

from io import BytesIO
from uuid import uuid4

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps

TAMANHO_PADRAO = 512
QUALIDADE_PADRAO = 82


def normalizar_avatar(arquivo, tamanho=TAMANHO_PADRAO, qualidade=QUALIDADE_PADRAO):
    """Devolve o upload convertido em um WEBP quadrado de ``tamanho`` px.

    Sai sempre quadrado, então o ``border-radius: 50%`` do CSS nunca distorce.
    """
    imagem = Image.open(arquivo)

    # Fotos de celular vêm com a orientação só no EXIF — sem isso entram deitadas.
    imagem = ImageOps.exif_transpose(imagem)

    # Recorte central + resize num passo só.
    imagem = ImageOps.fit(imagem, (tamanho, tamanho), Image.LANCZOS, centering=(0.5, 0.5))

    # WEBP aceita alpha, mas achatamos sobre branco para o avatar não ficar
    # com "buracos" sobre o card em um dos temas.
    if imagem.mode in ("RGBA", "LA", "P"):
        imagem = imagem.convert("RGBA")
        fundo = Image.new("RGB", imagem.size, (255, 255, 255))
        fundo.paste(imagem, mask=imagem.split()[-1])
        imagem = fundo
    elif imagem.mode != "RGB":
        imagem = imagem.convert("RGB")

    buffer = BytesIO()
    imagem.save(buffer, format="WEBP", quality=qualidade, method=6)
    tamanho_bytes = buffer.tell()
    buffer.seek(0)

    return InMemoryUploadedFile(
        buffer,
        "profile_image",
        f"{uuid4().hex}.webp",
        "image/webp",
        tamanho_bytes,
        None,
    )
