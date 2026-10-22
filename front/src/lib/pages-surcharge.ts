/**
 * **Une surcharge absente retombe sur la source** — jamais sur du vide.
 *
 * ## 🔴 Le défaut (#1105, 21/09/2026, capture à l'appui)
 *
 * Dans **Administration → Présentation → Menu et pages**, trois entrées
 * s'affichaient **sans nom** : seulement leur icône et leur descriptif.
 *
 * Elles ont pourtant toutes un `nom` dans `pages.ts`. Ce qui manquait est
 * ailleurs : l'écran partait de l'ENREGISTREMENT (`{...saved}`) et n'y
 * réimposait que `id` et `href`. Or ce qui est enregistré est `PageConfig` —
 * titre, descriptif, libellé de menu, icône, onglets —, et **`nom` n'en fait
 * pas partie**, parce qu'il n'est pas administrable.
 *
 * Donc : toute page dont la configuration avait été enregistrée une fois
 * perdait son nom à l'affichage. Les trois vues n'étaient pas trois anomalies,
 * c'étaient les trois pages qu'on avait éditées.
 *
 * ⚠️ **C'est le cas zéro appliqué à une surcharge** : une valeur *absente* lue
 * comme une valeur *vide*. Le dépôt en a déjà un exemple nommé — huit variables
 * de modèle d'e-mail annoncées perdues alors que rien ne manquait (09/09/2026).
 * La forme est toujours la même, et elle est toujours silencieuse.
 *
 * ## Pourquoi cette fonction est ICI, et pas dans les deux écrans
 *
 * Elle l'était **deux fois** : `normalizePageConfig` (le store, qui sert le
 * site) et `normalizeSavedPageDef` (l'écran d'administration). Les deux
 * portaient les **mêmes** rattrapages historiques — l'onglet `consommation`
 * des prestataires, les libellés `validations` de l'Espace CS — recopiés au
 * caractère près. Deux copies d'une règle, c'est deux occasions de la corriger
 * à moitié : c'est exactement ce qui est arrivé, l'une ayant reçu le repli sur
 * les défauts et l'autre non.
 *
 * 🔒 `npm run lint:pages-surcharge` éprouve cette fonction — le front n'ayant
 * pas de lanceur de tests, c'est le pattern de `check-liste-depliable.mjs` :
 * fonction pure + `--selftest`, sur le module que le site embarque.
 */
import type { PageConfig } from '$lib/stores/pageConfig';

/** Ce qu'un onglet porte, une fois la forme historique convertie. */
export interface OngletSurcharge {
	label: string;
	descriptif: string;
}

/**
 * Les rattrapages d'identifiants d'onglets, écrits **une seule fois**.
 *
 * ⚠️ Ils ne sont pas symétriques, et la différence est voulue :
 *
 * - un onglet **renommé** se reporte (`consommation` → `consommations`) ;
 * - un onglet **disparu** se retire, et l'on ne le réinjecte jamais depuis les
 *   défauts — cela ressusciterait sa clé à chaque ouverture de la page.
 *
 * Les défauts ne portent plus ces onglets : c'est la configuration **déjà
 * enregistrée chez l'utilisateur** qu'on nettoie, et elle survit aux
 * déploiements.
 */
const RENOMMAGES: Record<string, Array<[string, string]>> = {
	prestataires: [['consommation', 'consommations']],
};

const RETRAITS: Record<string, string[]> = {
	//  « Prestations ponctuelles » a disparu avec l'objet qu'il rendait.
	prestataires: ['devis'],
	//  « Tickets résidence », retiré le 28/08/2026 — redondant avec la page.
	'espace-cs': ['tickets'],
};

/**
 * Les valeurs qu'un enregistrement ancien porte et qu'il faut REPRENDRE aux
 * défauts : l'utilisateur ne les a pas choisies, elles ont été figées par une
 * version antérieure du produit.
 */
const VALEURS_FIGEES: Array<{
	page: string;
	onglet: string;
	champ: keyof OngletSurcharge;
	ancienne: string;
}> = [
	{ page: 'espace-cs', onglet: 'validations', champ: 'label', ancienne: '✅ Validations' },
	{
		page: 'espace-cs',
		onglet: 'validations',
		champ: 'descriptif',
		ancienne: "Comptes en attente de validation et demandes d'accès à traiter.",
	},
];

/** Les onglets d'une surcharge, ramenés à la forme `{ label, descriptif }`. */
function onglets(
	brut: unknown,
	defauts: Record<string, OngletSurcharge> | undefined,
): Record<string, OngletSurcharge> | undefined {
	if (!brut || typeof brut !== 'object') return undefined;
	const sortie: Record<string, OngletSurcharge> = {};
	for (const [id, v] of Object.entries(brut as Record<string, unknown>)) {
		if (typeof v === 'string') {
			//  Forme historique : la valeur était le seul libellé. Le descriptif
			//  vient alors des défauts — il n'a jamais été saisi.
			sortie[id] = { label: v, descriptif: defauts?.[id]?.descriptif ?? '' };
		} else if (v && typeof v === 'object') {
			const o = v as Partial<OngletSurcharge>;
			sortie[id] = {
				label: o.label ?? defauts?.[id]?.label ?? '',
				descriptif: o.descriptif ?? defauts?.[id]?.descriptif ?? '',
			};
		}
	}
	return sortie;
}

/**
 * **La configuration effective d'une page** : les défauts, corrigés par ce que
 * l'administration a réellement saisi.
 *
 * 🔴 L'ordre compte, et c'est tout le correctif : les **défauts d'abord**, la
 * surcharge par-dessus. L'inverse — partir de l'enregistrement — perd tout
 * champ que l'enregistrement ne porte pas, et il n'en porte jamais qu'une
 * partie.
 *
 * ⚠️ Une clé présente mais `undefined` ne compte pas comme une saisie : un
 * `onglets: undefined` explicite effacerait sinon les onglets par défaut. Une
 * chaîne **vide**, elle, compte — c'est un choix de l'administrateur, qui a le
 * droit de vider un descriptif.
 *
 * @param id L'identifiant de la page — il décide des rattrapages historiques.
 * @param surcharge Ce que porte `page_config_<id>`, déjà désérialisé.
 * @param defauts Ce que `pages.ts` dit de cette page.
 */
export function fusionnerSurcharge(
	id: string,
	surcharge: unknown,
	defauts: PageConfig,
): PageConfig {
	const s = (surcharge && typeof surcharge === 'object' ? surcharge : {}) as Record<
		string,
		unknown
	>;
	const pris = <T>(clef: string, defaut: T): T => (s[clef] === undefined ? defaut : (s[clef] as T));

	const fusion: PageConfig = {
		titre: pris('titre', defauts.titre),
		descriptif: pris('descriptif', defauts.descriptif),
		navLabel: pris('navLabel', defauts.navLabel),
		icone: pris('icone', defauts.icone),
		onglets: s.onglets === undefined ? defauts.onglets : onglets(s.onglets, defauts.onglets),
	};

	if (fusion.onglets) {
		for (const [ancien, nouveau] of RENOMMAGES[id] ?? []) {
			if (fusion.onglets[ancien] && !fusion.onglets[nouveau]) {
				fusion.onglets[nouveau] = fusion.onglets[ancien];
			}
			delete fusion.onglets[ancien];
		}
		for (const retire of RETRAITS[id] ?? []) delete fusion.onglets[retire];
		for (const v of VALEURS_FIGEES) {
			if (v.page !== id) continue;
			const onglet = fusion.onglets[v.onglet];
			const defaut = defauts.onglets?.[v.onglet];
			if (onglet && defaut && onglet[v.champ] === v.ancienne) {
				onglet[v.champ] = defaut[v.champ];
			}
		}
	}

	return fusion;
}
