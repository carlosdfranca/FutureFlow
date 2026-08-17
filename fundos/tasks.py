# fundos/tasks.py

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from datetime import date, timedelta
import logging

from .models import MovimentacaoCota
from .services.movimentacoes import efetivar_movimentacao

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def efetivar_movimentacoes_pendentes(self):
    """
    Task que efetiva aplicações e resgates pendentes
    Executa às 8h via Celery Beat
    """
    try:
        ontem = date.today() - timedelta(days=1)
        
        # Buscar aplicações pendentes
        aplicacoes = MovimentacaoCota.objects.filter(
            tipo_movimentacao='APLICACAO',
            status='AGUARDANDO_PAGAMENTO',
            data_cotizacao=ontem
        )
        
        # Buscar resgates pendentes
        resgates = MovimentacaoCota.objects.filter(
            tipo_movimentacao='RESGATE',
            status='SOLICITADO',
            data_cotizacao=ontem
        )
        
        total = aplicacoes.count() + resgates.count()
        
        logger.info(
            f"[EFETIVAÇÃO] Iniciando: {aplicacoes.count()} aplicações + "
            f"{resgates.count()} resgates = {total} movimentações"
        )
        
        sucesso = 0
        erros = []
        
        # Efetivar aplicações
        for app in aplicacoes:
            try:
                efetivar_movimentacao(str(app.id))
                logger.info(f"[EFETIVAÇÃO] ✅ Aplicação {app.id}: {app.quantidade_cotas} cotas")
                sucesso += 1
            except Exception as e:
                erro_msg = f"Aplicação {app.id}: {str(e)}"
                logger.error(f"[EFETIVAÇÃO] ❌ {erro_msg}")
                erros.append(erro_msg)
        
        # Efetivar resgates
        for resgate in resgates:
            try:
                efetivar_movimentacao(str(resgate.id))
                logger.info(
                    f"[EFETIVAÇÃO] ✅ Resgate {resgate.id}: "
                    f"R$ {resgate.valor_liquido:,.2f}"
                )
                sucesso += 1
            except Exception as e:
                erro_msg = f"Resgate {resgate.id}: {str(e)}"
                logger.error(f"[EFETIVAÇÃO] ❌ {erro_msg}")
                erros.append(erro_msg)
        
        # Enviar email de resumo
        if erros:
            enviar_email_alerta_task.delay(
                assunto=f"⚠️ Efetivação - {sucesso} OK / {len(erros)} Erros",
                mensagem=f"Sucesso: {sucesso}\n\nErros:\n" + "\n".join(erros)
            )
        
        logger.info(f"[EFETIVAÇÃO] Finalizado: {sucesso}/{total} efetivadas")
        
        return {
            'data': ontem.isoformat(),
            'total': total,
            'sucesso': sucesso,
            'erros': len(erros)
        }
        
    except Exception as e:
        logger.error(f"[EFETIVAÇÃO] Erro crítico: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task
def enviar_email_alerta_task(assunto, mensagem):
    """
    Task que envia emails de alerta
    Chamada por outras tasks quando há erros/alertas
    """
    try:
        # Lista de emails para receber alertas
        emails_destino = [
            settings.ADMINS[0][1] if settings.ADMINS else 'admin@exemplo.com'
        ]
        
        send_mail(
            subject=assunto,
            message=mensagem,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=emails_destino,
            fail_silently=False,
        )
        
        logger.info(f"[EMAIL] ✅ Enviado: {assunto}")

    except Exception as e:
        logger.error(f"[EMAIL] ❌ Erro ao enviar: {e}")