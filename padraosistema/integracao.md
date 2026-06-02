# Como Integrar em um Novo Sistema

> Checklist e código base para iniciar um novo sistema já com o padrão visual Speed/Ageis.

---

## Checklist de Integração

- [ ] Adicionar CDNs no `<head>` (Tailwind, Lucide, Plus Jakarta Sans)
- [ ] Configurar cores customizadas do Tailwind (`ageis-black`, `ageis-yellow`)
- [ ] Definir `font-family: 'Plus Jakarta Sans'` no `body`
- [ ] Criar o CSS de componentes globais (sidebar ativa, scrollbar, animações)
- [ ] Montar a estrutura HTML base (sidebar + header + main + footer)
- [ ] Adicionar o JavaScript de comportamento da sidebar
- [ ] Criar a tela de login seguindo o padrão de dois painéis

---

## `<head>` Padrão (copie para todo novo sistema)

```html
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nome do Sistema — Speed OS</title>

  <!-- Tailwind CSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            'ageis-black': '#0F0F0F',
            'ageis-yellow': '#FFC107',
          }
        }
      }
    }
  </script>

  <!-- Plus Jakarta Sans -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">

  <!-- Lucide Icons -->
  <script src="https://unpkg.com/lucide@latest"></script>

  <style>
    /* Fonte base */
    body { font-family: 'Plus Jakarta Sans', sans-serif; }

    /* Item ativo no menu da sidebar */
    .sidebar-link-active {
      background-color: rgba(255, 193, 7, 0.1);
      color: #FFC107 !important;
      border-left: 4px solid #FFC107;
      border-radius: 0 12px 12px 0 !important;
    }

    /* Scrollbar da sidebar */
    #sidebar::-webkit-scrollbar { width: 4px; }
    #sidebar::-webkit-scrollbar-track { background: transparent; }
    #sidebar::-webkit-scrollbar-thumb { background: #2d2d2d; border-radius: 10px; }

    /* Botão de toggle da sidebar no desktop */
    #desktopToggleBtn {
      position: fixed;
      top: 50%;
      left: 256px;
      transform: translate(-50%, -50%);
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background-color: white;
      border: 1px solid #e5e7eb;
      z-index: 55;
      transition: all 0.3s ease;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    /* Estados da sidebar colapsada */
    body.sidebar-collapsed #sidebar { transform: translateX(-100%) !important; }
    body.sidebar-collapsed #main-wrapper { margin-left: 0 !important; }
    body.sidebar-collapsed #desktopToggleBtn {
      left: 0 !important;
      width: 24px !important;
      height: 48px !important;
      border-radius: 0 12px 12px 0 !important;
    }

    /* Animação shake para campos inválidos */
    @keyframes shake {
      0%, 100% { transform: translateX(0); }
      25% { transform: translateX(-5px); }
      75% { transform: translateX(5px); }
    }
    .animate-shake { animation: shake 0.4s ease-in-out; }
  </style>
</head>
```

---

## HTML Base Completo (template de página interna)

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <!-- cole o <head> padrão acima -->
</head>
<body class="bg-[#F8F9FA]">

  <!-- ========== SIDEBAR ========== -->
  <aside id="sidebar" class="fixed top-0 left-0 h-full w-64 bg-ageis-black border-r border-white/5 shadow-2xl z-50 flex flex-col transition-transform duration-300 overflow-y-auto">

    <!-- Logo / Identidade -->
    <div class="p-6 border-b border-white/5 flex items-center gap-3">
      <img src="/static/img/logo1.png" alt="Logo" class="h-7">
      <div>
        <p class="text-white font-black text-sm">Speed OS</p>
        <p class="text-white/40 text-[10px] uppercase tracking-widest">Nome do Sistema</p>
      </div>
    </div>

    <!-- Navegação -->
    <nav class="flex-1 p-4 space-y-1">
      <a href="/dashboard" class="sidebar-link flex items-center gap-3 px-4 py-3 rounded-xl text-white/70 hover:text-white hover:bg-white/5 transition-all text-sm font-medium">
        <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
        <span>Dashboard</span>
      </a>
      <a href="/outro-modulo" class="sidebar-link flex items-center gap-3 px-4 py-3 rounded-xl text-white/70 hover:text-white hover:bg-white/5 transition-all text-sm font-medium">
        <i data-lucide="database" class="w-4 h-4"></i>
        <span>Outro Módulo</span>
      </a>
    </nav>

    <!-- Rodapé da sidebar -->
    <div class="p-4 border-t border-white/5">
      <p class="text-white/20 text-[10px] text-center font-medium">v1.0.0</p>
    </div>

  </aside>

  <!-- Botão toggle sidebar (desktop) -->
  <button id="desktopToggleBtn" class="hidden md:flex" onclick="toggleSidebar()">
    <i data-lucide="chevron-left" class="w-3 h-3 text-gray-500" id="toggleIcon"></i>
  </button>

  <!-- Overlay mobile -->
  <div id="sidebar-overlay" class="hidden fixed inset-0 bg-black/50 z-40 md:hidden" onclick="fecharSidebarMobile()"></div>

  <!-- ========== CONTEÚDO PRINCIPAL ========== -->
  <div id="main-wrapper" class="md:ml-64 min-h-screen flex flex-col transition-all duration-300">

    <!-- Header -->
    <header class="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-gray-200">
      <div class="px-6 py-4 flex items-center justify-between">

        <!-- Hambúrguer mobile -->
        <button class="md:hidden p-2 rounded-xl hover:bg-gray-100" onclick="abrirSidebarMobile()">
          <i data-lucide="menu" class="w-5 h-5 text-gray-600"></i>
        </button>

        <!-- Título -->
        <div>
          <h1 class="text-lg font-black text-gray-900 italic tracking-tight">Nome da Tela</h1>
        </div>

        <!-- Ações -->
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-full bg-ageis-yellow flex items-center justify-center font-black text-black text-sm">
            U
          </div>
        </div>

      </div>
    </header>

    <!-- Main -->
    <main class="flex-1 p-6 md:p-10">
      <div class="max-w-7xl mx-auto space-y-6">

        <!-- Conteúdo da página aqui -->

      </div>
    </main>

    <!-- Footer -->
    <footer class="border-t border-gray-200 bg-white/50 p-6">
      <p class="text-xs text-gray-400 text-center">Speed Systems © 2026</p>
    </footer>

  </div>

  <!-- ========== SCRIPTS ========== -->
  <script>
    // Inicializar ícones Lucide
    lucide.createIcons();

    // Marcar link ativo da sidebar
    const currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-link').forEach(link => {
      if (link.getAttribute('href') === currentPath) {
        link.classList.add('sidebar-link-active');
      }
    });

    // Toggle sidebar desktop
    function toggleSidebar() {
      const collapsed = document.body.classList.toggle('sidebar-collapsed');
      const icon = document.getElementById('toggleIcon');
      icon.setAttribute('data-lucide', collapsed ? 'chevron-right' : 'chevron-left');
      lucide.createIcons();
      localStorage.setItem('sidebarCollapsed', collapsed);
    }

    // Sidebar mobile
    function abrirSidebarMobile() {
      document.getElementById('sidebar').style.transform = 'translateX(0)';
      document.getElementById('sidebar-overlay').classList.remove('hidden');
    }
    function fecharSidebarMobile() {
      document.getElementById('sidebar').style.transform = '';
      document.getElementById('sidebar-overlay').classList.add('hidden');
    }

    // Restaurar estado do toggle (desktop)
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
      document.body.classList.add('sidebar-collapsed');
    }
  </script>

</body>
</html>
```

---

## Template de Tela de Login

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <!-- cole o <head> padrão acima (sem os estilos de sidebar) -->
  <style>
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
    @keyframes shake {
      0%, 100% { transform: translateX(0); }
      25% { transform: translateX(-5px); }
      75% { transform: translateX(5px); }
    }
    .animate-shake { animation: shake 0.4s ease-in-out; }
  </style>
</head>
<body class="min-h-screen bg-ageis-black flex">

  <!-- Lado esquerdo — branding (apenas desktop) -->
  <div class="hidden lg:flex w-1/2 bg-ageis-black flex-col items-center justify-center p-16">
    <div class="text-center">
      <img src="/static/img/logo1.png" alt="Logo" class="h-16 mx-auto mb-8">
      <h1 class="text-5xl font-black text-white italic tracking-tighter leading-none">
        Speed<br><span class="text-ageis-yellow">OS</span>
      </h1>
      <p class="text-white/40 text-sm mt-4 font-medium uppercase tracking-widest">
        Nome do Sistema
      </p>
    </div>
  </div>

  <!-- Lado direito — formulário -->
  <div class="w-full lg:w-1/2 bg-[#F8F9FA] flex items-center justify-center p-8">
    <div class="w-full max-w-md">

      <!-- Logo mobile -->
      <div class="flex justify-center mb-10 lg:hidden">
        <img src="/static/img/logo1.png" alt="Logo" class="h-10">
      </div>

      <!-- Card do formulário -->
      <div class="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100">
        <h2 class="text-2xl font-black text-gray-900 italic tracking-tight mb-1">Entrar</h2>
        <p class="text-sm text-gray-500 mb-8">Acesse com suas credenciais</p>

        <!-- Mensagem de erro (exibir se houver erro) -->
        <!--
        <div class="flex items-center gap-3 bg-red-50 border border-red-100 rounded-2xl p-4 mb-4 animate-shake">
          <i data-lucide="alert-circle" class="w-5 h-5 text-red-600 flex-shrink-0"></i>
          <p class="text-sm font-medium text-red-700">Usuário ou senha incorretos.</p>
        </div>
        -->

        <form method="post" class="space-y-4">
          <!-- campo CSRF para Django: {% csrf_token %} -->

          <div class="space-y-1">
            <label class="text-[10px] font-black uppercase text-gray-400 tracking-widest">Usuário</label>
            <input type="text" name="username" placeholder="seu.usuario" autocomplete="username"
              class="w-full p-4 bg-gray-50 border border-gray-100 rounded-2xl outline-none focus:ring-2 focus:ring-ageis-yellow transition-all font-medium text-gray-800">
          </div>

          <div class="space-y-1">
            <label class="text-[10px] font-black uppercase text-gray-400 tracking-widest">Senha</label>
            <input type="password" name="password" placeholder="••••••••" autocomplete="current-password"
              class="w-full p-4 bg-gray-50 border border-gray-100 rounded-2xl outline-none focus:ring-2 focus:ring-ageis-yellow transition-all font-medium text-gray-800">
          </div>

          <button type="submit"
            class="w-full bg-ageis-yellow text-black font-black py-4 rounded-2xl uppercase italic tracking-tight hover:opacity-90 transition-opacity mt-2">
            Entrar
          </button>
        </form>
      </div>

    </div>
  </div>

  <script>lucide.createIcons();</script>
</body>
</html>
```

---

## Dependências Externas (CDN)

| Recurso | URL |
|---|---|
| Tailwind CSS | `https://cdn.tailwindcss.com` |
| Lucide Icons | `https://unpkg.com/lucide@latest` |
| Plus Jakarta Sans | `https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:...` |
| IMask (máscaras) | `https://unpkg.com/imask` *(opcional)* |

> **Importante:** Em produção, considere hospedar o Tailwind localmente (com a CLI) para não depender de CDN externo e evitar o aviso de uso em produção.

---

## Adaptação para Django (Templates)

### Configuração de static files

```html
{% load static %}
<img src="{% static 'img/logo1.png' %}" alt="Logo">
```

### Login com `{% if form.errors %}`

```html
{% if form.errors %}
<div class="flex items-center gap-3 bg-red-50 border border-red-100 rounded-2xl p-4 mb-4 animate-shake">
  <i data-lucide="alert-circle" class="w-5 h-5 text-red-600 flex-shrink-0"></i>
  <p class="text-sm font-medium text-red-700">Usuário ou senha incorretos.</p>
</div>
{% endif %}
```

### Herança de templates

```html
<!-- base.html -->
{% block content %}{% endblock %}
{% block extra_scripts %}{% endblock %}

<!-- pagina_filha.html -->
{% extends 'core/base.html' %}
{% block content %}
  <!-- conteúdo da página -->
{% endblock %}
```
