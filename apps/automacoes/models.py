from django.db import models
import os

class Automacao(models.Model):
    STATUS_CHOICES = [
        ('PARADO', 'Parado'),
        ('RODANDO', 'Rodando'),
        ('ERRO', 'Erro'),
        ('CONCLUIDO', 'Concluído'),
    ]

    nome = models.CharField(max_length=100, verbose_name="Nome da Automação")
    slug = models.SlugField(unique=True, help_text="Nome na URL (ex: robo-excel)")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    
    # Pasta onde os arquivos da automação vivem (ex: scripts/robo1)
    pasta_script = models.CharField(max_length=255, help_text="Nome da pasta dentro de automacoes/scripts/")
    
    # Gerenciamento de Status e Arquivos
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PARADO')
    arquivo_entrada = models.FileField(upload_to='automacoes/entradas/', blank=True, null=True)
    resultado_processamento = models.FileField(upload_to='automacoes/resultados/', blank=True, null=True)
    # automacoes/models.py
    progresso = models.IntegerField(default=0)
    
    ultima_execucao = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Automação"
        verbose_name_plural = "Automações"