# Estrutura de Layout

> O layout padrão é composto por: Sidebar fixa + Header sticky + Área de conteúdo responsiva.

---

## Visão Geral da Estrutura

```
┌─────────────────────────────────────────────┐
│  SIDEBAR (256px, fixa, fundo preto)          │
│  ┌───────────────────────────────────────┐  │
│  │  Logo                                  │  │
│  │  ─────────────────────────────────    │  │
│  │  [ícone] Menu Item 1                   │  │
│  │  [ícone] Menu Item 2  ← ativo          │  │
│  │  [ícone] Menu Item 3                   │  │
│  │  ─────────────────────────────────    │  │
│  │  [ícone] Usuário / Sair                │  │
│  │  v1.6.0                                │  │
│  └───────────────────────────────────────┘  │
│                                              │
│  CONTEÚDO PRINCIPAL (margem-esquerda: 256px) │
│  ┌───────────────────────────────────────┐  │
│  │  HEADER (sticky, fundo branco)         │  │
│  │  Nome da tela  |  Usuário + Ações      │  │
│  ├───────────────────────────────────────┤  │
│  │                                        │  │
│  │  MAIN CONTENT (fundo #F8F9FA)          │  │
│  │  max-w-7xl, padding: p-6 md:p-10      │  │
│  │                                        │  │
│  ├───────────────────────────────────────┤  │
│  │  FOOTER                                │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## Sidebar (Menu Lateral)

### Especificações

| Propriedade | Valor |
|---|---|
| Largura | `256px` (`w-64`) |
| Posição | `fixed top-0 left-0` |
| Z-index | `z-50` |
| Fundo | `#0F0F0F` (`bg-ageis-black`) |
| Cor do texto | `white` |
| Borda direita | `border-r border-white/5` |
| Sombra | `shadow-2xl` |
| Comportamento | Colapsável em desktop, oculta em mobile |

### HTML da Sidebar

```html
<aside id="sidebar" class="fixed top-0 left-0 h-full w-64 bg-ageis-black border-r border-white/5 shadow-2xl z-50 flex flex-col transition-transform duration-300 overflow-y-auto">

  <!-- Cabeçalho com logo -->
  <div class="p-6 border-b border-white/5 flex items-center gap-3">
    <img src="{% static 'img/logo1.png' %}" alt="Logo" class="h-7">
    <div>
      <p class="text-white font-black text-sm">Speed OS</p>
      <p class="text-white/40 text-[10px] uppercase tracking-widest">Engine Ageis</p>
    </div>
  </div>

  <!-- Navegação -->
  <nav class="flex-1 p-4 space-y-1">
    <a href="/dashboard" class="sidebar-link flex items-center gap-3 px-4 py-3 rounded-xl text-white/70 hover:text-white hover:bg-white/5 transition-all text-sm font-medium">
      <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
      <span>Dashboard</span>
    </a>
    <!-- repita o padrão acima para cada item de menu -->
  </nav>

  <!-- Rodapé da sidebar -->
  <div class="p-4 border-t border-white/5">
    <p class="text-white/20 text-[10px] text-center font-medium">v1.6.0</p>
  </div>

</aside>
```

### CSS do item de menu ativo

```css
.sidebar-link-active {
  background-color: rgba(255, 193, 7, 0.1);
  color: #FFC107 !important;
  border-left: 4px solid #FFC107;
  border-radius: 0 12px 12px 0 !important;
}
```

### Scrollbar customizada da sidebar

```css
#sidebar::-webkit-scrollbar { width: 4px; }
#sidebar::-webkit-scrollbar-track { background: transparent; }
#sidebar::-webkit-scrollbar-thumb { background: #2d2d2d; border-radius: 10px; }
```

### Comportamento de colapso (desktop)

```css
/* Botão de toggle fixo na borda da sidebar */
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
}

/* Estado colapsado */
body.sidebar-collapsed #sidebar {
  transform: translateX(-100%) !important;
}
body.sidebar-collapsed #main-wrapper {
  margin-left: 0 !important;
}
body.sidebar-collapsed #desktopToggleBtn {
  left: 0 !important;
  width: 24px !important;
  height: 48px !important;
  border-radius: 0 12px 12px 0 !important;
}
```

---

## Header (Topo)

### Especificações

| Propriedade | Valor |
|---|---|
| Posição | `sticky top-0` |
| Z-index | `z-30` |
| Fundo | `bg-white/80 backdrop-blur-md` |
| Borda inferior | `border-b border-gray-200` |
| Padding | `px-6 py-4` |
| Altura | Auto (conteúdo define) |

### HTML do Header

```html
<header class="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-gray-200">
  <div class="px-6 py-4 flex items-center justify-between">

    <!-- Título da tela -->
    <div>
      <h1 class="text-lg font-black text-gray-900 italic tracking-tight">Nome da Tela</h1>
      <p class="text-xs text-gray-500">Subtítulo ou breadcrumb</p>
    </div>

    <!-- Ações do header -->
    <div class="flex items-center gap-3">
      <!-- Botão de ação principal -->
      <button class="bg-ageis-yellow text-black font-black py-2 px-4 rounded-xl text-sm uppercase italic hover:opacity-90 transition-opacity">
        + Nova Ação
      </button>

      <!-- Avatar do usuário -->
      <div class="w-9 h-9 rounded-full bg-ageis-yellow flex items-center justify-center font-black text-black text-sm">
        {{ user.first_name|first|upper }}
      </div>
    </div>

  </div>
</header>
```

---

## Wrapper do Conteúdo Principal

```html
<!-- Wrapper que ocupa o espaço após a sidebar -->
<div id="main-wrapper" class="md:ml-64 min-h-screen flex flex-col bg-[#F8F9FA] transition-all duration-300">

  <!-- Header -->
  <header>...</header>

  <!-- Conteúdo -->
  <main class="flex-1 p-6 md:p-10">
    <div class="max-w-7xl mx-auto space-y-6">
      <!-- conteúdo da página -->
    </div>
  </main>

  <!-- Footer -->
  <footer class="border-t border-gray-200 bg-white/50 p-6">
    <p class="text-xs text-gray-400 text-center">Speed Systems © 2026</p>
  </footer>

</div>
```

---

## Tela de Login

### Como o cenário funciona (Django / base.html)

A tela de login **não tem sidebar, header nem footer**. Esses elementos são exibidos condicionalmente no `base.html` apenas quando o usuário está autenticado. Quando não autenticado, o `<main>` vira a tela inteira:

```html
<!-- Trecho do base.html — o <main> quando o usuário NÃO está logado -->
<main class="flex-grow flex items-center justify-center bg-ageis-black p-4">
  <div>
    {% block content %}{% endblock %}
  </div>
</main>
```

O `flex items-center justify-center` + `bg-ageis-black` são os responsáveis pelo **fundo preto e centralização perfeita** do card.

---

### Diagrama do layout de login

```
┌──────────────────────────────────────────────────────────┐
│  <main> — bg-ageis-black, flex, items-center, justify-center, p-4  │
│                                                          │
│   ┌──────────────────────────────────────────────────┐  │
│   │  Card  max-w-[950px]  rounded-[3rem]             │  │
│   │  flex-col (mobile) / flex-row (md+)              │  │
│   │  shadow-[0_20px_50px_rgba(0,0,0,0.3)]            │  │
│   │                                                  │  │
│   │  ┌─────────────────┐  ┌─────────────────────┐   │  │
│   │  │  PAINEL ESQUERDO│  │  PAINEL DIREITO      │   │  │
│   │  │  w-1/2          │  │  w-1/2               │   │  │
│   │  │  bg-ageis-black │  │  bg-white            │   │  │
│   │  │  p-12           │  │  p-12                │   │  │
│   │  │                 │  │                      │   │  │
│   │  │  [logos]        │  │  "Login"  text-3xl   │   │  │
│   │  │  "Gestão de"    │  │  [usuário input]     │   │  │
│   │  │  PARCEIROS      │  │  [senha input]       │   │  │
│   │  │  text-5xl       │  │  [botão amarelo]     │   │  │
│   │  │                 │  │                      │   │  │
│   │  │  • Online       │  │  Speed Engine v3.0   │   │  │
│   │  └─────────────────┘  └─────────────────────┘   │  │
│   └──────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

### Especificações detalhadas

#### Container externo (centering)

| Propriedade | Valor |
|---|---|
| Fundo da tela | `bg-ageis-black` (#0F0F0F) |
| Display | `flex items-center justify-center` |
| Padding | `p-4` |

#### Card principal

| Propriedade | Valor |
|---|---|
| Largura máxima | `max-w-[950px]` |
| Alinhamento | `mx-auto` |
| Direção | `flex-col` (mobile) / `flex-row` (md+) |
| Fundo | `bg-white` |
| Borda arredondada | `rounded-[3rem]` (48px) |
| Sombra | `shadow-[0_20px_50px_rgba(0,0,0,0.3)]` |
| Borda | `border border-white/10` |
| Animação de entrada | `animate-in fade-in zoom-in duration-700` |

#### Painel esquerdo (branding)

| Propriedade | Valor |
|---|---|
| Largura | `w-full md:w-1/2` |
| Fundo | `bg-ageis-black` |
| Padding | `p-12` |
| Layout interno | `flex flex-col justify-between` |
| Decoração | `absolute -top-24 -left-24 w-64 h-64 bg-ageis-yellow/10 blur-[100px] rounded-full` |

| Elemento | Classes |
|---|---|
| Barra de logos | `inline-flex items-center gap-4 bg-white/5 backdrop-blur-md p-4 rounded-3xl border border-white/10 mb-12 shadow-2xl` |
| Cada logo | `h-7 w-auto object-contain` |
| Divisor entre logos | `w-px h-5 bg-white/20` |
| Tag acima do título | `text-ageis-yellow font-black tracking-[0.3em] text-xs uppercase italic` |
| Linha decorativa | `w-8 h-1 bg-ageis-yellow rounded-full` |
| Título principal | `text-5xl font-black italic uppercase leading-[0.9] tracking-tighter` |
| Subtítulo do título | `text-white/50 text-3xl` |
| Descrição | `text-gray-400 text-sm max-w-[280px] leading-relaxed pt-4` |
| Indicador de status | `animate-ping` dot + `text-[10px] text-gray-400 font-bold uppercase tracking-widest` |

#### Painel direito (formulário)

| Propriedade | Valor |
|---|---|
| Largura | `w-full md:w-1/2` |
| Fundo | `bg-white` |
| Padding | `p-12` |
| Layout interno | `flex flex-col justify-center` |

| Elemento | Classes |
|---|---|
| Título "Login" | `text-3xl font-black text-gray-900 tracking-tight` |
| Subtítulo | `text-sm text-gray-400 mt-1` |
| Label do campo | `text-[10px] font-black text-gray-400 uppercase tracking-widest ml-1` |
| Ícone do input | `absolute inset-y-0 left-0 flex items-center pl-4` — ícone `w-5 h-5` |
| Input | `w-full pl-12 pr-4 py-4 bg-gray-50 border border-gray-100 rounded-2xl outline-none focus:ring-4 focus:ring-ageis-yellow/10 focus:border-ageis-yellow transition-all` |
| Botão submit | `w-full bg-ageis-yellow text-black font-black py-5 rounded-2xl shadow-[0_10px_30px_rgba(255,193,7,0.3)] hover:scale-[1.02] active:scale-[0.98] transition-all` |
| Texto do botão | `uppercase tracking-widest text-xs` |
| Ícone do botão | `w-4 h-4 group-hover:translate-x-1 transition-transform` |
| Mensagem de erro | `p-4 text-xs font-bold text-red-700 bg-red-50 border border-red-100 rounded-2xl flex items-center gap-3 animate-shake` |
| Rodapé da versão | `text-[9px] text-gray-300 font-bold uppercase tracking-[0.3em]` com linhas `h-px w-8 bg-gray-100` |

---

### HTML completo da tela de login

```html
{% extends "core/base.html" %}
{% load static %}

{% block content %}
<div class="w-full max-w-[950px] mx-auto animate-in fade-in zoom-in duration-700">
  <div class="flex flex-col md:flex-row bg-white rounded-[3rem] overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.3)] border border-white/10">

    <!-- ===== PAINEL ESQUERDO — Branding ===== -->
    <div class="w-full md:w-1/2 bg-ageis-black p-12 flex flex-col justify-between text-white relative overflow-hidden">

      <!-- Blob decorativo -->
      <div class="absolute -top-24 -left-24 w-64 h-64 bg-ageis-yellow/10 blur-[100px] rounded-full"></div>

      <div class="relative z-10">
        <!-- Barra de logos -->
        <div class="inline-flex items-center gap-4 bg-white/5 backdrop-blur-md p-4 rounded-3xl border border-white/10 mb-12 shadow-2xl">
          <img src="{% static 'img/logo1.png' %}" alt="Logo 1" class="h-7 w-auto object-contain">
          <div class="w-px h-5 bg-white/20"></div>
          <img src="{% static 'img/logo2.png' %}" alt="Logo 2" class="h-7 w-auto object-contain">
          <div class="w-px h-5 bg-white/20"></div>
          <img src="{% static 'img/logo3.png' %}" alt="Logo 3" class="h-7 w-auto object-contain">
        </div>

        <!-- Título -->
        <div class="space-y-4">
          <div class="flex items-center gap-3">
            <div class="w-8 h-1 bg-ageis-yellow rounded-full"></div>
            <span class="text-ageis-yellow font-black tracking-[0.3em] text-xs uppercase italic">Sistema Integrado</span>
          </div>
          <h1 class="text-5xl font-black italic uppercase leading-[0.9] tracking-tighter">
            <span class="text-white/50 text-3xl">Gestão de</span><br>
            Parceiros
          </h1>
          <p class="text-gray-400 text-sm max-w-[280px] leading-relaxed pt-4">
            Descrição do sistema aqui.
          </p>
        </div>
      </div>

      <!-- Indicador online -->
      <div class="relative z-10 mt-12">
        <div class="flex items-center gap-2">
          <span class="flex h-2 w-2">
            <span class="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-ageis-yellow opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-ageis-yellow"></span>
          </span>
          <span class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">
            Servidor Online & Protegido
          </span>
        </div>
      </div>
    </div>

    <!-- ===== PAINEL DIREITO — Formulário ===== -->
    <div class="w-full md:w-1/2 p-12 bg-white flex flex-col justify-center">
      <div class="mb-10 text-center md:text-left">
        <h2 class="text-3xl font-black text-gray-900 tracking-tight">Login</h2>
        <p class="text-sm text-gray-400 mt-1">Insira suas credenciais de acesso.</p>
      </div>

      <!-- Erro de autenticação -->
      {% if form.errors or error %}
      <div class="p-4 mb-8 text-xs font-bold text-red-700 bg-red-50 border border-red-100 rounded-2xl flex items-center gap-3 animate-shake">
        <i data-lucide="alert-circle" class="w-5 h-5"></i>
        <span>Usuário ou senha inválidos.</span>
      </div>
      {% endif %}

      <form method="POST" class="space-y-6">
        {% csrf_token %}

        <!-- Campo Usuário -->
        <div class="space-y-2">
          <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-1">Usuário da Rede</label>
          <div class="relative group">
            <span class="absolute inset-y-0 left-0 flex items-center pl-4 text-gray-400 group-focus-within:text-ageis-yellow transition-colors">
              <i data-lucide="user" class="w-5 h-5"></i>
            </span>
            <input type="text" name="username" required
              class="w-full pl-12 pr-4 py-4 bg-gray-50 border border-gray-100 rounded-2xl outline-none focus:ring-4 focus:ring-ageis-yellow/10 focus:border-ageis-yellow transition-all placeholder:text-gray-300"
              placeholder="Nome do usuario">
          </div>
        </div>

        <!-- Campo Senha -->
        <div class="space-y-2">
          <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-1">Senha de Acesso</label>
          <div class="relative group">
            <span class="absolute inset-y-0 left-0 flex items-center pl-4 text-gray-400 group-focus-within:text-ageis-yellow transition-colors">
              <i data-lucide="lock" class="w-5 h-5"></i>
            </span>
            <input type="password" name="password" required
              class="w-full pl-12 pr-4 py-4 bg-gray-50 border border-gray-100 rounded-2xl outline-none focus:ring-4 focus:ring-ageis-yellow/10 focus:border-ageis-yellow transition-all placeholder:text-gray-300"
              placeholder="••••••••">
          </div>
        </div>

        <!-- Botão submit -->
        <button type="submit"
          class="w-full bg-ageis-yellow text-black font-black py-5 rounded-2xl shadow-[0_10px_30px_rgba(255,193,7,0.3)] hover:scale-[1.02] active:scale-[0.98] transition-all flex justify-center items-center gap-3 group">
          <span class="uppercase tracking-widest text-xs">Entrar no Sistema</span>
          <i data-lucide="arrow-right" class="w-4 h-4 group-hover:translate-x-1 transition-transform"></i>
        </button>
      </form>

      <!-- Rodapé de versão -->
      <div class="mt-12 flex items-center justify-center gap-4">
        <div class="h-px w-8 bg-gray-100"></div>
        <p class="text-[9px] text-gray-300 font-bold uppercase tracking-[0.3em]">
          Speed Engine v3.0
        </p>
        <div class="h-px w-8 bg-gray-100"></div>
      </div>
    </div>

  </div>
</div>

<style>
  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    25% { transform: translateX(-5px); }
    75% { transform: translateX(5px); }
  }
  .animate-shake { animation: shake 0.4s ease-in-out; }
</style>
{% endblock %}
```

> **Obs. para sistemas sem Django:** remova as tags `{% %}` e substitua a verificação de erro por lógica da sua linguagem/framework.

---

## Responsividade

### Breakpoints Tailwind

| Prefixo | Min-width | Uso |
|---|---|---|
| *(sem prefixo)* | 0px | Mobile (base) |
| `sm:` | 640px | Celular grande |
| `md:` | 768px | Tablet — sidebar aparece |
| `lg:` | 1024px | Desktop |
| `xl:` | 1280px | Desktop grande |
| `2xl:` | 1536px | Telas muito largas |

### Comportamento da sidebar por breakpoint

| Breakpoint | Comportamento |
|---|---|
| Mobile (< md) | Sidebar oculta, menu via hambúrguer |
| Tablet/Desktop (>= md) | Sidebar visível com `ml-64` no conteúdo |
| Desktop com toggle | Sidebar colapsável via botão |

### Overlay mobile (quando sidebar está aberta)

```html
<div id="sidebar-overlay"
  class="hidden fixed inset-0 bg-black/50 z-40 md:hidden"
  onclick="fecharSidebar()">
</div>
```
