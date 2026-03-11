from django import forms
from .models import Cliente, Endereco

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['razao_social', 'nome_fantasia', 'cnpj_cpf']
        labels = {
            'razao_social': 'Razão Social / Nome',
            'nome_fantasia': 'Nome Fantasia',
            'cnpj_cpf': 'CNPJ / CPF',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'w-full p-4 bg-gray-100 border border-gray-200 text-gray-900 font-bold rounded-2xl outline-none focus:ring-2 focus:ring-ageis-yellow transition-all',
                'placeholder': self.fields[field].label
            })

class EnderecoForm(forms.ModelForm):
    class Meta:
        model = Endereco
        # ADICIONADOS: contato_suporte e telefone_suporte
        fields = [
            'tipo', 'status', 'cep', 'logradouro', 'numero', 
            'bairro', 'cidade', 'estado', 'principal'
        ]
        labels = {
            'tipo': 'Tipo da Unidade (Ex: Matriz, Filial)',
            'status': 'Status da Unidade',
            'cep': 'CEP',
            'logradouro': 'Logradouro/Endereço',
            'numero': 'Número',
            'bairro': 'Bairro',
            'cidade': 'Cidade',
            'estado': 'Estado (UF)',
            'principal': 'Definir como Endereço Principal',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            # Estilização Ageis Premium para inputs e selects
            if field != 'principal':
                self.fields[field].widget.attrs.update({
                    'class': 'w-full p-4 bg-gray-100 border border-gray-200 text-gray-900 font-bold rounded-2xl outline-none focus:ring-2 focus:ring-ageis-yellow transition-all',
                    'placeholder': self.fields[field].label
                })
            # Estilização para o Checkbox
            else:
                self.fields[field].widget.attrs.update({
                    'class': 'w-5 h-5 rounded border-gray-300 text-ageis-yellow focus:ring-ageis-yellow cursor-pointer'
                })