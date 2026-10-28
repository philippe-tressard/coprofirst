/**
 * Liens profonds — arriver sur l'ÉLÉMENT visé, pas seulement sur sa page.
 *
 * Le fil d'activité, les notifications et les e-mails renvoient vers une page qui
 * contient parfois des centaines d'éléments répartis en onglets. Y arriver sans
 * précision oblige l'utilisateur à chercher ce sur quoi il vient de cliquer — et le
 * 24/07/2026 « Voir l'annonce → » ouvrait l'onglet Sondages, où l'annonce n'est
 * évidemment pas.
 *
 * Convention du projet, à respecter des deux côtés :
 *   - une **route dédiée** par onglet (`/annonces`, `/calendrier/kanban`) — la
 *     table est dans `#lib/pages.ts`, et elle seule ;
 *   - `#<prefixe>-<id>`  → élément à ouvrir et à révéler (`#annonce-42`).
 *
 * ⚠️ `?onglet=<id>` était la première moitié de cette convention (24/07/2026). Il
 * ne l'est plus depuis le 05/09/2026 : un paramètre ne se lisait que par la page
 * qui l'attendait, et il n'était JAMAIS écrit dans la barre d'adresse — ce que
 * l'utilisateur copiait ne portait donc pas l'onglet qu'il regardait, et c'est
 * exactement ce dont il s'est plaint. Les anciennes adresses restent servies :
 * `resoudreOnglet()` les redirige en 308, définitivement.
 *
 * Les préfixes sont vérifiés en CI (`api/tests/test_liens_front.py`) : un lien de
 * l'API dont l'ancre n'est produite par aucune page fait échouer le build.
 */

import { error, redirect } from '@sveltejs/kit';
import { ongletDepuisChemin, routeOnglet } from '#lib/routes-onglets.ts';

/** Ce que le chemin désigne : l'onglet, et son sous-onglet s'il en a un. */
export interface OngletCourant {
	onglet: string;
	sous: string | null;
}

/**
 * Résout l'onglet d'une page depuis son URL — à appeler dans le `load` d'un
 * `+page.ts`, jamais dans le composant.
 *
 * Trois issues, et aucune n'est muette :
 *   - une ancienne adresse (`?onglet=`) part en **308** vers la route dédiée. Le
 *     navigateur reporte le fragment, donc `/sondages?onglet=annonces#annonce-12`
 *     arrive bien sur `/annonces#annonce-12` — les e-mails déjà envoyés, les
 *     favoris et les liens de l'API continuent de fonctionner ;
 *   - un chemin déclaré rend son onglet ;
 *   - un chemin inconnu rend une **404**. Se replier en silence sur le premier
 *     onglet ferait passer `/calendrier/kanbna` pour une adresse valide, et le
 *     lien resterait cassé sans que personne ne le sache.
 */
export function resoudreOnglet(pageId: string, url: URL): OngletCourant {
	const ancien = url.searchParams.get('onglet');
	if (ancien) {
		const reste = new URLSearchParams(url.searchParams);
		reste.delete('onglet');
		const suite = reste.toString();
		//  Un identifiant d'onglet inconnu ne mérite pas une 404 : le lien vient
		//  peut-être d'un e-mail d'il y a six mois. On dépose le lecteur sur la page,
		//  qui est la bonne moitié de sa demande.
		let cible: string;
		try {
			cible = routeOnglet(pageId, ancien);
		} catch {
			cible = url.pathname;
		}
		throw redirect(308, suite ? `${cible}?${suite}` : cible);
	}
	const resolu = ongletDepuisChemin(pageId, url.pathname);
	if (!resolu) {
		throw error(404, 'Cette adresse ne correspond à aucun onglet de cette page.');
	}
	return resolu;
}

/** Identifiant ciblé par `#<prefixe>-<id>`, ou `null` si l'URL ne vise rien. */
export function cibleDuHash(prefixe: string): number | null {
	if (typeof window === 'undefined') return null;
	const m = window.location.hash.match(new RegExp(`^#${prefixe}-(\\d+)$`));
	return m ? parseInt(m[1], 10) : null;
}

/**
 * Amène l'élément à l'écran et le souligne brièvement.
 *
 * Le délai laisse Svelte rendre l'élément (il vient souvent d'être déplié par
 * l'appelant). La surbrillance est retirée d'elle-même : sur une longue liste, un
 * simple défilement ne dit pas *lequel* des éléments visibles était visé.
 */
export function revelerCible(elementId: string, delaiMs = 100): void {
	if (typeof window === 'undefined') return;
	setTimeout(() => {
		const el = document.getElementById(elementId);
		if (!el) return;
		el.scrollIntoView({ behavior: 'smooth', block: 'start' });
		el.classList.add('cible-lien');
		setTimeout(() => el.classList.remove('cible-lien'), 2500);
	}, delaiMs);
}
