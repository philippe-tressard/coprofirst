/**
 * Le vocabulaire du PUBLIC CIBLE — « à qui ça s'adresse ? » — écrit une fois.
 *
 * Il vivait dans `DestinatairePicker.svelte`, donc uniquement dans le
 * SÉLECTEUR : rien ne permettait d'afficher un ciblage ailleurs sans recopier la
 * table. C'est ce qui s'est passé sur la liste des sondages, qui affichait les
 * valeurs BRUTES de la base (« copropriétaire_résident ») dans ses badges.
 *
 * Même partage que `$lib/perimetres.ts` pour l'axe géographique : le sélecteur
 * et l'affichage lisent la même liste, et une valeur ajoutée ici se dit des deux
 * côtés sans qu'on y pense.
 *
 * ⚠️ Les codes sont ceux du serveur (`app/utils/visibility.py`,
 * `CODES_PUBLIC_CIBLE` et `public_cible_visible`). Rien dans le code n'oblige
 * les deux côtés à rester d'accord, et un écart est SILENCIEUX : un code proposé
 * ici mais inconnu du serveur rend la publication invisible de tous, puisque la
 * règle refuse ce qu'elle ne reconnaît pas. C'est
 * `api/tests/test_destinataires_vocabulaire.py` qui lit les deux fichiers et
 * exige le même vocabulaire, dans le même ordre — il a d'ailleurs trouvé que la
 * règle serveur n'honorait pas `conseil_syndical` par elle-même.
 */

/** Ce que « rien de précisé » veut dire. Vide et `['résidents']` sont équivalents. */
export const TOUS_LES_RESIDENTS = 'résidents';

/**
 * Le LIBELLÉ de ce cas — « Tous », et non plus « Tous les résidents »
 * (arbitré le 25/09/2026) : le bailleur n'est pas un résident, et c'est
 * pourtant lui aussi que ce choix vise. Le mot promettait moins que la règle.
 *
 * ⚠️ Seul le libellé change : le CODE reste `résidents`, stocké en base et lu
 * par le serveur (`public_cible_visible`). Le renommer serait une migration.
 */
export const LIBELLE_TOUS = 'Tous';

export type Destinataire = { code: string; libelle: string; icone: string };

export const DESTINATAIRES: Destinataire[] = [
	//  🔴 « Copropriétaires » n'est plus proposée (#1301, 25/09/2026) : elle
	//  couvrait exactement les deux suivantes. Migration 0221 ; la règle du
	//  serveur et la pastille de lecture LISENT encore l'ancien code.
	//  `home` pour l'occupant (il y habite), `building-2` pour le bailleur (il le
	//  loue). Les deux existent au catalogue `$lib/icones-svg.json` — un nom
	//  inconnu y retombe SILENCIEUSEMENT sur `help-circle`.
	{ code: 'copropriétaires_occupants', libelle: 'Copropriétaires occupants', icone: 'home' },
	//  « Copropriétaires bailleurs » et non plus « Bailleurs » (25/09/2026) : le
	//  mot seul désignera celui qui loue PAR DÉLÉGATION d'un copropriétaire. Le
	//  code reste `bailleurs` — stocké, lu par le serveur.
	{ code: 'bailleurs', libelle: 'Copropriétaires bailleurs', icone: 'building-2' },
	//  « Bailleurs » : qui loue PAR DÉLÉGATION — agence, gestionnaire (statut
	//  `mandataire`, #1301). Code `mandataires` : `bailleurs` est déjà stocké.
	{ code: 'mandataires', libelle: 'Bailleurs', icone: 'heart-handshake' },
	{ code: 'locataires', libelle: 'Locataires', icone: 'user' },
	{ code: 'conseil_syndical', libelle: 'Conseil syndical', icone: 'shield-check' },
];

/** Le ciblage vise-t-il tout le monde ? Vide ou `résidents` = oui. */
export function concerneTousLesResidents(codes: string[] | null | undefined): boolean {
	if (!codes || codes.length === 0) return true;
	return codes.length === 1 && codes[0] === TOUS_LES_RESIDENTS;
}

/**
 * Des Destinataires choisis qui ne s'adressent pas à tout le monde : le groupe
 * de la résidence ne reçoit alors que le titre, le périmètre et le lien.
 *
 * ⚠️ Miroir de `visibility._diffusion_ciblee` côté serveur, qui seul DÉCIDE
 * (`sondage_hors_du_groupe`, `contenu_hors_du_groupe`) ; l'écran ne s'en sert
 * que pour dire ce qui partira. `résidents` parmi d'autres vise tout le monde.
 */
export function diffusionCiblee(codes: string[] | null | undefined): boolean {
	return !!codes && codes.length > 0 && !codes.includes(TOUS_LES_RESIDENTS);
}

/**
 * « Conseil syndical » SEUL — l'actualité est réservée au conseil, et RIEN ne
 * sort : ni groupe WhatsApp, ni courriel, ni affiche (#1096, 23/09/2026).
 *
 * ⚠️ Miroir de `visibility.reserve_au_conseil` côté serveur, qui seul DÉCIDE ;
 * l'écran ne s'en sert que pour prévenir avant l'envoi. `conseil_syndical`
 * parmi d'autres publics n'est PAS une réserve : les autres lisent.
 */
export function reserveAuConseil(codes: string[] | null | undefined): boolean {
	return !!codes && codes.length === 1 && codes[0] === 'conseil_syndical';
}

/**
 * Les CODES d'un public cible, qu'il arrive en tableau ou en chaîne JSON — ce
 * que rend l'API. Écrite une fois : la pastille de lecture (`$lib/lecture`) la
 * lit, et deux lectures d'une chaîne abîmée divergeraient sur le cas limite.
 * (Le libellé `destinatairesLabel` qui la lisait aussi est parti avec le badge
 * orange des cartes de la communauté, #1373.)
 */
export function codesDestinataires(valeur: string[] | string | null | undefined): string[] {
	if (Array.isArray(valeur)) return valeur;
	if (typeof valeur !== 'string' || !valeur.trim()) return [];
	try {
		const parse = JSON.parse(valeur);
		return Array.isArray(parse) ? parse.map(String) : [];
	} catch {
		//  Ancien format CSV, ou donnée abîmée : on rend ce qu'on a plutôt que rien.
		return valeur
			.split(',')
			.map((v) => v.trim())
			.filter(Boolean);
	}
}
