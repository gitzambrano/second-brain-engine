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
      border: 1px solid rgba(56, 189, 248, 0.25);
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

    .steps-container {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
      margin-bottom: 28px;
      position: relative;
    }

    .step-card {
      background: rgba(15, 23, 42, 0.75);
      border: 1px solid rgba(148, 163, 184, 0.14);
      border-radius: 14px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .step-card.active {
      border-color: rgba(245, 158, 11, 0.4);
      background: linear-gradient(180deg, rgba(30, 24, 14, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
    }

    .step-num {
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      font-weight: 700;
      color: #f59e0b;
      background: rgba(245, 158, 11, 0.15);
      border: 1px solid rgba(245, 158, 11, 0.3);
      padding: 3px 8px;
      border-radius: 6px;
      display: inline-block;
      width: fit-content;
    }

    .step-title {
      font-size: 16px;
      font-weight: 700;
      color: #f1f5f9;
      line-height: 1.3;
    }

    .step-desc {
      font-size: 13px;
      color: #cbd5e1;
      line-height: 1.5;
    }

    .step-examples {
      border-top: 1px solid rgba(148, 163, 184, 0.12);
      padding-top: 12px;
      font-size: 12px;
      color: #94a3b8;
    }

    .step-examples strong {
      color: #38bdf8;
      display: block;
      margin-bottom: 4px;
    }

    .footer-box {
      background: rgba(10, 18, 32, 0.95);
      border: 1px solid rgba(56, 189, 248, 0.25);
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
      <div class="badge">🚀 Sci-Fi Prototyping</div>
      <div class="badge badge-alt">🎲 Monte Carlo Narrativo</div>
    </div>

    <h1>O Loop da Imaginação Tecnológica</h1>
    <p class="subtitle">Como a narrativa especulativa atua como uma sandbox de baixíssimo custo para testar hipóteses, interfaces e dilemas sociais antes do primeiro protótipo de bancada.</p>

    <div class="steps-container">
      <!-- Passo 1 -->
      <div class="step-card">
        <span class="step-num">ETAPA 01</span>
        <div class="step-title">Premissa Contrafactual</div>
        <p class="step-desc">Um salto intuitivo do tipo <em>"E se...?"</em>. A tecnologia é inserida no mundo sem a obrigação de justificar sua viabilidade de fabricação imediata.</p>
        <div class="step-examples">
          <strong>Exemplos Canônicos:</strong>
          Clarke (satélite geoestacionário, 1945), Gibson (ciberespaço, 1984), Kubrick (tablets digitais, 1968).
        </div>
      </div>

      <!-- Passo 2 -->
      <div class="step-card active">
        <span class="step-num">ETAPA 02</span>
        <div class="step-title">Monte Carlo Narrativo</div>
        <p class="step-desc">A tecnologia é submetida a atritos humanos: falhas, incentivos econômicos perversos, dilemas éticos e efeitos colaterais de segunda e terceira ordem.</p>
        <div class="step-examples">
          <strong>O Teste de Estresse:</strong>
          A simulação narrativa descobre onde o sistema quebra sem custar bilhões de dólares ou vidas humanas.
        </div>
      </div>

      <!-- Passo 3 -->
      <div class="step-card">
        <span class="step-num">ETAPA 03</span>
        <div class="step-title">Cristalização em Design</div>
        <p class="step-desc">Engenheiros e pesquisadores adotam os artefatos da ficção como especificações conceituais e guias estéticos para seus próprios laboratórios.</p>
        <div class="step-examples">
          <strong>Do Filme à Realidade:</strong>
          As interfaces gestuais de <em>Minority Report</em> inspirando a computação espacial e os celulares em concha de <em>Star Trek</em>.
        </div>
      </div>
    </div>

    <div class="footer-box">
      <div class="footer-box-text">
        💡 <strong>Princípio Epistêmico:</strong> A ficção científica não acerta porque prevê o futuro mecanicamente, mas porque <strong>coloniza a imaginação dos futuros engenheiros</strong>, fornecendo a planta afetiva e funcional do que vale a pena construir.
      </div>
      <div class="brand">SECOND BRAIN ATLAS</div>
    </div>
  </div>
</body>
</html>
"""

async def main():
    html_path = Path("substack/assets/scifi_loop_infocard.html")
    html_path.write_text(HTML_CONTENT, encoding="utf-8")
    
    img_path = Path("substack/assets/scifi_loop_infocard.png")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(device_scale_factor=2)
        await page.goto(html_path.resolve().as_uri())
        card = page.locator(".infocard")
        await card.screenshot(path=str(img_path))
        await browser.close()
    
    print(f"[OK] Sci-fi infocard gerado em: {img_path}")

if __name__ == "__main__":
    asyncio.run(main())
