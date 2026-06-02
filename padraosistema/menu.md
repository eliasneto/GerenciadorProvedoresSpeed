# Menu Lateral (Sidebar)

> Documentação fiel extraída do `apps/core/templates/core/base.html`.  
> Todos os tamanhos, cores e classes estão exatamente como estão em produção.

---

## Diagrama da estrutura

```
┌──────────────────────────────────────────┐
│  <aside>  w-64 (256px)  bg-ageis-black   │
│  fixed, top-0, left-0, h-full, z-50      │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │  BLOCO DE LOGOS  p-6 mb-2          │  │
│  │  ┌──────────────────────────────┐  │  │
│  │  │ [logo1] | [logo2] | [logo3]  │  │  │
│  │  │  bg-white/5  rounded-2xl     │  │  │
│  │  │  p-3  border border-white/5  │  │  │
│  │  └──────────────────────────────┘  │  │
│  │  "Gerenciador Parceiros"  text-2xl  │  │
│  │  "Partner Manager"  text-[10px]    │  │
│  └────────────────────────────────────┘  │
│                                          │
│  <nav>  px-4  space-y-1  flex-grow       │
│  ┌────────────────────────────────────┐  │
│  │  MENU PRINCIPAL  (label seção)      │  │
│  │  [ícone] Dashboard                 │  │
│  │  [ícone] Minhas Cotações  ← ativo  │  │
│  │                                    │  │
│  │  OPERAÇÕES  (label seção)           │  │
│  │  [ícone] LastMile ▾  (submenu)     │  │
│  │      • Provedores                  │  │
│  │      • Cotação                     │  │
│  │  [ícone] Parceiros ▾               │  │
│  │  [ícone] Backoffice ▾              │  │
│  │                                    │  │
│  │  GESTÃO / ADMINISTRAÇÃO            │  │
│  │  [ícone] Gestão ▾                  │  │
│  │  [ícone] Automações                │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │  CARD DO USUÁRIO  mt-auto mb-8 px-6│  │
│  │  bg-white/5  rounded-3xl  p-5      │  │
│  │  [avatar gradiente]  username      │  │
│  │  cargo badge                       │  │
│  │  [botão Sair]                      │  │
│  └────────────────────────────────────┘  │
│  "Speed OS • v1.6.0"  text-[9px]        │
└──────────────────────────────────────────┘

  ◀  Botão toggle (borda da sidebar, 50% altura)
```

---

## Especificações do `<aside>`

| Propriedade | Valor | Classe Tailwind |
|---|---|---|
| Largura | 256px | `w-64` |
| Posição | Fixa | `fixed top-0 left-0` |
| Altura | Tela toda | `h-full` |
| Z-index | 50 | `z-50` |
| Fundo | `#0F0F0F` | `bg-ageis-black` |
| Cor do texto | Branco | `text-white` |
| Borda direita | Branco 5% | `border-r border-white/5` |
| Sombra | Extra-grande | `shadow-2xl` |
| Layout interno | Coluna | `flex flex-col` |
| Scroll vertical | Habilitado | `overflow-y-auto` |
| Animação | Slide | `transform transition-transform duration-300 ease-in-out` |
| Estado desktop | Visível | `md:translate-x-0` |
| Estado mobile | Oculto | `-translate-x-full` |

```html
<aside id="sidebar"
  class="fixed top-0 left-0 h-full w-64 bg-ageis-black text-white z-50
         transform transition-transform duration-300 ease-in-out
         md:translate-x-0 -translate-x-full
         border-r border-white/5 shadow-2xl
         flex flex-col overflow-y-auto">
```

---

## Bloco de logos e nome do sistema

```html
<div class="p-6 mb-2">

  <!-- Barra com os 3 logos -->
  <div class="flex items-center justify-between gap-2 bg-white/5 p-3 rounded-2xl border border-white/5 mb-4">
    <div class="flex-1 flex justify-center">
      <img src="{% static 'img/logo1.png' %}" alt="Logo 1" class="h-6 w-auto object-contain">
    </div>
    <div class="w-px h-4 bg-white/10"></div>
    <div class="flex-1 flex justify-center">
      <img src="{% static 'img/logo2.png' %}" alt="Logo 2" class="h-6 w-auto object-contain">
    </div>
    <div class="w-px h-4 bg-white/10"></div>
    <div class="flex-1 flex justify-center">
      <img src="{% static 'img/logo3.png' %}" alt="Logo 3" class="h-6 w-auto object-contain">
    </div>
  </div>

  <!-- Nome do sistema -->
  <div class="flex flex-col ml-1">
    <span class="text-2xl font-black italic uppercase tracking-tighter leading-none text-white">
      Gerenciador Parceiros
    </span>
    <p class="text-[10px] text-ageis-yellow font-bold tracking-[0.2em] mt-1 uppercase">
      Partner Manager
    </p>
  </div>

</div>
```

### Especificações do bloco de logos

| Elemento | Classes |
|---|---|
| Container da barra de logos | `flex items-center justify-between gap-2 bg-white/5 p-3 rounded-2xl border border-white/5 mb-4` |
| Cada slot de logo | `flex-1 flex justify-center` |
| Cada logo | `h-6 w-auto object-contain` |
| Divisor entre logos | `w-px h-4 bg-white/10` |
| Nome do sistema | `text-2xl font-black italic uppercase tracking-tighter leading-none text-white` |
| Subtítulo | `text-[10px] text-ageis-yellow font-bold tracking-[0.2em] mt-1 uppercase` |

---

## Navegação — Estrutura geral

```html
<nav class="px-4 space-y-1 flex-grow">
  <!-- labels de seção + links ficam aqui -->
</nav>
```

### Label de seção

```html
<p class="text-[10px] uppercase text-gray-600 font-extrabold px-4 py-3 tracking-widest">
  Menu Principal
</p>
```

| Propriedade | Valor |
|---|---|
| Tamanho | `text-[10px]` |
| Cor | `text-gray-600` |
| Peso | `font-extrabold` |
| Transform | `uppercase` |
| Espaçamento de letras | `tracking-widest` |
| Padding | `px-4 py-3` |

---

## Item de menu simples (link direto)

```html
<a href="{% url 'home' %}"
   class="flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200
          text-gray-400 hover:bg-white/5 hover:text-white group">
  <i data-lucide="layout-dashboard" class="w-5 h-5 group-hover:scale-110 transition-transform"></i>
  <span class="text-sm font-semibold">Dashboard</span>
</a>
```

### Especificações do link simples

| Estado | Classes |
|---|---|
| Padrão (inativo) | `text-gray-400 hover:bg-white/5 hover:text-white` |
| Ativo | `sidebar-link-active text-ageis-yellow` |
| Container | `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group` |
| Ícone | `w-5 h-5 group-hover:scale-110 transition-transform` |
| Texto | `text-sm font-semibold` |

### CSS do estado ativo (definido no `<style>` do base.html)

```css
.sidebar-link-active {
  background-color: rgba(255, 193, 7, 0.1);  /* amarelo 10% de opacidade */
  color: #FFC107 !important;
  border-left: 4px solid #FFC107;
  border-radius: 0 12px 12px 0 !important;
}
```

---

## Item de menu com submenu (dropdown)

```html
<div class="mb-1 relative">

  <!-- Botão do item pai -->
  <button onclick="toggleSubmenu('submenu-lastmile', 'seta-lastmile')"
    class="w-full flex items-center justify-between px-4 py-3 rounded-xl transition-all duration-200 group
           text-gray-400 hover:text-white hover:bg-white/5">
    <div class="flex items-center gap-3">
      <i data-lucide="network" class="w-5 h-5 group-hover:scale-110 transition-transform"></i>
      <span class="text-sm font-semibold">LastMile</span>
    </div>
    <i data-lucide="chevron-down" id="seta-lastmile"
       class="w-4 h-4 transition-transform duration-300"></i>
    <!-- Adicionar rotate-180 quando aberto -->
  </button>

  <!-- Container do submenu -->
  <div id="submenu-lastmile"
    class="hidden flex flex-col gap-1 bg-black/20 rounded-xl mt-1 py-2 overflow-hidden">
    <!-- Remover 'hidden' quando ativo -->

    <!-- Item do submenu -->
    <a href="/provedores/"
      class="pl-[3.25rem] pr-4 py-2 text-sm font-semibold transition-colors flex items-center gap-2
             text-gray-500 hover:text-gray-300">
      <div class="w-1.5 h-1.5 rounded-full bg-gray-500"></div>
      <!-- Trocar por bg-ageis-yellow quando ativo -->
      Provedores
    </a>

  </div>
</div>
```

### Especificações do submenu

| Elemento | Classes |
|---|---|
| Botão pai (inativo) | `w-full flex items-center justify-between px-4 py-3 rounded-xl transition-all duration-200 group text-gray-400 hover:text-white hover:bg-white/5` |
| Botão pai (ativo) | `text-ageis-yellow bg-white/5` |
| Ícone seta (fechado) | `w-4 h-4 transition-transform duration-300` |
| Ícone seta (aberto) | adicionar `rotate-180` |
| Container do submenu | `flex flex-col gap-1 bg-black/20 rounded-xl mt-1 py-2 overflow-hidden` |
| Item do submenu | `pl-[3.25rem] pr-4 py-2 text-sm font-semibold transition-colors flex items-center gap-2` |
| Item inativo | `text-gray-500 hover:text-gray-300` |
| Item ativo | `text-ageis-yellow` |
| Dot indicator (inativo) | `w-1.5 h-1.5 rounded-full bg-gray-500` |
| Dot indicator (ativo) | `w-1.5 h-1.5 rounded-full bg-ageis-yellow` |

### JavaScript do toggle de submenu

```javascript
function toggleSubmenu(menuId, arrowId) {
  const menu = document.getElementById(menuId);
  const arrow = document.getElementById(arrowId);
  if (menu.classList.contains('hidden')) {
    menu.classList.remove('hidden');
    arrow.classList.add('rotate-180');
  } else {
    menu.classList.add('hidden');
    arrow.classList.remove('rotate-180');
  }
}
```

---

## Card do usuário (rodapé da sidebar)

```html
<div class="mt-auto mb-8 px-6">

  <!-- Card -->
  <div class="bg-white/5 rounded-3xl p-5 border border-white/5">

    <!-- Linha do usuário -->
    <div class="flex items-center gap-3 mb-6">

      <!-- Avatar com gradiente -->
      <div class="w-10 h-10 rounded-2xl bg-gradient-to-br from-ageis-yellow to-orange-500
                  flex items-center justify-center text-black font-black shadow-lg text-lg">
        {{ user.username|slice:":1"|upper }}
      </div>

      <!-- Nome e cargo -->
      <div class="overflow-hidden">
        <p class="text-[11px] font-bold truncate text-white leading-tight">
          {{ user.username }}
        </p>
        <span class="text-[8px] bg-white/10 text-gray-400 px-2 py-0.5 rounded-full
                     font-bold uppercase tracking-widest border border-white/5">
          Consultor
          <!-- Diretor se is_superuser / Gestor se is_gestor -->
        </span>
      </div>
    </div>

    <!-- Botão de logout -->
    <form action="{% url 'logout' %}" method="post">
      {% csrf_token %}
      <button type="submit"
        class="w-full flex items-center justify-center gap-2 py-3
               text-[10px] font-black text-red-400 bg-red-400/10
               hover:bg-red-500 hover:text-white
               rounded-2xl transition-all uppercase tracking-widest">
        <i data-lucide="power" class="w-3.5 h-3.5"></i>
        Sair do Sistema
      </button>
    </form>

  </div>

  <!-- Versão -->
  <div class="mt-4 text-center pb-2">
    <p class="text-[9px] font-black text-gray-600 uppercase tracking-widest select-none">
      Speed OS • v1.6.0
    </p>
  </div>

</div>
```

### Especificações do card do usuário

| Elemento | Classes |
|---|---|
| Wrapper externo | `mt-auto mb-8 px-6` |
| Card | `bg-white/5 rounded-3xl p-5 border border-white/5` |
| Avatar | `w-10 h-10 rounded-2xl bg-gradient-to-br from-ageis-yellow to-orange-500 flex items-center justify-center text-black font-black shadow-lg text-lg` |
| Nome do usuário | `text-[11px] font-bold truncate text-white leading-tight` |
| Badge do cargo | `text-[8px] bg-white/10 text-gray-400 px-2 py-0.5 rounded-full font-bold uppercase tracking-widest border border-white/5` |
| Botão de logout | `w-full flex items-center justify-center gap-2 py-3 text-[10px] font-black text-red-400 bg-red-400/10 hover:bg-red-500 hover:text-white rounded-2xl transition-all uppercase tracking-widest` |
| Ícone do botão | `w-3.5 h-3.5` |
| Texto da versão | `text-[9px] font-black text-gray-600 uppercase tracking-widest select-none` |

---

## Botão de toggle da sidebar (desktop)

O botão fica fixo na borda direita da sidebar, centralizado verticalmente. É definido via CSS puro no `<style>` do `base.html`.

```css
/* Estado padrão — sidebar aberta */
#desktopToggleBtn {
  position: fixed;
  top: 50%;
  left: 256px;                     /* colado na borda direita da sidebar */
  transform: translate(-50%, -50%);
  width: 32px;
  height: 32px;
  border-radius: 50%;              /* círculo */
  background-color: white;
  border: 1px solid #e5e7eb;
  z-index: 55;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

#desktopToggleBtn:hover {
  transform: translate(-50%, -50%) scale(1.1);
  background-color: #f9fafb;
}

/* Ícone do botão */
#desktopToggleIcon {
  transition: transform 0.3s ease;    /* gira quando colapsa */
}

/* Estado colapsado — sidebar fechada */
body.sidebar-collapsed #desktopToggleBtn {
  left: 0 !important;
  transform: translateY(-50%) !important;
  width: 24px !important;
  height: 48px !important;
  border-radius: 0 12px 12px 0 !important;   /* vira uma aba lateral */
  border-left: none;
}

body.sidebar-collapsed #desktopToggleBtn:hover {
  width: 32px !important;
}

body.sidebar-collapsed #desktopToggleIcon {
  transform: rotate(180deg) !important;      /* seta aponta para direita */
}

/* Ocultar em mobile */
@media (max-width: 768px) {
  #desktopToggleBtn { display: none !important; }
}
```

```html
<!-- HTML do botão -->
<button id="desktopToggleBtn" onclick="toggleDesktopSidebar()" class="group">
  <i data-lucide="chevron-left" id="desktopToggleIcon"
     class="w-4 h-4 text-gray-400 group-hover:text-ageis-yellow transition-colors"></i>
</button>
```

```javascript
function toggleDesktopSidebar() {
  document.body.classList.toggle('sidebar-collapsed');
  const isClosed = document.body.classList.contains('sidebar-collapsed');
  localStorage.setItem('desktopSidebarState', isClosed ? 'closed' : 'open');
}

// Restaurar estado ao carregar a página
document.addEventListener('DOMContentLoaded', function() {
  if (localStorage.getItem('desktopSidebarState') === 'closed') {
    document.body.classList.add('sidebar-collapsed');
  }
});
```

---

## Overlay mobile

Quando o menu é aberto no celular, um overlay escuro cobre o conteúdo. Clicar nele fecha o menu.

```html
<div id="sidebarOverlay"
  class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 hidden md:hidden transition-opacity"
  onclick="toggleSidebar()">
</div>
```

```javascript
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (sidebar.classList.contains('-translate-x-full')) {
    sidebar.classList.remove('-translate-x-full');
    overlay.classList.remove('hidden');
    overlay.style.display = 'block';
  } else {
    sidebar.classList.add('-translate-x-full');
    overlay.classList.add('hidden');
    overlay.style.display = 'none';
  }
}
```

---

## Header (barra do topo do conteúdo)

O header fica acima do conteúdo principal, fora da sidebar.

```html
<header class="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-gray-200 px-6 py-4 flex items-center justify-between">

  <div class="flex items-center gap-4">
    <!-- Hambúrguer — só aparece em mobile -->
    <button onclick="toggleSidebar()" class="p-2 text-gray-600 md:hidden hover:bg-gray-100 rounded-lg transition">
      <i data-lucide="menu"></i>
    </button>

    <!-- Breadcrumb — só aparece em desktop -->
    <div class="hidden md:block">
      <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest italic">
        Ageis Sistemas / <span class="text-gray-900">Gerenciador</span>
      </h2>
    </div>
  </div>

  <!-- Badge de status do sistema -->
  <div id="systemHealthBadge"
    class="flex items-center gap-3 bg-green-50 px-3 py-1.5 rounded-full border border-green-100 transition-colors duration-200">
    <span id="systemHealthDot" class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
    <span id="systemHealthText" class="text-[10px] font-black text-green-700 uppercase">Sistema Online</span>
  </div>

</header>
```

### Especificações do header

| Elemento | Classes |
|---|---|
| `<header>` | `sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-gray-200 px-6 py-4 flex items-center justify-between` |
| Botão hambúrguer (mobile) | `p-2 text-gray-600 md:hidden hover:bg-gray-100 rounded-lg transition` |
| Breadcrumb | `text-xs font-bold text-gray-400 uppercase tracking-widest italic` |
| Parte destacada do breadcrumb | `text-gray-900` |

### Badge de status do sistema

| Estado | Classes do container | Dot | Texto |
|---|---|---|---|
| Online | `bg-green-50 border-green-100` | `bg-green-500` | `text-green-700` — "Sistema Online" |
| Offline | `bg-red-50 border-red-100` | `bg-red-500` | `text-red-700` — "Sistema Offline" |
| Verificando | `bg-amber-50 border-amber-100` | `bg-amber-500` | `text-amber-700` — "Verificando Sistema" |

O badge faz uma verificação automática a cada **90 segundos** via `fetch` para um endpoint de health check (`/system-health/`).

---

## Scrollbar customizada da sidebar

```css
#sidebar::-webkit-scrollbar { width: 4px; }
#sidebar::-webkit-scrollbar-thumb { background: #2d2d2d; border-radius: 10px; }
```

---

## Resumo visual — todas as cores do menu

| Elemento | Cor | Valor |
|---|---|---|
| Fundo da sidebar | Preto profundo | `#0F0F0F` |
| Borda direita da sidebar | Branco 5% | `rgba(255,255,255,0.05)` |
| Fundo da barra de logos | Branco 5% | `rgba(255,255,255,0.05)` |
| Divisor entre logos | Branco 10% | `rgba(255,255,255,0.10)` |
| Nome do sistema | Branco | `#ffffff` |
| Subtítulo do sistema | Amarelo | `#FFC107` |
| Label de seção | Cinza médio | `#4b5563` (gray-600) |
| Link inativo | Cinza claro | `#9ca3af` (gray-400) |
| Link hover fundo | Branco 5% | `rgba(255,255,255,0.05)` |
| Link ativo fundo | Amarelo 10% | `rgba(255,193,7,0.1)` |
| Link ativo texto | Amarelo | `#FFC107` |
| Link ativo borda esquerda | Amarelo | `#FFC107` (4px) |
| Fundo submenu | Preto 20% | `rgba(0,0,0,0.20)` |
| Item submenu inativo | Cinza | `#6b7280` (gray-500) |
| Item submenu ativo | Amarelo | `#FFC107` |
| Dot ativo | Amarelo | `#FFC107` |
| Dot inativo | Cinza | `#6b7280` |
| Fundo card usuário | Branco 5% | `rgba(255,255,255,0.05)` |
| Avatar gradiente | Amarelo → Laranja | `from-ageis-yellow to-orange-500` |
| Badge de cargo | Cinza | `text-gray-400 bg-white/10` |
| Botão logout (normal) | Vermelho suave | `text-red-400 bg-red-400/10` |
| Botão logout (hover) | Vermelho sólido | `bg-red-500 text-white` |
| Versão | Cinza escuro | `text-gray-600` |
| Scrollbar thumb | Cinza carvão | `#2d2d2d` |
