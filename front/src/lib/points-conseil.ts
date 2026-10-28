//  Le vocabulaire du POINT CONSEIL SYNDICAL / SYNDIC (#2041) — écrit une fois
//  pour le bandeau, la saisie et le CR global (`#lib/components/reporting/`).
//
//  ⚠️ Aucune fonction d'ici ne touche au réseau ni au DOM : les règles (un point
//  par mode, reprise, non traitées) vivent au serveur, `utils/points_conseil`.

import { nomAffiche } from '#lib/noms.ts';
import type {
	CrAffaire,
	EtatPoint,
	NaturePresent,
	PresentEntree,
	PresentPoint,
} from '#lib/api/index.ts';

/** Ce que dit l'état d'un point, à l'écran. */
export const ETATS_POINT: Record<EtatPoint, { libelle: string; teinte: string }> = {
	en_cours: { libelle: 'En cours', teinte: 'badge-blue' },
	a_valider: { libelle: 'À valider', teinte: 'badge-orange' },
	valide: { libelle: 'Validé', teinte: 'badge-green' },
};

/** Les trois groupes du Qui, dans l'ordre du CR (maquette C1). */
export const GROUPES_PRESENTS: readonly { nature: NaturePresent; libelle: string }[] = [
	{ nature: 'cs', libelle: 'Conseil syndical' },
	{ nature: 'syndic', libelle: 'Syndic' },
	{ nature: 'invite', libelle: 'Invités' },
];

/** Le nom d'un présent : « Prénom NOM » (`nomAffiche`), sinon l'entreprise, sinon « Invité ». */
export function nomPresent(p: {
	prenom?: string | null;
	nom?: string | null;
	entreprise?: string | null;
}): string {
	return nomAffiche(p) || p.entreprise || 'Invité';
}

/** Ce qui suit le nom : fonction et entreprise d'un invité ou d'un membre du syndic. */
export function precisionPresent(p: PresentPoint): string {
	return [p.fonction, nomAffiche(p) ? p.entreprise : null].filter(Boolean).join(', ');
}

/**  Le moyen d'un point à reproposer — un point saisi avant le moyen se lit
 *   par `a_distance` (#2041). */
export function moyenDe(point: { moyen: string | null; a_distance: boolean }): string {
	return point.moyen ?? (point.a_distance ? 'visio' : 'sur_place');
}

/**  Les présents d'un point, rendus en ce que l'API attend : un membre par sa
 *   fiche (le serveur recopie son nom), un invité par ses champs. */
export function entreesDepuisPresents(presents: readonly PresentPoint[]): PresentEntree[] {
	return presents.map((p) =>
		p.nature === 'invite'
			? {
					nature: 'invite',
					prenom: p.prenom,
					nom: p.nom,
					entreprise: p.entreprise,
					fonction: p.fonction,
					telephone: p.telephone,
					email: p.email,
				}
			: { nature: p.nature, membre_id: p.membre_cs_id ?? p.membre_syndic_id },
	);
}

/** La fiche d'un membre coché — `cs-3`, `syndic-7` : la clé d'une pastille du Qui. */
export function cleMembre(nature: NaturePresent, id: number | null | undefined): string {
	return `${nature}-${id ?? ''}`;
}

/** L'état d'un CR d'affaire, en un mot — ce que la ligne du tableau en montre. */
export function etatCr(cr: CrAffaire | undefined): string {
	if (!cr) return '';
	return cr.brouillon ? 'Brouillon' : 'CR saisi';
}

/**  « CS et présents » (#2082, ex-« Conseil seul ») : le CR se lit du conseil et
 *   des présents — PDF et validation compris —, masqué au fil et dans l'affaire. */
export const LIBELLE_CS_ET_PRESENTS = 'CS et présents';
