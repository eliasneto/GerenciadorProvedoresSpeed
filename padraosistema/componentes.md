# Componentes de Interface

> Todos os componentes usam Tailwind CSS + Plus Jakarta Sans. Copie e adapte o HTML abaixo.

---

## Botões

### Botão Primário (Amarelo — ação principal)

```html
<button class="bg-ageis-yellow text-black font-black py-4 px-6 rounded-2xl uppercase italic tracking-tight hover:opacity-90 transition-opacity">
  Texto do Botão
</button>
```

### Botão Secundário (Preto — ação alternativa)

```html
<button class="bg-ageis-black text-ageis-yellow font-black py-4 px-6 rounded-2xl uppercase italic tracking-tight hover:opacity-90 transition-opacity">
  Texto do Botão
</button>
```

### Botão Neutro (Cinza — ação secundária ou cancelar)

```html
<button class="bg-gray-50 text-gray-500 font-semibold py-3 px-5 rounded-xl hover:bg-gray-100 transition-colors">
  Cancelar
</button>
```

### Botão Destrutivo (Vermelho — deletar, remover)

```html
<button class="bg-red-50 text-red-600 font-semibold py-3 px-5 rounded-xl hover:bg-red-100 border border-red-100 transition-colors">
  Excluir
</button>
```

---

## Cards

### Card padrão (branco com sombra)

```html
<div class="bg-white p-6 rounded-[2rem] shadow-sm border border-gray-100">
  <!-- conteúdo -->
</div>
```

### Card com hover

```html
<div class="bg-white p-6 rounded-[2rem] shadow-sm border border-gray-100 hover:shadow-2xl transition-all duration-200 cursor-pointer">
  <!-- conteúdo -->
</div>
```

### Card de estatística (número em destaque)

```html
<div class="bg-white p-6 rounded-[2rem] shadow-sm border border-gray-100">
  <p class="text-[10px] font-black uppercase text-gray-400 tracking-widest mb-2">Título da Métrica</p>
  <p class="text-3xl font-black text-gray-900">42</p>
  <p class="text-sm text-gray-500 mt-1">Descrição complementar</p>
</div>
```

---

## Inputs e Formulários

### Input de texto padrão

```html
<div class="space-y-1">
  <label class="text-[10px] font-black uppercase text-gray-400 tracking-widest">
    Nome do Campo
  </label>
  <input
    type="text"
    placeholder="Digite aqui..."
    class="w-full p-4 bg-gray-50 border border-gray-100 rounded-2xl outline-none focus:ring-2 focus:ring-ageis-yellow focus:border-ageis-yellow transition-all text-gray-800 font-medium"
  >
</div>
```

### Select (dropdown)

```html
<div class="space-y-1">
  <label class="text-[10px] font-black uppercase text-gray-400 tracking-widest">
    Selecione
  </label>
  <select class="w-full p-4 bg-gray-50 border border-gray-100 rounded-2xl outline-none focus:ring-2 focus:ring-ageis-yellow text-gray-800 font-medium">
    <option value="">Escolha uma opção</option>
    <option value="1">Opção 1</option>
  </select>
</div>
```

### Textarea

```html
<div class="space-y-1">
  <label class="text-[10px] font-black uppercase text-gray-400 tracking-widest">
    Observações
  </label>
  <textarea
    rows="4"
    placeholder="Digite aqui..."
    class="w-full p-4 bg-gray-50 border border-gray-100 rounded-2xl outline-none focus:ring-2 focus:ring-ageis-yellow resize-none text-gray-800 font-medium"
  ></textarea>
</div>
```

### Grid de formulário (2 colunas)

```html
<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
  <!-- campo 1 -->
  <!-- campo 2 -->
</div>
```

---

## Badges e Status

### Badge Sucesso

```html
<span class="inline-flex items-center gap-1 bg-green-50 text-green-700 border border-green-100 rounded-full px-3 py-1 text-xs font-semibold">
  Ativo
</span>
```

### Badge Erro

```html
<span class="inline-flex items-center gap-1 bg-red-50 text-red-700 border border-red-100 rounded-full px-3 py-1 text-xs font-semibold">
  Inativo
</span>
```

### Badge Aviso

```html
<span class="inline-flex items-center gap-1 bg-amber-50 text-amber-700 border border-amber-100 rounded-full px-3 py-1 text-xs font-semibold">
  Pendente
</span>
```

### Badge Info (Amarelo da marca)

```html
<span class="inline-flex items-center gap-1 bg-ageis-yellow/20 text-ageis-black rounded-full px-3 py-1 text-xs font-black uppercase">
  Destaque
</span>
```

---

## Modais

### Modal padrão

```html
<!-- Overlay -->
<div id="modal-overlay" class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-[80] flex items-center justify-center p-4">
  <!-- Container do modal -->
  <div class="bg-white rounded-[2rem] shadow-2xl border border-gray-100 w-full max-w-md">
    <!-- Header -->
    <div class="p-6 border-b border-gray-100">
      <h3 class="text-lg font-black text-gray-900">Título do Modal</h3>
      <p class="text-sm text-gray-500 mt-1">Descrição opcional</p>
    </div>
    <!-- Corpo -->
    <div class="p-6 space-y-4">
      <!-- conteúdo -->
    </div>
    <!-- Footer -->
    <div class="p-6 border-t border-gray-100 flex gap-3 justify-end">
      <button onclick="fecharModal()" class="bg-gray-50 text-gray-500 font-semibold py-3 px-5 rounded-xl hover:bg-gray-100 transition-colors">
        Cancelar
      </button>
      <button class="bg-ageis-yellow text-black font-black py-3 px-6 rounded-xl uppercase italic hover:opacity-90 transition-opacity">
        Confirmar
      </button>
    </div>
  </div>
</div>

<script>
  function abrirModal() {
    document.getElementById('modal-overlay').classList.remove('hidden');
    document.getElementById('modal-overlay').classList.add('flex');
  }
  function fecharModal() {
    document.getElementById('modal-overlay').classList.add('hidden');
    document.getElementById('modal-overlay').classList.remove('flex');
  }
</script>
```

---

## Tabelas

### Tabela padrão

```html
<div class="bg-white rounded-[2rem] shadow-sm border border-gray-100 overflow-hidden">
  <table class="w-full">
    <thead>
      <tr class="border-b border-gray-100">
        <th class="text-left p-4 text-[10px] font-black uppercase text-gray-400 tracking-widest">
          Coluna 1
        </th>
        <th class="text-left p-4 text-[10px] font-black uppercase text-gray-400 tracking-widest">
          Coluna 2
        </th>
      </tr>
    </thead>
    <tbody>
      <tr class="border-b border-gray-50 hover:bg-gray-50 transition-colors">
        <td class="p-4 text-sm font-medium text-gray-800">Valor 1</td>
        <td class="p-4 text-sm text-gray-500">Valor 2</td>
      </tr>
    </tbody>
  </table>
</div>
```

---

## Mensagens de Feedback (Toast / Alertas)

### Alerta de sucesso inline

```html
<div class="flex items-center gap-3 bg-green-50 border border-green-100 rounded-2xl p-4">
  <i data-lucide="check-circle" class="w-5 h-5 text-green-600 flex-shrink-0"></i>
  <p class="text-sm font-medium text-green-700">Operação realizada com sucesso!</p>
</div>
```

### Alerta de erro inline

```html
<div class="flex items-center gap-3 bg-red-50 border border-red-100 rounded-2xl p-4">
  <i data-lucide="alert-circle" class="w-5 h-5 text-red-600 flex-shrink-0"></i>
  <p class="text-sm font-medium text-red-700">Ocorreu um erro. Tente novamente.</p>
</div>
```

---

## Animações e Transições

### Animação de shake (campo inválido)

```css
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-5px); }
  75% { transform: translateX(5px); }
}
.animate-shake { animation: shake 0.4s ease-in-out; }
```

### Transição padrão para hover

```html
<!-- Use em botões, cards, links -->
class="transition-all duration-200"
class="transition-colors duration-200"
class="transition-opacity duration-200"
```

---

## Ícones

O sistema usa **Lucide Icons**.

```html
<!-- CDN no <head> -->
<script src="https://unpkg.com/lucide@latest"></script>

<!-- Uso no HTML -->
<i data-lucide="nome-do-icone" class="w-5 h-5 text-gray-500"></i>

<!-- Inicializar após o conteúdo ser carregado -->
<script>lucide.createIcons();</script>
```

Tamanhos padrão de ícones:

| Uso | Classes |
|---|---|
| Ícone pequeno (badge, label) | `w-3 h-3` |
| Ícone normal (texto) | `w-4 h-4` |
| Ícone médio (botão, nav) | `w-5 h-5` |
| Ícone grande (destaque) | `w-6 h-6` |
| Ícone hero (ilustração) | `w-8 h-8` ou `w-10 h-10` |
