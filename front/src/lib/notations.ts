/**
 * La notation d'un prestataire — ses trois états, leur libellé, et le commentaire
 * qui justifie l'état.
 *
 * ## Trois états depuis le 14/11/2026 (arbitré)
 *
 * Mauvais · Neutre · Excellent, au lieu des cinq étoiles. Le serveur écrit 1, 3 ou 5
 * (`api/app/utils/notes_prestataires.py`) et lit les anciennes notes 1 à 5 par
 * `etat_de_note` : 1-2 → Mauvais, 3 → Neutre, 4-5 → Excellent. Cette table est la
 * SEULE du front : rien ne recopie les seuils.
 *
 * ## Le commentaire : généré, puis libre
 *
 * Les cases cochées (points forts, points faibles) composent une phrase ; le
 * commentaire libre s'ajoute après. Le texte enregistré est la somme des deux.
 */

import { parAttribut } from './table-statuts.ts';
import type { Notation } from './api/index.ts';

export const ETATS = ['mauvais', 'neutre', 'excellent'] as const;
export type Etat = (typeof ETATS)[number];

/**
 * Libellé et teinte de chaque état — UNE table, les colonnes s'en déduisent
 * (`#lib/table-statuts`). Le libellé porte le sens, la teinte (`<Badge>`) le confirme.
 */
export const { libelle: LIBELLE_ETAT, badge: TEINTE_ETAT } = parAttribut({
	mauvais: { libelle: 'Mauvais', badge: 'badge-red' },
	neutre: { libelle: 'Neutre', badge: 'badge-gray' },
	excellent: { libelle: 'Excellent', badge: 'badge-green' },
});

/**
 * L'état d'une MOYENNE (1 à 5, décimale) — pour la carte du prestataire.
 * Seuils déclarés ici : `< 2,5` mauvais · `< 4` neutre · sinon excellent.
 */
export function etatDeMoyenne(moyenne: number): Etat {
	if (moyenne < 2.5) return 'mauvais';
	if (moyenne < 4) return 'neutre';
	return 'excellent';
}

/** Les motifs à cocher, par nature — la liste est ce qui compose la phrase. */
export const POINTS_FORTS = [
	'délai respecté',
	'travail soigné',
	'pièces fournies',
	'interlocuteur réactif',
] as const;
export const POINTS_FAIBLES = [
	'retard',
	'travail à refaire',
	'facture contestée',
	'intervenant injoignable',
] as const;

/** La phrase générée d'après les cases cochées. Vide si rien n'est coché. */
export function phraseGeneree(forts: readonly string[], faibles: readonly string[]): string {
	const morceaux: string[] = [];
	if (forts.length) morceaux.push(`Points forts : ${forts.join(', ')}.`);
	if (faibles.length) morceaux.push(`Points faibles : ${faibles.join(', ')}.`);
	return morceaux.join(' ');
}

/** Le commentaire enregistré : la phrase générée, puis le texte libre. */
export function commentaireComplet(genere: string, libre: string): string {
	return [genere, libre.trim()].filter((s) => s.length > 0).join('\n');
}

/** Les avis d'un exercice comptable, et combien de chaque état (R3d). */
export interface ExerciceAvis {
	annee: number | null;
	libelle: string;
	avis: Notation[];
	compte: Record<Etat, number>;
}

/**
 * Les avis rangés par exercice, le plus récent d'abord ; dans un exercice, l'avis le
 * plus récent d'abord. L'exercice vient du serveur (`exercice_annee`) : la règle du
 * mois de début n'est pas recopiée ici.
 */
export function avisParExercice(notations: readonly Notation[]): ExerciceAvis[] {
	const groupes = new Map<number | null, ExerciceAvis>();
	for (const n of notations) {
		const cle = n.exercice_annee ?? null;
		let g = groupes.get(cle);
		if (!g) {
			g = {
				annee: cle,
				libelle: n.exercice_libelle ?? 'Exercice non renseigné',
				avis: [],
				compte: { mauvais: 0, neutre: 0, excellent: 0 },
			};
			groupes.set(cle, g);
		}
		g.avis.push(n);
		g.compte[n.etat] += 1;
	}
	const liste = [...groupes.values()];
	for (const g of liste) {
		g.avis.sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime());
	}
	return liste.sort((a, b) => (b.annee ?? -Infinity) - (a.annee ?? -Infinity));
}
