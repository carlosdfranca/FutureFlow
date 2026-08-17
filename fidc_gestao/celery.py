import os
from celery import Celery
from celery.schedules import crontab

# Define o settings padrão do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fidc_gestao.settings')

# Cria instância do Celery
app = Celery('fidc_gestao')

# Carrega configurações do Django (settings.py)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descobre tasks automaticamente em todos os apps
app.autodiscover_tasks()

# Configuração do Celery Beat (agendador)
app.conf.beat_schedule = {
    # Efetivar movimentações todos os dias às 8h
    'efetivar-movimentacoes-8h': {
        'task': 'fundos.tasks.efetivar_movimentacoes_pendentes',
        'schedule': crontab(hour=8, minute=0),
    },
}

# Timezone
app.conf.timezone = 'America/Sao_Paulo'


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Task de teste para verificar se Celery está funcionando"""
    print(f'Request: {self.request!r}')