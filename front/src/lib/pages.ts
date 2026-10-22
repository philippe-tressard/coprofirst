/**
 * Source unique des pages de l'application : identifiant de configuration, route,
 * libellés, icône, descriptif et onglets.
 *
 * Posé le 17/08/2026 (#401). Ces informations vivaient dans DEUX tables qui ne se
 * connaissaient pas — `NAV_DEFAULTS` + `DEFAULT_HREFS` dans `Nav.svelte`, et
 * `pagesDefaults` dans l'écran `admin` — et elles avaient déjà divergé de trois
 * façons, chacune invisible :
 *
 *  1. **Les deux ordres par défaut n'étaient pas le même.** Le menu commençait par
 *     Résidence, Mes lots, Accès & badges ; l'écran d'administration par Actualités,
 *     Affaires, Mes lots. Deux listes décrivaient le même ordre sans dire la même chose.
 *  2. **`profil` et `notifications` étaient réordonnables sans être dans le menu.**
 *     L'écran proposait le geste, `Nav` écartait ces identifiants en silence : le
 *     déplacement n'avait aucun effet, et rien ne le disait.
 *  3. **`delegations` était dans le menu sans être dans l'écran.** On ne pouvait donc
 *     ni la positionner ni la renommer, et elle atterrissait toujours en dernier —
 *     après Admin — par le jeu du repli sur l'ordre par défaut.
 *
 * `href: null` = page atteignable sans entrée de menu (profil, notifications). C'est
 * la même distinction qui décide des flèches d'ordre dans l'écran d'administration :
 * on n'ordonne que ce qui apparaît dans le menu.
 *
 * ⚠️ Ne jamais recopier cette table, même partiellement : `npm run lint:pages` refuse
 * tout identifiant ou route de page écrit ailleurs, **et tout titre, descriptif,
 * libellé de menu, icône ou onglet passé en dur à `getPageConfig`** — les pages
 * prennent leurs valeurs par défaut de `defautsDePage()` (#420). Une table recopiée
 * finit toujours par diverger de celle qu'elle copie — c'est exactement ce qui s'est
 * produit ici, et c'est déjà arrivé aux périmètres (#316) et aux canaux de
 * notification.
 */

import { TITRE_ARCHIVES } from '$lib/archives';
import { PAGES_ROLES } from './pages-roles';
import type { PageConfig } from '$lib/stores/pageConfig';

export interface OngletDef {
	id: string;
	label: string;
	descriptif: string;
	/**
	 * L'URL dédiée de cet onglet — celle qu'on copie dans la barre d'adresse et
	 * qu'on envoie à un voisin. Elle est ABSOLUE (elle commence par `/`) et non
	 * relative à la page : les trois rubriques de la Communauté vivent à la racine
	 * (`/annonces`), les vues d'un même objet sous leur page (`/calendrier/kanban`).
	 *
	 * La règle, arbitrée le 05/09/2026 : **plate quand l'onglet est un CONTENU,
	 * imbriquée quand il est une VUE**. `/kanban` ou `/archives` seuls ne disent
	 * pas de quoi ils parlent ; `/annonces` si.
	 *
	 * ⚠️ La route de l'onglet par défaut est celle de la page (`href`) : sans quoi
	 * l'entrée de menu et le premier onglet seraient deux adresses pour le même
	 * écran, et `test_liens_front.py` refuse.
	 *
	 * ⚠️ Une seule page garde la forme `?onglet=` : l'administration (« sauf
	 * admin », demandé le 05/09/2026). Sa route est donc `/admin?onglet=<id>`,
	 * et `/admin` pour l'onglet par défaut — l'adresse réelle, que la page lit.
	 */
	route: string;
	/**
	 * Le GROUPE de l'onglet, quand la rangée se partage en groupes nommés —
	 * l'administration seule, rangée par niveau en six groupes (#2062).
	 * `BarreOnglets` rend alors deux rangées : les groupes, puis les onglets du
	 * groupe actif. Les onglets d'un même groupe se suivent dans la table.
	 */
	groupe?: string;
	/** Les sous-onglets, quand l'onglet en porte une rangée (un seul cas : les
	    baux de la gestion locative). Ils ont une URL, pas d'entrée dans la
	    configuration éditable — l'administration n'ordonne et ne renomme que les
	    onglets de premier niveau. */
	sous?: SousOngletDef[];
	/**
	 * À qui cet onglet est RÉSERVÉ, quand sa route d'API refuse les autres.
	 *
	 * 🔴 Déclaré ici, avec l'onglet, et pas dans la page (#1039). L'onglet
	 * « Carnet d'entretien » s'affichait à un locataire alors que
	 * `api/app/routers/carnet.py` lui répond 403 : la page rendait sa rangée sans
	 * rien masquer, et rien ne pouvait le signaler — il n'y avait aucun endroit
	 * où la réservation était *écrite*. Elle l'est maintenant là où l'onglet est
	 * défini, donc celui qui en ajoute un la voit.
	 *
	 * `BarreOnglets` s'en charge ensuite, des deux côtés : il retire l'entrée ET
	 * ramène sur l'onglet par défaut si l'adresse est ouverte directement.
	 *
	 * ⚠️ Pour un masquage qui dépend des DONNÉES et non du rôle — « Gestion
	 * locative » n'apparaît que si le lot a des baux — c'est la prop `masques`
	 * de la page, qui seule peut le savoir.
	 *
	 * ⚠️ Masquer ne protège rien : le serveur tranche. Cela évite de tendre une
	 * entrée qui mène à une erreur.
	 *
	 * 🔒 `npm run lint:onglets-reserves` confronte chaque valeur ici à la
	 * dépendance d'auth du routeur qui la justifie.
	 */
	//  `nonGestionnaire` : ni syndic ni mandataire — la Communauté hors de l'Avis
	//  (#2075), que `utils/communaute.exiger_acces` refuse à leur profil.
	reserve?: 'proprioOuCS' | 'nonLocataire' | 'operateur' | 'nonGestionnaire';
	/**
	 * Sur une page `reserveeAdmin`, l'onglet que l'**opérateur** de la plateforme
	 * ouvre aussi quand il n'est pas administrateur — sa supervision, et rien
	 * d'autre (#2029). La règle se lit dans `$lib/onglets-ouverts`.
	 */
	ouvertOperateur?: true;
}

/** Un sous-onglet : une URL et rien d'autre. Son libellé vit dans l'écran, qui
    est le seul à savoir ce qu'il compte (« Baux actifs (3) »). */
export interface SousOngletDef {
	id: string;
	route: string;
}

export interface PageDef {
	/** Identifiant de configuration : clé `page_config_<id>` et entrée de `pages_order`. */
	id: string;
	/** Route du menu, ou `null` pour une page sans entrée de navigation. */
	href: string | null;
	/** Nom de la page dans l'écran « Descriptif pages ». */
	nom: string;
	/** Titre affiché en tête de la page. */
	titre: string;
	/** Libellé dans le menu de navigation. */
	navLabel: string;
	icone: string;
	descriptif: string;
	onglets?: OngletDef[];
	/**
	 * Page de l'administration : un compte qui n'est pas administrateur n'y voit
	 * que les onglets `ouvertOperateur` — l'opérateur seul l'ouvre ainsi (#2029).
	 */
	reserveeAdmin?: true;
}

/** Toutes les pages, dans l'ordre de navigation par défaut. */
export const PAGES: PageDef[] = [
	{
		id: 'tableau-de-bord',
		href: '/tableau-de-bord',
		nom: 'Tableau de bord',
		titre: 'Tableau de bord',
		navLabel: 'Accueil',
		icone: 'layout-dashboard',
		descriptif:
			'Votre espace numérique de résidence : actualités, demandes, accès et gouvernance de votre copropriété en un seul endroit.',
	},
	{
		id: 'residence',
		href: '/residence',
		nom: 'Ma résidence',
		titre: 'Ma résidence',
		navLabel: 'Résidence',
		icone: 'building-2',
		descriptif: 'Informations, plans et documents de la copropriété.',
		//  🔴 Cette page n'avait AUCUN onglet jusqu'au 10/09/2026. En créer la
		//  transforme : la fiche devient « Fiche », et c'est elle qui s'ouvre par
		//  défaut — l'onglet initial porte le nom de l'écran (`ux-patterns` §4 ter).
		//
		//  Le carnet est rangé ICI et non sous Prestataires, bien que la moitié de
		//  ses données en vienne : une entrée de menu doit contenir ce qu'elle
		//  nomme, et personne ne cherche l'histoire de son immeuble sous
		//  « Prestataires ». Adresse IMBRIQUÉE, parce que le carnet est une VUE de
		//  la résidence et non un contenu autonome (`ux-patterns` §4).
		onglets: [
			{
				id: 'fiche',
				route: '/residence',
				label: '\u{1F3E2} Fiche',
				descriptif: 'Informations, plans et documents de la copropriété.',
			},
			{
				id: 'carnet',
				route: '/residence/carnet',
				reserve: 'proprioOuCS',
				label: '\u{1F4D2} Carnet d’entretien',
				descriptif:
					'Ce qui a été entretenu, réparé et contrôlé dans la résidence — et ce qui ne l’a pas été.',
			},
			{
				//  Venu de l'Espace CS le 11/10/2026 pour s'ouvrir aux copropriétaires
				//  (`/espace-cs/reglement` redirige ici). Réservé comme le carnet, et
				//  MASQUÉ en plus par la page quand l'administration n'a pas ouvert
				//  l'usage aux copropriétaires (`GET /reglement/acces`).
				id: 'reglement',
				route: '/residence/reglement',
				reserve: 'proprioOuCS',
				label: '⚖️ Règlement',
				descriptif:
					"Posez la question sur le règlement de copropriété (« ai-je le droit de… ? ») : l'assistant répond en juriste, d'après le texte chargé ici, avec les extraits et les pages qui justifient sa réponse. Une réponse relue pourra rejoindre la FAQ par le CS.",
			},
		],
	},
	//  « Actualités » n'est plus une page (#1091, #1092, 23/09/2026) : une
	//  actualité est une affaire, lue sous le filtre « Actualité » d'Affaires.
	//  `/actualites` reste une ADRESSE, qui redirige — voir sa route.
	{
		id: 'mes-demandes',
		href: '/tickets',
		nom: 'Affaires',
		titre: 'Mes affaires',
		navLabel: 'Affaires',
		icone: 'message-square-text',
		descriptif:
			'Les actualités du conseil syndical et les affaires de la résidence : signalez un problème, posez une question, suivez l’avancement.',
		//  Les onglets du Calendrier le rejoignent (#1092, lot 5, 23/09/2026) :
		//  le Calendrier devient une vue d'Affaires, son kanban un onglet.
		onglets: [
			{
				id: 'liste',
				route: '/tickets',
				label: '\u{1F4CB} Liste',
				descriptif: 'Les actualités et les affaires en cours.',
			},
			{
				id: 'kanban',
				route: '/tickets/kanban',
				//  Pas aux locataires (arbitré le 28/09/2026, #1428) : le suivi des
				//  dossiers est l'affaire des copropriétaires et du conseil. Un
				//  masque d'ERGONOMIE : ce qu'il montrerait est déjà filtré par
				//  `ticket_visible`, aucune route ne le refuse au serveur.
				reserve: 'nonLocataire',
				label: '\u{1F5C3}️ Kanban',
				descriptif: 'Les affaires suivies, par état.',
			},
			{
				id: 'archives',
				route: '/tickets/archives',
				label: TITRE_ARCHIVES,
				descriptif: 'Les affaires closes et les actualités passées.',
			},
		],
	},
	//  « Calendrier » n'est plus une page (#1092, lot 5, 23/09/2026) : ses événements
	//  sont des affaires, lues sous le filtre « Calendrier » d'Affaires ; son kanban
	//  est l'onglet Kanban d'Affaires. `/calendrier` reste une ADRESSE, qui redirige.
	{
		id: 'mon-lot',
		href: '/mon-lot',
		//  🔴 « Mes lots & accès » (12/09/2026, #928) : la page réunit ce qui était
		//  deux entrées de menu, et le nom dit les DEUX.
		//  ⚠️ Les trois champs changent ENSEMBLE — recherche, en-tête, menu.
		nom: 'Mes lots & accès',
		titre: 'Mes lots & accès',
		navLabel: 'Mes lots & accès',
		//  `key-round` : c'est l'accès qu'on vient chercher le plus souvent.
		icone: 'key-round',
		//  ⚠️ Le lien « Quel prix ? » vient de l'ancienne page Accès — il n'est PAS
		//  perdu : il a rejoint les deux onglets d'accès (12/09/2026), à côté du
		//  bouton qui déclenche la demande. Le laisser aussi ici l'aurait affiché
		//  trois fois sur le même écran, dont deux sur des onglets — « Mes lots »,
		//  « Gestion locative » — où il ne répond à aucune question.
		descriptif:
			'Vos lots (appartement, cave & parkings), vos badges Vigik et télécommandes de parking, et la gestion locative pour les copropriétaires mandataires.',
		onglets: [
			{
				id: 'lots',
				route: '/mon-lot',
				label: '\u{1F3E0} Mes lots',
				descriptif: 'Situation de vos lots dans la résidence : appartements, caves et parkings.',
			},
			{
				id: 'badges',
				route: '/mon-lot/badges',
				label: '\u{1F3F7}\uFE0F Mes badges d’accès (Vigik)',
				//  🔴 Le descriptif NOMME le geste et où le trouver (12/09/2026) :
				//  « vos demandes » et « vos déclarations » ne désignaient rien de
				//  visible, alors que les deux boutons qui les produisent sont en haut
				//  à droite — et qu'ils ne disent pas la même chose (demander ce qu'on
				//  n'a pas / signaler ce qu'on détient déjà).
				//  ⚠️ Le lien vise `#badge-prix`, **jamais** `#faq-<id>` : l'identifiant
				//  d'une question varie d'une instance à l'autre, le raccourci non — il
				//  vise la question par son libellé (`faq/+page.svelte`).
				descriptif:
					'Vos badges Vigik : ceux que vous détenez (tableau ci-dessous), vos demandes (bouton « + Nouvel accès », en haut à droite, pour obtenir un badge supplémentaire) et vos déclarations (bouton « + Déclarer un accès », pour signaler un badge que vous détenez déjà). <a href="/faq#badge-prix" style="font-size:.85rem">Quel prix pour un badge ou une télécommande ?</a>',
			},
			{
				id: 'telecommandes',
				route: '/mon-lot/telecommandes',
				label: '\u{1F4E1} Télécommandes de parking',
				//  Même rédaction que « Mes badges » ci-dessus, et pour la même raison :
				//  les deux onglets partagent les deux mêmes boutons.
				descriptif:
					'Vos télécommandes de parking : celles que vous détenez (tableau ci-dessous), vos demandes (bouton « + Nouvel accès », en haut à droite, pour obtenir une télécommande supplémentaire) et vos déclarations (bouton « + Déclarer un accès », pour signaler une télécommande que vous détenez déjà). <a href="/faq#badge-prix" style="font-size:.85rem">Quel prix pour un badge ou une télécommande ?</a>',
			},
			{
				id: 'location',
				route: '/mon-lot/location',
				sous: [
					{ id: 'actif', route: '/mon-lot/location' },
					{ id: 'archives', route: '/mon-lot/location/archives' },
				],
				label: '\u{1F4CB} Gestion locative',
				descriptif: 'Suivi de vos baux, locataires et documents de gestion locative.',
			},
		],
	},
	//  🔴 `acces-badges` a quitté cette table (12/09/2026, #928) — ses listes sont
	//  des sous-onglets de « Mes lots & accès ». L'adresse `/acces-securite`
	//  redirige : voir `routes/(app)/acces-securite/+page.svelte`.
	{
		id: 'annuaire',
		href: '/annuaire',
		nom: 'Annuaire',
		titre: 'Annuaire',
		navLabel: 'Annuaire',
		icone: 'users',
		descriptif:
			"Coordonnées des membres du Conseil Syndical et du Syndic. En cas d'urgence, contactez le syndic directement par téléphone. Sinon, faites une demande depuis la plateforme.",
	},
	{
		id: 'prestataires',
		href: '/prestataires',
		nom: 'Prestataires',
		titre: 'Prestataires',
		navLabel: 'Prestataires',
		icone: 'hard-hat',
		descriptif:
			'Intervenants de la résidence et leurs contrats de maintenance (avec synthèse IA du contrat) et documents contractuels.',
		onglets: [
			{
				id: 'prestataires',
				route: '/prestataires',
				label: '\u{1F527} Prestataires',
				descriptif: "Intervenants et contrats d'entretien de la résidence.",
			},
			{
				id: 'contrats',
				route: '/prestataires/contrats',
				label: '\u{1F4C4} Contrats',
				descriptif: "Contrats d'entretien en cours, leur échéance et leurs documents.",
			},
			{
				id: 'consommations',
				route: '/prestataires/consommations',
				label: '\u{1F4A7} Consommations',
				descriptif: 'Suivi des relevés de compteurs et abonnements de la résidence.',
			},
		],
	},
	{
		id: 'communaute',
		href: '/sondages',
		nom: 'Communauté',
		titre: 'Communauté',
		navLabel: 'Communauté',
		icone: 'users-round',
		descriptif:
			'Sondages, boîte à idées, petites annonces entre résidents, et votre avis sur l’application.',
		onglets: [
			{
				id: 'sondages',
				route: '/sondages',
				reserve: 'nonGestionnaire',
				label: '\u{1F4CA} Sondages',
				descriptif: 'Participez aux votes et consultations de la copropriété.',
			},
			{
				id: 'idees',
				route: '/idees',
				reserve: 'nonGestionnaire',
				label: '\u{1F4A1} Boîte à idées',
				descriptif: 'Proposez et soutenez des idées pour améliorer la vie en résidence.',
			},
			{
				id: 'annonces',
				route: '/annonces',
				reserve: 'nonGestionnaire',
				label: '\u{1F3F7}️ Petites annonces',
				descriptif: 'Achetez, vendez ou donnez des objets entre résidents.',
			},
			{
				//  L'avis porte sur l'APPLICATION, pas sur la résidence (#2075).
				id: 'avis',
				route: '/avis',
				label: '⭐ Avis',
				descriptif: 'Votre avis sur l’application : ce qui vous aide, ce qui vous manque.',
			},
		],
	},
	{
		id: 'faq',
		href: '/faq',
		nom: 'FAQ',
		titre: 'FAQ',
		navLabel: 'FAQ',
		icone: 'help-circle',
		descriptif:
			'Réponses aux questions fréquentes sur la vie en résidence, les services et la réglementation de la copropriété.',
	},
	//  Les pages réservées à un RÔLE vivent dans `pages-roles.ts` (#928) : ce
	//  fichier a franchi son plafond, et la coupe suit ce que les pages SONT.
	//  Elles ferment le menu — Espace CS, Admin, Délégations — et précèdent les
	//  pages hors menu (profil, notifications), qui n'ont pas de rang.
	...PAGES_ROLES,
	{
		id: 'profil',
		href: null,
		nom: 'Mon profil',
		titre: 'Mon profil',
		navLabel: 'Profil',
		icone: 'user',
		descriptif:
			'Vos informations personnelles (mot de passe, lots...), sécurité du compte et préférences de notifications.',
	},
	{
		id: 'notifications',
		href: null,
		nom: 'Notifications',
		titre: 'Notifications',
		navLabel: 'Notifications',
		icone: 'bell',
		descriptif: 'Vos alertes et messages.',
	},
];

/** Les pages qui ont une entrée de menu — les seules qui s'ordonnent. */
export const PAGES_MENU: PageDef[] = PAGES.filter(
	(p): p is PageDef & { href: string } => p.href !== null,
);

/** Ordre de navigation par défaut, quand aucun ordre n'a été enregistré. */
export const HREFS_DEFAUT: string[] = PAGES_MENU.map((p) => p.href as string);

/** Identifiant de configuration → route. Sert à relire `pages_order`. */
export const ID_VERS_HREF: Record<string, string> = Object.fromEntries(
	PAGES_MENU.map((p) => [p.id, p.href as string]),
);

/** Route → page. */
export const HREF_VERS_PAGE: Record<string, PageDef> = Object.fromEntries(
	PAGES_MENU.map((p) => [p.href as string, p]),
);

/**
 * Valeurs par défaut d'une page, dans la forme attendue par `getPageConfig`.
 *
 * Posé le 17/08/2026 (#420) : la table n'était pas encore la seule source. Chaque
 * page recopiait à la main, dans le troisième argument de `getPageConfig`, les
 * valeurs déjà écrites ici — et DIX pages sur seize avaient déjà divergé (huit sur
 * un texte, deux sur une icône, deux sur leurs onglets), chacune cohérente de son
 * côté. La plus visible : `espace-cs` affichait un onglet
 * « Annonces Hall » que la table ignorait, donc que l'administrateur ne pouvait ni
 * renommer ni décrire dans « Descriptif pages » ; et son descriptif de page taisait
 * la relance syndic, que la table annonçait.
 *
 * La conversion liste → dictionnaire vit ICI et nulle part ailleurs : la table
 * décrit les onglets comme une LISTE — ils sont ordonnés, c'est l'ordre de l'écran —
 * quand la configuration enregistrée les indexe par identifiant, parce qu'elle est
 * partielle et éditable onglet par onglet.
 *
 * Lève si l'identifiant est absent de la table : une page configurée sous un
 * identifiant que la table ignore n'est ni ordonnable ni renommable, et rien ne le
 * dit — c'est la divergence n° 3 de #401. `npm run lint:pages` attrape le cas en CI,
 * avant que l'exécution n'ait la moindre chance de le rencontrer.
 */
export function defautsDePage(id: string): PageConfig {
	const def = PAGES.find((p) => p.id === id);
	if (!def) {
		throw new Error(
			`Page « ${id} » absente de PAGES (src/lib/pages.ts) : lui ajouter une entrée dans ` +
				'la table, plutôt que de recopier ses valeurs par défaut sur place.',
		);
	}
	return configDepuisPage(def);
}

/**
 * Passe d'une page — telle que la décrit la table ou telle que l'administration
 * vient de l'éditer — à la forme configuration : c'est ce que sérialise
 * `page_config_<id>` et ce qu'attend `getPageConfig`.
 *
 * Prend une page en paramètre plutôt qu'un identifiant, parce que l'écran
 * d'administration enregistre des valeurs MODIFIÉES, qui ne sont plus celles de la
 * table : il partage la conversion, pas la source.
 */
export function configDepuisPage(def: PageDef): PageConfig {
	return {
		titre: def.titre,
		descriptif: def.descriptif,
		navLabel: def.navLabel,
		icone: def.icone,
		onglets: def.onglets
			? Object.fromEntries(
					def.onglets.map((o) => [o.id, { label: o.label, descriptif: o.descriptif }]),
				)
			: undefined,
	};
}

export { identifiantsRepetes, ordonnerPages } from '$lib/pages-ordre';
