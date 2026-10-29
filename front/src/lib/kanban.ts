// Règles de visibilité kanban — source unique de vérité
// Utilisé par calendrier/+page.svelte et tableau-de-bord/+page.svelte

/** Une colonne du Kanban : son état, ses deux libellés, sa teinte. */
export interface KanbanCol {
	id: string;
	/** Le libellé complet — vue Kanban, pastilles du formulaire, Historique. */
	label: string;
	/** La forme brève, pour la brique d'accueil où la colonne est étroite. */
	labelCourt: string;
	/** Un jeton (`var(--kanban-…)`, `socle.css`), jamais une valeur : le thème sombre le redéfinit. */
	color: string;
	/** Déclaré sur les colonnes que la brique d'accueil n'affiche pas, avec la
	 *  raison en commentaire. Une absence sans ce drapeau est un oubli. */
	masqueAccueil?: boolean;
}

/**
 * Les COLONNES du Kanban — la source unique, extraite de `calendrier/+page.svelte`
 * le 18/08/2026.
 *
 * 🔴 **Ces colonnes SONT le workflow d'un événement** : elles répondent
 * exactement à la question de la section 3 du cadre #430 — *« où en est cet
 * objet ? »*. Arbitré ainsi : *« peut-être que le kanban tu le glisses dans
 * Workflow ? »*. Aucun second champ d'état n'a été créé — deux notions de suivi
 * sur le même objet se contredisent au premier écart.
 *
 * Elles alimentent trois choses qui doivent rester d'accord : la vue Kanban, les
 * pastilles du formulaire d'événement, et les libellés de l'Historique
 * (« État : X → Y »). Le pendant serveur est `KANBAN_LABELS` dans
 * `calendrier_historique.py` — les contextes de build sont `./api` et `./front`,
 * le partage d'un fichier est impossible, seule la copie l'est.
 *
 * ## Une seule table, et les divergences DÉCLARÉES (#1030, 19/09/2026)
 *
 * Elle était écrite **deux fois** : ici, et dans `KanbanTableauBord.svelte`
 * (`DASH_KANBAN_COLS`) — mêmes identifiants, mêmes couleurs recopiées, mais
 * cinq colonnes au lieu de six et des libellés plus courts.
 *
 * 🔴 `lint:tables-statuts` était **vert à cause de cela** : il refuse deux
 * tables qui partagent le même ensemble de clés, et ces deux-là n'en
 * partageaient que cinq sur six. C'est le cas limite de `standards/02` §1 bis —
 * la copie incomplète échappe au contrôle qui cherche la copie identique.
 *
 * Les deux écarts étaient **légitimes** et ne se déclaraient nulle part :
 *
 * | Écart | Pourquoi | Champ qui le porte |
 * |---|---|---|
 * | libellés plus courts sur l'accueil | la brique y est étroite, « CS (en cours) » y tient mal | `labelCourt` |
 * | « Annulé » absent de l'accueil | l'accueil montre ce qui avance ; le filtre de la brique écartait déjà `annule` | `masqueAccueil` |
 *
 * Une divergence légitime qui ne se déclare pas est **indistinguable d'un
 * oubli** (`standards/02` §4) — et c'est ce qui la rend impossible à corriger :
 * personne ne sait s'il faut aligner ou préserver.
 */
export const KANBAN_COLS: KanbanCol[] = [
	{ id: 'ag', label: 'AG', labelCourt: 'AG', color: 'var(--kanban-ag)' },
	{ id: 'cs', label: 'CS (en cours)', labelCourt: 'CS', color: 'var(--kanban-cs)' },
	{ id: 'syndic', label: 'Syndic (en cours)', labelCourt: 'Syndic', color: 'var(--kanban-syndic)' },
	{
		id: 'fournisseur',
		label: 'Prestataire (en cours)',
		labelCourt: 'Prestataire',
		color: 'var(--kanban-fournisseur)',
	},
	{ id: 'termine', label: 'Terminé', labelCourt: 'Terminé', color: 'var(--kanban-termine)' },
	//  `masqueAccueil` : l'accueil montre ce qui AVANCE. Un événement annulé n'a
	//  pas d'étape suivante, et la brique le filtrait déjà — la colonne y serait
	//  restée vide en permanence.
	{
		id: 'annule',
		label: 'Annulé',
		labelCourt: 'Annulé',
		color: 'var(--kanban-annule)',
		masqueAccueil: true,
	},
];

/** Les colonnes de la brique d'accueil : la table unique, moins ce qui y est masqué.
 *
 * ⚠️ Une **dérivation**, pas une seconde table : ajouter une colonne ici la fait
 * apparaître aux deux endroits, et c'est le but. Le seul moyen d'en exclure une
 * est de poser `masqueAccueil`, donc d'écrire pourquoi.
 */
export const KANBAN_COLS_ACCUEIL: KanbanCol[] = KANBAN_COLS.filter((c) => !c.masqueAccueil);

export interface KanbanCtx {
	isCS: boolean;
	isAdmin: boolean;
	canSeeAG: boolean;
	statut: string; // copropriétaire_résident, copropriétaire_bailleur, syndic, mandataire…
}

/**
 * Largeur en dessous de laquelle un kanban passe en vue étroite.
 *
 * 🔴 Le site rend le kanban à DEUX endroits — la page Calendrier (colonnes
 * empilées) et le tableau de bord (une colonne à la fois). Ils basculaient à
 * **767** et **900 px**, si bien qu'entre les deux l'un était lisible et l'autre
 * non : exactement la plage des tablettes en portrait (768 à 820 px), que ni un
 * téléphone ni un ordinateur n'occupent. Signalé le 01/09/2026 sur un iPad.
 *
 * ⚠️ Le condensé ne bascule plus par le CSS mais par un `{#if}` sur cette valeur.
 * Deux tentatives de bascule CSS ont échoué le même soir — la première parce
 * qu'une règle globale ne surcharge pas une règle scopée, la seconde pour une
 * raison que je n'ai jamais pu observer, faute de voir l'écran connecté. Un
 * rendu conditionnel ne dépend d'aucune cascade : une seule vue existe à la fois,
 * et ce qui n'est pas rendu ne peut pas être masqué par erreur.
 *
 * Le kanban complet, lui, garde sa bascule CSS (`.kanban`, `composants.css`) :
 * elle n'empile que des colonnes, sans changer ce qui est rendu.
 * `api/tests/test_seuil_kanban.py` refuse que les deux valeurs divergent.
 */
export const SEUIL_KANBAN_ETROIT = 900;

/**
 * Combien de cartes une colonne montre sur l'ACCUEIL, avant le report « +N ».
 *
 * 🔴 Ce nombre était écrit **trois fois** dans `KanbanTableauBord` — une fois pour
 * couper (`slice(0, 5)`), deux fois dans l'expression du compteur. Le changer
 * demandait de corriger les trois, et en oublier une donnait un compteur qui ment
 * (« +2 » sur une colonne qui en cache trois) sans qu'aucun test ne le voie : les
 * deux écritures restent valides séparément (#1076).
 *
 * Passé de 5 à **3** le 20/09/2026, à la demande de l'utilisateur : la brique de
 * l'accueil poussait vers le bas le fil d'activité et les alertes, et c'est la
 * page la plus consultée.
 *
 * ⚠️ L'accueil SEULEMENT. L'onglet Kanban d'Affaires est l'écran dédié : il a la place,
 * et y borner les colonnes cacherait ce qu'on vient précisément y chercher.
 */
export const MAX_CARTES_ACCUEIL = 3;

/**
 * Ce qu'une colonne vide affiche — **un seul endroit**.
 *
 * Il était écrit deux fois, dans les deux kanbans, avec un commentaire qui le
 * disait (« le même mot que sur le kanban complet, et la même classe »). Un
 * commentaire qui décrit une copie ne l'empêche pas de diverger : il note qu'elle
 * existe (`standards/02` §1 ter).
 */
export const MOT_COLONNE_VIDE = 'Aucune affaire';

/** Retourne true si la colonne doit être affichée pour cet utilisateur. */
export function kanbanColVisible(colId: string, ctx: KanbanCtx): boolean {
	if (colId === 'ag' || colId === 'cs') return ctx.canSeeAG;
	return true;
}

/*  ══════════════════════════════════════════════════════════════════════════
    LES TICKETS AU KANBAN (#833, 08/09/2026)

    Les tickets « Étude & travaux » décrivent un chantier suivi par le conseil —
    une étude d'étanchéité, un devis, des travaux. Ils vivaient dans la liste des
    tickets pendant que le kanban ne connaissait que les ÉVÉNEMENTS : deux
    endroits pour suivre la même chose.

    🔴 **Le kanban LIT les tickets ; il n'en crée pas de copie.** Arbitrage du
    08/09/2026, contre « un événement créé pour chaque ticket » — deux objets
    décrivant la même affaire divergent au premier geste, et il faudrait décider
    lequel fait foi. C'est déjà la règle des événements, écrite plus haut :
    *« aucun second champ d'état n'a été créé »*.

    Le statut du ticket EST donc sa colonne.

    ⚠️ **Copie assumée du serveur** (`app/utils/kanban_tickets.py`) : les
    contextes de build sont `./api` et `./front`, le partage d'un fichier est
    impossible. `api/tests/test_kanban_tickets.py` échoue si les deux dérivent —
    même dispositif que `KANBAN_LABELS`.
    ══════════════════════════════════════════════════════════════════════════ */

/** Statut d'un ticket → colonne du kanban. */
export const COLONNE_PAR_STATUT_TICKET: Record<string, string> = {
	ouvert: 'cs',
	en_ag: 'ag',
	en_cours: 'syndic',
	chez_prestataire: 'fournisseur',
	résolu: 'termine',
	annulé: 'annule',
};

/**
 * La colonne d'un ticket, ou `null` si son statut n'en désigne aucune.
 *
 * ⚠️ `null` plutôt qu'un repli sur `cs` : un statut inconnu doit SORTIR le
 * ticket du tableau, pas l'y ranger arbitrairement. Une carte posée dans la
 * mauvaise colonne se lit comme une information, et personne ne la remet en
 * cause.
 *
 * ⚠️ La colonne `fournisseur` est inatteignable depuis un ticket, et c'est un
 * constat : aucun statut de ticket ne dit « chez le prestataire ».
 */
export function colonneDuTicket(statut: string | null | undefined): string | null {
	if (!statut) return null;
	return COLONNE_PAR_STATUT_TICKET[statut] ?? null;
}
