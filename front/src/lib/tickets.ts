//  Le workflow d'un ticket — écrit UNE fois, pour les cinq écrans qui l'affichent.
//
//  Avant le 17/08/2026, chaque écran portait sa propre liste : quatre listes
//  d'options et trois tables de libellés, aucune dérivée de l'énumération du
//  serveur. Elles avaient divergé dans les deux sens (#415) — la fiche du ticket
//  proposait `fermé`, la liste et l'espace CS proposaient `annulé`, et le serveur
//  refusait précisément ce dernier. Chacune était cohérente avec elle-même ; c'est
//  ce qui les rendait invisibles à la relecture.
//
//  ⚠️ Ces quatre états sont la notion **Workflow** au sens de `ux-patterns`
//  §9 sexies — « où en est cet objet ? ». À ne pas confondre avec la Diffusion
//  (« qui le voit, et où ? »), ni avec les statuts d'une PUBLICATION, qui sont
//  une autre notion et vivent dans `#lib/publications.ts`.
//
//  La contrepartie serveur est `StatutTicket` (`api/app/models/core.py`), et
//  `api/tests/test_statuts_tickets.py` échoue si les deux divergent.

import {
	GLYPHE_URGENCE,
	optionsActives,
	type CleOptionPublication,
	type OptionPublication,
} from '#lib/options-publication.ts';
import type { Ticket } from '#lib/api/index.ts';
import { nombreOuNull } from '#lib/utils.ts';
import { parAttribut } from '#lib/table-statuts.ts';

//  Les catégories vivent dans leur propre module depuis le 21/09/2026 (500
//  lignes). `#lib/tickets` reste la porte du domaine : tout écran qui importait
//  `CATEGORIES_TICKET` d'ici continue de le faire.
export * from '#lib/tickets-categories.ts';

export interface StatutTicket {
	/** Valeur envoyée à l'API — jamais traduite, jamais réécrite. */
	value: string;
	/** Libellé seul, pour un badge ou une phrase. */
	label: string;
	/** Pastille de couleur, pour une liste d'options. */
	emoji: string;
	/** Classe de badge (`app.css`). */
	badge: string;
}

//: Les six états, dans l'ordre du workflow : c'est celui dans lequel ils
//: s'affichent partout, boutons de la fiche comme listes déroulantes.
//: « À l'AG » et « Chez le prestataire » sont nés le 23/09/2026 (#1092, lot 5) :
//: les colonnes du kanban des événements, qu'aucun état d'affaire ne disait. Leur
//: pastille reprend la couleur de leur colonne (`KANBAN_COLS`).
export const STATUTS_TICKET: readonly StatutTicket[] = [
	{ value: 'ouvert', label: 'Ouvert', emoji: '\u{1F535}', badge: 'badge-blue' },
	{ value: 'en_ag', label: 'À l’AG', emoji: '\u{1F7E3}', badge: 'badge-purple' },
	//  « Chez le syndic » et non plus « En cours » (24/09/2026, arbitré à l'écran) :
	//  À l'AG et Chez le prestataire sont AUSSI en cours — le mot désigne
	//  désormais leur regroupement dans le filtre (`GROUPES_SUIVI`).
	{ value: 'en_cours', label: 'Chez le syndic', emoji: '\u{1F7E1}', badge: 'badge-orange' },
	{
		value: 'chez_prestataire',
		label: 'Chez le prestataire',
		emoji: '\u{1F7E0}',
		badge: 'badge-yellow',
	},
	{ value: 'résolu', label: 'Résolu', emoji: '\u{1F7E2}', badge: 'badge-green' },
	{ value: 'annulé', label: 'Annulé', emoji: '⚫', badge: 'badge-gray' },
];

//: 🔁 Les trois états du suivi OPTIONNEL d'une actualité (10/10/2026) — un
//: sous-ensemble du cycle, tenu ici avec lui. Miroir de `ETATS_SUIVI_ACTUALITE`
//: (`api/app/utils/suivi_actualite.py`) ; ses règles : `#lib/suivi-actualite`.
export const ETATS_SUIVI_ACTUALITE: readonly string[] = ['ouvert', 'résolu', 'annulé'];

//: Options d'un `<select>` ou d'une rangée de boutons — pastille comprise.
export const STATUT_TICKET_OPTIONS = STATUTS_TICKET.map((s) => ({
	value: s.value,
	label: `${s.emoji} ${s.label}`,
}));

//: `fermé` n'est plus un état depuis le 17/08/2026 (migration 0149), mais le fil
//: d'évolutions d'un ticket ancien raconte encore « Ouvert → Fermé ». Il reste
//: donc **affichable**, et n'est jamais proposable : il n'apparaît ni dans
//: `STATUTS_TICKET`, ni dans les options, ni dans les états clos.
const STATUTS_TICKET_HISTORIQUES: Record<string, { label: string; badge: string }> = {
	fermé: { label: 'Fermé', badge: 'badge-gray' },
};

//: L'état SANS CYCLE d'une affaire de catégorie « Actualité » (#1091) : affichable,
//: jamais proposé — seule la catégorie y mène. Pendant de `STATUTS_TICKET_SANS_CYCLE`
//: côté serveur ; `test_statuts_tickets.py` tient la concordance.
const STATUTS_TICKET_SANS_CYCLE: Record<string, { label: string; badge: string }> = {
	publie: { label: 'Publiée', badge: 'badge-blue' },
};

export const STATUT_TICKET_LABELS: Record<string, string> = {
	...Object.fromEntries(STATUTS_TICKET.map((s) => [s.value, s.label])),
	...Object.fromEntries(Object.entries(STATUTS_TICKET_HISTORIQUES).map(([v, h]) => [v, h.label])),
	...Object.fromEntries(Object.entries(STATUTS_TICKET_SANS_CYCLE).map(([v, h]) => [v, h.label])),
};

export const STATUT_TICKET_BADGE: Record<string, string> = {
	...Object.fromEntries(STATUTS_TICKET.map((s) => [s.value, s.badge])),
	...Object.fromEntries(Object.entries(STATUTS_TICKET_HISTORIQUES).map(([v, h]) => [v, h.badge])),
	...Object.fromEntries(Object.entries(STATUTS_TICKET_SANS_CYCLE).map(([v, h]) => [v, h.badge])),
};

//: Un ticket dans l'un de ces états ne demande plus de suivi : il quitte la liste
//: active pour l'Historique, et sort des relances. `fermé` y figure parce que
//: l'affichage d'un ticket ancien ne doit pas dépendre du succès d'une migration.
export const STATUTS_TICKET_CLOS: readonly string[] = ['résolu', 'annulé', 'fermé'];

/**  Les états où une Étude & travaux sans choix du conseil s'ouvre à tous les
 *   copropriétaires (standard du 30/09/2026) : à l'AG, chez le prestataire, et
 *   close. Miroir de `STATUTS_ETUDE_OUVERTE` (`api/app/models/tickets.py`). */
export const STATUTS_ETUDE_OUVERTE: readonly string[] = [
	'en_ag',
	'chez_prestataire',
	...STATUTS_TICKET_CLOS,
];

//: Le complément : un ticket qui demande encore du suivi. La question s'écrivait
//: `t.statut === 'ouvert' || t.statut === 'en_cours'`, deux fois dans le même
//: fichier — trouvée par le garde-fou, pas à la relecture.
//: Déclaré après `STATUTS_TICKET_CLOS`, dont il dépend à l'initialisation.
export const STATUTS_TICKET_ACTIFS: readonly string[] = STATUTS_TICKET.map((s) => s.value).filter(
	(v) => !STATUTS_TICKET_CLOS.includes(v),
);

//: 🔴 LE FILTRE SE DÉDUIT DE LA LISTE, il ne se choisit plus.
//:
//: Il proposait les seuls états ACTIFS, au motif que « les clos ont leur section
//: Historique ». C'était faux d'une semaine : un ticket clôturé reste **sept
//: jours** dans la liste principale (délai de grâce). Un ticket « Résolu » hier
//: s'affiche donc, et aucun bouton ne permettait de l'isoler — signalé à l'écran
//: le 01/09/2026 : *« le filtre ne comprend pas tous les états du workflow
//: pouvant être affichés sur la page (notamment résolu ?) »*.
//:
//: ⚠️ Le défaut n'était pas la liste, c'était sa SOURCE : elle décrivait ce
//: qu'on croyait afficher, pas ce qui s'affiche. Elle se calcule maintenant sur
//: les tickets réellement rendus — ce qui couvre aussi `fermé`, l'état
//: historique qu'aucune liste écrite à la main n'aurait pensé à inclure.
//:
//: L'ordre reste celui du workflow, jamais celui d'apparition : un filtre dont
//: les boutons bougent d'un chargement à l'autre n'est pas un filtre.
//: 🔴 LE FILTRE REGROUPE ce que le travail sépare (24/09/2026, arbitré à
//: l'écran) : « Ouvert · En cours · Résolu », sur une ligne. À l'AG, Chez le
//: syndic et Chez le prestataire sont trois étapes du TRAITEMENT — le kanban
//: et la fiche les distinguent, la liste n'a besoin que de savoir que ça avance.
//: Un groupe ne paraît que si l'un de ses états est présent (règle ci-dessus).
export const GROUPES_SUIVI: readonly {
	value: string;
	label: string;
	statuts: readonly string[];
}[] = [
	{
		value: 'en_cours',
		label: '\u{1F7E1} En cours',
		statuts: ['en_ag', 'en_cours', 'chez_prestataire'],
	},
];

export function statutsPresents(
	tickets: readonly { statut: string }[],
): { value: string; label: string; statuts: readonly string[] }[] {
	const presents = new Set(tickets.map((t) => t.statut));
	const options: { value: string; label: string; statuts: readonly string[] }[] = [];
	for (const o of STATUT_TICKET_OPTIONS) {
		if (!presents.has(o.value)) continue;
		const groupe = GROUPES_SUIVI.find((g) => g.statuts.includes(o.value));
		if (!groupe) options.push({ ...o, statuts: [o.value] });
		else if (!options.some((x) => x.value === groupe.value)) options.push(groupe);
	}
	//: Les états historiques (`fermé`) n'ont pas d'emoji : ils portent leur
	//: libellé seul, ce qui les distingue sans les mettre en avant.
	const historiques = Object.keys(STATUTS_TICKET_HISTORIQUES)
		.filter((v) => presents.has(v))
		.map((v) => ({ value: v, label: STATUT_TICKET_LABELS[v], statuts: [v] }));
	return [...options, ...historiques];
}

/** Le statut d'une affaire relève-t-il de l'option de filtre choisie ? */
export function suiviCorrespond(
	options: readonly { value: string; statuts: readonly string[] }[],
	choix: string,
	statut: string,
): boolean {
	return options.find((o) => o.value === choix)?.statuts.includes(statut) ?? false;
}

//  ── Les catégories — même histoire que les statuts, un cran plus tard ────────
//
/** Ce ticket demande-t-il encore du suivi ? */
export function estTicketActif(statut: string | undefined | null): boolean {
	return STATUTS_TICKET_ACTIFS.includes(statut ?? '');
}

/** Ce ticket est-il clos ? — la seule écriture de cette question côté front. */
export function estTicketClos(statut: string | undefined | null): boolean {
	return STATUTS_TICKET_CLOS.includes(statut ?? '');
}

/**
 * L'identifiant d'une affaire que désigne un lien collé (`…/tickets/465?src=whatsapp`),
 * ou `null` si le texte n'en est pas un.
 */
export function idAffaireDepuisLien(texte: string): number | null {
	const m = /\/tickets\/(\d+)(?:[/?#]|$)/.exec(texte);
	return nombreOuNull(m?.[1]);
}

/** Libellé affichable d'un statut, valeur brute à défaut (jamais vide). */
export function statutTicketLabel(statut: string | undefined | null): string {
	return STATUT_TICKET_LABELS[statut ?? ''] ?? statut ?? '';
}

/**
 * Au nom de qui le conseil syndical ouvre un ticket.
 *
 * Le type vivait dans `FormulaireTicket.svelte`, d'où il n'était pas importable :
 * un `export type` dans le `<script>` d'instance d'un composant n'est pas exporté.
 * Il appartient de toute façon au vocabulaire du ticket, pas à l'écran qui le
 * saisit — comme les statuts et les catégories juste au-dessus.
 */
//  🔴 La notion a QUITTÉ ce fichier le 15/09/2026 : elle sert désormais aux
//  actualités et aux événements autant qu'aux tickets, et la laisser ici
//  aurait fait de « tickets » le domicile d'une règle partagée.
//  Réexporté pour que rien n'ait à changer chez les appelants.
export type { ModeSaisiPour } from '#lib/saisi-pour.ts';

// ── Options de publication ───────────────────────────────────────────────────

/**
 * 🔴 LES OPTIONS DE PUBLICATION D'UN TICKET — le pont écran ⇄ objet, écrit ICI.
 *
 * Demandé à l'écran le 05/09/2026 :
 *
 * > « tous les autres options de publication doivent être aussi conservé dans
 * >   l'objet pour les tickets en édition et commentaire »
 * > « pas que Visibilité du ticket »
 *
 * ## Les clés de l'écran ne sont pas les champs du ticket
 *
 * | Option (table `#lib/options-publication`) | Champ du ticket |
 * |---|---|
 * | `epingle` | `epingle` |
 * | `urgente` | `priorite === 'haute'` — ce que la catégorie « Urgence » pose déjà |
 * | `brouillon` (🛡️ « au seul conseil syndical ») | `confidentiel` |
 *
 * `confidentiel` de la table (🔒 « visible du seul périmètre ») **n'est pas
 * proposé** : un ticket l'est déjà. Sa lecture passe par `perimetre_visible`
 * sans `ouvert_a_la_copropriete`, là où une actualité le passe (#339) — la case
 * n'aurait rien restreint, et une case sans effet est une promesse vide.
 *
 * ⚠️ Deux noms se croisent, et c'est le piège de ce fichier : la clé d'écran
 * `brouillon` écrit la colonne `confidentiel`, tandis que la clé d'écran
 * `confidentiel` ne s'applique pas ici. Les deux sens du pont vivent donc côte
 * à côte, pour qu'aucun ne puisse être corrigé sans l'autre.
 */
/**
 * **Tout ce que la page fait quand une liste de tickets bouge** — un seul objet.
 *
 * 🔴 `ListeTickets` relayait TREIZE événements, et `tickets/+page.svelte` les
 * câblait **deux fois** : une fois pour les tickets actifs, une fois pour les
 * archives. Le fichier le disait lui-même — *« c'est le prix de ce relais ; il se
 * paie à chaque nouvel événement »* — et il s'est payé le 12/09/2026, quand le
 * panneau d'options rapides en a demandé deux de plus.
 *
 * Les événements Svelte ne se transmettent pas en bloc (`{...props}` ne porte que
 * des props) : tant qu'ils sont des `on:`, chaque liste doit les réécrire. En
 * objet, les deux listes passent le même `{gestes}`, et ne peuvent plus diverger.
 *
 * ⚠️ C'est la forme qu'`ActionsActualite` employait déjà (`onCommenter`,
 * `onModifier`, `onOptions`) : l'alignement sur le voisin, pas une exception.
 */
export interface GestesTicket {
	basculer: (t: Ticket) => void;
	evoluerOuvrir: (t: Ticket) => void;
	modifier: (t: Ticket) => void;
	optionsOuvrir: (t: Ticket) => void;
	optionsEnregistrer: (t: Ticket, data: unknown) => void;
	supprimer: (t: Ticket) => void;
	/** 📦 Le geste de la LISTE ; `supprimer` n'est plus offert qu'aux Archives. */
	archiver: (t: Ticket) => void;
	evoluer: (t: Ticket, data: unknown) => void;
	evolModifier: (evolId: number) => void;
	evolCorriger: (t: Ticket, data: unknown) => void;
	evolSupprimer: (e: { ticket: Ticket; evolId: number }) => void;
	evolAnnuler: () => void;
	modifie: (maj: Ticket) => void;
	annuler: () => void;
	/** L'affaire et son fil ont changé dans la carte — un transfert de courriel
	 *  défait, une synthèse produite (#1643) : la page les relit. */
	filChange: (t: Ticket) => void;
	/** 💬 Répondre (`gesteReponse`) : la page de l'affaire ouvre son formulaire
	 *  sur place ; une liste y mène, formulaire ouvert (`?repondre=1`). */
	repondre: (t: Ticket) => void;
}

/**
 * Les options de MISE EN AVANT d'une affaire — l'épinglage et l'urgence.
 *
 * 🔴 🛡️ et 🔒 en sont SORTIS le 25/09/2026 (lot 1 de la pastille de lecture) :
 * ils ne mettent rien en avant, ils disent qui LIT. Ils vivent désormais en
 * tête de leur section — « Confidentielle » en tête de Destinataires,
 * « Réservé au périmètre » en tête de Périmètre —, affaires comprises. La clé
 * `brouillon` continue d'écrire `confidentiel` (`optionsVersTicket`).
 */
export const OPTIONS_TICKET: CleOptionPublication[] = ['epingle', 'urgente'];

/** L'état COURANT des options — ce que le formulaire reprend à l'ouverture. */
export function optionsDuTicket(ticket: Ticket | null | undefined): {
	epingle: boolean;
	urgente: boolean;
	brouillon: boolean;
	suiviKanban: boolean;
	suiviActualite: boolean;
	etatSuivi: string | null;
} {
	return {
		epingle: ticket?.epingle ?? false,
		urgente: ticket?.priorite === 'haute',
		brouillon: ticket?.confidentiel ?? false,
		//  ⚠️ `suivi_kanban` n'est PAS une option de publication : elle ne dit pas
		//  qui voit le ticket, mais s'il paraît au tableau de suivi. Elle voyage
		//  pourtant par ce pont, parce que c'est lui que le formulaire emprunte —
		//  et qu'une seconde charge utile serait une seconde occasion d'oublier
		//  un champ (#833, et le défaut du 31/08 sur cinq écrans).
		suiviKanban: ticket?.suivi_kanban ?? false,
		//  La case « Activer le suivi » d'une actualité (10/10/2026), par le même pont.
		suiviActualite: !!ticket?.suivi_actualite,
		//  …et son état, que le formulaire choisit dès l'ouverture (10/10/2026).
		etatSuivi: ticket?.suivi_actualite ?? null,
	};
}

/**
 * Les options qu'une carte dit DÉJÀ par un badge dédié — et la raison.
 *
 * 🔴 Une affaire urgente portait DEUX badges sur sa carte (signalé à l'écran le
 * 27/09/2026, #TK-109008) : « ⚡ Urgente », le badge de priorité, et
 * « 🚨 Urgente », la rangée des options actives — un badge texte 🚨 que
 * `ux-patterns` §3 exclut (« bord gauche rouge, pas de badge texte 🚨 »). La
 * rangée filtrait `brouillon` en ligne, pour lui seul ; la seconde option
 * rendue ailleurs n'y est jamais entrée. 🔒 `npm run lint:options-en-double` exige qu'un badge dédié de la
 * carte figure ici.
 */
export const OPTIONS_RENDUES_AILLEURS: Partial<Record<CleOptionPublication, string>> = {
	brouillon: '`PastilleLecture` : « CS » le dit, avec les autres lecteurs',
	urgente: 'le badge de priorité (`PRIORITE_BREVE`), orange',
};

/** Les options actives qu'une carte rend en badge : sans celles qu'un badge dédié dit. */
export function optionsEnBadge(ticket: Ticket | null | undefined): OptionPublication[] {
	return optionsActives(optionsDuTicket(ticket)).filter(
		(o) => !(o.cle in OPTIONS_RENDUES_AILLEURS),
	);
}

/** Ce qu'on ENVOIE — l'autre sens du même pont. */
export function optionsVersTicket(options: {
	epingle: boolean;
	urgente: boolean;
	brouillon: boolean;
	suiviKanban: boolean;
	suiviActualite?: boolean;
	etatSuivi?: string | null;
	//  Ce que le CONSEIL pose dans une Suite (#1207) — Quand, Intervenant,
	//  Équipement : `SectionsSuiteConseil` l'écrit ici, et il voyage par ce même
	//  pont plutôt que par une variable de plus dans chaque carte.
	planification?: Record<string, unknown>;
}): Record<string, unknown> {
	return {
		epingle: options.epingle,
		urgente: options.urgente,
		confidentiel: options.brouillon,
		suivi_kanban: options.suiviKanban,
		//  Absente : le corps n'en dit rien, l'actualité garde son suivi.
		suivre_actualite: options.suiviActualite,
		//  Absent : le serveur part en « Ouvert », ou garde l'état en cours.
		suivi_actualite: (options.suiviActualite && options.etatSuivi) || undefined,
		...(options.planification ?? {}),
	};
}

/*  ══════════════════════════════════════════════════════════════════════════
    L'URGENCE D'UN TICKET — une seule écriture (#820)

    🔴 « Ce ticket est urgent » s'écrivait HUIT fois : cinq ici (`CarteTicket`,
    `FormulaireTicket`, `VueTickets`, `FluxCard`, `flux.ts`) et trois côté API.
    Toutes testaient la catégorie `'urgence'`.

    Or ce fichier écrivait DÉJÀ la vérité contraire, quelques lignes plus haut :
    « `urgente` → `priorite === 'haute'` — ce que la catégorie Urgence pose
    déjà ». Le produit avait deux façons de dire qu'un ticket presse, et huit
    endroits n'en connaissaient qu'une.

    La catégorie a été retirée (migration 0177) : elle répondait à la question du
    DÉLAI dans la liste qui pose celle de la NATURE. Une panne peut être urgente,
    une nuisance aussi — et le résident dont l'ascenseur est bloqué avec
    quelqu'un dedans n'avait aucun moyen de dire les deux.
    ══════════════════════════════════════════════════════════════════════════ */

/*  ── La PRIORITÉ ───────────────────────────────────────────────────────────
    🔴 Son vocabulaire vivait dans un ÉCRAN (`tickets/[id]`), en table locale —
    du spécifique, alors que tous les autres états du produit vivent ici. Et la
    carte du ticket en donnait un SECOND rendu, écrit à la main : « ⚡ Urgente »
    là où la fiche dit « Priorité haute ». Deux rendus du même état, aucun qui
    se voie depuis l'autre.

    ✂️ La forme LONGUE est partie le 15/10/2026 avec la fiche : le lien d'une
    affaire rend désormais la carte, et « Priorité haute » n'avait plus aucun
    lecteur. Reste la forme brève, et la teinte. `normale` et `basse` ne
    s'affichent nulle part — la carte ne montre que ce qui presse — et gardent
    leur ligne pour que la table couvre l'énumération du serveur —
    `PrioriteTicket` (`api/app/models/tickets.py`).                           */
const PRIORITE = parAttribut({
	basse: { bref: '', badge: 'badge-gray' },
	normale: { bref: '', badge: 'badge-gray' },
	//  Le glyphe est LU dans la table des options : il n'y est écrit qu'une fois.
	haute: { bref: `${GLYPHE_URGENCE} Urgente`, badge: 'badge-orange' },
});

/** « ⚡ Urgente » — la forme brève, pour une carte. **Vide** quand il n'y a rien
 *  à signaler : c'est ce qui permet à la carte de ne rien afficher sans reposer
 *  la question de son côté. */
export const PRIORITE_BREVE: Record<string, string> = PRIORITE.bref;

/** La teinte de la priorité. */
export const BADGE_PRIORITE: Record<string, string> = PRIORITE.badge;

/** Un ticket presse-t-il ? La priorité le dit, et elle seule.
 *
 *  ⚠️ `CarteTicket` écrivait `ticket.priorite === 'haute'` en toutes lettres —
 *  dans le composant le plus vu du produit, et sous une fonction qui se déclare
 *  le seul endroit où la question se pose. Une règle qui s'annonce unique et
 *  qu'un appelant contourne n'est pas unique : elle est ignorée. */
export function ticketUrgent(ticket: { priorite?: string | null } | null | undefined): boolean {
	return ticket?.priorite === 'haute';
}

/**
 * L'adresse de la FICHE d'une affaire — actualités comprises (#1091).
 *
 * Miroir de `utils/liens.lien_ticket` côté serveur : c'est l'adresse que les
 * courriels et le groupe WhatsApp portent, et celle que « Copier le lien »
 * doit rendre. Écrite une fois ici, jamais recomposée dans un écran.
 */
export function lienTicket(id: number): string {
	return `/tickets/${id}`;
}

/** La catégorie qui fait d'une affaire une actualité (#1091). */
export const CATEGORIE_ACTUALITE = 'actualite';

/**
 * Cette affaire est-elle une actualité ? Miroir de `nature_affaire.est_actualite`
 * côté serveur — la question ne se pose qu'ici, jamais par un `=== 'actualite'`
 * recopié dans un écran.
 */
export function estActualite(t: { categorie?: string | null } | null | undefined): boolean {
	return t?.categorie === CATEGORIE_ACTUALITE;
}

/**
 * **Répondre à une affaire** — ce que le bouton dit, ou `null` s'il n'est pas offert.
 *
 * 🔴 Une source pour les DEUX endroits qui l'offrent (23/10/2026, demandé à
 * l'écran : *« cette icône doit être sur l'affaire »*) : l'icône de la carte
 * (`ActionsTicket`) et le bouton sous le fil des messages (`FilMessagesTicket`).
 * Les mêmes règles que la route (`POST /tickets/{id}/messages`) : toute
 * personne qui LIT l'affaire peut y répondre — la liste ne montre que celles-là —,
 * sauf une affaire absorbée (#1704 : la discussion vit dans la principale). Une
 * actualité n'a pas de fil de messages : elle informe.
 */
export function gesteReponse(
	t: Ticket,
): { libelle: string; glyphe: string; icone: 'message-square-text' | 'undo-2' } | null {
	if (t.fusionnee || estActualite(t)) return null;
	return estTicketClos(t.statut)
		? { libelle: 'Rouvrir la discussion', glyphe: '↩️', icone: 'undo-2' }
		: { libelle: 'Répondre', glyphe: '💬', icone: 'message-square-text' };
}

/** La page de l'affaire, formulaire de réponse ouvert — lu par `tickets/[id]`. */
export const lienReponse = (t: Ticket) => `/tickets/${t.id}?repondre=1`;
