import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      width: 1920px;
      height: 1080px;
      background: #050a14;
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

    // Deep cosmic gradient
    const bg = ctx.createRadialGradient(960, 540, 100, 960, 540, 1100);
    bg.addColorStop(0, '#0d1a33');
    bg.addColorStop(0.5, '#081021');
    bg.addColorStop(0.8, '#040812');
    bg.addColorStop(1, '#020408');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, 1920, 1080);

    // Subtle isometric/perspective grid representing the hypothetical landscape
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.05)';
    ctx.lineWidth = 1;
    for (let x = -400; x <= 2320; x += 80) {
      ctx.beginPath();
      ctx.moveTo(x, 1080);
      ctx.lineTo(960 + (x - 960) * 0.15, 300);
      ctx.stroke();
    }
    for (let y = 300; y <= 1080; y += 40) {
      let f = (y - 300) / 780;
      let spread = f * 1200;
      ctx.beginPath();
      ctx.moveTo(960 - spread, y);
      ctx.lineTo(960 + spread, y);
      ctx.stroke();
    }

    // Branching Monte Carlo Tree (Narrative simulations radiating forward)
    // Starting point (Origin / Incubation Core)
    const ox = 300, oy = 540;

    // Glowing incubator nucleus
    const coreGrad = ctx.createRadialGradient(ox, oy, 2, ox, oy, 90);
    coreGrad.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
    coreGrad.addColorStop(0.25, 'rgba(56, 189, 248, 0.8)');
    coreGrad.addColorStop(0.6, 'rgba(245, 158, 11, 0.3)');
    coreGrad.addColorStop(1, 'rgba(2, 6, 23, 0)');
    ctx.fillStyle = coreGrad;
    ctx.beginPath();
    ctx.arc(ox, oy, 90, 0, Math.PI * 2);
    ctx.fill();

    // Geometric rings around origin
    for (let r of [30, 60, 110, 160]) {
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.25)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(ox, oy, r, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Monte Carlo Path Generator
    function pseudoRandom(s) {
      let x = Math.sin(s++) * 10000;
      return x - Math.floor(x);
    }

    let seed = 123;
    const branches = [];
    const numPaths = 36;

    for (let p = 0; p < numPaths; p++) {
      let currentX = ox;
      let currentY = oy;
      let angle = -0.65 + (p / (numPaths - 1)) * 1.3; // Fan out from -37 deg to +37 deg
      let points = [{x: currentX, y: currentY}];
      let steps = 6;
      let len = 220;

      for (let s = 1; s <= steps; s++) {
        let stepAngle = angle + (pseudoRandom(seed++) - 0.5) * 0.45;
        let stepDist = len * (0.8 + pseudoRandom(seed++) * 0.4);
        currentX += Math.cos(stepAngle) * stepDist;
        currentY += Math.sin(stepAngle) * stepDist;
        points.push({x: currentX, y: currentY});
      }
      branches.push(points);
    }

    // Draw Monte Carlo narrative paths
    for (let bIndex = 0; bIndex < branches.length; bIndex++) {
      let pts = branches[bIndex];
      let isHeroPath = (bIndex === 14 || bIndex === 21); // A few highlighted "realized" technological paths
      
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y);
      for (let i = 1; i < pts.length; i++) {
        let xc = (pts[i-1].x + pts[i].x) / 2;
        let yc = (pts[i-1].y + pts[i].y) / 2;
        ctx.quadraticCurveTo(pts[i-1].x, pts[i-1].y, xc, yc);
      }
      ctx.lineTo(pts[pts.length-1].x, pts[pts.length-1].y);

      if (isHeroPath) {
        ctx.strokeStyle = 'rgba(245, 158, 11, 0.85)';
        ctx.lineWidth = 3;
        ctx.shadowColor = '#f59e0b';
        ctx.shadowBlur = 15;
      } else {
        ctx.strokeStyle = `rgba(56, 189, 248, ${0.12 + (bIndex % 4) * 0.08})`;
        ctx.lineWidth = 1.4;
        ctx.shadowBlur = 0;
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Draw decision nodes
      for (let i = 1; i < pts.length; i++) {
        let pt = pts[i];
        if (pt.x > 1850 || pt.y < 30 || pt.y > 1050) continue;

        let nodeSize = isHeroPath ? 5 : (pseudoRandom(seed++) > 0.6 ? 3 : 2);
        ctx.fillStyle = isHeroPath ? '#fef3c7' : (i === pts.length - 1 ? '#38bdf8' : 'rgba(148, 163, 184, 0.6)');
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, nodeSize, 0, Math.PI * 2);
        ctx.fill();

        if (isHeroPath || (i === pts.length - 1 && pseudoRandom(seed++) > 0.5)) {
          ctx.strokeStyle = 'rgba(245, 158, 11, 0.5)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, nodeSize + 4, 0, Math.PI * 2);
          ctx.stroke();
        }
      }
    }

    // Floating isometric prototype blueprint frames on the right
    function drawWireframeCube(x, y, size, alpha) {
      let h = size * 0.5;
      let w = size * 0.866;
      ctx.strokeStyle = `rgba(56, 189, 248, ${alpha})`;
      ctx.lineWidth = 1.5;

      // Top face
      ctx.beginPath();
      ctx.moveTo(x, y - size);
      ctx.lineTo(x + w, y - h);
      ctx.lineTo(x, y);
      ctx.lineTo(x - w, y - h);
      ctx.closePath();
      ctx.stroke();

      // Pillars
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x, y + size);
      ctx.moveTo(x + w, y - h);
      ctx.lineTo(x + w, y + h);
      ctx.moveTo(x - w, y - h);
      ctx.lineTo(x - w, y + h);
      ctx.stroke();

      // Bottom face
      ctx.beginPath();
      ctx.moveTo(x, y + size);
      ctx.lineTo(x + w, y + h);
      ctx.lineTo(x, y + size * 1.5);
      ctx.lineTo(x - w, y + h);
      ctx.closePath();
      ctx.stroke();
    }

    drawWireframeCube(1550, 480, 70, 0.45);
    drawWireframeCube(1400, 260, 45, 0.3);
    drawWireframeCube(1620, 780, 55, 0.35);

    // Stardust of uninstantiated hypotheses
    for (let i = 0; i < 300; i++) {
      let sx = pseudoRandom(seed++) * 1920;
      let sy = pseudoRandom(seed++) * 1080;
      let sa = pseudoRandom(seed++) * 0.4;
      ctx.fillStyle = `rgba(226, 232, 240, ${sa})`;
      ctx.beginPath();
      ctx.arc(sx, sy, pseudoRandom(seed++) * 1.8 + 0.4, 0, Math.PI * 2);
      ctx.fill();
    }
  </script>
</body>
</html>
"""

async def main():
    html_file = Path("substack/assets/scifi_prototyping_hero.html")
    html_file.parent.mkdir(parents=True, exist_ok=True)
    html_file.write_text(HTML_CONTENT, encoding="utf-8")
    
    img_path = Path("substack/assets/scifi_prototyping_hero.png")
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
