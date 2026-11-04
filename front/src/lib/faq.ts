/**
 * **La FAQ côté écran** — ce qui se calcule sans écran. Fonctions PURES.
 *
 * Extraites de `routes/(app)/faq/+page.svelte` le 25/09/2026 (#1043) : la page
 * dépassait six cents lignes, et le garde-fou de modularité demande de découper
 * le fichier qu'on touche.
 *
 * 🔴 Le LIBELLÉ d'une catégorie (« 📋 Copropriétaire bailleur ») et le tri de
 * ce qu'un statut lit vivaient ici (`normalizeCategorieLabel`,
 * `categoriesPourStatut`) : l'app iOS, qui ne lit que le contrat de l'API,
 * montrait donc toutes les catégories sous leur nom brut. Le serveur les sert
 * depuis #2506 (`api/app/utils/faq_categories.py`) : `GET /faq` ne rend que ce
 * que le lecteur lit, et chaque entrée porte son `categorie_libelle`. L'écran
 * les LIT — `lint:regles-partagees` refuse leur retour ici.
 */

/** Les questions rangées par catégorie, sous le libellé que sert l'API. */
export function grouperParCategorie<T extends { categorie_libelle: string }>(
	items: T[],
): Record<string, T[]> {
	return items.reduce((acc: Record<string, T[]>, it) => {
		const cat = it.categorie_libelle;
		if (!acc[cat]) acc[cat] = [];
		acc[cat].push(it);
		return acc;
	}, {});
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
