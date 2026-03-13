from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, RegistroHistorico
from django.urls import path

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # 1. Removemos o formulário de alteração de senha do topo da página
    change_password_form = None

    # 2. Reorganiza os campos de edição (Removendo o campo de Password/Estrelinhas)
    fieldsets = (
        (None, {'fields': ('username',)}),
        ('Informações Pessoais', {'fields': ('first_name', 'last_name', 'email')}),
        ('Speed: Permissões Especiais', {'fields': ('is_gestor', 'is_active', 'is_staff', 'is_superuser')}),
        ('Grupos e Acessos', {'fields': ('groups', 'user_permissions')}),
        ('Datas', {'fields': ('last_login', 'date_joined')}),
    )
    
    # 3. Organiza o formulário de CRIAÇÃO (Removendo a obrigatoriedade de senha)
    # Aqui permitimos criar o usuário apenas com username e e-mail
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'is_gestor', 'is_staff', 'is_active'),
        }),
    )

    # Colunas na listagem
    list_display = ('username', 'email', 'is_gestor', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username',)
    readonly_fields = ('last_login', 'date_joined')

    # 4. Bloqueio de Segurança: Remove as URLs de alteração de senha do admin
    def get_urls(self):
        urls = super().get_urls()
        return [u for u in urls if 'password' not in u.pattern.get_regexp().pattern]

# Registro do Histórico
@admin.register(RegistroHistorico)
class RegistroHistoricoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'acao', 'data')
    list_filter = ('acao', 'data')
    search_fields = ('usuario__username', 'descricao')