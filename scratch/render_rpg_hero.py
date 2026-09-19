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
      background: #040812;
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

    // Deep cosmic background
    const bg = ctx.createRadialGradient(960, 540, 60, 960, 540, 1100);
    bg.addColorStop(0, '#0c1a36');
    bg.addColorStop(0.45, '#071024');
    bg.addColorStop(0.8, '#030814');
    bg.addColorStop(1, '#010308');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, 1920, 1080);

    // Subtle hexagonal / polyhedral ambient field
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.04)';
    ctx.lineWidth = 1;
    const hexSize = 50;
    const hDist = hexSize * Math.sqrt(3);
    for (let y = -50; y <= 1150; y += hexSize * 1.5) {
      let row = Math.round(y / (hexSize * 1.5));
      let xOffset = (row % 2 === 0) ? 0 : hDist / 2;
      for (let x = -50; x <= 1970; x += hDist) {
        let hx = x + xOffset;
        ctx.beginPath();
        for (let a = 0; a < 6; a++) {
          let angle = (a * Math.PI) / 3;
          let px = hx + Math.cos(angle) * (hexSize * 0.95);
          let py = y + Math.sin(angle) * (hexSize * 0.95);
          if (a === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.stroke();
      }
    }

    // Origin: Floating Icosahedron (d20) at center (960, 540)
    const cx = 960, cy = 540;

    // Ambient radial glow behind the d20
    const coreGlow = ctx.createRadialGradient(cx, cy, 10, cx, cy, 380);
    coreGlow.addColorStop(0, 'rgba(56, 189, 248, 0.35)');
    coreGlow.addColorStop(0.35, 'rgba(245, 158, 11, 0.15)');
    coreGlow.addColorStop(0.7, 'rgba(56, 189, 248, 0.04)');
    coreGlow.addColorStop(1, 'rgba(1, 3, 8, 0)');
    ctx.fillStyle = coreGlow;
    ctx.beginPath();
    ctx.arc(cx, cy, 380, 0, Math.PI * 2);
    ctx.fill();

    // 3D Projection of an Icosahedron (Wireframe geometry)
    // Golden ratio
    const phi = (1 + Math.sqrt(5)) / 2;
    const scale = 140;

    // 12 vertices of an icosahedron
    const rawVertices = [
      [-1,  phi,  0], [ 1,  phi,  0], [-1, -phi,  0], [ 1, -phi,  0],
      [ 0, -1,  phi], [ 0,  1,  phi], [ 0, -1, -phi], [ 0,  1, -phi],
      [ phi,  0, -1], [ phi,  0,  1], [-phi,  0, -1], [-phi,  0,  1]
    ];

    // Slight rotation around X and Y axes
    const rotX = 0.45;
    const rotY = 0.65;
    const rotZ = 0.2;

    function rotate(v) {
      let [x, y, z] = v;
      // Rot Y
      let x1 = x * Math.cos(rotY) + z * Math.sin(rotY);
      let z1 = -x * Math.sin(rotY) + z * Math.cos(rotY);
      // Rot X
      let y2 = y * Math.cos(rotX) - z1 * Math.sin(rotX);
      let z2 = y * Math.sin(rotX) + z1 * Math.cos(rotX);
      // Rot Z
      let x3 = x1 * Math.cos(rotZ) - y2 * Math.sin(rotZ);
      let y3 = x1 * Math.sin(rotZ) + y2 * Math.cos(rotZ);
      return [x3, y3, z2];
    }

    const projVertices = rawVertices.map(v => {
      let [rx, ry, rz] = rotate(v);
      return {
        x: cx + rx * scale,
        y: cy + ry * scale,
        z: rz
      };
    });

    // 30 edges of icosahedron (pairs with distance 2 in unit sphere)
    const edges = [];
    for (let i = 0; i < rawVertices.length; i++) {
      for (let j = i + 1; j < rawVertices.length; j++) {
        let dx = rawVertices[i][0] - rawVertices[j][0];
        let dy = rawVertices[i][1] - rawVertices[j][1];
        let dz = rawVertices[i][2] - rawVertices[j][2];
        let dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
        if (Math.abs(dist - 2.0) < 0.01) {
          edges.push([i, j]);
        }
      }
    }

    // Draw d20 edges with varying depth opacity
    for (let [i, j] of edges) {
      let v1 = projVertices[i];
      let v2 = projVertices[j];
      let avgZ = (v1.z + v2.z) / 2;
      let alpha = 0.3 + (avgZ + 1.6) * 0.25;

      ctx.strokeStyle = `rgba(56, 189, 248, ${alpha})`;
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      ctx.moveTo(v1.x, v1.y);
      ctx.lineTo(v2.x, v2.y);
      ctx.stroke();
    }

    // Draw d20 vertex nodes
    for (let v of projVertices) {
      let alpha = 0.4 + (v.z + 1.6) * 0.25;
      ctx.fillStyle = '#f8fafc';
      ctx.beginPath();
      ctx.arc(v.x, v.y, 4, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = `rgba(245, 158, 11, ${alpha})`;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(v.x, v.y, 8, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Radiating Shannon Information Rays (Networks branching into infinity)
    let seed = 777;
    function pseudoRandom(s) {
      let x = Math.sin(s++) * 10000;
      return x - Math.floor(x);
    }

    for (let v of projVertices) {
      let numRays = 3;
      for (let r = 0; r < numRays; r++) {
        let ang = Math.atan2(v.y - cy, v.x - cx) + (pseudoRandom(seed++) - 0.5) * 0.7;
        let dist = 320 + pseudoRandom(seed++) * 400;
        let targetX = v.x + Math.cos(ang) * dist;
        let targetY = v.y + Math.sin(ang) * dist;

        ctx.strokeStyle = 'rgba(245, 158, 11, 0.25)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(v.x, v.y);
        ctx.lineTo(targetX, targetY);
        ctx.stroke();

        // End-leaf nodes of possible narrative worlds
        ctx.fillStyle = 'rgba(56, 189, 248, 0.7)';
        ctx.beginPath();
        ctx.arc(targetX, targetY, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Subtle concentric probability waves expanding from the center
    for (let rad of [220, 360, 520, 680]) {
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.1)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 12]);
      ctx.beginPath();
      ctx.arc(cx, cy, rad, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  </script>
</body>
</html>
"""

async def main():
    html_file = Path("substack/assets/rpg_hero.html")
    html_file.parent.mkdir(parents=True, exist_ok=True)
    html_file.write_text(HTML_CONTENT, encoding="utf-8")
    
    img_path = Path("substack/assets/rpg_hero.png")
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
