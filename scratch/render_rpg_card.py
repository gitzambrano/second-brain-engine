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
      background: #040812;
      font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
      padding: 40px;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }

    .infocard {
      width: 1080px;
      background: linear-gradient(145deg, #0c182e 0%, #071022 100%);
      border: 1px solid rgba(56, 189, 248, 0.3);
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
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.35);
      border-radius: 9999px;
      padding: 5px 14px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 600;
      color: #38bdf8;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .badge-alt {
      background: rgba(245, 158, 11, 0.12);
      border-color: rgba(245, 158, 11, 0.35);
      color: #fbbf24;
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
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
      margin-bottom: 28px;
    }

    .card {
      background: rgba(15, 23, 42, 0.75);
      border: 1px solid rgba(148, 163, 184, 0.14);
      border-radius: 14px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .card.highlight {
      border-color: rgba(56, 189, 248, 0.45);
      background: linear-gradient(180deg, rgba(14, 32, 60, 0.8) 0%, rgba(10, 20, 40, 0.9) 100%);
    }

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid rgba(148, 163, 184, 0.12);
      padding-bottom: 12px;
    }

    .card-title {
      font-size: 16px;
      font-weight: 700;
      color: #f1f5f9;
    }

    .card-entropy {
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      padding: 3px 8px;
      border-radius: 6px;
      background: rgba(56, 189, 248, 0.15);
      color: #38bdf8;
      border: 1px solid rgba(56, 189, 248, 0.3);
    }

    .card.highlight .card-entropy {
      background: rgba(245, 158, 11, 0.15);
      color: #fbbf24;
      border-color: rgba(245, 158, 11, 0.35);
    }

    .metrics-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
      font-size: 13px;
      color: #cbd5e1;
      line-height: 1.45;
    }

    .metric-item strong {
      color: #94a3b8;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      display: block;
      margin-bottom: 2px;
    }

    .metric-item span {
      color: #e2e8f0;
    }

    .cost-badge {
      margin-top: auto;
      padding-top: 12px;
      border-top: 1px solid rgba(148, 163, 184, 0.12);
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
    }

    .cost-inf { color: #f87171; }
    .cost-high { color: #fbbf24; }
    .cost-zero { color: #34d399; font-weight: 700; }

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
      color: #38bdf8;
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
      <div class="badge">🎲 Teoria da Informação de Shannon</div>
      <div class="badge badge-alt">⚡ Entropia de Decisão: H = -∑ pᵢ log₂ pᵢ</div>
    </div>

    <h1>A Termodinâmica Informacional das Mídias Interativas</h1>
    <p class="subtitle">Por que nenhuma tecnologia digital superou a largura de banda ontológica de uma mesa de RPG reunida ao redor da linguagem natural.</p>

    <div class="grid">
      <!-- Coluna 1: Videogame Linear -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">Videogame Linear</span>
          <span class="card-entropy">H ≈ 0 bits</span>
        </div>
        <div class="metrics-list">
          <div class="metric-item">
            <strong>Espaço de Ações</strong>
            <span>N = 1 (Árvore estática)</span>
          </div>
          <div class="metric-item">
            <strong>Resolução de Mundo</strong>
            <span>Pré-compilada em código determinístico. Caminho pré-definido pelo designer.</span>
          </div>
        </div>
        <div class="cost-badge cost-inf">
          Custo do Imprevisto: <strong>Infinito</strong> (quebra o jogo)
        </div>
      </div>

      <!-- Coluna 2: Mundo Aberto AAA -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">Mundo Aberto AAA</span>
          <span class="card-entropy">H ≈ 5.6 bits</span>
        </div>
        <div class="metrics-list">
          <div class="metric-item">
            <strong>Espaço de Ações</strong>
            <span>N ≈ 50 (Ações mapeadas no controle)</span>
          </div>
          <div class="metric-item">
            <strong>Resolução de Mundo</strong>
            <span>Física pré-programada, scripts de colisão e limites rígidos de cenário.</span>
          </div>
        </div>
        <div class="cost-badge cost-high">
          Custo do Imprevisto: <strong>Elevadíssimo</strong> (orçamento astronômico)
        </div>
      </div>

      <!-- Coluna 3: RPG de Mesa -->
      <div class="card highlight">
        <div class="card-header">
          <span class="card-title">RPG de Mesa (Mesa Viva)</span>
          <span class="card-entropy">H ≥ 10 bits</span>
        </div>
        <div class="metrics-list">
          <div class="metric-item">
            <strong>Espaço de Ações</strong>
            <span>N → ∞ (Linguagem natural aberta)</span>
          </div>
          <div class="metric-item">
            <strong>Resolução de Mundo</strong>
            <span>Cognição distribuída: o Game Master sintetiza e acomoda qualquer premissa contrafactual.</span>
          </div>
        </div>
        <div class="cost-badge cost-zero">
          Custo do Imprevisto: <strong>ZERO</strong> (absorvido na fala)
        </div>
      </div>
    </div>

    <div class="footer-box">
      <div class="footer-box-text">
        💡 <strong>Conclusão Teórica:</strong> O RPG de mesa não é um fóssil pré-digital, mas uma <strong>arquitetura computacional distribuída</strong> onde a mente humana atua como o processador semântico mais sofisticado existente.
      </div>
      <div class="brand">SECOND BRAIN ATLAS</div>
    </div>
  </div>
</body>
</html>
"""

async def main():
    html_path = Path("substack/assets/rpg_entropy_infocard.html")
    html_path.write_text(HTML_CONTENT, encoding="utf-8")
    
    img_path = Path("substack/assets/rpg_entropy_infocard.png")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(device_scale_factor=2)
        await page.goto(html_path.resolve().as_uri())
        card = page.locator(".infocard")
        await card.screenshot(path=str(img_path))
        await browser.close()
    
    print(f"[OK] RPG infocard gerado em: {img_path}")

if __name__ == "__main__":
    asyncio.run(main())
