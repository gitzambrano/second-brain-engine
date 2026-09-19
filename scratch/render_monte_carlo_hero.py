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
      background: #030712;
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
    const bg = ctx.createRadialGradient(960, 540, 50, 960, 540, 1100);
    bg.addColorStop(0, '#0d182e');
    bg.addColorStop(0.45, '#071020');
    bg.addColorStop(0.8, '#030814');
    bg.addColorStop(1, '#01030a');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, 1920, 1080);

    // Subtle coordinate lattice
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.035)';
    ctx.lineWidth = 1;
    for (let x = 0; x <= 1920; x += 64) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, 1080);
      ctx.stroke();
    }
    for (let y = 0; y <= 1080; y += 64) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(1920, y);
      ctx.stroke();
    }

    // Origin: Probability generator point
    const ox = 240, oy = 540;

    // Glowing incubator nucleus
    const coreGrad = ctx.createRadialGradient(ox, oy, 2, ox, oy, 80);
    coreGrad.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
    coreGrad.addColorStop(0.3, 'rgba(56, 189, 248, 0.8)');
    coreGrad.addColorStop(0.7, 'rgba(245, 158, 11, 0.25)');
    coreGrad.addColorStop(1, 'rgba(3, 7, 18, 0)');
    ctx.fillStyle = coreGrad;
    ctx.beginPath();
    ctx.arc(ox, oy, 80, 0, Math.PI * 2);
    ctx.fill();

    // Concentric pulse rings
    for (let r of [30, 65, 110]) {
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.25)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(ox, oy, r, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Monte Carlo Trajectories
    let seed = 42;
    function pseudoRandom(s) {
      let x = Math.sin(s++) * 10000;
      return x - Math.floor(x);
    }

    const numTraj = 70;
    const paths = [];

    for (let i = 0; i < numTraj; i++) {
      let pts = [{x: ox, y: oy}];
      let curX = ox;
      let curY = oy;
      let baseAngle = -0.55 + (i / (numTraj - 1)) * 1.1; // -31 deg to +31 deg
      let steps = 7;
      let stepLen = 220;

      for (let s = 1; s <= steps; s++) {
        let ang = baseAngle + (pseudoRandom(seed++) - 0.5) * 0.4;
        let dist = stepLen * (0.8 + pseudoRandom(seed++) * 0.4);
        curX += Math.cos(ang) * dist;
        curY += Math.sin(ang) * dist;
        pts.push({x: curX, y: curY});
      }
      paths.push(pts);
    }

    // Draw ghost trajectories (Discarded Monte Carlo futures)
    for (let pIdx = 0; pIdx < paths.length; pIdx++) {
      let pts = paths[pIdx];
      let isHeroRealized = (pIdx === 35); // The single instantiated path in the center

      if (!isHeroRealized) {
        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i++) {
          let xc = (pts[i-1].x + pts[i].x) / 2;
          let yc = (pts[i-1].y + pts[i].y) / 2;
          ctx.quadraticCurveTo(pts[i-1].x, pts[i-1].y, xc, yc);
        }
        ctx.lineTo(pts[pts.length-1].x, pts[pts.length-1].y);

        let distFromCenter = Math.abs(pIdx - 35) / 35;
        let alpha = Math.max(0.04, 0.28 - distFromCenter * 0.22);
        ctx.strokeStyle = `rgba(56, 189, 248, ${alpha})`;
        ctx.lineWidth = 1.2;
        ctx.stroke();

        // Faint end particles
        let endPt = pts[pts.length - 1];
        if (endPt.x < 1900 && endPt.y > 40 && endPt.y < 1040) {
          ctx.fillStyle = `rgba(148, 163, 184, ${alpha * 1.5})`;
          ctx.beginPath();
          ctx.arc(endPt.x, endPt.y, 2, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }

    // Draw THE REALIZED / INSTANTIATED PATH (Intense luminous golden/cyan spine)
    const heroPts = paths[35];
    
    // Outer glow for hero path
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.3)';
    ctx.lineWidth = 8;
    ctx.beginPath();
    ctx.moveTo(heroPts[0].x, heroPts[0].y);
    for (let i = 1; i < heroPts.length; i++) {
      let xc = (heroPts[i-1].x + heroPts[i].x) / 2;
      let yc = (heroPts[i-1].y + heroPts[i].y) / 2;
      ctx.quadraticCurveTo(heroPts[i-1].x, heroPts[i-1].y, xc, yc);
    }
    ctx.stroke();

    // Sharp core for hero path
    ctx.strokeStyle = '#fef08a';
    ctx.lineWidth = 3;
    ctx.shadowColor = '#f59e0b';
    ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.moveTo(heroPts[0].x, heroPts[0].y);
    for (let i = 1; i < heroPts.length; i++) {
      let xc = (heroPts[i-1].x + heroPts[i].x) / 2;
      let yc = (heroPts[i-1].y + heroPts[i].y) / 2;
      ctx.quadraticCurveTo(heroPts[i-1].x, heroPts[i-1].y, xc, yc);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Instantiation nodes along hero path
    for (let i = 1; i < heroPts.length; i++) {
      let pt = heroPts[i];
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 11, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Quantum wave interference fringes across the manifold
    for (let w = 0; w < 5; w++) {
      let rad = 450 + w * 180;
      ctx.strokeStyle = `rgba(56, 189, 248, ${0.06 - w * 0.01})`;
      ctx.lineWidth = 1;
      ctx.setLineDash([8, 16]);
      ctx.beginPath();
      ctx.arc(ox, oy, rad, -0.6, 0.6);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  </script>
</body>
</html>
"""

async def main():
    html_file = Path("substack/assets/monte_carlo_hero.html")
    html_file.parent.mkdir(parents=True, exist_ok=True)
    html_file.write_text(HTML_CONTENT, encoding="utf-8")
    
    img_path = Path("substack/assets/monte_carlo_hero.png")
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
