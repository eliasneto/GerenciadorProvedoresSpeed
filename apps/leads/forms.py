from django import forms

from .models import Lead


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            'razao_social', 'cnpj_cpf', 'nome_fantasia', 'site',
            'cep', 'endereco', 'numero', 'bairro', 'cidade', 'estado',
            'contato_nome', 'email', 'telefone',
            'instagram_username', 'instagram_url',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.required = False
            field.widget.attrs.update({
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-ageis-yellow focus:ring-1 focus:ring-ageis-yellow outline-none transition'
            })

            if name == 'cep':
                field.widget.attrs['placeholder'] = '00000-000'
            elif name == 'endereco':
                field.widget.attrs['placeholder'] = 'Rua, avenida, alameda...'
            elif name == 'numero':
                field.widget.attrs['placeholder'] = 'Ex: 1500'
            elif name == 'bairro':
                field.widget.attrs['placeholder'] = 'Nome do bairro'
            elif name == 'cidade':
                field.widget.attrs['placeholder'] = 'Município'
            elif name == 'estado':
                field.widget.attrs['placeholder'] = 'UF'
            elif name == 'instagram_username':
                field.widget.attrs['placeholder'] = 'Ex: provedor_oficial'
            elif name == 'instagram_url':
                field.widget.attrs['placeholder'] = 'https://instagram.com/...'
