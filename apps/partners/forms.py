from django import forms
from .models import Partner, Proposal
from clientes.models import Endereco 

class PartnerForm(forms.ModelForm):
    """Formulário para os Dados Mestre do Parceiro"""
    class Meta:
        model = Partner
        fields = [
            'razao_social', 'cnpj_cpf', 'nome_fantasia', 
            'contato_nome', 'email', 'telefone', 'status'
        ]

    def __init__(self, *args, **kwargs):
        lock_relationship_fields = kwargs.pop('lock_relationship_fields', False)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full p-4 bg-gray-100 border border-gray-200 text-gray-900 rounded-2xl outline-none focus:ring-2 focus:ring-ageis-yellow transition-all',
                'placeholder': field.label
            })

class ProposalForm(forms.ModelForm):
    """
    Formulário Técnico da OS Normalizado.
    Versão corrigida para Chained Dropdowns e campos técnicos opcionais.
    """
    class Meta:
        model = Proposal
        fields = [
            # VÍNCULOS RELACIONAIS
            'cliente', 'client_address', 'status', 'nome_proposta',
            
            # DADOS TÉCNICOS
            'velocidade', 'tecnologia', 'disponibilidade', 'mttr', 
            'perda_pacote', 'latencia', 'interfaces', 'ipv4_bloco', 'designador',
            'trunk', 'dhcp', 'prazo_ativacao',

            # --- CONTATO SUPORTE---
            'contato_suporte', 'telefone_suporte',
            
            # COMERCIAL
            'ticket_cliente', 'valor_mensal', 'ticket_empresa', 'taxa_instalacao', 'valor_parceiro', 'tempo_contrato', 'email_faturamento'
        ]

        # CONTATOS SUPORTE LABEL
        labels = {
            'contato_suporte': 'Contato para Suporte (NOC)',
            'telefone_suporte': 'Número do Telefone',
        }

    def __init__(self, *args, **kwargs):
        lock_relationship_fields = kwargs.pop('lock_relationship_fields', False)
        super().__init__(*args, **kwargs)
        
        # 1. SOLUÇÃO DO ERRO DE SALVAMENTO:
        # Como o select de endereços é filtrado via JS, o Django precisa 
        # ter acesso a todos os endereços no backend para validar o ID enviado.
        self.fields['client_address'].queryset = Endereco.objects.all()
        self.fields['client_address'].required = False
        self.fields['nome_proposta'].required = True

        # 2. FLEXIBILIDADE DE CAMPOS (Prazo de Ativação):
        # Conforme seu pedido, deixamos o prazo opcional para esta tela.
        if 'prazo_ativacao' in self.fields:
            self.fields['prazo_ativacao'].required = False

        if lock_relationship_fields:
            self.fields['cliente'].disabled = True
            self.fields['status'].disabled = True
            self.fields['client_address'].disabled = True

        # 3. ESTILIZAÇÃO AGEIS DE ALTO CONTRASTE:
        # Trocamos bg-gray-50 por bg-gray-100 para destacar os campos no fundo branco.
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'w-full p-4 bg-gray-100 border border-gray-200 text-gray-900 font-bold rounded-2xl outline-none focus:ring-2 focus:ring-ageis-yellow transition-all',
            })
            
        # 4. REFINAMENTO DE LABELS
        if 'client_address' in self.fields:
            self.fields['client_address'].label = "Unidade de Instalação"
            self.fields['cliente'].label = "Cliente Final"
