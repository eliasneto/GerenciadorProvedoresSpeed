from django import forms
from .models import Lead

class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            'razao_social', 'cnpj_cpf', 'nome_fantasia', 'site',
            'endereco', 'cidade', 'estado', 
            'contato_nome', 'email', 'telefone', 'status'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # O Loop da Liberdade: Estilo + Opcional
        for field in self.fields.values():
            # 1. Remove a obrigatoriedade (pode deixar tudo em branco)
            field.required = False
            
            # 2. Aplica o seu estilo moderno Tailwind
            field.widget.attrs.update({
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-ageis-yellow focus:ring-1 focus:ring-ageis-yellow outline-none transition'
            })