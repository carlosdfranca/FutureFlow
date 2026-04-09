# fundos/tasks.py

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from datetime import date, timedelta
from decimal import Decimal
import logging

from .models import Fundo, MovimentacaoCota, Recebiveis
from .services.movimentacoes import efetivar_movimentacao

logger = logging.getLogger(__name__)


# DEPRECATED: cálculo diário substituído por importação do Informe Mensal XML (CVM)
# @shared_task(bind=True, max_retries=3)
# def calcular_cotas_diarias(self):
def calcular_cotas_diarias():
    """
    DEPRECATED — cálculo diário substituído por importação do Informe Mensal XML.
    Mantido apenas para referência. Não registrar no Celery Beat.
    """
    try:
        fundos = Fundo.objects.filter(ativo=True)
        hoje = date.today()
        
        sucesso = 0
        erros = []
        
        logger.info(f"[COTAS] Iniciando cálculo de {fundos.count()} fundos para {hoje}")
        
        for fundo in fundos:
            try:
                resultado = calcular_cota_fechamento(str(fundo.id), hoje)
                
                logger.info(
                    f"[COTAS] ✅ {fundo.razao_social}: "
                    f"R$ {resultado['valor_cota']:.6f} | "
                    f"PL: R$ {resultado['patrimonio_liquido']:,.2f}"
                )
                sucesso += 1
                
            except Exception as e:
                erro_msg = f"Erro em {fundo.razao_social}: {str(e)}"
                logger.error(f"[COTAS] ❌ {erro_msg}")
                erros.append(erro_msg)
        
        # Enviar email de resumo
        if erros:
            enviar_email_alerta_task.delay(
                assunto=f"⚠️ Cálculo de Cotas - {sucesso} OK / {len(erros)} Erros",
                mensagem=f"Sucesso: {sucesso}\n\nErros:\n" + "\n".join(erros)
            )
        
        logger.info(f"[COTAS] Finalizado: {sucesso} sucesso, {len(erros)} erros")
        
        return {
            'data': hoje.isoformat(),
            'total_fundos': fundos.count(),
            'sucesso': sucesso,
            'erros': len(erros)
        }
        
    except Exception as e:
        logger.error(f"[COTAS] Erro crítico: {e}")
        raise self.retry(exc=e, countdown=300)  # Retry em 5 minutos


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


# DEPRECATED: envio ANBIMA diário substituído pelo fluxo de Informe Mensal XML
# @shared_task
# def enviar_cotas_anbima_diarias():
def enviar_cotas_anbima_diarias():
    """
    DEPRECATED — envio diário substituído por importação do Informe Mensal XML.
    Mantido apenas para referência. Não registrar no Celery Beat.
    """
    try:
        data_ontem = date.today() - timedelta(days=1)
        
        cotas_pendentes = CotaHistorico.objects.filter(
            data_referencia=data_ontem,
            enviado_anbima=False
        )
        
        logger.info(f"[ANBIMA] Enviando {cotas_pendentes.count()} cotas")
        
        for cota in cotas_pendentes:
            try:
                # TODO: Implementar integração real com ANBIMA
                # Por enquanto apenas marca como enviado
                
                logger.info(
                    f"[ANBIMA] ✅ Fundo {cota.fundo.razao_social}: "
                    f"R$ {cota.valor_cota:.6f}"
                )
                
                cota.enviado_anbima = True
                cota.data_envio_anbima = date.today()
                cota.save()
                
            except Exception as e:
                logger.error(f"[ANBIMA] ❌ Erro: {e}")
        
        logger.info(f"[ANBIMA] Finalizado")
        
        return {
            'data': data_ontem.isoformat(),
            'enviadas': cotas_pendentes.count()
        }
        
    except Exception as e:
        logger.error(f"[ANBIMA] Erro crítico: {e}")
        raise


@shared_task
def verificar_inadimplencia():
    """
    Task que verifica inadimplência dos FIDCs
    Executa a cada 1 hora via Celery Beat
    """
    try:
        fundos_fidc = Fundo.objects.filter(tipo_fundo='FIDC', ativo=True)
        
        alertas = []
        
        for fundo in fundos_fidc:
            # Buscar recebíveis vencidos
            recebiveis_vencidos = Recebiveis.objects.filter(
                fundo=fundo,
                status='VENCIDO',
                dias_atraso__gt=0
            )
            
            if not recebiveis_vencidos.exists():
                continue
            
            # Calcular taxa de inadimplência
            total_recebiveis = Recebiveis.objects.filter(
                fundo=fundo,
                status__in=['A_VENCER', 'VENCIDO']
            ).aggregate(
                total=models.Sum('valor_nominal')
            )['total'] or Decimal('0')
            
            total_vencido = recebiveis_vencidos.aggregate(
                total=models.Sum('valor_nominal')
            )['total'] or Decimal('0')
            
            if total_recebiveis > 0:
                taxa_inadimplencia = (total_vencido / total_recebiveis) * 100
                
                # Alerta se acima de 5%
                if taxa_inadimplencia > 5.0:
                    alerta = (
                        f"⚠️ ALERTA: {fundo.razao_social}\n"
                        f"Inadimplência: {taxa_inadimplencia:.2f}%\n"
                        f"Valor vencido: R$ {total_vencido:,.2f}\n"
                        f"Total carteira: R$ {total_recebiveis:,.2f}"
                    )
                    
                    alertas.append(alerta)
                    logger.warning(f"[INADIMPLÊNCIA] {alerta}")
        
        # Enviar email se houver alertas
        if alertas:
            enviar_email_alerta_task.delay(
                assunto=f"⚠️ Alerta de Inadimplência - {len(alertas)} fundo(s)",
                mensagem="\n\n".join(alertas)
            )
        
        return {
            'verificados': fundos_fidc.count(),
            'alertas': len(alertas)
        }
        
    except Exception as e:
        logger.error(f"[INADIMPLÊNCIA] Erro: {e}")
        raise


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


# Task de teste
@shared_task
def tarefa_teste():
    """Task simples para testar se Celery está funcionando"""
    logger.info("✅ Celery está funcionando!")
    return "Sucesso!"