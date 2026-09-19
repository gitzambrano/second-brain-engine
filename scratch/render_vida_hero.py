import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
import math

HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      width: 1920px;
      height: 1080px;
      background: #060b14;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    canvas {
      width: 1920px;
      height: 1080px;
    }
  </style>
</head>
<body>
  <canvas id="c" width="1920" height="1080"></canvas>
  <script>
    const canvas = document.getElementById('c');
    const ctx = canvas.getContext('2d');

    // Deep space gradient
    const bg = ctx.createRadialGradient(960, 540, 50, 960, 540, 1100);
    bg.addColorStop(0, '#0f1f38');
    bg.addColorStop(0.4, '#091326');
    bg.addColorStop(0.8, '#050a14');
    bg.addColorStop(1, '#02050a');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, 1920, 1080);

    // Subtle background mesh / grid of entropy
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.04)';
    ctx.lineWidth = 1;
    for (let x = 0; x <= 1920; x += 60) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, 1080);
      ctx.stroke();
    }
    for (let y = 0; y <= 1080; y += 60) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(1920, y);
      ctx.stroke();
    }

    // Outer chaotic particles (Entropy)
    const seed = 42;
    function pseudoRandom(s) {
      let x = Math.sin(s++) * 10000;
      return x - Math.floor(x);
    }
    let rIdx = 1;
    for (let i = 0; i < 400; i++) {
      let px = pseudoRandom(rIdx++) * 1920;
      let py = pseudoRandom(rIdx++) * 1080;
      let dist = Math.hypot(px - 960, py - 540);
      let pSize = pseudoRandom(rIdx++) * 2.5 + 0.5;
      let alpha = Math.min(0.6, Math.max(0.05, (dist / 800) * 0.4));
      ctx.fillStyle = `rgba(148, 163, 184, ${alpha})`;
      ctx.beginPath();
      ctx.arc(px, py, pSize, 0, Math.PI * 2);
      ctx.fill();
    }

    // Markov Blanket Boundary (Concentric glowing organic membrane)
    const cx = 960, cy = 540;
    
    // Outer ambient glow
    const outerGlow = ctx.createRadialGradient(cx, cy, 200, cx, cy, 450);
    outerGlow.addColorStop(0, 'rgba(45, 212, 191, 0.15)');
    outerGlow.addColorStop(0.5, 'rgba(56, 189, 248, 0.08)');
    outerGlow.addColorStop(1, 'rgba(2, 6, 23, 0)');
    ctx.fillStyle = outerGlow;
    ctx.beginPath();
    ctx.arc(cx, cy, 450, 0, Math.PI * 2);
    ctx.fill();

    // Multi-layered organic boundary (representing autopoietic self-containment)
    for (let layer = 0; layer < 6; layer++) {
      let baseR = 300 + layer * 18;
      ctx.beginPath();
      let steps = 180;
      for (let s = 0; s <= steps; s++) {
        let theta = (s / steps) * Math.PI * 2;
        let wobble = Math.sin(theta * 6 + layer) * 12 + Math.cos(theta * 10 - layer * 2) * 8;
        let r = baseR + wobble;
        let x = cx + Math.cos(theta) * r;
        let y = cy + Math.sin(theta) * r;
        if (s === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = `rgba(56, 189, 248, ${0.15 + (5 - layer) * 0.1})`;
      ctx.lineWidth = 2.5;
      ctx.stroke();
    }

    // Phospholipid-like bilayer nodes along the perimeter
    let membraneSteps = 72;
    for (let s = 0; s < membraneSteps; s++) {
      let theta = (s / membraneSteps) * Math.PI * 2;
      let wobble = Math.sin(theta * 6) * 12 + Math.cos(theta * 10) * 8;
      let r1 = 305 + wobble;
      let r2 = 390 + wobble;
      let x1 = cx + Math.cos(theta) * r1;
      let y1 = cy + Math.sin(theta) * r1;
      let x2 = cx + Math.cos(theta) * r2;
      let y2 = cy + Math.sin(theta) * r2;

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = 'rgba(45, 212, 191, 0.4)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(x1, y1, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#38bdf8';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(x2, y2, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#34d399';
      ctx.fill();
    }

    // Core Interior: Highly organized crystalline / metabolic network (Negentropy)
    const innerNodes = [];
    const numInner = 28;
    for (let i = 0; i < numInner; i++) {
      let angle = (i / numInner) * Math.PI * 2 + Math.sin(i) * 0.3;
      let dist = 60 + Math.sqrt(i / numInner) * 200;
      let nx = cx + Math.cos(angle) * dist;
      let ny = cy + Math.sin(angle) * dist;
      innerNodes.push({x: nx, y: ny, id: i});
    }

    // Connect interior nodes with delicate glowing edges (metabolic graph)
    ctx.lineWidth = 1.8;
    for (let i = 0; i < innerNodes.length; i++) {
      for (let j = i + 1; j < innerNodes.length; j++) {
        let d = Math.hypot(innerNodes[i].x - innerNodes[j].x, innerNodes[i].y - innerNodes[j].y);
        if (d < 120) {
          let edgeGrad = ctx.createLinearGradient(innerNodes[i].x, innerNodes[i].y, innerNodes[j].x, innerNodes[j].y);
          edgeGrad.addColorStop(0, 'rgba(56, 189, 248, 0.5)');
          edgeGrad.addColorStop(1, 'rgba(52, 211, 153, 0.5)');
          ctx.strokeStyle = edgeGrad;
          ctx.beginPath();
          ctx.moveTo(innerNodes[i].x, innerNodes[i].y);
          ctx.lineTo(innerNodes[j].x, innerNodes[j].y);
          ctx.stroke();
        }
      }
    }

    // Draw organized nodes
    for (let n of innerNodes) {
      let nGrad = ctx.createRadialGradient(n.x, n.y, 1, n.x, n.y, 12);
      nGrad.addColorStop(0, '#ffffff');
      nGrad.addColorStop(0.3, '#38bdf8');
      nGrad.addColorStop(1, 'rgba(56, 189, 248, 0)');
      ctx.fillStyle = nGrad;
      ctx.beginPath();
      ctx.arc(n.x, n.y, 10, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#e0f2fe';
      ctx.beginPath();
      ctx.arc(n.x, n.y, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    // Central glowing nucleus / source of order
    const coreGrad = ctx.createRadialGradient(cx, cy, 5, cx, cy, 80);
    coreGrad.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
    coreGrad.addColorStop(0.2, 'rgba(56, 189, 248, 0.8)');
    coreGrad.addColorStop(0.6, 'rgba(16, 185, 129, 0.3)');
    coreGrad.addColorStop(1, 'rgba(2, 6, 23, 0)');
    ctx.fillStyle = coreGrad;
    ctx.beginPath();
    ctx.arc(cx, cy, 80, 0, Math.PI * 2);
    ctx.fill();

    // Geometric radial rays of order cutting through the membrane
    ctx.lineWidth = 1;
    for (let k = 0; k < 12; k++) {
      let a = (k / 12) * Math.PI * 2;
      ctx.strokeStyle = 'rgba(240, 249, 255, 0.2)';
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * 40, cy + Math.sin(a) * 40);
      ctx.lineTo(cx + Math.cos(a) * 420, cy + Math.sin(a) * 420);
      ctx.stroke();
    }
  </script>
</body>
</html>
"""

async def main():
    html_file = Path("substack/assets/o_que_e_vida_hero.html")
    html_file.parent.mkdir(parents=True, exist_ok=True)
    html_file.write_text(HTML_CONTENT, encoding="utf-8")
    
    img_path = Path("substack/assets/o_que_e_vida_hero.png")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto(html_file.resolve().as_uri())
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(img_path))
        await browser.close()
    
    print(f"[OK] Hero cover gerada em: {img_path}")

if __name__ == "__main__":
    asyncio.run(main())
