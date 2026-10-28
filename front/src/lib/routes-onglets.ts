/**
 * Les URL dédiées des onglets — résolution dans les deux sens.
 *
 * ## Pourquoi ces fonctions ne sont pas dans `pages.ts`
 *
 * Elles y étaient, et le contrôle de modularité les a refusées : la table faisait
 * 546 lignes. C'est le bon refus — `pages.ts` DÉCRIT les pages, ce fichier-ci les
 * INTERROGE. La table reste la source unique, personne n'écrit une route ailleurs
 * (`npm run lint:pages` le refuse) ; seule la lecture a déménagé.
 *
 * ## Pourquoi des routes plutôt qu'un `?onglet=` (05/09/2026)
 *
 * Un onglet n'avait pas d'adresse : `/sondages` ouvrait toujours les sondages, et
 * « Petites annonces » ne s'atteignait que par un clic. On ne pouvait donc pas
 * ENVOYER un lien vers une rubrique — signalé par l'utilisateur, qui voulait
 * partager une annonce et n'avait que l'adresse de la page voisine.
 *
 * Le paramètre `?onglet=` existait pour les liens que l'API fabrique, mais il
 * n'était jamais ÉCRIT dans la barre d'adresse : ce qu'on copiait ne portait pas
 * l'onglet qu'on regardait. Les routes règlent les deux d'un coup — l'adresse dit
 * toujours où l'on est, et elle se copie telle quelle.
 */

import { PAGES } from '#lib/pages.ts';

/** Retire la barre oblique finale, sauf pour la racine. */
function normaliserChemin(chemin: string): string {
	return chemin.length > 1 && chemin.endsWith('/') ? chemin.slice(0, -1) : chemin;
}

/**
 * L'URL dédiée d'un onglet.
 *
 * Lève si l'onglet n'est pas déclaré : une barre d'onglets qui pointerait vers
 * une adresse inventée mènerait à une 404, et rien ne le dirait avant la
 * production. Même parti que `defautsDePage`.
 */
export function routeOnglet(pageId: string, ongletId: string): string {
	const onglet = PAGES.find((p) => p.id === pageId)?.onglets?.find((o) => o.id === ongletId);
	if (!onglet) {
		throw new Error(
			`Onglet « ${ongletId} » absent de la page « ${pageId} » (src/lib/pages.ts) : lui ` +
				"ajouter une entrée avec sa route, plutôt que d'écrire l'URL sur place.",
		);
	}
	return onglet.route;
}

/**
 * Ce qu'une URL désigne sur cette page : l'onglet, et le sous-onglet s'il y en a.
 *
 * Rend `null` quand le chemin ne correspond à AUCUNE route déclarée — c'est ce qui
 * permet à une page de rendre une 404 plutôt que d'afficher silencieusement son
 * premier onglet sur `/calendrier/nimporte-quoi`. Un repli muet ferait passer une
 * faute de frappe pour une adresse valide, et les liens cassés survivraient.
 */
export function ongletDepuisChemin(
	pageId: string,
	chemin: string,
): { onglet: string; sous: string | null } | null {
	const page = PAGES.find((p) => p.id === pageId);
	if (!page?.onglets) return null;
	const cible = normaliserChemin(chemin);
	//  Le sous-onglet d'abord : `/mon-lot/location/archives` correspond aussi à la
	//  route de son onglet parent si on ne regarde que le préfixe. On compare des
	//  chemins ENTIERS, et on cherche le plus précis en premier.
	for (const o of page.onglets) {
		for (const s of o.sous ?? []) {
			if (s.route === cible) return { onglet: o.id, sous: s.id };
		}
	}
	for (const o of page.onglets) {
		if (o.route === cible) return { onglet: o.id, sous: o.sous?.[0]?.id ?? null };
	}
	return null;
}

/**
 * L'URL dédiée d'un sous-onglet (`/mon-lot/location/archives`).
 *
 * Lève comme `routeOnglet` : une rangée de sous-onglets qui pointerait vers une
 * adresse inventée mènerait à une 404, et rien ne le dirait avant la production.
 */
export function routeSousOnglet(pageId: string, ongletId: string, sousId: string): string {
	const sous = PAGES.find((p) => p.id === pageId)
		?.onglets?.find((o) => o.id === ongletId)
		?.sous?.find((x) => x.id === sousId);
	if (!sous) {
		throw new Error(
			`Sous-onglet « ${sousId} » absent de l'onglet « ${ongletId} » de la page ` +
				`« ${pageId} » (src/lib/pages.ts).`,
		);
	}
	return sous.route;
}

/**
 * La ROUTE qui rend une adresse d'onglet — `/annonces` → `/sondages`.
 *
 * Employée par `reroute` (`src/hooks.ts`) : les onglets d'une page sont servis
 * par le fichier de cette page, jamais par dix-sept jumeaux. Rend `undefined`
 * quand l'adresse n'est pas une route d'onglet : SvelteKit résout alors
 * normalement (une page ordinaire, ou une 404).
 */
export function routeInterne(chemin: string): string | undefined {
	const cible = normaliserChemin(chemin);
	for (const page of PAGES) {
		if (!page.href || !page.onglets) continue;
		for (const o of page.onglets) {
			const routes = [o.route, ...(o.sous ?? []).map((s) => s.route)];
			//  La route de l'onglet par défaut EST celle de la page : la traduire
			//  vers elle-même est inutile, et masquerait une boucle si elle
			//  divergeait un jour.
			if (routes.includes(cible) && cible !== page.href) return page.href;
		}
	}
	return undefined;
}
