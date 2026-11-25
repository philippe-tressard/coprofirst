/**
 * Cloudflare Worker — Hostachy
 * Intercepte chaque requête et retourne une page de maintenance
 * si l'origine (Cloudflare Tunnel → Raspberry Pi) est indisponible.
 *
 * Déploiement : Cloudflare Dashboard → Workers & Pages → Create Worker
 *               → coller ce fichier → Deploy
 *               → Settings → Triggers → ajouter la route : <your-domain>/*
 *
 * Plan Free : 100 000 req/jour incluses — largement suffisant.
 */

export default {
  async fetch(request, env, ctx) {
    // Sécurité : si le Worker lui-même plante, le site reste accessible
    ctx.passThroughOnException();

    // Test rapide : ajouter ?_maint=1 à n'importe quelle URL pour prévisualiser la page de maintenance
    if (new URL(request.url).searchParams.get('_maint') === '1') {
      return maintenancePage();
    }

    // Anti-boucle : si ce sous-fetch vient déjà du Worker, passer directement
    if (request.headers.get('x-hostachy-passthrough')) {
      return fetch(request);
    }

    try {
      const proxied = new Request(request);
      proxied.headers.set('x-hostachy-passthrough', '1');
      const response = await fetch(proxied);

      // Tunnel down → Cloudflare renvoie 530, 502 ou 503
      if (response.status === 530 || response.status === 502 || response.status === 503) {
        return maintenancePage();
      }

      return response;
    } catch {
      // Erreur réseau : tunnel coupé ou RPi inaccessible
      return maintenancePage();
    }
  }
};

function maintenancePage() {
  const html = `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#1E3A5F" />
  <title>Maintenance — Hostachy</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --color-primary:       #1E3A5F;
      --color-primary-dark:  #16304F;
      --color-primary-light: #EEF2F7;
      --color-secondary:     #3D6B4F;
      --color-accent:        #C9983A;
      --color-text:          #1A1A2E;
      --color-text-muted:    #5A6070;
      --color-text-inverse:  #F2EFE9;
      --color-bg:            #F2EFE9;
      --color-surface:       #FFFFFF;
      --color-border:        #D0D8E4;
      --radius:              0.5rem;
      --shadow:              0 4px 12px rgba(30, 58, 95, 0.12);
      font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif;
      font-size: 16px;
      color: var(--color-text);
      background: var(--color-bg);
    }

    /* ── Layout ── */
    body {
      min-height: 100vh;
      background: var(--color-bg);
      display: flex;
      flex-direction: column;
    }

    /* ── Header ── */
    header {
      background: var(--color-primary);
      padding: 0.875rem 1.5rem;
      display: flex;
      align-items: center;
      gap: 0.75rem;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }

    header .brand-icon {
      color: var(--color-accent);
      flex-shrink: 0;
    }

    header .brand-name {
      font-family: Georgia, 'Palatino Linotype', Palatino, serif;
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--color-text-inverse);
      letter-spacing: 0.01em;
    }

    /* ── Main ── */
    main {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem 1rem;
    }

    .card {
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 2.5rem 2rem;
      max-width: 480px;
      width: 100%;
      text-align: center;
    }

    /* ── Icône principale ── */
    .icon-wrap {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 72px;
      height: 72px;
      background: var(--color-primary-light);
      border-radius: 50%;
      margin-bottom: 1.5rem;
      color: var(--color-primary);
    }

    /* ── Titres ── */
    h1 {
      font-family: Georgia, 'Palatino Linotype', Palatino, serif;
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--color-primary);
      margin-bottom: 0.75rem;
      line-height: 1.2;
    }

    .subtitle {
      font-size: 1rem;
      color: var(--color-text-muted);
      line-height: 1.6;
      margin-bottom: 2rem;
    }

    /* ── Séparateur avec accent ── */
    .divider {
      width: 48px;
      height: 3px;
      background: var(--color-accent);
      border-radius: 2px;
      margin: 0 auto 2rem;
    }

    /* ── Badge statut ── */
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background: #FEF3C7;
      color: #92400E;
      border: 1px solid #FDE68A;
      border-radius: 9999px;
      padding: 0.375rem 1rem;
      font-size: 0.875rem;
      font-weight: 500;
      margin-bottom: 1.75rem;
    }

    /* ── Pulsation ── */
    .pulse {
      width: 8px;
      height: 8px;
      background: #D97706;
      border-radius: 50%;
      animation: pulse 1.8s infinite;
      flex-shrink: 0;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50%       { opacity: 0.4; transform: scale(0.75); }
    }

    /* ── Note informative ── */
    .info-box {
      background: var(--color-primary-light);
      border: 1px solid #C4D3E6;
      border-left: 3px solid var(--color-primary);
      border-radius: var(--radius);
      padding: 0.875rem 1rem;
      text-align: left;
      font-size: 0.875rem;
      color: var(--color-text-muted);
      line-height: 1.5;
    }

    /* ── Footer ── */
    footer {
      background: var(--color-primary);
      padding: 1rem 1.5rem;
      text-align: center;
      font-size: 0.75rem;
      color: rgba(242, 239, 233, 0.6);
    }

    /* ── Responsive ── */
    @media (max-width: 480px) {
      .card { padding: 2rem 1.25rem; }
      h1 { font-size: 1.5rem; }
    }
  </style>
</head>
<body>

  <header>
    <span class="brand-icon" aria-hidden="true">
      <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24"
           fill="none" stroke="currentColor" stroke-width="1.75"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/>
        <path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/>
        <path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/>
        <path d="M10 6h4"/><path d="M10 10h4"/>
        <path d="M10 14h4"/><path d="M10 18h4"/>
      </svg>
    </span>
    <span class="brand-name">Hostachy</span>
  </header>

  <main>
    <div class="card">

      <div class="icon-wrap" aria-hidden="true">
        <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="1.5"
             stroke-linecap="round" stroke-linejoin="round">
          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
        </svg>
      </div>

      <span class="status-badge">
        <span class="pulse" aria-hidden="true"></span>
        Maintenance en cours
      </span>

      <h1>Site temporairement indisponible</h1>
      <div class="divider" aria-hidden="true"></div>

      <p class="subtitle">
        Nous effectuons une opération de maintenance pour améliorer votre expérience.
        Le service sera rétabli très prochainement.
      </p>

      <div class="info-box" role="note">
        Si vous êtes gestionnaire ou membre du conseil syndical et avez une urgence,
        contactez directement l'administrateur de la résidence.
      </div>

    </div>
  </main>

  <footer>
    Portail de gestion de résidence &mdash; Hostachy
  </footer>

</body>
</html>`;

  return new Response(html, {
    status: 503,
    headers: {
      'Content-Type': 'text/html; charset=UTF-8',
      'Retry-After': '300',
      'Cache-Control': 'no-store',
    },
  });
}
