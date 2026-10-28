/**
 * **Les catégories de la FAQ, et qui les voit.** Fonctions PURES.
 *
 * Extraites de `routes/(app)/faq/+page.svelte` le 25/09/2026 (#1043) : la page
 * dépassait six cents lignes, et le garde-fou de modularité demande de découper
 * le fichier qu'on touche. La coupe suit la nature du code : ici ce qui se
 * calcule sans écran — le libellé d'une catégorie, et le tri de ce qu'un statut
 * doit lire —, dans la page ce qui se montre.
 *
 * ⚠️ Les catégories sont du TEXTE administrable, pas une énumération : on les
 * reconnaît donc par les mots qu'elles portent, accents et casse repliés.
 */
import { replier } from '#lib/texte.ts';

export function normalizeCategorieLabel(cat: string | null | undefined): string {
	const original = cat ?? 'Général';
	const n = replier(original);
	if (n.includes('coproprietaire') && n.includes('mandataire')) {
		return '📋 Copropriétaire bailleur';
	}
	return original;
}

function isLocataireCategory(cat: string): boolean {
	return replier(cat).includes('locataire');
}

function isCoproBailleurCategory(cat: string): boolean {
	const n = replier(cat);
	return n.includes('coproprietaire') && (n.includes('bailleur') || n.includes('mandataire'));
}

function isCoproResidentCategory(cat: string): boolean {
	const n = replier(cat);
	return n.includes('coproprietaire') && n.includes('resident');
}

function isCoproprietaireStatus(statut: string): boolean {
	return replier(statut).includes('coproprietaire');
}

function isCoproBailleurStatus(statut: string): boolean {
	const n = replier(statut);
	return isCoproprietaireStatus(statut) && (n.includes('bailleur') || n.includes('mandataire'));
}

function isCoproResidentStatus(statut: string): boolean {
	return isCoproprietaireStatus(statut) && replier(statut).includes('resident');
}

/** Les questions rangées par catégorie, libellés normalisés. */
export function grouperParCategorie<T extends { categorie?: string | null }>(
	items: T[],
): Record<string, T[]> {
	return items.reduce((acc: Record<string, T[]>, it) => {
		const cat = normalizeCategorieLabel(it.categorie ?? 'Général');
		if (!acc[cat]) acc[cat] = [];
		acc[cat].push(it);
		return acc;
	}, {});
}

/**
 * Les catégories qu'un statut doit lire : un locataire ne voit pas celles des
 * copropriétaires, un résident pas celles des bailleurs, et inversement. Sans
 * statut connu, tout reste visible.
 */
export function categoriesPourStatut<T>(
	grouped: Record<string, T[]>,
	statut: string | null | undefined,
): Record<string, T[]> {
	if (!statut) return grouped;

	const out: Record<string, T[]> = {};
	for (const [cat, catItems] of Object.entries(grouped)) {
		if (replier(statut) === 'locataire') {
			if (isCoproResidentCategory(cat) || isCoproBailleurCategory(cat)) continue;
			out[cat] = catItems;
			continue;
		}

		if (isCoproResidentStatus(statut)) {
			if (isLocataireCategory(cat) || isCoproBailleurCategory(cat)) continue;
			out[cat] = catItems;
			continue;
		}

		if (isCoproBailleurStatus(statut)) {
			if (isLocataireCategory(cat) || isCoproResidentCategory(cat)) continue;
			out[cat] = catItems;
			continue;
		}

		if (isCoproprietaireStatus(statut)) {
			if (isLocataireCategory(cat)) continue;
			out[cat] = catItems;
			continue;
		}

		out[cat] = catItems;
	}
	return out;
}

/**
 * La SAISIE d'une question, en un objet (#1329).
 *
 * Cinq champs liés un par un, à deux endroits — la création en tête de liste,
 * la correction dans la carte : chaque montage aurait recopié ses cinq
 * liaisons. Un objet se lie d'un geste, et ses deux constructions s'écrivent ici.
 */
export interface SaisieFaq {
	categorie: string;
	nouvelleCategorie: string;
	estNouvelleCategorie: boolean;
	question: string;
	reponse: string;
}

/** La valeur sentinelle du choix « ➕ Nouvelle catégorie… ». */
export const NOUVELLE_CATEGORIE = '__new__';

export function saisieFaqVide(): SaisieFaq {
	return {
		categorie: '',
		nouvelleCategorie: '',
		estNouvelleCategorie: false,
		question: '',
		reponse: '',
	};
}

/**  La saisie d'une question existante : sa catégorie est choisie si elle est
 *   en service, sinon elle se présente comme une nouvelle catégorie à nommer. */
export function saisieFaqDepuis(
	it: { question: string; reponse: string; categorie?: string | null },
	categories: readonly string[],
): SaisieFaq {
	const cat = it.categorie ?? '';
	const connue = categories.includes(cat);
	return {
		categorie: connue ? cat : NOUVELLE_CATEGORIE,
		nouvelleCategorie: connue ? '' : cat,
		estNouvelleCategorie: !connue,
		question: it.question,
		reponse: it.reponse,
	};
}

/** La catégorie qui part au serveur. */
export function categorieSaisie(f: SaisieFaq): string {
	return (f.estNouvelleCategorie ? f.nouvelleCategorie : f.categorie).trim();
}

/**  La question qui mène à la demande d'accès (le prix d'un badge) : sa carte
 *   porte les boutons « Faire une demande », et `#badge-prix` l'ouvre. */
export function estQuestionPrixBadge(question: string | null | undefined): boolean {
	return !!question && /quel\s+prix.*badge|prix.*badge|badge.*prix/i.test(question);
}
