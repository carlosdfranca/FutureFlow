import uuid

from django.conf import settings
from django.db import models


class CategoriaDocumento(models.TextChoices):
    LAUDO_PRECIFICACAO = 'LAUDO_PRECIFICACAO', 'Laudo de Precificação'
    LAUDO_AVALIACAO    = 'LAUDO_AVALIACAO',    'Laudo de Avaliação'
    CONTRATO_CESSAO    = 'CONTRATO_CESSAO',    'Contratos de Cessão'
    LASTRO             = 'LASTRO',             'Lastros'
    ATA_COMITE         = 'ATA_COMITE',         'Atas de Comitê'


# Ícone (Bootstrap Icons) e variante de cor (mesma paleta dos .kpi-card) por categoria —
# usados para renderizar os "folder cards" na tela de diretórios do fundo.
CATEGORIA_META = {
    CategoriaDocumento.LAUDO_PRECIFICACAO: {'icon': 'bi-graph-up-arrow', 'variant': 'blue'},
    CategoriaDocumento.LAUDO_AVALIACAO:    {'icon': 'bi-clipboard-data', 'variant': 'green'},
    CategoriaDocumento.CONTRATO_CESSAO:    {'icon': 'bi-file-earmark-text', 'variant': 'amber'},
    CategoriaDocumento.LASTRO:             {'icon': 'bi-link-45deg', 'variant': 'gray'},
    CategoriaDocumento.ATA_COMITE:         {'icon': 'bi-journal-text', 'variant': 'danger'},
}


def upload_documento_path(instance, filename):
    """media/documentos/<empresa_id>/<fundo_id>/<categoria>/<uuid>_<filename>"""
    return f"documentos/{instance.fundo.empresa_id}/{instance.fundo_id}/{instance.categoria}/{instance.id}_{filename}"


class DocumentoFundo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fundo = models.ForeignKey('fundos.Fundo', on_delete=models.CASCADE, related_name='documentos')
    categoria = models.CharField(max_length=30, choices=CategoriaDocumento.choices, db_index=True)

    arquivo = models.FileField(upload_to=upload_documento_path, max_length=500)
    nome = models.CharField(max_length=255)
    descricao = models.CharField(max_length=500, blank=True, default='')
    tamanho = models.PositiveBigIntegerField(default=0, help_text='Tamanho do arquivo em bytes')

    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    data_upload = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'documentos_fundo'
        verbose_name = 'Documento do Fundo'
        verbose_name_plural = 'Documentos do Fundo'
        ordering = ['-data_upload']
        indexes = [
            models.Index(fields=['fundo', 'categoria']),
        ]

    def __str__(self):
        return f"{self.nome} ({self.get_categoria_display()}) — {self.fundo.razao_social}"

    def save(self, *args, **kwargs):
        if self.arquivo and not self.tamanho:
            try:
                self.tamanho = self.arquivo.size
            except (ValueError, OSError):
                pass
        if not self.nome and self.arquivo:
            self.nome = self.arquivo.name.rsplit('/', 1)[-1]
        super().save(*args, **kwargs)
