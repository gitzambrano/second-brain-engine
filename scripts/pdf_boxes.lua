-- pdf_boxes.lua - Premium PDF: semantic boxes, typographic Sumário,
-- reference items with hanging indent, styled figure captions.
--
-- Pipeline: html_preprocess.transform_markdown → fenced divs → this filter
-- → LaTeX environments defined in HEADER_TEX (export_essay_pdf.py).
-- Wikibox receives a color argument from the explicit semantic class.
-- Sumário is converted from BulletList to sbtoc environment.
-- References (## Referências) get sbrefitem wrapping + Link→↗.

local stringify = pandoc.utils.stringify

local function lescape(s)
  s = s:gsub('\\', '\001BSL\001')
  s = s:gsub('([#$%%_{}])', '\\%1')
  s = s:gsub('&', '\\&')
  s = s:gsub('~', '\\textasciitilde{}')
  s = s:gsub('%^', '\\textasciicircum{}')
  s = s:gsub('\001BSL\001', '$\\backslash$')
  return s
end

local function has_class(el, class)
  for _, c in ipairs(el.classes) do
    if c == class then return true end
  end
  return false
end

-- ------------------------------------------------------------------
-- Box color from explicit semantic class
-- ------------------------------------------------------------------

local CLASS_COLOR_RULES = {
  {'experimento', 'boxexp'},
  {'evidencia', 'boxev'},
  {'mapa', 'boxmap'},
  {'ataque', 'boxav'}, {'aviso', 'boxav'},
  {'ideia', 'boxid'},
  {'generico', 'boxline'},
}

local function get_box_color(el)
  -- The Python preprocessor chooses the class from the explicit [!type].
  -- Badge, title, emoji and body text are never inspected to choose a type.
  for _, rule in ipairs(CLASS_COLOR_RULES) do
    if has_class(el, rule[1]) then return rule[2] end
  end
  return 'boxline'
end

-- ------------------------------------------------------------------
-- State: Sumário and References tracking
-- ------------------------------------------------------------------

local after_sumario = false
local in_references = false

local ROMAN = {'I','II','III','IV','V','VI','VII','VIII','IX','X',
               'XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX'}

local function is_roman(s)
  return s:match('^[IVXLCDM]+$') ~= nil
end

local function romanize_toc(num)
  local n = tonumber(num)
  if n and n <= #ROMAN then return ROMAN[n] end
  return num
end

-- Devolve (numeral, tamanho-do-prefixo-em-bytes) do inicio do texto, ou nil.
--
-- ATENCAO: padroes do Lua NAO tem grupo nao-capturante. A versao anterior
-- usava `%d+(?:%.%d+)*`, sintaxe de PCRE, que em Lua nunca casa — o ramo
-- arabe morria silenciosamente e todo Sumario numerado com "1." saia com a
-- numeracao DUPLICADA (goteira romana do contador + "1." no proprio titulo).
--
-- O numeral tambem e preservado no sistema em que o autor escreveu: romano
-- continua romano, arabe continua arabe. Romanizar "3." virava "III" no
-- kicker enquanto as subsecoes seguiam "3.1" — dois sistemas para o mesmo
-- capitulo na mesma pagina.
local function extract_toc_number(text)
  -- 1) Romanos: "I.", "II -", "XIV:"
  local r, rest_r = text:match('^%s*([IVXLCDM]+)%s*[%.%-%–:]%s*(.*)$')
  if r and is_roman(r) then
    return r, #text - #rest_r
  end
  -- 2) Arabes, com ou sem subnivel: "1.", "2 -", "1.1", "4:"
  local a, rest_a = text:match('^%s*(%d+[%d%.]*)%s*[%.%-%–:]%s*(.*)$')
  if a then
    a = a:gsub('%.$', '')
    return a, #text - #rest_a
  end
  -- 3) "1 Titulo" / "III Titulo" (sem pontuacao separadora)
  local b, rest_b = text:match('^%s*(%d+)%s+(%a.*)$')
  if b then
    return b, #text - #rest_b
  end
  return nil, 0
end

-- Remove `n` bytes do inicio dos inlines, descendo em elementos aninhados
-- (o item do Sumario e quase sempre um Link envolvendo o texto). Preserva
-- Math/Emph/Code intactos: o `stringify` + `lescape` da versao anterior
-- achatava tudo em texto e cuspia `\dot{\beta}` e `C_{n_\beta}` crus na
-- pagina.
local function drop_prefix(inlines, n)
  if n <= 0 then return inlines end
  local left = n
  local function walk(list)
    local out = {}
    for _, el in ipairs(list) do
      if left <= 0 then
        table.insert(out, el)
      elseif el.t == 'Str' then
        if #el.text <= left then
          left = left - #el.text
        else
          table.insert(out, pandoc.Str(el.text:sub(left + 1)))
          left = 0
        end
      elseif el.t == 'Space' or el.t == 'SoftBreak' then
        left = left - 1
      elseif el.content then
        el.content = walk(el.content)
        table.insert(out, el)
      else
        table.insert(out, el)
      end
    end
    return out
  end
  return walk(inlines)
end

-- Inlines de um item de lista (primeiro bloco Para/Plain).
local function item_inlines(item)
  for _, b in ipairs(item) do
    if b.t == 'Para' or b.t == 'Plain' then return b.content end
  end
  return {}
end

-- ------------------------------------------------------------------
-- Header: state machine for Sumário and References
-- ------------------------------------------------------------------

-- Padroes do Lua trabalham em BYTES, nao em caracteres: `[áa]` vira a classe
-- dos bytes 0xC3/0xA1/'a', entao `sum[áa]rio` exige UM byte entre "sum" e
-- "rio" e nunca casa com "sumário" (dois bytes). Busca literal (plain=true)
-- em cada grafia e o jeito seguro — sem esta correcao o Sumario continuava
-- lista de bullets e as Referencias nunca recebiam recuo pendente.
-- Casa o titulo INTEIRO, nao um pedaco dele. Com busca por substring, o
-- capitulo "Indice de Experimentos Mentais e Evidencias Empiricas" (um
-- capitulo de verdade, em quem-e-voce) era lido como o Sumario gerado: o
-- titulo era apagado e a lista seguinte reformatada como sumario. O lado
-- Python ja tinha essa correcao em SEMANTIC_APARATO_RE; aqui faltava.
--
-- O sufixo opcional cobre as variantes reais ("Referencias Bibliograficas")
-- sem reabrir a porta para qualquer continuacao.
local function equals_any(haystack, needles, suffixes)
  local title = haystack:gsub("^%s+", ""):gsub("%s+$", "")
  for _, n in ipairs(needles) do
    if title == n then return true end
    for _, suffix in ipairs(suffixes or {}) do
      if title == n .. ' ' .. suffix then return true end
    end
  end
  return false
end

local SUMARIO_TITLES = {'sumário', 'sumario', 'summary', 'índice', 'indice'}
local REFS_TITLES = {'referências', 'referencias', 'references', 'bibliography'}
local REFS_SUFFIXES = {'bibliográficas', 'bibliograficas', 'bibliográfica',
                       'bibliografica', 'citadas', 'consultadas'}

function Header(el)
  if el.level == 2 then
    after_sumario = false
    in_references = false
    local title = pandoc.text.lower(stringify(el))
    if equals_any(title, SUMARIO_TITLES) then
      after_sumario = true
      -- O kicker \sbkicker{Sumário} ja nomeia a secao (mesmo comportamento do
      -- HTML, onde `h2#sumário` fica display:none). Manter o titulo aqui
      -- imprimiria "SUMÁRIO" e "Sumário" em duas linhas seguidas.
      return {}
    elseif equals_any(title, REFS_TITLES, REFS_SUFFIXES) then
      in_references = true
      -- O kicker \sbkicker{Referências} já nomeia a seção em dourado.
      -- Suprime o título duplicado.
      return {}
    end
  end
  -- Numeral do subtitulo em dourado. `\texorpdfstring` mantem o marcador do
  -- PDF em texto puro: cor nao existe em bookmark, e sem ele o hyperref
  -- reclamaria do comando de cor dentro do titulo.
  if el.level == 3 or el.level == 4 then
    local primeiro = el.content[1]
    if primeiro and primeiro.t == 'Str' then
      local num = primeiro.text:match('^(%d[%d%.]*%d)$')
                or primeiro.text:match('^(%d)$')
      if num then
        el.content[1] = pandoc.RawInline('latex',
          '\\texorpdfstring{\\textcolor{sbink}{' .. num .. '}}{' .. num .. '}')
        return el
      end
    end
  end
  return nil
end

-- ------------------------------------------------------------------
-- Link: underline inline hyperlinks in PDF body
-- ------------------------------------------------------------------

-- Envolve os inlines num \uline, descendo por dentro de enfase/forte/span.
--
-- O ulem so quebra linha em espaco que NAO esteja dentro de chaves. Deixar a
-- enfase por fora do sublinhado e o que permite quebrar: `\emph{\uline{a b}}`
-- quebra no espaco, `\uline{\emph{a b}}` nao. Um link misto ("Catalyst, *The
-- Bottom Line...*") precisa do tratamento em cada trecho, nao so quando o link
-- inteiro e italico — era esse o caso que ainda vazava a margem direita.
local ENVOLTORIOS = { Emph = true, Strong = true, SmallCaps = true,
                      Span = true, Underline = true }

local function uline_wrap(inlines)
  local out = {}
  local corrida = {}

  local function despeja()
    if #corrida == 0 then return end
    table.insert(out, pandoc.RawInline('latex', '\\uline{'))
    for _, c in ipairs(corrida) do table.insert(out, c) end
    table.insert(out, pandoc.RawInline('latex', '}'))
    corrida = {}
  end

  for _, el in ipairs(inlines) do
    if ENVOLTORIOS[el.t] and el.content and #el.content > 0 then
      despeja()
      el.content = uline_wrap(el.content)
      table.insert(out, el)
    else
      table.insert(corrida, el)
    end
  end
  despeja()
  return out
end

-- ------------------------------------------------------------------
-- Code: pontos de quebra dentro de codigo em linha
-- ------------------------------------------------------------------

-- `\texttt` nao hifeniza. Um identificador longo ("erro_padrao=0.00001") nao
-- tinha onde quebrar e vazava a margem direita. Partir o Code em pedacos nos
-- separadores e inserir `\allowbreak` entre eles nao muda uma virgula do que e
-- impresso — so devolve ao TeX pontos de corte legais.
local SEPARADOR = '[_=%.,/:%-%+%(%)%[%]]'

function Code(el)
  if #el.text < 14 or not el.text:find(SEPARADOR) then
    return nil
  end
  local out, buf = {}, ''
  for ch in el.text:gmatch('.') do
    buf = buf .. ch
    if ch:match(SEPARADOR) then
      table.insert(out, pandoc.Code(buf))
      table.insert(out, pandoc.RawInline('latex', '\\allowbreak{}'))
      buf = ''
    end
  end
  if #buf > 0 then
    table.insert(out, pandoc.Code(buf))
  end
  return out
end

function Link(el)
  -- Link interno (Sumário -> capítulo): o Pandoc, deixado sozinho, escreve
  -- `\hyperref[id]{...}` usando o PRÓPRIO id auto-gerado do heading — que
  -- não é o mesmo id do `\hypertarget{}` que export_essay_pdf.py insere
  -- antes de cada capítulo (heading_anchor(), preservando o número e sem
  -- manglar acentos para ASCII). Os dois nomes nunca batiam, e o link do
  -- Sumário nunca navegava para lugar nenhum. `\hyperlink{}` aponta direto
  -- para o MESMO nome do `\hypertarget{}`, sem depender do id do Pandoc.
  if el.target:match('^#') then
    -- \sbtoclink (definido em export_essay_pdf.py) e' \hyperlink + um
    -- sublinhado bem sutil — sem ele o link interno fica na mesma cor do
    -- texto normal (linkcolor=sblink e' quase preto) e não da nenhuma pista
    -- de que aquilo e' clicavel.
    local anchor = el.target:sub(2)
    local out = { pandoc.RawInline('latex', '\\sbtoclink{' .. anchor .. '}{') }
    for _, inl in ipairs(el.content) do
      table.insert(out, inl)
    end
    table.insert(out, pandoc.RawInline('latex', '}'))
    return out
  end
  if in_references then
    return el
  end
  el.content = uline_wrap(el.content)
  return el
end

-- ------------------------------------------------------------------
-- BulletList: convert Sumário to sbtoc environment
-- ------------------------------------------------------------------

function BulletList(el)
  if after_sumario then
    after_sumario = false
    -- O essay numera os proprios capitulos? Se sim, a goteira usa o numeral
    -- do autor; se nao, um romano sequencial (mesma convencao do kicker).
    local any_numbered = false
    for _, item in ipairs(el.content) do
      if extract_toc_number(stringify(item)) then
        any_numbered = true
      end
    end

    local blocks = { pandoc.RawBlock('latex', '\\begin{sbtoc}') }
    for i, item in ipairs(el.content) do
      local inlines = item_inlines(item)
      local num, plen = extract_toc_number(stringify(item))
      local gutter
      if num then
        gutter = num
        inlines = drop_prefix(inlines, plen)
      elseif not any_numbered then
        -- Arabico, igual ao contador sequencial do kicker (ver
        -- inject_chapter_kickers): as subsecoes sao "3.1" e um "III" na
        -- goteira poria dois sistemas de numeracao no mesmo documento.
        gutter = tostring(i)
      else
        gutter = ''
      end
      local cmd = (i == #el.content) and '\\sbtocopenlast' or '\\sbtocopen'
      -- Abre o comando, despeja os inlines ORIGINAIS (math/enfase intactos)
      -- e fecha. Nada de stringify aqui.
      table.insert(blocks, pandoc.RawBlock('latex', cmd .. '{' .. lescape(gutter) .. '}{%'))
      table.insert(blocks, pandoc.Plain(inlines))
      table.insert(blocks, pandoc.RawBlock('latex', '}%'))
    end
    table.insert(blocks, pandoc.RawBlock('latex', '\\end{sbtoc}'))
    return blocks
  end
  return nil
end

-- ------------------------------------------------------------------
-- Div: internal markers + external environments
-- ------------------------------------------------------------------

function Div(el)
  if has_class(el, 'box-badge') then
    return { pandoc.RawBlock('latex',
      '\\wbbadge{' .. lescape(stringify(el)) .. '}%') }
  end
  if has_class(el, 'box-title') then
    return { pandoc.RawBlock('latex',
      '\\wbtitle{' .. lescape(stringify(el)) .. '}%') }
  end
  if has_class(el, 'card-name') then
    return { pandoc.RawBlock('latex',
      '\\cardname{' .. lescape(stringify(el)) .. '}%') }
  end
  if has_class(el, 'card-meta') then
    return { pandoc.RawBlock('latex',
      '\\cardmeta{' .. lescape(stringify(el)) .. '}%') }
  end

  if has_class(el, 'box-verdict') then
    local out = { pandoc.RawBlock('latex',
      '\\vspace{4pt}\\par\\hrule height 0.4pt\\vspace{5pt}\\begingroup\\small%') }
    for _, b in ipairs(el.content) do table.insert(out, b) end
    table.insert(out, pandoc.RawBlock('latex', '\\endgroup%'))
    return out
  end

  if has_class(el, 'pq-cite') then
    return {
      pandoc.RawBlock('latex',
        '\\par\\vspace{2pt}\\noindent{\\upshape\\footnotesize\\color{subtlegray}' .. lescape(stringify(el)) .. '}%')
    }
  end

  if has_class(el, 'label-solo') then
    return { pandoc.RawBlock('latex',
      '\\parahead{' .. lescape(stringify(el)) .. '}') }
  end

  if has_class(el, 'box') then
    local color = get_box_color(el)
    local out = { pandoc.RawBlock('latex',
      '\\begin{wikibox}{' .. color .. '}%') }
    for _, b in ipairs(el.content) do table.insert(out, b) end
    table.insert(out, pandoc.RawBlock('latex', '\\end{wikibox}%'))
    return out
  end
  if has_class(el, 'quote') then
    local out = { pandoc.RawBlock('latex', '\\begin{wikiquote}%') }
    for _, b in ipairs(el.content) do table.insert(out, b) end
    table.insert(out, pandoc.RawBlock('latex', '\\end{wikiquote}%'))
    return out
  end
  if has_class(el, 'pull-quote') then
    local out = { pandoc.RawBlock('latex', '\\begin{wikipull}%') }
    for _, b in ipairs(el.content) do table.insert(out, b) end
    table.insert(out, pandoc.RawBlock('latex', '\\end{wikipull}%'))
    return out
  end
  if has_class(el, 'card') then
    local out = { pandoc.RawBlock('latex', '\\begin{wikicard}%') }
    for _, b in ipairs(el.content) do table.insert(out, b) end
    table.insert(out, pandoc.RawBlock('latex', '\\end{wikicard}%'))
    return out
  end

  return nil
end

-- ------------------------------------------------------------------
-- Para: figure centering, references wrapping, styled captions
-- ------------------------------------------------------------------

function Para(el)
  -- 1) Paragraph contains an Image (standalone or with inline caption text)
  local has_image = false
  for _, inl in ipairs(el.content) do
    if inl.t == 'Image' then
      has_image = true
      break
    end
  end

  if has_image then
    local images = {}
    local rest = {}
    for _, inl in ipairs(el.content) do
      if inl.t == 'Image' then
        table.insert(images, inl)
      else
        table.insert(rest, inl)
      end
    end
    -- Sem glue entre as imagens o LaTeX nao tem onde quebrar a linha, e um
    -- grupo de figuras lado a lado estoura a margem direita em vez de passar
    -- para a linha seguinte. Um Space entre elas da o ponto de quebra.
    local espacadas = {}
    for idx, im in ipairs(images) do
      if idx > 1 then
        table.insert(espacadas, pandoc.Space())
      end
      table.insert(espacadas, im)
    end
    local blocks = {
      pandoc.RawBlock('latex', '\\begin{center}%'),
      pandoc.Para(espacadas),
    }
    if #rest > 0 then
      local rest_text = stringify(pandoc.Para(rest)):gsub('^%s+', ''):gsub('%s+$', '')
      if rest_text ~= '' then
        table.insert(blocks, pandoc.RawBlock('latex', '\\vspace{-4pt}\\begingroup\\small%'))
        table.insert(blocks, pandoc.Para(rest))
        table.insert(blocks, pandoc.RawBlock('latex', '\\endgroup%'))
      end
    end
    table.insert(blocks, pandoc.RawBlock('latex', '\\end{center}%'))
    return blocks
  end

  -- 2) References handling
  if in_references then
    -- O "Link" no fim de cada referencia e um pandoc.Link (t == 'Link'),
    -- nao um Str. A palavra fica (decisao do autor) e ganha UMA seta
    -- discreta ao lado. Os demais links da citacao (o titulo da obra, um
    -- termo no comentario) nao recebem seta nenhuma — antes cada um
    -- ganhava a sua e a referencia terminava com duas ou tres.
    local new_content = {}
    for _, inl in ipairs(el.content) do
      if inl.t == 'Link' and stringify(inl) == 'Link' then
        inl.content = {
          pandoc.Str('Link'),
          pandoc.RawInline('latex', '\\,\\textup{\\scriptsize↗}'),
        }
      end
      table.insert(new_content, inl)
    end
    return {
      pandoc.RawBlock('latex', '\\begin{sbrefitem}%'),
      pandoc.Plain(new_content),
      pandoc.RawBlock('latex', '\\end{sbrefitem}%'),
    }
  end

  -- 3) Standalone figure caption paragraph (e.g. "*Figura 1 — ...*")
  local text = stringify(el)
  if text:match('^Fig%.%s*%d') or text:match('^Figura%s+%d') then
    local out = {}
    local found_fig = false
    for _, inl in ipairs(el.content) do
      if inl.t == 'Str' and not found_fig then
        local fig_num = inl.text:match('^(Fig%.?%s*%d+)')
        if fig_num then
          table.insert(out, pandoc.RawInline('latex',
            '{\\color{sbink}\\textbf{' .. fig_num .. '}}'))
          local rest_str = inl.text:sub(#fig_num + 1)
          if rest_str ~= '' then
            table.insert(out, pandoc.Str(rest_str))
          end
          found_fig = true
        else
          table.insert(out, inl)
        end
      else
        table.insert(out, inl)
      end
    end
    return {
      pandoc.RawBlock('latex', '\\begin{center}\\vspace{-6pt}\\small%'),
      pandoc.Para(out),
      pandoc.RawBlock('latex', '\\end{center}%'),
    }
  end

  return nil
end

-- ------------------------------------------------------------------
-- RawBlock: ornament glyphs from HTML
-- ------------------------------------------------------------------

function RawBlock(el)
  if el.format == 'html' then
    local glyph = el.text:match('^<div class="ornament">(.-)</div>%s*$')
    if glyph then
      return { pandoc.RawBlock('latex',
        '\\begin{center}\\color{subtlegray}\\ornamentglyph{' ..
        lescape(glyph) .. '}\\end{center}') }
    end
  end
  return nil
end

-- ------------------------------------------------------------------
-- Table: larguras de coluna proporcionais, com piso na palavra mais longa
-- ------------------------------------------------------------------

-- Largura VISUAL aproximada, em unidades de "caractere medio".
--
-- Contar bytes (`#s`) dava 2 para cada letra acentuada e inflava toda coluna em
-- portugues. Contar caracteres corrige isso, mas ainda trata "Ordem" e "iiiii"
-- como iguais — e foi por isso que a coluna "Ordem" saia estreita demais e
-- quebrava em "Or-/dem". Aqui maiuscula e letra larga pesam mais que a media, e
-- letra estreita pesa menos.
local WIDE = { M = 1.7, W = 1.8, m = 1.6, w = 1.4 }
local NARROW = { i = 0.45, l = 0.45, j = 0.5, t = 0.6, f = 0.6, r = 0.6,
                 I = 0.6, ['.'] = 0.5, [','] = 0.5, [' '] = 0.5,
                 ['('] = 0.6, [')'] = 0.6, ['-'] = 0.6 }

local function ulen(s)
  local n = 0
  for ch in s:gmatch('[%z\1-\127\194-\244][\128-\191]*') do
    if WIDE[ch] then n = n + WIDE[ch]
    elseif NARROW[ch] then n = n + NARROW[ch]
    elseif ch:match('%u') then n = n + 1.35
    else n = n + 1.0 end
  end
  return n
end

-- Maior palavra da celula. E o piso duro da coluna: um nome proprio longo
-- ("Kolmogorov-Smirnov") dentro de um link nao tem onde quebrar, e numa coluna
-- estreita demais ele simplesmente transborda por cima da coluna vizinha.
local function longest_word(s)
  local m = 0
  for w in s:gmatch('%S+') do
    local l = ulen(w)
    if l > m then m = l end
  end
  return m
end

function Table(el)
  local num_cols = #el.colspecs
  if num_cols == 0 then return el end

  local pref = {}   -- largura desejada (maior celula)
  local floor_ = {} -- largura minima (maior palavra)
  for i = 1, num_cols do pref[i] = 0; floor_[i] = 0 end

  local function scan(row)
    for c, cell in ipairs(row.cells) do
      if c <= num_cols then
        local s = pandoc.utils.stringify(cell.contents)
        local l, w = ulen(s), longest_word(s)
        if l > pref[c] then pref[c] = l end
        if w > floor_[c] then floor_[c] = w end
      end
    end
  end

  if el.head and el.head.rows then
    for _, row in ipairs(el.head.rows) do scan(row) end
  end
  for _, body in ipairs(el.bodies) do
    for _, row in ipairs(body.body) do scan(row) end
  end

  -- Capacidade da linha em \small: a mancha tem 172 mm, o Pandoc ja desconta
  -- 2*	abcolsep por coluna, e sobram cerca de 90 caracteres. E a escala comum
  -- entre piso e preferencia — subestimar aqui aperta as colunas e faz o piso
  -- perder a disputa, que era exatamente o defeito da versao anterior.
  local CAP = 90

  -- Uma celula muito longa nao deve engolir a tabela: acima de 55 caracteres o
  -- texto ja vai quebrar em varias linhas de qualquer forma.
  local total_pref = 0
  for i = 1, num_cols do
    pref[i] = math.max(math.min(pref[i], 55), 4)
    -- Pequena folga sobre o piso: `vislen` e estimativa, nao medicao.
    floor_[i] = math.max(floor_[i] * 1.15, 3)
    total_pref = total_pref + pref[i]
  end

  -- Reparticao: distribui CAP proporcionalmente a `pref`, eleva ao piso quem
  -- ficou abaixo dele, e redistribui o que sobra entre as colunas ainda
  -- livres. Repete ate estabilizar (no maximo uma vez por coluna).
  local w, fixed = {}, {}
  for i = 1, num_cols do w[i] = CAP * pref[i] / total_pref; fixed[i] = false end

  for _ = 1, num_cols do
    local restante, soma_livre, mudou = CAP, 0, false
    for i = 1, num_cols do
      if not fixed[i] and w[i] < floor_[i] then
        w[i] = floor_[i]; fixed[i] = true; mudou = true
      end
    end
    if not mudou then break end
    for i = 1, num_cols do
      if fixed[i] then restante = restante - w[i] else soma_livre = soma_livre + pref[i] end
    end
    if restante <= 0 or soma_livre <= 0 then break end
    for i = 1, num_cols do
      if not fixed[i] then w[i] = restante * pref[i] / soma_livre end
    end
  end

  local total = 0
  for i = 1, num_cols do total = total + w[i] end

  local new_colspecs = {}
  for i = 1, num_cols do
    new_colspecs[i] = { el.colspecs[i][1], w[i] / total }
  end
  el.colspecs = new_colspecs
  return el
end
