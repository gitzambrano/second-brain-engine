from pathlib import Path

exp_path = Path('scripts/export_essay_pdf.py')
exp = exp_path.read_text(encoding='utf-8')
old = r'''\AtBeginEnvironment{longtable}{%
  \small
  \setlength{\emergencystretch}{3em}%
  \hyphenpenalty=50\exhyphenpenalty=50%
  \setlength{\tabcolsep}{5pt}%
  \renewcommand{\arraystretch}{1.25}%
}'''
new = r'''\newlength{\sbtablecolsep}
\setlength{\sbtablecolsep}{5pt}
\AtBeginEnvironment{longtable}{%
  \small
  \setlength{\emergencystretch}{3em}%
  \hyphenpenalty=50\exhyphenpenalty=50%
  \setlength{\tabcolsep}{\sbtablecolsep}%
  \renewcommand{\arraystretch}{1.25}%
}'''
if old in exp:
    exp = exp.replace(old, new, 1)
elif new not in exp:
    raise SystemExit('longtable tabcolsep anchor missing')
exp_path.write_text(exp, encoding='utf-8')

lua_path = Path('scripts/pdf_boxes.lua')
lua = lua_path.read_text(encoding='utf-8')
old_tail = '''  if (num_cols >= 6 or total_floor > CAP) and el.head and el.head.rows then
    for _, row in ipairs(el.head.rows) do
      for _, cell in ipairs(row.cells) do
        local compact = pandoc.RawInline('latex', '\\\\footnotesize{}')
        if cell.contents and #cell.contents > 0
           and (cell.contents[1].t == 'Plain' or cell.contents[1].t == 'Para') then
          table.insert(cell.contents[1].content, 1, compact)
        else
          table.insert(cell.contents, 1, pandoc.Plain({compact}))
        end
      end
    end
  end
  return el
end'''
new_tail = '''  if (num_cols >= 6 or total_floor > CAP) and el.head and el.head.rows then
    for _, row in ipairs(el.head.rows) do
      for _, cell in ipairs(row.cells) do
        local compact = pandoc.RawInline('latex', '\\\\footnotesize{}')
        if cell.contents and #cell.contents > 0
           and (cell.contents[1].t == 'Plain' or cell.contents[1].t == 'Para') then
          table.insert(cell.contents[1].content, 1, compact)
        else
          table.insert(cell.contents, 1, pandoc.Plain({compact}))
        end
      end
    end
  end

  -- Tabelas largas perdem uma parcela grande da largura em padding: com sete
  -- colunas, 5pt por lado consomem 70pt antes de uma unica letra. Reduzir esse
  -- padding apenas a partir de seis colunas devolve 4pt de largura util a cada
  -- celula, sem encolher o texto nem afetar tabelas comuns. O grupo limita a
  -- mudanca a esta longtable; \n-- \AtBeginEnvironment usa \sbtablecolsep ao abrir o ambiente.
  if num_cols >= 6 then
    return {
      pandoc.RawBlock('latex', '\\\\begingroup\\\\setlength{\\\\sbtablecolsep}{3pt}%'),
      el,
      pandoc.RawBlock('latex', '\\\\endgroup%'),
    }
  end
  return el
end'''
if old_tail in lua:
    lua = lua.replace(old_tail, new_tail, 1)
elif 'sbtablecolsep' not in lua:
    raise SystemExit('Table tail anchor missing')
lua_path.write_text(lua, encoding='utf-8')

test_path = Path('tests/test_visual_export_regressions.py')
test = test_path.read_text(encoding='utf-8')
anchor = '''def test_pdf_table_word_floor_has_real_font_and_padding_margin():
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert "floor_[i] = math.max(floor_[i] * 1.30, 3)" in lua


'''
addition = anchor + '''def test_wide_pdf_tables_reduce_padding_without_affecting_normal_tables():
    exporter = (SCRIPTS / "export_essay_pdf.py").read_text(encoding="utf-8")
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert r"\\newlength{\\sbtablecolsep}" in exporter
    assert r"\\setlength{\\sbtablecolsep}{5pt}" in exporter
    assert r"\\setlength{\\tabcolsep}{\\sbtablecolsep}" in exporter
    assert "if num_cols >= 6 then" in lua
    assert r"\\\\setlength{\\\\sbtablecolsep}{3pt}" in lua


'''
if 'def test_wide_pdf_tables_reduce_padding_without_affecting_normal_tables():' not in test:
    if test.count(anchor) != 1:
        raise SystemExit(f'test anchor count={test.count(anchor)}')
    test = test.replace(anchor, addition, 1)
    test_path.write_text(test, encoding='utf-8')
