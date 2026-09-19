import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

HTML_CONTENT = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #060b14;
      font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
      padding: 40px;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }

    .infocard {
      width: 1080px;
      background: linear-gradient(145deg, #0d172a 0%, #080f1d 100%);
      border: 1px solid rgba(245, 158, 11, 0.3);
      border-radius: 20px;
      padding: 44px 48px;
      box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.7), inset 0 1px 1px rgba(255, 255, 255, 0.08);
      position: relative;
    }

    .badge-bar {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(245, 158, 11, 0.12);
      border: 1px solid rgba(245, 158, 11, 0.35);
      border-radius: 9999px;
      padding: 5px 14px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 600;
      color: #fbbf24;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .badge-alt {
      background: rgba(56, 189, 248, 0.12);
      border-color: rgba(56, 189, 248, 0.35);
      color: #38bdf8;
    }

    h1 {
      font-size: 28px;
      font-weight: 800;
      color: #f8fafc;
      letter-spacing: -0.02em;
      line-height: 1.25;
      margin-bottom: 8px;
    }

    p.subtitle {
      font-size: 15px;
      color: #94a3b8;
      line-height: 1.5;
      margin-bottom: 32px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 28px;
    }

    .card {
      background: rgba(15, 23, 42, 0.75);
      border: 1px solid rgba(148, 163, 184, 0.14);
      border-radius: 14px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .card-num {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 700;
      color: #f59e0b;
      background: rgba(245, 158, 11, 0.12);
      border: 1px solid rgba(245, 158, 11, 0.25);
      padding: 3px 8px;
      border-radius: 6px;
      width: fit-content;
    }

    .card-title {
      font-size: 15px;
      font-weight: 700;
      color: #f1f5f9;
      line-height: 1.3;
    }

    .card-body {
      font-size: 12px;
      color: #cbd5e1;
      line-height: 1.5;
    }

    .card-stat {
      margin-top: auto;
      border-top: 1px solid rgba(148, 163, 184, 0.12);
      padding-top: 10px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: #38bdf8;
    }

    .footer-box {
      background: rgba(10, 18, 32, 0.95);
      border: 1px solid rgba(245, 158, 11, 0.25);
      border-radius: 12px;
      padding: 18px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .footer-box-text {
      font-size: 13px;
      color: #94a3b8;
      line-height: 1.5;
    }

    .footer-box-text strong {
      color: #fbbf24;
    }

    .brand {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: #64748b;
      white-space: nowrap;
      margin-left: 20px;
    }
  </style>
</head>
<body>
  <div class="infocard">
    <div class="badge-bar">
      <div class="badge">📊 Teoria dos Valores Extremos</div>
      <div class="badge badge-alt">🧬 Fisiologia & Estatística</div>
    </div>

    <h1>A Anatomia da Anomalia: Os Quatro Filtros Invisíveis</h1>
    <p class="subtitle">O atleta de elite mundial não é apenas um indivíduo determinado. É o sobrevivente de uma cascata multiplicativa onde dezenas de variáveis aleatórias convergiram simultaneamente para o extremo da distribuição.</p>

    <div class="grid">
      <!-- Filtro 1 -->
      <div class="card">
        <span class="card-num">FILTRO 01</span>
        <div class="card-title">Loteria Genética</div>
        <p class="card-body">Teto inato de VO2 máx, prevalência de fibras rápidas (ACTN3), eficiência biomecânica de alavancas ósseas e capacidade individual de adaptação ao treino.</p>
        <div class="card-stat">Herdabilidade: 50% a 80%</div>
      </div>

      <!-- Filtro 2 -->
      <div class="card">
        <span class="card-num">FILTRO 02</span>
        <div class="card-title">Idade Relativa (RAE)</div>
        <p class="card-body">Meses de nascimento arbitrários no início do ano esportivo oferecem maturidade física precoce na infância, capturando mais atenção técnica e tempo de jogo.</p>
        <div class="card-stat">NHL Q1 vs Q4: 40% vs 10%</div>
      </div>

      <!-- Filtro 3 -->
      <div class="card">
        <span class="card-num">FILTRO 03</span>
        <div class="card-title">Geografia & Capital</div>
        <p class="card-body">Acesso precoce a pistas, piscinas, gelo, técnicos de elite e suporte nutricional durante a janela crítica de desenvolvimento neuromuscular.</p>
        <div class="card-stat">Janela Crítica: 6 a 14 anos</div>
      </div>

      <!-- Filtro 4 -->
      <div class="card">
        <span class="card-num">FILTRO 04</span>
        <div class="card-title">Resistência a Lesões</div>
        <p class="card-body">Viés de sobrevivência brutal. Milhares de atletas idênticos em talento e garra sofrem rupturas de ligamento ou estresse ósseo antes de atingir o circuito profissional.</p>
        <div class="card-stat">Atrição Silenciosa: &gt; 95%</div>
      </div>
    </div>

    <div class="footer-box">
      <div class="footer-box-text">
        💡 <strong>Veredito Estatístico:</strong> O campeão olímpico não treinou 10 vezes mais do que o 50º colocado mundial. A diferença milimétrica no pódio é explicada pela <strong>conjunção probabilística perfeita</strong> de fatores que nenhum indivíduo pode controlar por pura força de vontade.
      </div>
      <div class="brand">SECOND BRAIN ATLAS</div>
    </div>
  </div>
</body>
</html>
"""

async def main():
    html_path = Path("substack/assets/campeoes_infocard.html")
    html_path.write_text(HTML_CONTENT, encoding="utf-8")
    
    img_path = Path("substack/assets/campeoes_infocard.png")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(device_scale_factor=2)
        await page.goto(html_path.resolve().as_uri())
        card = page.locator(".infocard")
        await card.screenshot(path=str(img_path))
        await browser.close()
    
    print(f"[OK] Campeões infocard gerado em: {img_path}")

if __name__ == "__main__":
    asyncio.run(main())
