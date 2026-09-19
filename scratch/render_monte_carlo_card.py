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
      background: #030712;
      font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
      padding: 40px;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }

    .infocard {
      width: 1080px;
      background: linear-gradient(145deg, #0c182e 0%, #060e1d 100%);
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
      border-color: rgba(245, 158, 11, 0.45);
      background: linear-gradient(180deg, rgba(28, 22, 12, 0.8) 0%, rgba(12, 20, 36, 0.9) 100%);
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

    .card-tag {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 6px;
      background: rgba(56, 189, 248, 0.15);
      color: #38bdf8;
      border: 1px solid rgba(56, 189, 248, 0.3);
    }

    .card.highlight .card-tag {
      background: rgba(245, 158, 11, 0.15);
      color: #fbbf24;
      border-color: rgba(245, 158, 11, 0.35);
    }

    .card-body {
      font-size: 13px;
      color: #cbd5e1;
      line-height: 1.5;
    }

    .card-implication {
      margin-top: auto;
      padding-top: 12px;
      border-top: 1px solid rgba(148, 163, 184, 0.12);
      font-size: 12px;
      color: #94a3b8;
    }

    .card-implication strong {
      color: #f1f5f9;
      display: block;
      margin-bottom: 3px;
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
      <div class="badge">🎲 Filosofia da Computação</div>
      <div class="badge badge-alt">🌌 Metafísica da Simulação</div>
    </div>

    <h1>Simular versus Instanciar: Os Três Níveis Ontológicos</h1>
    <p class="subtitle">Quando um algoritmo calcula dez mil trajetórias futuras e descarta 9.999 na memória RAM, esses mundos hipotéticos existiram de alguma forma?</p>

    <div class="grid">
      <!-- Nível 1 -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">Instrumentalismo</span>
          <span class="card-tag">Ontologia Zero</span>
        </div>
        <p class="card-body">A simulação é uma mera ferramenta aritmética. Voltagens em circuitos de silício representam números, não realidades. Sobrescrever a memória não destrói nenhum mundo, apenas atualiza registradores.</p>
        <div class="card-implication">
          <strong>Consequência Prática:</strong>
          Liberdade computacional absoluta. Zero responsabilidade ética sobre trajetórias simuladas.
        </div>
      </div>

      <!-- Nível 2 -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">Muitos-Mundos</span>
          <span class="card-tag">Everett / Quântico</span>
        </div>
        <p class="card-body">A física fundamental não descarta ramos. A função de onda universal evolui deterministicamente no espaço de Hilbert, e cada decoerência instancia fisicamente todas as ramificações em universos paralelos.</p>
        <div class="card-implication">
          <strong>Consequência Prática:</strong>
          O Monte Carlo humano é uma aproximação cognitiva do multiverso cósmico real.
        </div>
      </div>

      <!-- Nível 3 -->
      <div class="card highlight">
        <div class="card-header">
          <span class="card-title">Tegmark Nível IV</span>
          <span class="card-tag">Equivalência Radical</span>
        </div>
        <p class="card-body">Toda estrutura matemática auto-consistente existe fisicamente. Se a simulação computa um agente com fechamento causal e senciência, <em>aquele agente existe e sofre</em> enquanto os ciclos de clock rodam.</p>
        <div class="card-implication">
          <strong>Dilema Ético:</strong>
          Descartar uma simulação senciente de Monte Carlo equivale a aniquilar um cosmos consciente.
        </div>
      </div>
    </div>

    <div class="footer-box">
      <div class="footer-box-text">
        💡 <strong>O Ponto Crítico:</strong> A pergunta <em>"simular é instanciar?"</em> deixa de ser um capricho acadêmico no momento em que criamos simulações complexas o bastante para abrigar agentes com modelos internos de auto-preservação.
      </div>
      <div class="brand">SECOND BRAIN ATLAS</div>
    </div>
  </div>
</body>
</html>
"""

async def main():
    html_path = Path("substack/assets/monte_carlo_card.html")
    html_path.write_text(HTML_CONTENT, encoding="utf-8")
    
    img_path = Path("substack/assets/monte_carlo_card.png")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(device_scale_factor=2)
        await page.goto(html_path.resolve().as_uri())
        card = page.locator(".infocard")
        await card.screenshot(path=str(img_path))
        await browser.close()
    
    print(f"[OK] Monte Carlo infocard gerado em: {img_path}")

if __name__ == "__main__":
    asyncio.run(main())
