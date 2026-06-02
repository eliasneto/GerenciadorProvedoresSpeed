# Cores e Tipografia

## Paleta de Cores

### Cores Primárias (Identidade da Marca)

| Nome | Hex | Classe Tailwind custom | Uso |
|---|---|---|---|
| Preto Ageis | `#0F0F0F` | `bg-ageis-black` / `text-ageis-black` | Sidebar, botões secundários, texto principal escuro |
| Amarelo Ageis | `#FFC107` | `bg-ageis-yellow` / `text-ageis-yellow` | Destaque, links ativos, botões primários, ícones |

### Cores Neutras (Escala de Cinzas)

| Uso | Hex | Classe Tailwind equivalente |
|---|---|---|
| Fundo geral do conteúdo | `#F8F9FA` | `bg-[#F8F9FA]` |
| Fundo de cards e inputs | `#ffffff` | `bg-white` |
| Fundo de campos neutros | `#f9fafb` | `bg-gray-50` |
| Borda sutil | `#e5e7eb` | `border-gray-200` |
| Texto secundário / placeholder | `#6b7280` | `text-gray-500` |
| Texto padrão | `#1f2937` | `text-gray-800` |
| Texto forte / títulos | `#111827` | `text-gray-900` |

### Cores de Status

| Estado | Hex | Classes Tailwind |
|---|---|---|
| Sucesso (Verde) | `#10b981` | `text-green-700 bg-green-50 border-green-100` |
| Erro (Vermelho) | `#ef4444` | `text-red-700 bg-red-50 border-red-100` |
| Aviso (Âmbar) | `#f59e0b` | `text-amber-700 bg-amber-50 border-amber-100` |
| Info (Azul) | `#3b82f6` | `text-blue-700 bg-blue-50 border-blue-100` |

### Cores com Transparência

```css
/* Amarelo 10% — fundo de item ativo no menu */
rgba(255, 193, 7, 0.1)

/* Preto 60% — backdrop de modais */
rgba(0, 0, 0, 0.6)

/* Branco 5% — divisores sutis na sidebar escura */
rgba(255, 255, 255, 0.05)
```

### Configuração Tailwind para Classes Customizadas

Adicione esse bloco ao `<script>` do Tailwind CDN em cada sistema:

```html
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
```

---

## Tipografia

### Fonte Principal

**Plus Jakarta Sans** — Google Fonts

```html
<!-- Adicionar no <head> de cada sistema -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">

<style>
  body { font-family: 'Plus Jakarta Sans', sans-serif; }
</style>
```

### Pesos de Fonte

| Peso | Valor | Uso principal |
|---|---|---|
| Light | `300` | Subtextos decorativos |
| Regular | `400` | Texto corrido |
| Medium | `500` | Texto de destaque leve |
| SemiBold | `600` | Subtítulos, labels importantes |
| Bold | `700` | Títulos de seção |
| ExtraBold | `800` | Títulos de página |
| Black | `900` | Destaques máximos, botões de ação |

### Tamanhos de Fonte

| Uso | Classe Tailwind | Equivalente em px |
|---|---|---|
| Labels, badges, status | `text-[10px]` | 10px |
| Subtextos menores | `text-xs` | 12px |
| Conteúdo normal | `text-sm` | 14px |
| Padrão | `text-base` | 16px |
| Subtítulos | `text-lg` | 18px |
| Títulos médios | `text-2xl` | 24px |
| Títulos grandes | `text-3xl` | 30px |
| Títulos de tela (login) | `text-5xl` | 48px |

### Padrões de Estilo de Texto

```html
<!-- Label padrão de formulário -->
<label class="text-[10px] font-black uppercase text-gray-400 tracking-widest">
  Nome do Campo
</label>

<!-- Título de página -->
<h1 class="text-2xl font-black text-gray-900 italic tracking-tight">
  Título da Tela
</h1>

<!-- Subtítulo / descrição -->
<p class="text-sm text-gray-500 font-medium">
  Descrição complementar
</p>
```

### Observações de Estilo

- Títulos de tela frequentemente usam **`italic`** para dar personalidade visual.
- Labels de formulário usam **`uppercase`** + **`tracking-widest`** (espaçamento máximo entre letras).
- Títulos grandes usam **`tracking-tight`** ou **`tracking-tighter`** (letras mais comprimidas).
- Botões de ação usam **`font-black`** + **`uppercase`** + **`italic`** para máximo impacto visual.
