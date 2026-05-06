from django import forms

from .models import Lead, LeadEmpresa


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

    def clean(self):
        cleaned_data = super().clean()
        razao_social = (cleaned_data.get('razao_social') or '').strip()
        cnpj_cpf = (cleaned_data.get('cnpj_cpf') or '').strip()
        endereco = (cleaned_data.get('endereco') or '').strip()
        numero = (cleaned_data.get('numero') or '').strip()
        bairro = (cleaned_data.get('bairro') or '').strip()
        cidade = (cleaned_data.get('cidade') or '').strip()
        estado = (cleaned_data.get('estado') or '').strip()
        cep = (cleaned_data.get('cep') or '').strip()

        filtros_endereco = {
            'endereco__iexact': endereco,
            'numero__iexact': numero,
            'bairro__iexact': bairro,
            'cidade__iexact': cidade,
            'estado__iexact': estado,
            'cep__iexact': cep,
        }
        filtros_endereco_estruturado = {
            'enderecos__endereco__iexact': endereco,
            'enderecos__numero__iexact': numero,
            'enderecos__bairro__iexact': bairro,
            'enderecos__cidade__iexact': cidade,
            'enderecos__estado__iexact': estado,
            'enderecos__cep__iexact': cep,
        }

        duplicado_estruturado = LeadEmpresa.objects.none()
        if endereco or numero or bairro or cidade or estado or cep:
            if cnpj_cpf:
                duplicado_estruturado = LeadEmpresa.objects.filter(
                    cnpj_cpf__iexact=cnpj_cpf,
                    **filtros_endereco_estruturado,
                ).distinct()
            elif razao_social:
                duplicado_estruturado = LeadEmpresa.objects.filter(
                    razao_social__iexact=razao_social,
                    **filtros_endereco_estruturado,
                ).distinct()

        duplicado_legado = Lead.objects.none()
        if cnpj_cpf:
            duplicado_legado = Lead.objects.filter(cnpj_cpf__iexact=cnpj_cpf, **filtros_endereco)
        elif razao_social:
            duplicado_legado = Lead.objects.filter(razao_social__iexact=razao_social, **filtros_endereco)

        if self.instance.pk:
            duplicado_legado = duplicado_legado.exclude(pk=self.instance.pk)

        if duplicado_estruturado.exists() or duplicado_legado.exists():
            raise forms.ValidationError(
                "Ja existe um cliente com o mesmo documento/nome e o mesmo endereco cadastrado."
            )

        return cleaned_data
