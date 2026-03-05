from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # Removidos 'is_tecnico' e 'is_financeiro' que causavam o erro E108
    list_display = ('email', 'is_staff', 'is_active') 
    search_fields = ('email',)