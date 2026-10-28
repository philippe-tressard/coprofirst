/**
 * Le vocabulaire des petites annonces — types, catégories, statuts et leurs rendus.
 *
 * Extrait de `routes/(app)/sondages/+page.svelte` le 14/08/2026 : cette page porte
 * TROIS rubriques (sondages, boîte à idées, petites annonces) et dépassait les
 * 1 000 lignes, deux fois le plafond de modularité (rang 1 §4). La règle est « au
 * fil de l'eau » — on découpe le fichier quand on y touche, et le contrôle de CI
 * refuse qu'il grossisse encore.
 *
 * Ces tables vivent ici plutôt que dans `AnnonceCard.svelte` parce qu'elles sont
 * lues des deux côtés : la carte les rend, la page en fait ses filtres et son
 * formulaire de dépôt. Les laisser dans le composant aurait obligé la page à les
 * recopier — la duplication que tout le reste du projet passe son temps à défaire.
 *
 * ⚠️ Emojis en `\u{…}` : hors du plan multilingue de base, ils survivent mal aux
 * allers-retours d'encodage sous Windows (cf. skill `svelte-patterns`).
 */

import { classeDe, type ClasseGouttiere, type MarqueGouttiere } from '#lib/gouttiere.ts';

/**  Photos d'une petite annonce. ⚠️ Bornée CÔTÉ SERVEUR — `routers/annonces.py`
 *   refuse au-delà (`MAX_PHOTOS = 5`). Les deux doivent rester d'accord :
 *   `api/tests/test_plafonds_pieces_jointes.py` le vérifie. */
export const MAX_PHOTOS_ANNONCE = 5;

/**  Photos d'une AFFICHE DE HALL. ⚠️ Bornée côté serveur elle aussi —
 *   `utils/annonce_hall.py` (`MAX_PHOTOS = 2`), et `POST /annonces-hall` refuse
 *   en **422** au-delà.
 *
 *   🔴 L'écran passait `MAX_FICHIERS` (10) jusqu'au 01/09/2026 : un conseiller
 *   qui ajoutait cinq photos remplissait tout son formulaire, cliquait, et
 *   perdait sa saisie sur un 422. Le manuel, lui, disait « 1 ou 2 » — il avait
 *   raison, c'est l'écran qui mentait.
 *
 *   La raison de la limite est le format : au-delà de deux, l'affiche déborde du
 *   feuillet et le format A4/A5 n'est plus tenu. Ce n'est donc pas un plafond
 *   d'interface, c'est une contrainte du document. */
export const MAX_PHOTOS_AFFICHE = 2;

export const TYPES_ANNONCE = [
	{ val: 'vente', label: '\u{1F3F7}️ Vente' },
	{ val: 'don', label: '\u{1F381} Don' },
	{ val: 'recherche', label: '\u{1F50D} Recherche' },
];

/**  La marque de GOUTTIÈRE de chaque type (10/10/2026, la page Affaires devenue
 *   le standard du site) : le type est ce qui CLASSE une annonce, comme la
 *   nature classe une affaire. L'émoji reste celui du filtre ; la carte dessine
 *   son pictogramme au trait. Le catalogue n'a ni étiquette ni cadeau : la vente
 *   prend le reçu, le don la poignée de main au cœur. */
const MARQUES_ANNONCE: Record<string, MarqueGouttiere> = {
	vente: ['receipt', 'VENTE'],
	don: ['heart-handshake', 'DON'],
	recherche: ['search', 'RECH.'],
};

/**  Ce qui CLASSE une annonce dans la gouttière de sa carte — son type —, ou
 *   rien pour un type inconnu : un classement ne s'invente pas. */
export function classementAnnonce(val: string): ClasseGouttiere | null {
	return classeDe(TYPES_ANNONCE, MARQUES_ANNONCE, val);
}

/**  Les ordres de la liste des annonces. Un TRI, pas un filtre : il n'a pas
 *   d'entrée vide et échappe au seuil des listes courtes (`PastilleDeroulante`,
 *   prop `tri`). La première est l'ordre par défaut. */
export const TRIS_ANNONCE = [
	{ val: 'recent', label: 'Plus récentes' },
	{ val: 'prix_asc', label: 'Prix croissant' },
	{ val: 'prix_desc', label: 'Prix décroissant' },
];

export const CATEGORIES_ANNONCE = [
	{ val: 'appartement', label: '\u{1F3E0} Appartement' },
	{ val: 'parking_cave', label: '\u{1F17F}️ Parking / Cave' },
	{ val: 'mobilier', label: '\u{1F6CB}️ Mobilier' },
	{ val: 'electromenager', label: '\u{1FAD9} Électroménager' },
	{ val: 'high_tech', label: '\u{1F4BB} High-tech' },
	{ val: 'vehicule', label: '\u{1F697} Véhicule' },
	{ val: 'vetements', label: '\u{1F457} Vêtements' },
	{ val: 'services', label: '\u{1F6E0}️ Services' },
	{ val: 'divers', label: '\u{1F4E6} Divers' },
];

/**
 * 🔴 **LE WORKFLOW d'une annonce** — section 3 du cadre #430, arbitré par
 * l'utilisateur le 18/08/2026.
 *
 * ⚠️ Contredit la déclaration de la veille (`entites/annonce.ts`), qui posait
 * `sansObjet` : *« une annonce n'a pas d'étapes de vie suivies à plusieurs »*.
 * C'était mon arbitrage, pas celui du produit. La déclaration a été corrigée
 * avec — une entité ne peut pas dire une chose et son écran une autre, et
 * `lint:etats` le refuserait.
 *
 * **Donné** est distinct de **Vendu** : le type « Don » n'aboutit pas à une
 * vente, et « Vendu » sonnerait faux sur un objet donné.
 *
 * ⚠️ **`archive` n'est pas dans cette liste**, et c'est délibéré : l'archivage
 * n'est pas une étape qu'on choisit, c'est une conséquence du temps. Il se
 * calcule côté serveur (`est_archivee`) et arrive dans le champ `archivee`.
 * En faire une pastille aurait donné deux notions pour la même chose.
 */
export const STATUTS_ANNONCE = [
	{ val: 'en_cours', label: 'En cours' },
	{ val: 'reserve', label: 'Réservé' },
	{ val: 'vendu', label: 'Vendu' },
	{ val: 'donne', label: 'Donné' },
	{ val: 'annule', label: 'Annulé' },
];

/** La forme attendue par `WorkflowPastilles`, sans la recopier chez l'appelant. */
export const OPTIONS_STATUT_ANNONCE = STATUTS_ANNONCE.map((s) => ({
	value: s.val,
	label: s.label,
}));

export function statutAnnonceLabel(val: string) {
	return STATUTS_ANNONCE.find((s) => s.val === val)?.label ?? val;
}

export function typeAnnonceLabel(val: string) {
	return TYPES_ANNONCE.find((t) => t.val === val)?.label ?? val;
}

export function categorieAnnonceLabel(val: string) {
	return CATEGORIES_ANNONCE.find((c) => c.val === val)?.label ?? val;
}

export function statutAnnonceClass(val: string) {
	return (
		(
			{
				en_cours: 'badge-green',
				reserve: 'badge-orange',
				vendu: 'badge-blue',
				donne: 'badge-blue',
				annule: 'badge-gray',
			} as Record<string, string>
		)[val] ?? 'badge-gray'
	);
}
