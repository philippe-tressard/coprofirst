import type { CorrectionEvolution } from '$lib/api';
import { separerFichiers } from '$lib/fichiers';
import { perimetreHerite } from '$lib/perimetres';
import { richEmpty } from '$lib/publications';
import {
	motifInactif,
	SECTIONS_ORDRE,
	sectionPresente,
	type ConditionInactive,
	type EntiteDeclaree,
	type IdSection,
} from '$lib/entites/types';
/**
 * Le vocabulaire d'un **fil d'évolution** — écrit une fois pour les trois entités
 * qui en portent un : tickets, actualités, événements de calendrier.
 *
 * ## Pourquoi ce module (19/08/2026, signalé à l'écran)
 *
 * > *« Pourquoi mon commentaire sur un ticket a une icône de type relance et non
 * > commentaire ? »*
 *
 * Parce que la même notion était écrite **trois fois, avec trois valeurs** :
 *
 * | Où | `commentaire` | `reponse` | `etat` |
 * |---|---|---|---|
 * | le bouton qui ouvre le formulaire (`HistoriqueTicket`) | 💬 | — | — |
 * | le fil lui-même (`RubriqueHistorique`) | 📝 | 💬 | 🔄 |
 * | le flux d'activité (`api/app/routers/flux/tickets.py`) | 🔧 | 💬 | — |
 *
 * On cliquait donc « 💬 Commenter » et l'entrée s'affichait en 📝 — un mémo, que
 * l'utilisateur a lu comme une relance. Et 💬, l'icône qu'il attendait, était
 * prise par `reponse`.
 *
 * C'est le défaut de #415 (les statuts) et #413 (les champs), sur un troisième
 * objet : *« Chacune était cohérente avec elle-même ; c'est ce qui les rendait
 * invisibles à la relecture. »*
 *
 * ⚠️ **Le geste et son résultat doivent porter le MÊME signe.** C'est la règle
 * qui tranche ici : l'icône de l'entrée est celle du bouton qui l'a créée, pas
 * l'inverse. Un utilisateur ne relit pas une table, il reconnaît un dessin.
 *
 * ## Ce qui reste écrit deux fois, et pourquoi
 *
 * L'API a sa propre table (`flux/tickets.py`) : les contextes de build sont
 * `./api` et `./front`, rien de la racine n'entre dans les images — aucun fichier
 * ne peut être partagé (cf. la mémoire projet du 14/08/2026). Elle décrit
 * d'ailleurs un AUTRE rendu — une carte de flux « ticket mis à jour », pas une
 * entrée de fil — donc son 🔧 n'est pas forcément faux. L'écart est signalé, pas
 * corrigé en silence.
 */

/**
 * Icône d'une entrée de fil.
 *
 * `commentaire` → 💬, **la même que le bouton « Commenter »**.
 * `reponse` → ↩️ : elle répond à quelque chose, ce que la bulle seule ne disait
 * pas — et la bulle revient à qui la mérite.
 * `etat` → 🔄, inchangée : une transition de workflow.
 */
export const EVOLUTION_ICONE: Record<string, string> = {
	commentaire: '\u{1F4AC}',
	reponse: '↩️',
	etat: '\u{1F504}',
	synthese: '🧾', // la synthèse d'une affaire close (#1643)
};

/**
 * L'icône du type, ou celle du commentaire par défaut.
 *
 * ⚠️ Le repli est `commentaire` et non un point d'interrogation : un type inconnu
 * vient forcément d'une entrée de fil, et lui donner un signe d'erreur ferait
 * croire à un défaut de la donnée là où il n'y a qu'un type que l'écran ne
 * connaît pas encore.
 */
export function evolutionIcone(type: string | undefined | null): string {
	return EVOLUTION_ICONE[type ?? ''] ?? EVOLUTION_ICONE.commentaire;
}

/**
 * Les entrées que le FIL raconte — toutes, sauf la Suite de synthèse (#1643).
 *
 * Elle n'a aucun texte (il vit dans sa table) : `SyntheseFil` la rend en bloc
 * au-dessus du fil, sur la carte comme sur la fiche (15/10/2026). Le fil et son
 * compte (« La suite · n ») lisent la même liste, d'ici.
 */
export function entreesDuFil<T extends { type: string }>(evolutions: readonly T[]): T[] {
	return evolutions.filter((e) => e.type !== 'synthese');
}

/**
 * **La charge utile qu'un formulaire d'évolution émet** — le contrat entre
 * `EvolForm` et ceux qui la relaient à l'API.
 *
 * ## Pourquoi ce type existe (#529, 20/08/2026)
 *
 * Signalé à l'écran : *« j'ai créé une réponse au ticket en changeant le
 * périmètre, celui-ci n'a pas été pris en compte »*.
 *
 * `CarteTicket` proposait bien la section Périmètre, `EvolForm` la collectait et
 * l'émettait — et `tickets/+page.svelte` la **jetait** en recopiant la charge
 * utile champ par champ, à partir d'un type local qui l'ignorait. Ce type local
 * portait pourtant le commentaire *« même contrat que la fiche détail »*, ce qui
 * était faux : la fiche, elle, relaie la charge entière.
 *
 * 🔴 **Le défaut ne lève rien.** Le formulaire annonce l'enregistrement, le
 * serveur enregistre une évolution parfaitement valide, et seul le périmètre
 * affiché ensuite trahit la perte. C'est le profil d'erreur qu'aucun test
 * fonctionnel ne voit et qu'une relecture ne trouve pas — il faut comparer deux
 * fichiers distants de quatre cents lignes.
 *
 * ⚠️ Un champ ajouté ici doit l'être **aussi** dans le `dispatch` d'`EvolForm` et
 * dans le client d'API. `npm run lint:charge-utile` échoue si un relais oublie
 * un champ que le formulaire émet.
 */
export interface ChargeUtileEvolution {
	/** « Rédigé avec l'assistant IA » (#985) — seulement quand c'est vrai. */
	assiste_ia?: boolean;
	type: string;
	contenu?: string;
	nouveau_statut?: string;
	fichiers_urls?: string[];
	/** Les affaires à LIER — une Suite ajoute, elle ne retire rien (#1342). */
	affaires_liees?: number[];
	/** 🔀 Les affaires à ABSORBER en clôturant (#1704) — posé par `SuiteAffaire`, jamais par `EvolForm`. */
	fusionner?: number[];
	email_externe?: string;
	partager_whatsapp?: boolean;
	envoyer_syndic?: boolean;
	envoyer_cs?: boolean;
	/**  « M'envoyer une copie » — la 4e case de la Diffusion (31/08/2026). Un
	 *   CHOIX, jamais un envoi implicite : le formulaire annonçait trois
	 *   destinataires et en servait quatre. */
	envoyer_auteur?: boolean;
	/**  Le périmètre que l'entrée PRÉCISE — absent quand elle n'en parle pas, et
	 *   le serveur ne touche alors pas à celui de l'objet (#497). */
	perimetre_cible?: string[];
	/**  À qui l'on parle — émis quand la section Destinataires est affichée, et
	 *   appliqué par le serveur au conseil seul (une actualité, #1091). */
	public_cible?: string[];
	/**  Message interne : proposé seulement là où `avecInterne` est activé, donc
	 *   aujourd'hui la seule fiche d'un ticket. */
	interne?: boolean;
	/**  🔴 LES OPTIONS DE PUBLICATION D'UN TICKET (05/09/2026) — corrigées depuis
	 *   un commentaire, comme sur une actualité : le formulaire montre le dernier
	 *   état, ce qu'on enregistre devient l'état.
	 *
	 *   ⚠️ Elles ne sortent PAS d'`EvolForm`, qui reste générique : l'écran les
	 *   fusionne dans la charge utile (`optionsVersTicket`). Elles voyagent ici
	 *   parce que c'est ce type que les relais recopient — et un relais qui
	 *   énumère ses champs jette ce qu'il ne nomme pas (#529). */
	epingle?: boolean;
	urgente?: boolean;
	confidentiel?: boolean;
	/**  En CORRECTION seulement : le Suivi était à l'écran, donc `type` et
	 *   `nouveau_statut` disent l'état corrigé (01/10/2026). Absent, la correction
	 *   ne touche pas au Suivi — une actualité n'en a pas. */
	corrige_suivi?: boolean;
}

/**
 * Ce qu'une correction lit de l'entrée corrigée — la forme commune aux fils qui
 * la passent (`RubriqueHistorique` rend des entrées de plusieurs entités).
 */
export interface EntreeCorrigee {
	id: number;
	type: string;
	contenu?: string;
	fichiers_urls?: string[];
	perimetre_cible?: string[];
	nouveau_statut?: string;
	/** L'état d'avant elle, calculé par le serveur (`TicketEvolution.statut_avant`). */
	statut_avant?: string | null;
}

/**  Ce qui ne part pas en correction : les canaux (la Suite est déjà partie),
 *   le message interne, et le Suivi — remis seulement s'il était à l'écran. */
const HORS_CORRECTION = new Set<string>([
	'partager_whatsapp',
	'envoyer_syndic',
	'envoyer_cs',
	'envoyer_auteur',
	'email_externe',
	'interne',
	'type',
	'nouveau_statut',
	'corrige_suivi',
]);

/**
 * La charge d'une CORRECTION, tirée de ce que le formulaire émet — la seule
 * écriture, pour les deux relais (fiche et liste).
 *
 * Tout passe, sauf la Diffusion (absente en correction, arbitré le 01/10/2026 :
 * la Suite est déjà partie) et l'adresse externe. Le Suivi ne part que s'il
 * était à l'écran : sinon la Suite garde le sien.
 */
export function chargeCorrection(saisie: ChargeUtileEvolution): CorrectionEvolution {
	const reste = Object.fromEntries(
		Object.entries(saisie).filter(([cle]) => !HORS_CORRECTION.has(cle)),
	);
	return {
		...reste,
		contenu: saisie.contenu ?? '',
		...(saisie.corrige_suivi
			? { type: saisie.type, nouveau_statut: saisie.nouveau_statut ?? null }
			: {}),
	};
}

/**
 * Le contenu riche est-il vide ? (balises retirées, espaces compris)
 *
 * Sorti d'`EvolForm` le 05/09/2026 avec les deux règles qui suivent : ce sont
 * des règles **du fil**, pas de l'affichage — elles répondent à « cette entrée
 * dit-elle quelque chose ? », question qui se pose pareil quel que soit l'écran.
 * La RÈGLE, elle, est celle de toute saisie riche : `richEmpty`, dont elle était
 * une copie (le formulaire d'affaire en portait une troisième).
 */
export const contenuRicheVide = richEmpty;

/**
 * 🔴 LE GESTE EST DÉDUIT, il ne se déclare pas.
 *
 * Une pastille laissée sur l'état courant ne change rien : l'entrée est un
 * commentaire. En choisir une autre en fait un changement d'état. C'est ce qui
 * permet UN seul point d'entrée à l'écran — la question « lequel des deux ? » a
 * déjà sa réponse dans ce que l'utilisateur a fait.
 *
 * En CORRECTION, la même règle (01/10/2026) : `statutCourant` est alors l'état
 * d'AVANT l'entrée, et le reprendre en refait un commentaire. L'écran ne pose
 * plus « une correction n'est jamais un changement d'état » — c'est l'entrée
 * qu'on corrige, à sa date, sans ajouter d'étape (`app/utils/suivi_fil.py`).
 */
export function typeDeLEntree(
	nouveauStatut: string,
	statutCourant: string,
): 'commentaire' | 'etat' {
	return nouveauStatut && nouveauStatut !== statutCourant ? 'etat' : 'commentaire';
}

/**
 * Une entrée vaut si elle APPORTE quelque chose : un changement d'état, un
 * texte, ou une pièce jointe. Rien des trois → rien à enregistrer.
 */
export function entreeEnregistrable(
	type: 'commentaire' | 'etat',
	contenu: string,
	nbFichiers: number,
): boolean {
	return type === 'etat' || !(contenuRicheVide(contenu) && nbFichiers === 0);
}

/**
 *  L'état INITIAL d'une entrée de fil, tel qu'`EvolForm` l'ouvre.
 *
 *  Sorti du formulaire le 17/09/2026 (modularité) : trois règles de DONNÉE qui
 *  n'ont rien d'un écran, et qui se lisent — et se testent — sans le monter :
 *    · le périmètre est celui que l'entrée avait déclaré en correction, sinon
 *      l'HÉRITÉ (`perimetreHerite`, 31/08/2026) ;
 *    · les destinataires se replient sur le défaut du site : une liste vide
 *      serait un effacement ;
 *    · 7. Photos · 8. Documents — DEUX sections, jamais une seule (cadre #430) ;
 *      le tri est une règle de FICHIERS (`separerFichiers`), pas de formulaire.
 */
export function etatInitialEntree(
	editMode: boolean,
	initialPerimetre: string[],
	perimetreCourant: string[],
	entrees: { perimetre_cible?: string[] | null }[],
	initialDestinataires: string[],
	initialFichiers: { url: string }[],
	/**  Une AFFAIRE : vides, ses Destinataires sont ceux de sa nature (#1343) —
	 *   « Tous » posé d'office l'ouvrirait aux locataires sans que personne l'ait choisi. */
	destinatairesVides = false,
): { perimetre: string[]; destinataires: string[]; photos: string[]; documents: string[] } {
	const perimetre =
		editMode && initialPerimetre.length
			? [...initialPerimetre]
			: perimetreHerite(perimetreCourant, entrees);
	const destinataires =
		initialDestinataires.length || destinatairesVides ? [...initialDestinataires] : ['résidents'];
	const tries = separerFichiers(editMode ? initialFichiers.map((f) => f.url) : []);
	return { perimetre, destinataires, photos: tries.photos, documents: tries.documents };
}

/**
 * Les sections qu'un ÉCRAN HÔTE pose dans une Suite — la Catégorie, et ce qu'une
 * Suite d'affaire y ajoute : Équipement · Quand · Intervenant pour le conseil
 * (`SectionsSuiteConseil`, #1207), et la Mise en avant (`OptionsEvolutionTicket`,
 * `SectionOptionsPublication`).
 *
 * 🔴 Le créneau ne s'ouvrait que sur `nature` (25/09/2026). L'affaire la déclare
 * `hérité` en évolution : sa Suite ne rendait donc AUCUNE de ces sections, et une
 * affaire ne pouvait pas devenir urgente en cours de suivi.
 */
const SECTIONS_DE_L_HOTE: readonly IdSection[] = [
	'nature',
	'equipement',
	'quand',
	'intervenant',
	'mise_en_avant',
];

/**
 * Les TROIS créneaux d'`EvolForm`, à leur rang (#1326, 25/09/2026).
 *
 * Il n'y en avait qu'UN, rendu après le Suivi et avant le Périmètre : l'Équipement
 * (rang 2) y passait APRÈS le Suivi (3), et la Mise en avant (12) avant le
 * Périmètre (7). Signalé à l'écran : « l'ordre de section d'une affaire n'est pas
 * le même en mode édition et en mode suite ».
 *
 * Le créneau d'une section se DÉDUIT de `SECTIONS_ORDRE` — avant le Suivi, avant
 * le Périmètre, ou après les Destinataires — jamais d'une seconde table : c'est
 * elle qui avait laissé la Suite dans l'ordre d'avant la recomposition du cadre (#1095).
 */
export type Creneau = 'avant_suivi' | 'specifiques' | 'mise_en_avant';

export function creneauDe(id: IdSection): Creneau {
	const rang = SECTIONS_ORDRE.indexOf(id);
	if (rang < SECTIONS_ORDRE.indexOf('suivi')) return 'avant_suivi';
	if (rang < SECTIONS_ORDRE.indexOf('perimetre')) return 'specifiques';
	return 'mise_en_avant';
}

/** Le créneau s'ouvre dès que l'une de ses sections est déclarée en évolution. */
function creneauPresent(entite: EntiteDeclaree, creneau: Creneau): boolean {
	return SECTIONS_DE_L_HOTE.some(
		(id) => creneauDe(id) === creneau && sectionPresente(entite, 'evolution', id),
	);
}

/**
 * Une section du CIBLAGE est-elle offerte dans la Suite, pour cet objet-là ?
 *
 * Présente dans l'état `evolution` ET non éteinte par ce que l'objet EST
 * (`conditions` — la nature d'une affaire, `natureDe`). Une section éteinte
 * ne se rend pas du tout dans une Suite : dans le formulaire, elle reste grisée
 * pour montrer ce qu'un changement de catégorie rallumerait ; une Suite ne
 * change pas la catégorie, il n'y a donc rien à rallumer.
 *
 * 🔴 Les Destinataires d'une affaire SUIVIE ne s'offrent pas dans la Suite
 * (25/09/2026) — voir `sectionsDeLaSuite`.
 */
function sectionDeLaSuite(
	entite: EntiteDeclaree,
	id: IdSection,
	conditions: readonly ConditionInactive[],
): boolean {
	return (
		sectionPresente(entite, 'evolution', id) && !motifInactif(entite, 'evolution', id, conditions)
	);
}

/** Les sections qu'une Suite offre — `EvolForm` n'en décide plus lui-même. */
export interface SectionsDeLaSuite {
	perimetre: boolean;
	destinataires: boolean;
	avantSuivi: boolean;
	specifiques: boolean;
	miseEnAvant: boolean;
	piecesJointes: boolean;
	affairesLiees: boolean;
	diffusion: boolean;
}

/**
 * Ce qu'une Suite (ou la correction d'une entrée) offre, pour CET objet et CE
 * lecteur. Chaque ligne combine ce qui EXISTE (la déclaration de l'entité) et
 * ce que cet utilisateur-ci PEUT (le droit, passé par l'appelant) — jamais l'un
 * à la place de l'autre (#463). Extrait d'`EvolForm` le 25/09/2026 : la règle
 * est pure, et le composant dépassait 500 lignes.
 *
 * 🔴 LE PÉRIMÈTRE SE CORRIGE AUSSI (01/09/2026, à l'écran) :
 *
 * > *« L'édition peut modifier le périmètre (correction d'erreur
 * > d'affectation d'un périmètre) »*
 *
 * La ligne valait `avecPerimetre && !editMode`, au motif que « préciser est un
 * geste de SUIVI, qui raturerait un fait daté en réécrivant une entrée passée »
 * — et le serveur refusait le champ en PATCH, ce qui fermait la question. Le
 * motif vaut pour un RESSERREMENT, pas pour une faute de clic. Et la faute coûte
 * cher : le périmètre d'une entrée écrase celui du ticket, donc une erreur
 * d'affectation reclasse tout le ticket.
 *
 * ⚠️ Côté serveur, la correction ne se propage à l'objet que si l'entrée
 * corrigée est la dernière à avoir précisé quelque chose
 * (`app/utils/perimetre_fil.py`) : corriger une vieille entrée ne défait pas une
 * précision récente.
 */
export function sectionsDeLaSuite(
	entite: EntiteDeclaree,
	conditions: readonly ConditionInactive[],
	droits: {
		perimetre: boolean;
		/**  Choisir les Destinataires change QUI LIT l'objet : un droit, comme le
		 *   périmètre (#2142). La Suite l'accorde au conseil, que seule sa route
		 *   honore (`suite_sections`) ; la réponse, jamais — `MessageCreate` ne
		 *   porte pas le champ. */
		destinataires: boolean;
		piecesJointes: boolean;
		/** L'hôte offre de lier l'affaire à d'autres (#1342). */
		affairesLiees: boolean;
		diffusion: boolean;
		/**  La CORRECTION d'une entrée : la Diffusion s'y tait (01/10/2026) — la
		 *   Suite est déjà partie, et un destinataire ne reçoit jamais deux
		 *   courriels pour un même fait. Toutes les autres sections restent. */
		correction?: boolean;
		/** Les créneaux que l'écran hôte REMPLIT (`$$slots`). */
		creneaux: Record<Creneau, boolean>;
	},
): SectionsDeLaSuite {
	//  🔴 Les Destinataires d'une affaire SUIVIE rouvrent dans la Suite (#1343,
	//  26/09/2026) : elle en a désormais, que `ticket_visible` honore. Ils en
	//  avaient été retirés le 25/09 parce que le serveur les écrivait sans que
	//  rien ne les lise — ce n'est plus vrai. L'hôte donne ceux de sa nature
	//  (`destinatairesParDefautDuTicket`), présélectionnés.
	return {
		perimetre: droits.perimetre && sectionDeLaSuite(entite, 'perimetre', conditions),
		destinataires: droits.destinataires && sectionDeLaSuite(entite, 'destinataires', conditions),
		avantSuivi: droits.creneaux.avant_suivi && creneauPresent(entite, 'avant_suivi'),
		specifiques: droits.creneaux.specifiques && creneauPresent(entite, 'specifiques'),
		miseEnAvant: droits.creneaux.mise_en_avant && creneauPresent(entite, 'mise_en_avant'),
		piecesJointes: droits.piecesJointes && sectionPresente(entite, 'evolution', 'pieces_jointes'),
		affairesLiees: droits.affairesLiees && sectionDeLaSuite(entite, 'affaires_liees', conditions),
		diffusion:
			droits.diffusion && !droits.correction && sectionDeLaSuite(entite, 'diffusion', conditions),
	};
}
