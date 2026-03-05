from django.contrib import admin
from .models import Cliente, Endereco

class EnderecoInline(admin.TabularInline):
    model = Endereco
    extra = 1 # Quantidade de linhas em branco para novos endereços

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('razao_social', 'cnpj_cpf', 'cidade_principal')
    inlines = [EnderecoInline]

    def cidade_principal(self, obj):
        # Apenas um exemplo de como acessar os endereços relacionados
        principal = obj.enderecos.filter(principal=True).first()
        return principal.cidade if principal else "Não definido"