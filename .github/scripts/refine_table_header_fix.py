from pathlib import Path

lua_path = Path('scripts/pdf_boxes.lua')
lua = lua_path.read_text(encoding='utf-8')
old = "if total_floor > CAP and el.head and el.head.rows then"
new = "if (num_cols >= 6 or total_floor > CAP) and el.head and el.head.rows then"
if old in lua:
    lua = lua.replace(old, new, 1)
elif new not in lua:
    raise SystemExit('wide-table header condition anchor missing')
lua_path.write_text(lua, encoding='utf-8')

test_path = Path('tests/test_visual_export_regressions.py')
test = test_path.read_text(encoding='utf-8')
test = test.replace(
    'assert "if total_floor > CAP and el.head and el.head.rows then" in lua',
    'assert "if (num_cols >= 6 or total_floor > CAP) and el.head and el.head.rows then" in lua',
)
if 'if (num_cols >= 6 or total_floor > CAP) and el.head and el.head.rows then' not in test:
    raise SystemExit('test condition was not updated')
test_path.write_text(test, encoding='utf-8')
