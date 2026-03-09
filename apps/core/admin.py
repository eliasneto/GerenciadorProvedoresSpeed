from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, RegistroHistorico

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Organiza os campos no formulário de edição
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Speed: Permissões Especiais', {'fields': ('is_gestor',)}),
    )
    
    # Organiza os campos no formulário de criação (Onde a mágica acontece)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Speed: Informações Adicionais', {
            'classes': ('wide',),
            'fields': ('email', 'is_gestor'),
        }),
    )

    # Colunas que aparecem na listagem
    list_display = ('username', 'email', 'is_gestor', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username',)

# Registro do Histórico continua igual
admin.site.register(RegistroHistorico)