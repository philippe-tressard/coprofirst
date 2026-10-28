/**
 * Les avis sur l'application, côté écran (#2075) — les seuils et les mots.
 *
 * ## Les seuils sont ceux du serveur
 *
 * `NOTE_REMARQUE` et `NOTE_PUBLIABLE` décident de ce que le formulaire
 * DEMANDE ; le serveur (`app/utils/avis.py`) décide de ce qu'il ACCEPTE. Les
 * contextes de build interdisent le partage d'un fichier entre les deux
 * (mémoire `project_partage_front_api_impossible`) : la copie est tenue par
 * `api/tests/test_avis_seuils_front.py`, qui lit ce fichier.
 */
import type { Avis } from '#lib/api/index.ts';
import type { ClasseGouttiere } from '#lib/gouttiere.ts';
import { NOM_PLATEFORME, SITE_PLATEFORME } from '#lib/plateforme.ts';

/** Le site vitrine, tel qu'on le nomme dans une phrase : « coprofirst.fr ». */
export const VITRINE = new URL(SITE_PLATEFORME).host;

/** Sous ce seuil, l'avis dit ce qui a manqué. */
export const NOTE_REMARQUE = 3;
/** À partir de ce seuil, l'auteur dit s'il accepte que l'avis paraisse. */
export const NOTE_PUBLIABLE = 4;

/** Le filtre par note, de la meilleure à la moins bonne — cinq valeurs, des pastilles. */
export const FILTRES_NOTE = [5, 4, 3, 2, 1].map((n) => ({ val: String(n), label: `${n} ★` }));

/** Les deux réponses à la question de publication — et aucune par défaut. */
export const ACCORD_OUI = 'oui';
export const ACCORD_NON = 'non';
export const OPTIONS_ACCORD = [
	{ val: ACCORD_OUI, label: 'Oui' },
	{ val: ACCORD_NON, label: 'Non' },
] as const;

/** La pastille qui correspond à l'accord enregistré — `''` tant qu'on n'a pas répondu. */
export function choixAccord(accord: boolean | null): string {
	return accord === null ? '' : accord ? ACCORD_OUI : ACCORD_NON;
}

/** L'accord à envoyer — `null` tant qu'on n'a pas répondu : jamais un oui présumé. */
export function accordDe(choix: string): boolean | null {
	return choix === ACCORD_OUI ? true : choix === ACCORD_NON ? false : null;
}

/** Le remerciement, selon ce que l'auteur a accepté (arbitrage du 18/10/2026). */
export function merciPour(avis: Avis): string {
	return avis.consentement_publication
		? `Merci ! Votre témoignage nous aide à faire connaître ${NOM_PLATEFORME}. Il sera relu avant de paraître sur ${VITRINE}.`
		: `Merci pour votre avis : il nous aide à améliorer ${NOM_PLATEFORME}.`;
}

/** La signature d'un avis : « Prénom N. · Rôle » — les deux morceaux servis par l'API. */
export function auteurAvis(avis: Avis): string {
	return [avis.auteur_nom, avis.auteur_role].filter(Boolean).join(' · ');
}

/**  La note dans la gouttière de la carte, sous la date : ce qui CLASSE un avis
 *   (`ux-patterns` §3) — un seul endroit pour la note sur la carte. */
export function classeNote(note: number): ClasseGouttiere {
	return {
		icone: 'star',
		abrege: `${note}/5`,
		libelle: `${note} étoile${note > 1 ? 's' : ''} sur 5`,
	};
}
