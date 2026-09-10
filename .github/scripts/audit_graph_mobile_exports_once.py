from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_graph  # noqa: E402
from lib.build_public_map import with_public_chrome  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

nodes = [
    {"id":"essay:a","title":"Alpha","type":"essay","tags":[],"degree":1,"sizeBytes":100,"sizeLines":10,"x0":-50,"y0":0,"x":-50,"y":0,"htmlFile":None,"url":None,"public":False},
    {"id":"concept:b","title":"Beta","type":"concept","tags":[],"degree":2,"sizeBytes":80,"sizeLines":8,"x0":0,"y0":25,"x":0,"y":25,"htmlFile":None,"url":None,"public":False},
    {"id":"entity:c","title":"Gamma","type":"entity","tags":[],"degree":1,"sizeBytes":60,"sizeLines":6,"x0":50,"y0":0,"x":50,"y":0,"htmlFile":None,"url":None,"public":False},
]
edges = [
    {"source":"essay:a","target":"concept:b","kind":"wikilink"},
    {"source":"concept:b","target":"entity:c","kind":"wikilink"},
]
html = build_graph.render_html(nodes, edges, [], {"essays":{}, "mathjax":"", "css":""})
html = with_public_chrome(html, "graph")

out = ROOT / "visual-audit"
out.mkdir(exist_ok=True)
page_path = out / "graph-fixture.html"
page_path.write_text(html, encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width":390,"height":844}, device_scale_factor=1, accept_downloads=True)
    page.goto(page_path.as_uri(), wait_until="load")
    page.wait_for_selector("#graph")
    page.wait_for_selector("#sb-map-switch")
    page.wait_for_function("document.querySelectorAll('#sb-map-switch a').length === 2 && !!document.querySelector('#sb-theme')")
    page.wait_for_timeout(500)

    controls = page.evaluate("""() => {
      const els = document.querySelectorAll('#sb-map-switch a');
      const box = el => {
        if (!el) throw new Error('missing control');
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return {x:r.x,y:r.y,w:r.width,h:r.height,display:s.display,align:s.alignItems,justify:s.justifyContent,font:s.fontSize,line:s.lineHeight,text:el.textContent.trim()};
      };
      return {graph:box(els[0]), globe:box(els[1]), theme:box(document.querySelector('#sb-theme'))};
    }""")
    assert controls["graph"]["text"] == "Grafo", controls
    assert controls["globe"]["text"] == "Globo", controls
    for name in ("graph", "globe"):
        c = controls[name]
        assert abs(c["h"] - 36) < 0.1, (name, c)
        assert c["display"] == "flex", (name, c)
        assert c["align"] == "center" and c["justify"] == "center", (name, c)
        assert c["line"] == "13px", (name, c)
    assert abs(controls["theme"]["w"] - 36) < 0.1 and abs(controls["theme"]["h"] - 36) < 0.1, controls["theme"]
    assert controls["theme"]["font"] == "21px", controls["theme"]

    shown = page.evaluate("""() => { labelsShown=false; updateLabelVisibility(0.61); const before=labelsShown; updateLabelVisibility(0.62); return {before, after:labelsShown}; }""")
    assert shown == {"before": False, "after": True}, shown

    page.locator("#sb-map-switch").screenshot(path=str(out / "graph-mobile-controls.png"))

    with page.expect_download(timeout=10000) as dl_info:
        page.locator("#btn-export-png").click()
    png_path = out / "graph-export-test.png"
    dl_info.value.save_as(str(png_path))
    assert png_path.stat().st_size > 1000, png_path.stat().st_size

    with page.expect_download(timeout=10000) as dl_info:
        page.locator("#btn-export-svg").click()
    svg_path = out / "graph-export-test.svg"
    dl_info.value.save_as(str(svg_path))
    svg_text = svg_path.read_text(encoding="utf-8")
    root = ET.fromstring(svg_text)
    assert root.tag.endswith("svg")
    assert any(el.tag.endswith("circle") for el in root.iter())
    assert any(el.tag.endswith("line") for el in root.iter())

    browser.close()

print("browser audit PASS", controls, shown, png_path.stat().st_size, svg_path.stat().st_size)
