# Plano de Refinamento: Sistema de Callouts Premium

**Versão:** 1.0  
**Data:** 2026-09-07  
**Base:** Design Review v5 + feedback do usuário  
**Escopo:** Conventions + CSS + Testes

---

## Decisões Aprovadas

### 1. Arquitetura Base — Imutável
- [x] 13 tipos nativos Obsidian apenas
- [x] Zero heurística textual
- [x] Type define função; theme define aparência
- [x] Surface + accents derivados do tema
- [x] Obsidian-first + export determinístico

### 2. Famílias Visuais — Novo Contrato

| Tipo | Função Local | Família | Aparência |
|------|---|---|---|
| **note** | contexto/reflexão | tonal | surface neutra + rail discreto |
| **abstract** | mapa/framework/síntese | tab | surface + accent frio (azul/ouro) |
| **info** | evidência empírica/factual | tab | surface + accent blue-tint |
| **example** | experimento/caso/cenário | tab | surface + accent rust-tint |
| **tip** | ideia/insight/proposta | tab | surface + accent gold-warm |
| **todo** | **entity card** | entity | entity card typography + rail |
| **warning** | **stat card** | stat | surface2 + número grande + rail |
| **question** | objeção/tensão/ataque | objection | surface + accent rust medium |
| **success** | resultado/veredicto | result | verde discreto (standalone); herdar pai (nested) |
| **failure** | hipótese/teste falho | failure | surface + accent rust low |
| **danger** | invalidez/risco crítico | danger | surface + accent rust stronger |
| **bug** | defeito técnico | technical | surface + rust + mono |
| **quote** | citação destacada | pull-quote | **cinza neutro** + filete discreto |

---

## Preferências do Usuário — Aplicadas

### 3.1 Entity Cards (aprovado ✓)
```
Thomas Hobbes
1588–1679 · Inglaterra
contexto...
```
- Nome em Playfair Display
- Metadata em JetBrains Mono
- Rail theme-native (azul light, ouro dark)
- Uso: pessoa, filósofo, cientista, organização, obra

### 3.2 Quote Cards — Cinza Neutro (NOVO)
- **Antes:** surface azul/colorido
- **Depois:** cinza neutro + filete discreto
- **Light:** `#F2F2F0` surface + `#9E9E9C` filete
- **Dark:** `#0D0D0C` + `#5A5A58` filete
- **Rationale:** Pullquotes integram-se com prosa, não competem

### 3.3 Note como Padrão (aprovado ✓)
- Função: nota filosófica, contexto, ressalva editorial
- Peso visual: baixo
- OK usar em massa quando função é clara
- Surface neutra

### 3.4 Evidence × Experiment — Tipos Distintos (NOVO)

**Info (Evidência Empírica)**
- Acento: **azul-tint** (mais frio, factual)
- Uso: dados, estudos, observações documentadas

**Example (Experimento Mental)**
- Acento: **rust-tint** (mais quente, narrativo)
- Uso: cenários, casos, experimentos

**Diferenciação:** mesma surface, accents sutilmente diferentes, anatomia levemente distinta.

---

## Refinamento: Respiro Vertical (CRÍTICO)

### Problema Identificado
Títulos, subtítulos e corpo comprimidos. Melhor respiro entre parágrafos do que entre ênfases estruturais.

### Solução CSS

```css
/* Entity Card */
.box-entity {
  padding-top: 1.2rem;
  padding-bottom: 1.2rem;
}

.box-entity-title {
  margin-bottom: 0.8rem;
  font-size: 1.1rem;
  font-family: Playfair Display;
  font-weight: 700;
}

.box-entity > h4 {
  margin-top: 0.6rem;
  margin-bottom: 1.0rem;
  font-size: 0.85rem;
  font-family: JetBrains Mono;
  color: var(--text-dim);
}

/* Editorial Tabs (info/example/abstract/tip) */
.box-tab {
  padding-top: 1.1rem;
  padding-bottom: 1.1rem;
}

.box-tab-kicker {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 0.7rem;
  color: var(--text-dim);
}

.box-tab > h4 {
  margin-top: 0.4rem;
  margin-bottom: 0.9rem;
  font-size: 1.0rem;
  font-family: Playfair Display;
}

/* Stat Card (warning) */
.box-stat {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 1.2rem;
  padding: 1.2rem;
}

.box-stat-number {
  font-size: 2.2rem;
  font-family: Playfair Display;
  font-weight: 700;
  color: var(--stat-accent);
  line-height: 1;
}

.box-stat-text {
  padding-top: 0.4rem;
}
```

---

## Paleta Proposta — LIGHT

### Surfaces
- background: `#F7F9FC`
- surface: `#FAFBFD`
- surface2: `#EDF2F8`
- text: `#2B3645`
- text-dim: `#6A7582`
- border: `#D6DEE9`

### Accents Derivados de Atlas Blue
- accent-blue: `#2F5FB0` (abstract, link)
- accent-blue-tint: `#5B7FC4` (info; factual)
- accent-rust: `#A0664D` (example, failure, question)
- accent-rust-warm: `#B08B4F` (tip, success)
- accent-gray: `#9E9E9C` (quote, note)

---

## Paleta Proposta — DARK

### Surfaces
- background: `#0A0A0A`
- surface: `#141414`
- surface2: `#1C1C1C`
- text: `#E8E8E6`
- text-dim: `#A0A09E`
- border: `#2A2A28`

### Accents Derivados de Ouro Contido
- accent-gold: `#D4AF6A` (abstract, tip)
- accent-rust: `#9D6E5F` (example, question)
- accent-gray: `#5A5A58` (quote, note)
- accent-success: `#5FA973` (success)

---

## Ajustes CSS Necessários

### Borders e Rails
**Antes:**
```css
border: 2px solid var(--callout-type);  /* saturado */
```

**Depois:**
```css
border-left: 3px solid var(--accent-type);
border-radius: 6px;
background: var(--surface);
box-shadow: 0 1px 3px rgba(0,0,0,0.05);
```

### Respiro Vertical Global

```css
.box {
  padding: 1.2rem;
  margin: 1.6rem 0;
}

.box > h4:first-child {
  margin-top: 0;
  margin-bottom: 0.9rem;
}

.box > p:first-of-type {
  margin-top: 0.8rem;
}

.box > p + p {
  margin-top: 1.0rem;
}
```

---

## Conventions — Seção Atualizada

### Princípios

1. **Somente 13 tipos nativos Obsidian** — zero customizados
2. **Type define função; theme define aparência**
3. **Zero heurística** — Obsidian-first e determinístico
4. **Surface + accents derivados do tema**

### Decision Table

| Função | Tipo | Família | Uso |
|---|---|---|---|
| Contexto/reflexão | note | tonal | nota editorial, ressalva |
| Mapa/framework | abstract | tab | definição, blueprint |
| Evidência empírica | info | tab | estudo, dado, observação |
| Experimento/caso | example | tab | teste mental, aplicação |
| Ideia/proposta | tip | tab | recomendação, intuição |
| Pessoa/obra/fonte | todo | entity card | filósofo, livro, instituição |
| Métrica | warning | stat card | percentual, valor-chave |
| Objeção/tensão | question | objection card | pergunta aberta, desafio |
| Resultado | success | result | confirmação; herda pai se aninhado |
| Teste falho | failure | failure card | refutação |
| Risco crítico | danger | danger card | erro grave |
| Defeito técnico | bug | technical card | bug, falha |
| Citação | quote | pull quote | citação enfatizada |

---

## Roadmap de Implementação

### Fase 1: Conventions + CSS (Semana 1)
- [ ] Reescrever conventions/SKILL.md com decision table
- [ ] Atualizar paleta em essay_template.html
- [ ] Implementar respiro vertical em .box
- [ ] Implementar entity card typography
- [ ] Implementar stat card layout grid
- [ ] Implementar quote card cinza

### Fase 2: Corpus Refactor (Semana 2–3)
- [ ] Audit: psicometria — note → info para evidência
- [ ] Audit: paradoxo-de-fermi — obras → todo; A1–C9 → abstract
- [ ] Audit: outros essays para semântica correta
- [ ] Preservar: quem-e-voce (semanticamente correto)
- [ ] Preservar: xadrez-computacional (contenção correta)

### Fase 3: QA (Semana 4)
- [ ] 6 essays × 2 temas × 2 form factors = 24 screenshots
- [ ] Entity cards: nome/metadata legível
- [ ] Stat cards: número destacado
- [ ] Tabs: accents distinguíveis
- [ ] Quote: integração com prosa
- [ ] Respiro: verificar mobile

---

## Por Que Isso é Premium

1. **Semântica clara** — type por função, não cor
2. **Tema-native** — accents sempre derivados
3. **Respiro visual** — hierarquia clara por espaçamento
4. **Anatomia forte** — entity/stat/quote diferenciáveis
5. **Modulação discreta** — não arco-íris
6. **Obsidian-first** — portável, legível, determinístico
7. **Tipografia proposital** — Playfair/Mono/Serif intencional
8. **Escala** — legível desktop e mobile

---

## Próximos Passos

1. Aprove paleta luz/escuro
2. Aprove respiro vertical
3. Aprove entity card anatomia
4. Aprove quote cinza
5. Inicie Fase 1
