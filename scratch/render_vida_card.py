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
      background: #070d18;
      font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
      padding: 40px;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }

    .infocard {
      width: 1080px;
      background: linear-gradient(145deg, #0d1627 0%, #080f1d 100%);
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
      background: rgba(52, 211, 153, 0.12);
      border-color: rgba(52, 211, 153, 0.35);
      color: #34d399;
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
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .card.highlight {
      border-color: rgba(56, 189, 248, 0.4);
      background: linear-gradient(180deg, rgba(14, 30, 56, 0.8) 0%, rgba(10, 20, 38, 0.9) 100%);
    }

    .card-header {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 15px;
      font-weight: 700;
      color: #e2e8f0;
      border-bottom: 1px solid rgba(148, 163, 184, 0.12);
      padding-bottom: 10px;
    }

    .card-header .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }

    .dot-green { background: #34d399; box-shadow: 0 0 10px #34d399; }
    .dot-amber { background: #fbbf24; box-shadow: 0 0 10px #fbbf24; }
    .dot-blue  { background: #38bdf8; box-shadow: 0 0 10px #38bdf8; }

    .card ul {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 10px;
      font-size: 13px;
      color: #cbd5e1;
      line-height: 1.45;
    }

    .card li strong {
      color: #f1f5f9;
      display: block;
      font-size: 13px;
      margin-bottom: 2px;
    }

    .verdict {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 6px;
      display: inline-block;
      margin-top: 4px;
    }
    .verdict-full { background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); }
    .verdict-partial { background: rgba(251, 191, 36, 0.15); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.3); }
    .verdict-abstract { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }

    .footer-bar {
      background: rgba(10, 18, 32, 0.9);
      border: 1px solid rgba(56, 189, 248, 0.2);
      border-radius: 12px;
      padding: 16px 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .footer-bar-left {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 13px;
      color: #94a3b8;
    }

    .footer-bar-left strong {
      color: #38bdf8;
    }

    .footer-bar-right {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: #64748b;
    }
  </style>
</head>
<body>
  <div class="infocard">
    <div class="badge-bar">
      <div class="badge">🔬 Biologia Teórica</div>
      <div class="badge badge-alt">⚡ Termodinâmica do Não-Equilíbrio</div>
    </div>

    <h1>O Espectro da Vida: Onde as Fronteiras Teóricas se Cruzam</h1>
    <p class="subtitle">Nenhuma definição isolada esgota o fenômeno. Cada lente física, química e informacional captura uma faceta do espectro contínuo entre matéria inerte e agência auto-sustentada.</p>

    <div class="grid">
      <!-- Coluna 1: Vida Celular Clássica -->
      <div class="card highlight">
        <div class="card-header">
          <span class="dot dot-green"></span>
          <span>Vida Celular Canônica</span>
        </div>
        <ul>
          <li>
            <strong>Bactérias, Archaea e Eucariotos</strong>
            Fechamento termodinâmico e autopoiese completa.
          </li>
          <li>
            <strong>Negentropia Contínua:</strong>
            Mantêm gradientes químicos e bombeiam entropia para o meio externo.
          </li>
          <li>
            <strong>Markov Blanket Biológico:</strong>
            Membrana fosfolipídica separa estados internos e minimiza surpresa estatística.
          </li>
        </ul>
        <div>
          <span class="verdict verdict-full">7 / 7 Definições Atingidas</span>
        </div>
      </div>

      <!-- Coluna 2: Entidades Limítrofes -->
      <div class="card">
        <div class="card-header">
          <span class="dot dot-amber"></span>
          <span>Fronteira Cinzenta</span>
        </div>
        <ul>
          <li>
            <strong>Vírus, Príons e Viróides</strong>
            Informação pura sem metabolismo autocontido.
          </li>
          <li>
            <strong>Dependência Hospedeira:</strong>
            Operam como software parasita: ativam termodinâmica apenas dentro de outra célula.
          </li>
          <li>
            <strong>Autopoiese Emprestada:</strong>
            Evoluem darwinianamente mas não geram seus próprios componentes.
          </li>
        </ul>
        <div>
          <span class="verdict verdict-partial">3 / 7 Definições (Condicional)</span>
        </div>
      </div>

      <!-- Coluna 3: Sistemas Dissipativos e Digitais -->
      <div class="card">
        <div class="card-header">
          <span class="dot dot-blue"></span>
          <span>Sistemas Dissipativos / IA</span>
        </div>
        <ul>
          <li>
            <strong>Estrelas, Redes Neurais e Autômatos</strong>
            Estruturas de não-equilíbrio e computação.
          </li>
          <li>
            <strong>Vida Informacional:</strong>
            Processamento algorítmico e minimização de surpresa sem química orgânica.
          </li>
          <li>
            <strong>Desafio Astrobiológico:</strong>
            A armadilha do N=1 (terráqueo) cega para formas exóticas de organização.
          </li>
        </ul>
        <div>
          <span class="verdict verdict-abstract">FEP & Computação Universal</span>
        </div>
      </div>
    </div>

    <div class="footer-bar">
      <div class="footer-bar-left">
        <span>💡 <strong>Conclusão Epistêmica:</strong> A vida não é um interruptor binário ligado/desligado, mas uma transição de fase contínua em complexidade, organização negentrópica e agência.</span>
      </div>
      <div class="footer-bar-right">SECOND BRAIN ATLAS</div>
    </div>
  </div>
</body>
</html>
"""

async def main():
    html_path = Path("substack/assets/o_que_e_vida_body_card.html")
    html_path.write_text(HTML_CONTENT, encoding="utf-8")
    
    img_path = Path("substack/assets/o_que_e_vida_body_card.png")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(device_scale_factor=2)
        await page.goto(html_path.resolve().as_uri())
        card = page.locator(".infocard")
        await card.screenshot(path=str(img_path))
        await browser.close()
    
    print(f"[OK] Body infocard gerado em: {img_path}")

if __name__ == "__main__":
    asyncio.run(main())
