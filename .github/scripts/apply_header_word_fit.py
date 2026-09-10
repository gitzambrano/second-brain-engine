from pathlib import Path

exp_path = Path('scripts/export_essay_pdf.py')
exp = exp_path.read_text(encoding='utf-8')
anchor = r'''\newcommand{\sbfit}[1]{%
  \resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{$\displaystyle #1$}}
'''
addition = anchor + r'''
% Mesmo principio para palavras de cabecalho de tabela: mede na fonte corrente
% e so encolhe se a palavra realmente ultrapassar a largura util da celula.
% Diferente de reduzir o cabecalho inteiro, preserva legibilidade e permite
% quebra normal entre palavras como "Poder Filosofico".
\newcommand{\sbfittext}[1]{%
  \resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{#1}}
'''
if r'\newcommand{\sbfittext}' not in exp:
    if exp.count(anchor) != 1:
        raise SystemExit(f'sbfit anchor count={exp.count(anchor)}')
    exp = exp.replace(anchor, addition, 1)
exp_path.write_text(exp, encoding='utf-8')

lua_path = Path('scripts/pdf_boxes.lua')
lua = lua_path.read_text(encoding='utf-8')
marker = 'function Table(el)\n'
helper = r'''-- Mantem cada palavra do cabecalho dentro da largura REAL de sua celula.
-- RawInline abre/fecha a macro ao redor do Str; wrappers como Strong continuam
-- por fora, portanto a medicao usa exatamente a fonte/peso que sera impressa.
local function fit_header_words(inlines)
  local out = {}
  for _, inl in ipairs(inlines) do
    if inl.t == 'Str' then
      table.insert(out, pandoc.RawInline('latex', '\\sbfittext{'))
      table.insert(out, inl)
      table.insert(out, pandoc.RawInline('latex', '}'))
    elseif inl.content then
      inl.content = fit_header_words(inl.content)
      table.insert(out, inl)
    else
      table.insert(out, inl)
    end
  end
  return out
end

'''
if 'local function fit_header_words(inlines)' not in lua:
    if lua.count(marker) != 1:
        raise SystemExit(f'Table marker count={lua.count(marker)}')
    lua = lua.replace(marker, helper + marker, 1)

needle = '  if (num_cols >= 6 or total_floor > CAP) and el.head and el.head.rows then\n'
replacement = '''  -- Tabela larga: garante por medicao TeX que nenhuma palavra de cabecalho
  -- invade a celula vizinha. Palavras que ja cabem conservam tamanho natural.
  if num_cols >= 6 and el.head and el.head.rows then
    for _, row in ipairs(el.head.rows) do
      for _, cell in ipairs(row.cells) do
        for _, block in ipairs(cell.contents or {}) do
          if block.content then block.content = fit_header_words(block.content) end
        end
      end
    end
  end

  -- O passo menor de fonte fica apenas como fallback para tabelas cujo piso
  -- de palavras, mesmo medido, excede a capacidade total.
  if total_floor > CAP and el.head and el.head.rows then
'''
if needle in lua:
    lua = lua.replace(needle, replacement, 1)
elif 'block.content = fit_header_words(block.content)' not in lua:
    raise SystemExit('wide header condition anchor missing')
lua_path.write_text(lua, encoding='utf-8')

test_path = Path('tests/test_visual_export_regressions.py')
test = test_path.read_text(encoding='utf-8')
test = test.replace(
    'assert "if (num_cols >= 6 or total_floor > CAP) and el.head and el.head.rows then" in lua',
    'assert "if total_floor > CAP and el.head and el.head.rows then" in lua',
)
anchor_t = '''def test_wide_pdf_tables_reduce_padding_without_affecting_normal_tables():
    exporter = (SCRIPTS / "export_essay_pdf.py").read_text(encoding="utf-8")
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert r"\\newlength{\\sbtablecolsep}" in exporter
    assert r"\\setlength{\\sbtablecolsep}{5pt}" in exporter
    assert r"\\setlength{\\tabcolsep}{\\sbtablecolsep}" in exporter
    assert "if num_cols >= 6 then" in lua
    assert r"\\\\setlength{\\\\sbtablecolsep}{3pt}" in lua


'''
addition_t = anchor_t + '''def test_wide_pdf_table_header_words_are_measured_and_fit_to_cell():
    exporter = (SCRIPTS / "export_essay_pdf.py").read_text(encoding="utf-8")
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert r"\\newcommand{\\sbfittext}" in exporter
    assert "local function fit_header_words(inlines)" in lua
    assert "block.content = fit_header_words(block.content)" in lua
    assert "if num_cols >= 6 and el.head and el.head.rows then" in lua


'''
if 'def test_wide_pdf_table_header_words_are_measured_and_fit_to_cell():' not in test:
    if test.count(anchor_t) != 1:
        raise SystemExit(f'wide-table test anchor count={test.count(anchor_t)}')
    test = test.replace(anchor_t, addition_t, 1)
test_path.write_text(test, encoding='utf-8')
