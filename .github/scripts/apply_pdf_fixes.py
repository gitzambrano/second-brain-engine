from pathlib import Path

lua_path = Path('scripts/pdf_boxes.lua')
lua = lua_path.read_text(encoding='utf-8')

marker = "function Link(el)\n"
helper = r'''-- Referencias podem conter DOI/URL como texto visivel, fora de um Link.
-- Esses tokens nao tem espacos e o TeX nao cria pontos de quebra em `/`, `:`
-- ou `.` por conta propria. Insere apenas discretionary breaks invisiveis em
-- identificadores longos com estrutura de URL/DOI; o texto impresso nao muda.
local REF_BREAK_SEP = '[:/._%-]'

local function break_reference_tokens(inlines)
  local out = {}
  for _, inl in ipairs(inlines) do
    if inl.t == 'Str' and #inl.text >= 22 and inl.text:find('[:/]') then
      local text = inl.text
      local pos = 1
      while pos <= #text do
        local s, e = text:find(REF_BREAK_SEP, pos)
        if not s then
          table.insert(out, pandoc.Str(text:sub(pos)))
          break
        end
        table.insert(out, pandoc.Str(text:sub(pos, e)))
        table.insert(out, pandoc.RawInline('latex', '\\allowbreak{}'))
        pos = e + 1
      end
    elseif inl.content then
      inl.content = break_reference_tokens(inl.content)
      table.insert(out, inl)
    else
      table.insert(out, inl)
    end
  end
  return out
end

'''
if helper not in lua:
    if lua.count(marker) != 1:
        raise SystemExit(f'Link marker count={lua.count(marker)}')
    lua = lua.replace(marker, helper + marker, 1)

old_ref = """      table.insert(new_content, inl)\n    end\n    return {\n      pandoc.RawBlock('latex', '\\\\begin{sbrefitem}%'),\n"""
new_ref = """      table.insert(new_content, inl)\n    end\n    new_content = break_reference_tokens(new_content)\n    return {\n      pandoc.RawBlock('latex', '\\\\begin{sbrefitem}%'),\n"""
if old_ref in lua:
    lua = lua.replace(old_ref, new_ref, 1)
elif "new_content = break_reference_tokens(new_content)" not in lua:
    raise SystemExit('reference insertion anchor missing')

old_floor = "floor_[i] = math.max(floor_[i] * 1.15, 3)"
new_floor = "floor_[i] = math.max(floor_[i] * 1.30, 3)"
if old_floor in lua:
    lua = lua.replace(old_floor, new_floor, 1)
elif new_floor not in lua:
    raise SystemExit('table floor anchor missing')

old_comment = '''-- Maior palavra da celula. E o piso duro da coluna: um nome proprio longo
-- ("Kolmogorov-Smirnov") dentro de um link nao tem onde quebrar, e numa coluna
-- estreita demais ele simplesmente transborda por cima da coluna vizinha.
'''
new_comment = '''-- Maior palavra da celula. E o piso duro da coluna: um nome proprio longo
-- ("Kolmogorov-Smirnov") dentro de um link nao tem onde quebrar, e numa coluna
-- estreita demais ele simplesmente transborda por cima da coluna vizinha. A
-- folga de 30% cobre largura real da fonte, padding e erro do estimador visual;
-- 15% ainda cortava a ultima letra de headers portugueses como "Extrapolacao".
'''
if old_comment in lua:
    lua = lua.replace(old_comment, new_comment, 1)

lua_path.write_text(lua, encoding='utf-8')

test_path = Path('tests/test_visual_export_regressions.py')
test = test_path.read_text(encoding='utf-8')
anchor = '''def test_pdf_table_headers_prevent_hyphenation_before_breaking_words():
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert r"\\\\hyphenpenalty=10000\\\\exhyphenpenalty=10000\\\\raggedright" in lua


'''
addition = anchor + '''def test_pdf_reference_tokens_get_discretionary_breaks():
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert "local function break_reference_tokens(inlines)" in lua
    assert "new_content = break_reference_tokens(new_content)" in lua
    assert r"\\\\allowbreak{}" in lua


def test_pdf_table_word_floor_has_real_font_and_padding_margin():
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert "floor_[i] = math.max(floor_[i] * 1.30, 3)" in lua


'''
if "def test_pdf_reference_tokens_get_discretionary_breaks():" not in test:
    if test.count(anchor) != 1:
        raise SystemExit(f'test anchor count={test.count(anchor)}')
    test = test.replace(anchor, addition, 1)
    test_path.write_text(test, encoding='utf-8')
