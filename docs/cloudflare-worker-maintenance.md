# Cloudflare Worker — Page de maintenance

## Principe

Un Cloudflare Worker intercepte **toutes les requêtes** avant qu'elles atteignent le tunnel.  
Si l'origine (Cloudflare Tunnel → Raspberry Pi) répond avec un code d'erreur (502, 503, 530)
ou ne répond pas du tout (tunnel coupé, RPi éteint), le Worker renvoie une page de maintenance
aux couleurs du site plutôt que l'écran d'erreur Cloudflare par défaut.

```
Visiteur → Cloudflare Edge → Worker → Tunnel → RPi
                                  ↘ Page maintenance (si RPi KO)
```

## Fichier source

`infra/cloudflare-worker.js` à la racine du projet.

## Déploiement (une seule fois)

### 1. Créer le Worker

1. Cloudflare Dashboard → **Workers & Pages** → **Create application** → **Create Worker**
2. Donner un nom : `hostachy-maintenance`
3. Cliquer **Deploy** (page vide par défaut)
4. Cliquer **Edit code** → **remplacer tout** par le contenu de `infra/cloudflare-worker.js` → **Save and deploy**

### 2. Assigner une Route

1. Cloudflare Dashboard → ton domaine → **Workers Routes** → **Add route**
2. Route : `<your-domain>/*`
3. Worker : `hostachy-maintenance`
4. Sauvegarder

> La route `/*` couvre toutes les pages du site, y compris l'API (`/api/*`).

## Mise à jour du Worker

1. Cloudflare Dashboard → **Workers & Pages** → `hostachy-maintenance` → **Edit code**
2. Modifier le HTML dans la fonction `maintenancePage()`
3. **Save and deploy**

## Comportement

| Situation | Résultat |
|---|---|
| RPi UP, réponse 200 | Requête passée telle quelle — aucun impact |
| RPi répond 502 / 503 / 530 | Page de maintenance HTML (503 + `Retry-After: 300`) |
| Tunnel coupé (erreur réseau) | Page de maintenance HTML (503 + `Retry-After: 300`) |

## Limites plan Free

| | Free | Workers Paid ($5/mois) |
|---|---|---|
| Requêtes incluses | 100 000 / jour | 10 millions / mois |
| Au-delà | Worker désactivé | $0,30 / million |
| Cold start | < 5 ms | < 5 ms |

Pour un usage résidence (< 500 utilisateurs), le plan Free est largement suffisant.

## Design

La page de maintenance respecte la charte graphique Hostachy :
- Police titres : Georgia (serif système)
- Police UI : Segoe UI / system-ui
- Couleurs : Bleu Seine `#1E3A5F`, Or Croissy `#C9983A`, Pierre de taille `#F2EFE9`
- Composants : header + card + badge statut animé + note informative
- Responsive mobile / desktop
