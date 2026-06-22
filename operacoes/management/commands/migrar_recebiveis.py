"""
Management command to migrate existing Recebiveis to new Operacoes structure.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from fundos.models import Recebiveis, Fundo
from operacoes.models import OperacaoCessao, Titulo, EventoTitulo, TipoEventoTitulo
from collections import defaultdict
import uuid


class Command(BaseCommand):
    help = 'Migra dados de Recebiveis para o novo modelo de Operações'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem salvar no banco (teste)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('=== MODO DRY-RUN: Nenhuma alteração será salva ==='))
        
        # Buscar todos os recebíveis
        recebiveis = Recebiveis.objects.select_related('fundo').all()
        
        if not recebiveis.exists():
            self.stdout.write(self.style.SUCCESS('Nenhum recebível encontrado para migrar.'))
            return
        
        self.stdout.write(f'Encontrados {recebiveis.count()} recebíveis para migrar.')
        
        # Agrupar por fundo + cedente (simula uma operação de cessão)
        operacoes_map = defaultdict(list)
        
        for recebivel in recebiveis:
            key = (recebivel.fundo.id, recebivel.cedente_cnpj)
            operacoes_map[key].append(recebivel)
        
        self.stdout.write(f'Agrupados em {len(operacoes_map)} operações de cessão.')
        
        operacoes_criadas = 0
        titulos_criados = 0
        eventos_criados = 0
        
        try:
            with transaction.atomic():
                for (fundo_id, cedente_cnpj), recebiveis_grupo in operacoes_map.items():
                    fundo = Fundo.objects.get(id=fundo_id)
                    primeiro_recebivel = recebiveis_grupo[0]
                    
                    # Calcular valores totais
                    valor_total_nominal = sum(r.valor_nominal for r in recebiveis_grupo)
                    valor_total_aquisicao = sum(r.valor_cessao for r in recebiveis_grupo)
                    
                    # Gerar número de contrato único
                    numero_contrato = f"MIGR-{cedente_cnpj}-{uuid.uuid4().hex[:8].upper()}"
                    
                    # Criar OperacaoCessao
                    operacao = OperacaoCessao(
                        fundo=fundo,
                        cedente_cnpj=cedente_cnpj,
                        cedente_nome=primeiro_recebivel.cedente_nome,
                        numero_contrato=numero_contrato,
                        data_contrato=timezone.now().date(),  # Data atual como fallback
                        data_aquisicao=timezone.now().date(),
                        valor_total_nominal=valor_total_nominal,
                        valor_total_aquisicao=valor_total_aquisicao,
                        status='CONFIRMADA',
                        observacoes='Migrado automaticamente do modelo Recebiveis'
                    )
                    
                    if not dry_run:
                        operacao.save()
                    
                    operacoes_criadas += 1
                    self.stdout.write(f'  Operação: {numero_contrato} ({len(recebiveis_grupo)} títulos)')
                    
                    # Criar Titulos e Eventos
                    for recebivel in recebiveis_grupo:
                        # Criar Titulo
                        titulo = Titulo(
                            operacao_cessao=operacao,
                            fundo=fundo,
                            numero_titulo=recebivel.numero_titulo,
                            sacado_nome=recebivel.sacado_nome,
                            sacado_cpf_cnpj=recebivel.sacado_cpf_cnpj,
                            valor_nominal=recebivel.valor_nominal,
                            valor_aquisicao=recebivel.valor_cessao,
                            data_emissao=timezone.now().date(),  # Fallback
                            data_vencimento=recebivel.data_vencimento,
                            saldo_devedor=recebivel.valor_nominal,
                            ativo=recebivel.status not in ['PAGO', 'BAIXADO'],
                            percentual_pdd=recebivel.pdd_percentual,
                            valor_pdd=recebivel.pdd_valor,
                            classificacao_risco=self._calcular_classificacao(recebivel.dias_atraso)
                        )
                        
                        if not dry_run:
                            titulo.save()
                        
                        titulos_criados += 1
                        
                        # Criar EventoTitulo inicial (AQUISICAO)
                        evento = EventoTitulo(
                            titulo=titulo,
                            tipo_evento=TipoEventoTitulo.AQUISICAO,
                            data_evento=operacao.data_aquisicao,
                            valor_evento=recebivel.valor_cessao,
                            descricao=f'Aquisição - Migrado de Recebiveis (tipo: {recebivel.tipo_credito})'
                        )
                        
                        if not dry_run:
                            evento.save()
                        
                        eventos_criados += 1
                        
                        # Se estava PAGO ou BAIXADO, criar evento de BAIXA
                        if recebivel.status in ['PAGO', 'BAIXADO']:
                            evento_baixa = EventoTitulo(
                                titulo=titulo,
                                tipo_evento=TipoEventoTitulo.BAIXA,
                                data_evento=recebivel.data_vencimento,
                                descricao=f'Baixa - Status original: {recebivel.status}'
                            )
                            
                            if not dry_run:
                                evento_baixa.save()
                            
                            eventos_criados += 1
                
                if dry_run:
                    raise Exception("Dry run - rollback intencional")
                    
        except Exception as e:
            if str(e) == "Dry run - rollback intencional":
                self.stdout.write(self.style.WARNING('\n=== DRY-RUN COMPLETO ==='))
            else:
                self.stdout.write(self.style.ERROR(f'\nErro na migração: {e}'))
                raise
        
        self.stdout.write(self.style.SUCCESS('\n=== RESUMO DA MIGRAÇÃO ==='))
        self.stdout.write(f'Operações de Cessão criadas: {operacoes_criadas}')
        self.stdout.write(f'Títulos criados: {titulos_criados}')
        self.stdout.write(f'Eventos criados: {eventos_criados}')
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS('\n✓ Migração concluída com sucesso!'))
            self.stdout.write(self.style.WARNING('\nATENÇÃO: Revisar as operações criadas e ajustar datas se necessário.'))
        else:
            self.stdout.write(self.style.WARNING('\nNada foi salvo. Execute sem --dry-run para aplicar.'))
    
    def _calcular_classificacao(self, dias_atraso):
        """Calcula classificação de risco baseado em dias de atraso (Res. CMN 2682)"""
        if dias_atraso == 0:
            return 'AA'
        elif dias_atraso <= 30:
            return 'A'
        elif dias_atraso <= 60:
            return 'B'
        elif dias_atraso <= 90:
            return 'C'
        elif dias_atraso <= 120:
            return 'D'
        elif dias_atraso <= 150:
            return 'E'
        elif dias_atraso <= 180:
            return 'F'
        elif dias_atraso <= 360:
            return 'G'
        else:
            return 'H'
