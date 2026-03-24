from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, RegistroHistorico

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # 1. Removemos o formulário de alteração de senha do topo da página
    change_password_form = None

    # 2. Reorganiza os campos de EDIÇÃO (Removendo o campo de Password/Estrelinhas)
    fieldsets = (
        (None, {'fields': ('username',)}),
        ('Informações Pessoais', {'fields': ('first_name', 'last_name', 'email')}),
        ('Speed: Permissões Especiais', {'fields': ('is_gestor', 'is_active', 'is_staff', 'is_superuser')}),
        ('Grupos e Acessos', {'fields': ('groups', 'user_permissions')}),
        ('Datas', {'fields': ('last_login', 'date_joined')}),
    )
    
    # 3. Organiza o formulário de CRIAÇÃO (Puxando apenas o essencial para o AD)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
            ('Configurações Speed', {
                'classes': ('wide',),
                'fields': ('is_gestor',),
            }),
        )

    # Colunas na listagem
    list_display = ('username', 'email', 'is_gestor', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username',)
    readonly_fields = ('last_login', 'date_joined')

    # 4. Bloqueio de Segurança: Remove o acesso à view de senha
    # Esta é a forma correta e segura para Django 4.0+
    # 4. Bloqueio de Segurança: Remove o acesso à view de senha
    def get_urls(self):
        urls = super().get_urls()
        # Filtramos as URLs garantindo que u.name não seja None
        return [u for u in urls if u.name and 'password' not in u.name]

# Registro do Histórico
@admin.register(RegistroHistorico)
class RegistroHistoricoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'acao', 'data')
    list_filter = ('acao', 'data')
    search_fields = ('usuario__username', 'descricao')