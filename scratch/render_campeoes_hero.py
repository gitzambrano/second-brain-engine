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

    // Deep background gradient
    const bg = ctx.createRadialGradient(960, 600, 80, 960, 540, 1100);
    bg.addColorStop(0, '#0c1629');
    bg.addColorStop(0.5, '#070f1e');
    bg.addColorStop(0.8, '#040913');
    bg.addColorStop(1, '#02040a');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, 1920, 1080);

    // Subtle coordinate grid
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.04)';
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

    // Baseline axis
    const baseY = 840;
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(120, baseY);
    ctx.lineTo(1800, baseY);
    ctx.stroke();

    // Gaussian Distribution (Bell Curve) representing population
    // Mean at x = 700, Standard Deviation = 180
    const meanX = 700;
    const sigma = 190;
    const peakHeight = 520;

    function gaussian(x) {
      let z = (x - meanX) / sigma;
      return Math.exp(-0.5 * z * z);
    }

    // Shaded area under the curve
    const areaGrad = ctx.createLinearGradient(0, baseY - peakHeight, 0, baseY);
    areaGrad.addColorStop(0, 'rgba(56, 189, 248, 0.12)');
    areaGrad.addColorStop(1, 'rgba(15, 23, 42, 0.0)');
    ctx.fillStyle = areaGrad;

    ctx.beginPath();
    ctx.moveTo(120, baseY);
    for (let x = 120; x <= 1800; x += 4) {
      let y = baseY - gaussian(x) * peakHeight;
      ctx.lineTo(x, y);
    }
    ctx.lineTo(1800, baseY);
    ctx.closePath();
    ctx.fill();

    // Multiple layered curves (representing multi-factorial distributions: VO2, Reaction time, Training response)
    const sigmas = [170, 190, 210];
    const opacities = [0.25, 0.6, 0.3];
    for (let sIdx = 0; sIdx < sigmas.length; sIdx++) {
      let s = sigmas[sIdx];
      ctx.strokeStyle = `rgba(56, 189, 248, ${opacities[sIdx]})`;
      ctx.lineWidth = (sIdx === 1) ? 2.5 : 1.5;
      ctx.beginPath();
      for (let x = 120; x <= 1800; x += 6) {
        let z = (x - meanX) / s;
        let y = baseY - Math.exp(-0.5 * z * z) * peakHeight;
        if (x === 120) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Population scatter points (The thousands of hard workers falling within 1-3 sigma)
    let seed = 999;
    function pseudoRandom(s) {
      let x = Math.sin(s++) * 10000;
      return x - Math.floor(x);
    }

    for (let i = 0; i < 450; i++) {
      // Box-Muller transform for normal distribution
      let u1 = Math.max(0.0001, pseudoRandom(seed++));
      let u2 = pseudoRandom(seed++);
      let randStdNormal = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
      let px = meanX + randStdNormal * sigma;
      if (px < 150 || px > 1750) continue;

      let maxY = baseY - gaussian(px) * peakHeight;
      let py = baseY - pseudoRandom(seed++) * (baseY - maxY);
      let alpha = Math.min(0.4, Math.max(0.05, 0.5 - (px / 1800) * 0.3));

      ctx.fillStyle = `rgba(148, 163, 184, ${alpha})`;
      ctx.beginPath();
      ctx.arc(px, py, 1.8, 0, Math.PI * 2);
      ctx.fill();
    }

    // THE OUTLIER ZONE (Extreme Right Tail: 5 to 7 Sigma, x = 1450 to 1680)
    // Golden vertical threshold line of extreme rarity
    const thresholdX = 1380;
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.4)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 6]);
    ctx.beginPath();
    ctx.moveTo(thresholdX, baseY);
    ctx.lineTo(thresholdX, 320);
    ctx.stroke();
    ctx.setLineDash([]);

    // Golden halo around extreme tail
    const outlierGlow = ctx.createRadialGradient(1540, baseY - 60, 10, 1540, baseY - 60, 220);
    outlierGlow.addColorStop(0, 'rgba(245, 158, 11, 0.45)');
    outlierGlow.addColorStop(0.5, 'rgba(245, 158, 11, 0.15)');
    outlierGlow.addColorStop(1, 'rgba(245, 158, 11, 0)');
    ctx.fillStyle = outlierGlow;
    ctx.beginPath();
    ctx.arc(1540, baseY - 60, 220, 0, Math.PI * 2);
    ctx.fill();

    // The Champion Anomaly: Single solitary luminous outlier node at 6.5 sigma
    const champX = 1560;
    const champY = baseY - 65;

    // Glowing rings around champion
    for (let r of [15, 30, 55, 90]) {
      ctx.strokeStyle = `rgba(245, 158, 11, ${0.4 - r * 0.0035})`;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(champX, champY, r, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Center radiant core
    const coreGrad = ctx.createRadialGradient(champX, champY, 1, champX, champY, 16);
    coreGrad.addColorStop(0, '#ffffff');
    coreGrad.addColorStop(0.3, '#fef08a');
    coreGrad.addColorStop(0.7, '#f59e0b');
    coreGrad.addColorStop(1, 'rgba(245, 158, 11, 0)');
    ctx.fillStyle = coreGrad;
    ctx.beginPath();
    ctx.arc(champX, champY, 16, 0, Math.PI * 2);
    ctx.fill();

    // High-energy particle burst from champion node
    for (let k = 0; k < 16; k++) {
      let ang = (k / 16) * Math.PI * 2;
      let len = 40 + pseudoRandom(seed++) * 35;
      ctx.strokeStyle = 'rgba(254, 240, 138, 0.6)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(champX + Math.cos(ang) * 10, champY + Math.sin(ang) * 10);
      ctx.lineTo(champX + Math.cos(ang) * len, champY + Math.sin(ang) * len);
      ctx.stroke();
    }

    // A few rare adjacent outliers (medallists)
    const rareOutliers = [
      {x: 1470, y: baseY - 90},
      {x: 1510, y: baseY - 50},
      {x: 1620, y: baseY - 45}
    ];

    for (let ro of rareOutliers) {
      ctx.fillStyle = '#fde047';
      ctx.beginPath();
      ctx.arc(ro.x, ro.y, 4, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = 'rgba(245, 158, 11, 0.4)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(ro.x, ro.y, 12, 0, Math.PI * 2);
      ctx.stroke();
    }
  </script>
</body>
</html>
"""

async def main():
    html_file = Path("substack/assets/campeoes_hero.html")
    html_file.parent.mkdir(parents=True, exist_ok=True)
    html_file.write_text(HTML_CONTENT, encoding="utf-8")
    
    img_path = Path("substack/assets/campeoes_hero.png")
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
