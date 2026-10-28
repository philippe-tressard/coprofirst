import { writable, derived, get } from 'svelte/store';
import { browser } from '$app/env';

import { config as configApi } from '$lib/api';
import { NOM_SITE_PAR_DEFAUT } from '$lib/configSite';

import { fusionnerSurcharge } from '$lib/pages-surcharge';

export interface PageConfig {
	titre: string;
	descriptif: string;
	navLabel: string;
	icone?: string;
	onglets?: Record<string, { label: string; descriptif: string }>;
}

function decodeEscapedHtml(input: string): string {
	if (!input) return '';
	return input
		.replace(/&lt;/gi, '<')
		.replace(/&gt;/gi, '>')
		.replace(/&quot;/gi, '"')
		.replace(/&#39;|&#x27;/gi, "'")
		.replace(/&nbsp;/gi, ' ')
		.replace(/&amp;/gi, '&');
}

/**
 * La configuration effective — défauts, puis ce que l'administration a saisi.
 *
 * 🔴 La règle du repli et les rattrapages d'onglets vivent dans
 * `$lib/pages-surcharge` depuis le 21/09/2026 (#1105) : ils étaient écrits ICI
 * **et** dans l'écran d'administration, au caractère près, et l'une des deux
 * copies ne repliait pas sur les défauts. C'est elle qui affichait trois pages
 * sans nom.
 *
 * Ne reste ici que ce qui est propre à l'AFFICHAGE du site : le décodage des
 * entités HTML d'un descriptif, que l'écran d'édition ne doit justement pas
 * faire — il édite le texte source.
 */
function normalizePageConfig(id: string, parsed: unknown, defaults: PageConfig): PageConfig {
	const next = fusionnerSurcharge(id, parsed, defaults);
	next.descriptif = decodeEscapedHtml(next.descriptif ?? '');
	if (next.onglets) {
		for (const o of Object.values(next.onglets)) {
			o.descriptif = decodeEscapedHtml(o.descriptif ?? '');
		}
	}
	return next;
}

// ── Store global alimenté depuis l'API ──────────────────────────────────────
//  Ré-export : `getPageConfig` et `defautsDePage` sont les deux moitiés d'un même
//  geste — « lis la configuration, avec ces défauts-là » — et `check-pages.mjs`
//  impose déjà de les écrire ensemble. Une page ouvrait pourtant DEUX imports
//  pour cela, ce qui faisait grossir d'une ligne dix fichiers déjà au-dessus du
//  plafond de 500 lignes : le garde-fou de modularité l'a refusé, à raison. La
//  table reste la source (`lib/pages.ts` expose toujours ces fonctions, ce que
//  vérifie le cas zéro de `check-pages.mjs`) ; c'est la PORTE qui est unifiée.
//  L'import de `pages.ts` vers ce fichier est un `import type`, effacé à la
//  compilation : aucun cycle à l'exécution.
export { defautsDePage, configDepuisPage } from '$lib/pages';

export const configStore = writable<Record<string, string>>({});

/**
 * Le nom de la résidence vient d'être enregistré par la fiche (#2056) : l'en-tête,
 * l'onglet du navigateur et le menu le reprennent sans attendre un rechargement.
 * Le nom n'a qu'une source, `site_nom`, que la fiche écrit et relit.
 */
export function nomResidenceEnregistre(nom: string): void {
	configStore.update((c) => ({ ...c, site_nom: nom }));
}

// Nom du site réactif — le repli neutre vient de `$lib/configSite` (#1725)
export const siteNomStore = derived(
	configStore,
	($c) => ($c['site_nom'] ?? '').trim() || NOM_SITE_PAR_DEFAUT,
);

//  La DÉMO PUBLIQUE (#1906) : `mode_demo` est une clé CALCULÉE par le serveur
//  (`GET /config`), jamais saisie — le bandeau, la connexion par personnage et
//  les encarts des onglets fermés la lisent ici.
export const modeDemoStore = derived(configStore, ($c) => $c['mode_demo'] === '1');

let _configLoaded = false;

/**
 * Charge la configuration depuis l'API et peuple le store.
 * Idempotente : ne refait pas appel réseau si déjà chargée.
 */
export async function loadSiteConfig(): Promise<void> {
	if (!browser || _configLoaded) return;
	// Store déjà alimenté depuis le SSR root layout → pas besoin de refetch
	if (Object.keys(get(configStore)).length > 0) {
		_configLoaded = true;
		return;
	}
	_configLoaded = true;
	try {
		//  🔴 `fetch('/api/config')` en dur jusqu'au 12/09/2026 (#932).
		//
		//  Le chemin était écrit ici et dans `$lib/api/administration` — deux
		//  écritures d'une même route, dont l'une échappait aux deux contrôles :
		//  `lint:client-api` ne lit pas les stores, et `lint:client-appele`
		//  croyait `config.get` appelée parce que neuf objets du client portent
		//  un `.get`. La méthode était morte et la route dupliquée, en silence.
		//
		//  ⚠️ Passer par le client n'ajoute pas de renouvellement de session
		//  parasite : `GET /config` répond 200 à un anonyme, donc le 401 qui
		//  déclenche `tryRefresh` ne se présente pas ici.
		configStore.set(await configApi.get());
	} catch {
		_configLoaded = false; // autoriser retry si erreur réseau
	}
}

/**
 * Retourne la config d'une page à partir du store brut (réactif via $configStore).
 * Utiliser : $: _pc = getPageConfig($configStore, 'id', defaults)
 */
export function getPageConfig(
	raw: Record<string, string>,
	id: string,
	defaults: PageConfig,
): PageConfig {
	try {
		const s = raw[`page_config_${id}`];
		if (s) {
			const parsed = normalizePageConfig(id, JSON.parse(s), defaults);
			return { ...defaults, ...parsed };
		}
	} catch {
		/* ignore */
	}
	return defaults;
}

/** Compat backward — retourne la valeur synchrone du store. */
export function getSiteNom(): string {
	return get(siteNomStore);
}
