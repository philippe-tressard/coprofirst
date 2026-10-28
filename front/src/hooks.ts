/**
 * `reroute` — plusieurs adresses, un seul écran.
 *
 * ## Pourquoi ce fichier existe (05/09/2026)
 *
 * Chaque onglet a désormais son URL (`/annonces`, `/calendrier/kanban`,
 * `/mon-lot/location/archives`…). Trois façons de servir ces adresses :
 *
 * | Façon | Ce qu'elle coûte |
 * |---|---|
 * | un dossier de route par onglet | dix-sept fichiers jumeaux, qui divergeront |
 * | un segment de reste `[...vue]` | **déplacer** les quatre écrans concernés — 1 000 à 1 800 lignes chacun, que le garde-fou de modularité compte alors comme des fichiers neufs au-dessus du plafond |
 * | **`reroute`** | ce fichier, et rien d'autre ne bouge |
 *
 * `reroute` traduit une adresse en **route** avant que SvelteKit ne cherche le
 * fichier ; l'URL affichée, elle, ne change pas — et c'est elle que reçoit le
 * `load`, qui y lit l'onglet (`resoudreOnglet`). `/annonces` est donc rendue par
 * `routes/(app)/sondages/+page.svelte`, sans redirection et sans duplication.
 *
 * ⚠️ Cette fonction s'exécute **à chaque navigation, sur le serveur ET dans le
 * navigateur**. Elle doit rester synchrone, pure et rapide : c'est une lecture de
 * table, jamais un appel réseau.
 *
 * ⚠️ Une adresse inconnue (`/calendrier/kanbna`) n'est pas traduite : SvelteKit ne
 * lui trouve aucune route et rend une **404**. C'est voulu — se replier sur la
 * page ferait passer une faute de frappe pour une adresse valide, et le lien
 * cassé survivrait.
 */
import { routeInterne } from '#lib/routes-onglets.ts';
import type { Reroute } from '@sveltejs/kit/hooks';

export const reroute: Reroute = ({ url }) => routeInterne(url.pathname);
