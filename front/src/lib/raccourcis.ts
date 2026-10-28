/**
 * La rangée de raccourcis du tableau de bord — **une** table, lue par l'écran.
 *
 * Avant #399, chaque pastille portait sa propre condition de visibilité écrite
 * dans le balisage (`{#if $isCS || $isAdmin}`), et son compteur venait d'une
 * source différente des autres. Trois pastilles, trois portées incomparables :
 * Tickets comptait ce que le fil affichait **après filtrage par l'utilisateur**,
 * Sondages et Espace CS comptaient côté serveur. Rien ne se voyait à l'écran :
 * les trois nombres se ressemblaient.
 *
 * ## Ce que la table garantit
 *
 * Un raccourci déclare ensemble **qui le voit** et **d'où vient son nombre**.
 * Les deux ne peuvent plus diverger par inadvertance, parce qu'ils ne sont plus
 * écrits à deux endroits. Ajouter une pastille, c'est ajouter une ligne ici.
 *
 * ## Ce qu'elle ne garantit pas — et qui n'est pas son travail
 *
 * `visible` **ne protège rien**. C'est un reflet du droit, jamais le droit
 * lui-même : le serveur reste seul juge, et il renvoie 0 pour un compteur que
 * l'appelant n'a pas à connaître (`api/app/routers/flux/sante.py`). Une pastille
 * masquée dont le serveur remplirait quand même le compteur serait du travail
 * inutile ; une pastille visible dont le compteur vaut 0 faute de droit serait un
 * mensonge à l'écran. Les deux moitiés se vérifient donc côté API, où elles sont
 * décidées — cf. `api/tests/test_compteurs_tableau_de_bord.py`.
 */
import { aRole } from '#lib/stores/auth.ts';
import type { FluxSante, User } from '#lib/api/index.ts';

/** Un décompte affiché sur une pastille. `valeur === 0` → rien ne s'affiche. */
export interface CompteurRaccourci {
	valeur: number;
	/** Couleur du badge : le bleu par défaut, le rouge pour ce qui attend une action. */
	ton?: 'urgent' | 'orange';
	/** Complément de libellé accordé au nombre — « 2 relances ». */
	libelle?: (n: number) => string;
	/**
	 *  🔴 L'adresse de CE compteur, quand elle diffère de celle du raccourci.
	 *
	 *  Signalé à l'écran le 21/09/2026 : *« la relance ne pointe pas vers la
	 *  bonne URL »*. La pastille « 1 relance » menait à `/espace-cs`, c'est-à-dire
	 *  à l'onglet Comptes & accès — il fallait ensuite trouver Reporting, puis la
	 *  vue Relance syndic. Un compteur qui annonce un travail doit mener AU
	 *  travail, pas à la porte de l'immeuble.
	 *
	 *  ⚠️ L'adresse existe déjà : c'est celle que l'alerte du tableau de bord
	 *  emploie. Elle est ici la MÊME constante, et `check-client-api` n'a rien à
	 *  voir là-dedans — une route d'écran, pas d'API.
	 */
	href?: string;
}

export interface Raccourci {
	id: string;
	libelle: string;
	href: string;
	/** Nom Lucide — doit exister dans `#lib/icones-svg.json`, sinon `Icon` retombe en silence sur `help-circle`. */
	icone: string;
	/** Variante visuelle ; absente = pastille neutre. */
	variante?: 'cs' | 'admin';
	visible: (user: User | null) => boolean;
	/** D'où vient le nombre affiché. Une seule source par pastille, côté serveur. */
	compteurs: (sante: FluxSante) => CompteurRaccourci[];
}

/** Tout utilisateur connecté voit ce raccourci. */
const TOUS = (user: User | null) => user !== null;

/**
 *  L'adresse de la relance syndic — **une seule écriture**.
 *
 *  Elle vit ici parce que deux endroits y mènent : la pastille de la rangée de
 *  raccourcis et l'alerte du tableau de bord. Écrite deux fois, elle aurait
 *  divergé au premier renommage d'onglet — et c'est exactement ce que
 *  `project_onglet_est_une_adresse` enseigne : un onglet EST une adresse, donc
 *  une adresse d'onglet est une donnée, pas une chaîne qu'on retape.
 */
export const HREF_RELANCE_SYNDIC = '/espace-cs/reporting?vue=relance';

export const RACCOURCIS: Raccourci[] = [
	{
		id: 'tickets',
		libelle: 'Affaires',
		href: '/tickets',
		icone: 'ticket',
		visible: TOUS,
		//  `tickets_ouverts`, et non plus un décompte reconstruit dans la page sur
		//  le fil déjà filtré : le nombre changeait quand l'utilisateur filtrait
		//  son fil, seul de la rangée à bouger. Le compteur serveur applique
		//  désormais `ticket_visible` — un résident y lit ses affaires, pas celles
		//  de la résidence.
		compteurs: (s) => [{ valeur: s.tickets_ouverts }],
	},
	{
		id: 'calendrier',
		libelle: 'Calendrier',
		//  Le Calendrier est le filtre « Calendrier » d'Affaires (#1092, 23/09/2026).
		href: '/tickets?nature=calendrier',
		icone: 'calendar',
		visible: TOUS,
		compteurs: () => [],
	},
	{
		id: 'sondages',
		libelle: 'Sondages',
		href: '/sondages',
		icone: 'bar-chart-3',
		visible: TOUS,
		compteurs: (s) => [{ valeur: s.sondages_actifs }],
	},
	{
		id: 'actualites',
		libelle: 'Actualités',
		//  Le filtre « Actualité » de la vue Affaires (#1092) : la page n'existe plus.
		href: '/tickets?nature=actualite',
		icone: 'megaphone',
		visible: TOUS,
		compteurs: () => [],
	},
	{
		id: 'espace-cs',
		libelle: 'Espace CS',
		href: '/espace-cs',
		icone: 'shield-check',
		variante: 'cs',
		//  Même règle que le garde de la page elle-même et que le serveur —
		//  écrite ici, et à un seul endroit côté front.
		visible: (u) => aRole(u, 'conseil_syndical', 'admin'),
		compteurs: (s) => [
			{ valeur: s.validations_cs, ton: 'urgent' },
			{
				valeur: s.tickets_relance_syndic,
				ton: 'orange',
				libelle: (n) => `${n} relance${n > 1 ? 's' : ''}`,
				href: HREF_RELANCE_SYNDIC,
			},
		],
	},
	{
		id: 'admin',
		libelle: 'Admin',
		href: '/admin',
		//  L'icône de la page Admin dans la navigation — la rangée ne s'invente
		//  pas un second symbole pour la même destination.
		icone: 'sliders-horizontal',
		variante: 'admin',
		//  `/admin` est fermé au CS non-admin par son layout : la pastille dit
		//  exactement ce que le garde de la page décide.
		visible: (u) => aRole(u, 'admin'),
		compteurs: (s) => [{ valeur: s.validations_admin, ton: 'urgent' }],
	},
];

/** Les raccourcis que cet utilisateur a le droit de voir, dans l'ordre de la table. */
export function raccourcisVisibles(user: User | null): Raccourci[] {
	return RACCOURCIS.filter((r) => r.visible(user));
}
