/**
 * Ce que l'écran de l'état descriptif calcule à partir de ce que le serveur rend —
 * des fonctions PURES, sans appel ni état.
 *
 * Les colonnes de clés portent le nom que le règlement leur donne (« Escalier A' »,
 * « Charges générales ») : il tient mal dans un tableau de treize colonnes. L'en-tête
 * montre une forme COURTE ; le nom entier reste dans l'infobulle et dans le nom
 * accessible de la colonne.
 */
import type { LigneEtatDescriptif } from '#lib/api/index.ts';
import { sansAccents } from '#lib/texte.ts';

/** Mot du règlement → son abréviation d'en-tête. Un mot inconnu reste tel quel. */
const ABREVIATIONS: Record<string, string> = {
	batiment: 'Bât.',
	ascenseur: 'Asc.',
	escalier: 'Esc.',
	generales: 'Gén.',
	generale: 'Gén.',
	charges: '',
	communes: '',
	parties: '',
};

/** « Ascenseur A » → « Asc. A » ; « Charges générales » → « Gén. ». */
export function abregerCle(libelle: string): string {
	const mots = libelle.trim().split(/\s+/);
	const courts = mots.map((mot) => {
		const brut = sansAccents(mot).toLowerCase();
		return brut in ABREVIATIONS ? ABREVIATIONS[brut] : mot;
	});
	const court = courts.filter(Boolean).join(' ');
	return court || libelle;
}

/** La somme d'une clé sur TOUTES les lignes lues (jamais sur celles qu'une recherche laisse). */
export function sommeDeCle(lignes: LigneEtatDescriptif[], code: string): number {
	return lignes.reduce((total, l) => total + (l.quotes[code] ?? 0), 0);
}

/** L'écart d'une somme au dénominateur déclaré, en toutes lettres (infobulle du pied de tableau). */
export function libelleEcart(denominateur: number, somme: number): string {
	const ecart = denominateur - somme;
	if (ecart === 0) return 'La somme tombe juste';
	return ecart > 0
		? `Il manque ${ecart} sur ${denominateur}`
		: `${-ecart} de trop sur ${denominateur}`;
}
