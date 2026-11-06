/**
 * Le lien d'un compte à un lot — `TypeLien` côté serveur — en clair.
 *
 * ## Pourquoi ici (06/11/2026, #2562)
 *
 * Deux écrans déclaraient chacun leur table, divergentes : l'import des lots
 * disait « Propriétaire », sa correction « Copropriétaire résident », pour la
 * même valeur. Et Admin › Audit des lots, qui n'en avait aucune, rendait le
 * code brut (« propriétaire », « bailleur »). Une table, deux formes — le
 * libellé (liste déroulante) et sa forme abrégée (pastille d'un tableau dense),
 * comme la table des statuts de `#lib/roles` —, et la teinte de la pastille.
 *
 * L'ordre de la liste est celui de la liste déroulante.
 */
import { parAttributDepuisListe } from '#lib/table-statuts.ts';

export const TYPES_LIEN = [
	{
		value: 'propriétaire',
		libelle: 'Copropriétaire résident',
		abrege: 'Propriétaire',
		//  ⚠️ Un CODE COULEUR, pas une classe de badge : la pastille est pleine, et
		//  la charte ne porte pas ces quatre teintes en badge.
		couleur: 'var(--color-success)',
	},
	{
		value: 'bailleur',
		libelle: 'Copropriétaire bailleur',
		abrege: 'Bailleur',
		couleur: 'var(--color-import-lie)',
	},
	{
		value: 'locataire',
		libelle: 'Locataire',
		abrege: 'Locataire',
		couleur: 'var(--color-warning-texte)',
	},
	{
		value: 'mandataire',
		libelle: 'Mandataire (gestion)',
		abrege: 'Mandataire',
		couleur: 'var(--color-violet)',
	},
] as const;

const COLONNES = parAttributDepuisListe(TYPES_LIEN, 'value');

/**  La teinte de la pastille d'un lien. */
export const COULEUR_TYPE_LIEN: Record<string, string> = COLONNES.couleur;

/**  « propriétaire » → « Propriétaire » : la forme d'une pastille. Un code
 *   inconnu est rendu TEL QUEL — un lien ajouté doit se voir, pas s'effacer. */
export function typeLienAbrege(code: string | null | undefined): string {
	if (!code) return '';
	return COLONNES.abrege[code] ?? code;
}
