/**
 * Les tables du site que l'app iOS GÉNÈRE, publiées avec la release (#2634).
 *
 * Lu par `tables-clients.mjs`, qui en produit `front/tables-clients.json` — joint à la
 * release à côté d'`openapi.json` (`scripts/ci/lib-contrat-version.sh`). L'app lit ce
 * fichier au lieu du code du site : un remaniement du front (déplacer une table,
 * renommer une constante) ne casse plus sa montée sans que la CI le dise.
 *
 * Clé : le nom PUBLIÉ de la table (stable : c'est lui que l'app lit). Champs :
 *
 * - `source` — `src/lib/<module>.ts#<EXPORT>` : une constante EXPORTÉE, LITTÉRALE
 *   (objet, liste, chaîne, nombre, booléen ; `as const` admis), qui peut nommer
 *   d'autres constantes du fichier ou des modules de `src/lib` qu'il importe, par un
 *   identifiant, un gabarit `${…}`, une concaténation ou un étalement. Le script lit
 *   l'arbre syntaxique et n'exécute rien (`tables-clients.lecture.mjs`). Un OBJET de
 *   sources (`{ nom: 'src/lib/m.ts#NOM', … }`) publie un objet de ces valeurs ;
 * - `sans` (facultatif) — les propriétés NON publiées d'une source unique, quand elles
 *   ne sont pas littérales (`['[].lien.cible']` : une fonction) ; une exclusion qui ne
 *   rencontre rien est refusée ;
 * - `quoi` — ce que la table dit, en une ligne ;
 * - `lecteur` — le générateur de coprofirst-ios qui la lit.
 *
 * Une source peut aussi être une règle CSS : `src/styles/<feuille>.css@<sélecteur>` ou
 * le `<style>` d'un composant, `src/lib/…/X.svelte@<sélecteur>` — ses déclarations ;
 * un `*` dans le sélecteur publie une famille, par code (`tables-clients.css.mjs`).
 *
 * Ce qui n'est PAS ici : ce que l'API peut servir en champ (#2501, règles partagées).
 *
 * `RETRAITS` — une table retirée, ou dont la forme recule (un champ retiré, un type
 * qui change), s'ANNONCE ici avant d'écrire la référence : `{ ticket, raison }`.
 * Une annonce qui nomme une table encore publiée sous la même forme fait échouer le
 * contrôle : elle ne sert plus.
 */
export const TABLES = {
	//  ── Lot A : les tables qui vivaient DANS un composant (lues par motif) ────
	dureeToastMs: {
		source: 'src/lib/toast.ts#DUREE_TOAST_MS',
		quoi: "la durée par défaut d'un avis bref (le « toast »), en millisecondes",
		lecteur: 'scripts/generateurs/avis.py',
	},
	rolesMisEnAvant: {
		source: 'src/lib/roles.ts#ROLES_MIS_EN_AVANT',
		quoi: "les rôles que l'en-tête de l'accueil ajoute au statut, dans l'ordre",
		lecteur: 'scripts/generateurs/charte.py',
	},
	statutsDelegation: {
		source: 'src/lib/delegations.ts#STATUTS_DELEGATION',
		quoi: "le libellé et la pastille de l'état d'une délégation",
		lecteur: 'scripts/generateurs/delegations_cs.py',
	},
	teinteAge: {
		source: 'src/lib/reporting.ts#TEINTE_AGE',
		quoi: "la pastille de l'ancienneté d'une affaire (Reporting)",
		lecteur: 'scripts/generateurs/delegations_cs.py',
	},
	modesSuivi: {
		source: 'src/lib/reporting.ts#MODES_SUIVI',
		quoi: 'les modes du Suivi des affaires, dans leur ordre',
		lecteur: 'scripts/generateurs/delegations_cs.py',
	},
	formatsAffiche: {
		source: 'src/lib/annonces-hall.ts#AH_FORMATS',
		quoi: "les formats qu'on peut demander pour une affiche de hall",
		lecteur: 'scripts/generateurs/delegations_cs.py',
	},
	verdictsReleve: {
		source: 'src/lib/courriels-affaires.ts#VERDICTS_RELEVE',
		quoi: "ce que la relève des courriels a fait d'un message, et son ton",
		lecteur: 'scripts/generateurs/delegations_cs.py',
	},
	classesReleve: {
		source: 'src/lib/courriels-affaires.ts#CLASSES_RELEVE',
		quoi: "ce qui a été fait d'un message classé par le conseil, et son ton",
		lecteur: 'scripts/generateurs/delegations_cs.py',
	},
	teinteDuTon: {
		source: 'src/lib/journal-verdicts.ts#TEINTE_DU_TON',
		quoi: "la pastille de chaque ton d'un verdict de journal",
		lecteur: 'scripts/generateurs/delegations_cs.py',
	},
	civilites: {
		source: 'src/lib/annuaire.ts#CIVILITES',
		quoi: "les civilités d'une fiche de l'annuaire, dans l'ordre",
		lecteur: 'scripts/generateurs/espace_cs.py',
	},

	//  ── Lot B : les tables qui vivaient déjà dans `#lib` (lues par motif) ──────
	//  Navigation et droits d'affichage
	pages: {
		source: 'src/lib/pages.ts#PAGES',
		quoi: "les pages du site dans l'ordre par défaut (celles de l'Espace CS et de l'administration comprises), leurs onglets et leurs réserves",
		lecteur: 'scripts/generateurs/onglets.py',
	},
	titreFil: {
		source: 'src/lib/flux.ts#TITRE_FIL',
		quoi: 'le titre de la section du fil au tableau de bord',
		lecteur: 'scripts/generateurs/onglets.py',
	},
	rolesDuDroit: {
		source: 'src/lib/roles.ts#ROLES_DU_DROIT',
		quoi: "les rôles qui portent chaque droit d'affichage (isAdmin, isCS…)",
		lecteur: 'scripts/generateurs/onglets.py',
	},
	statutsDuProfil: {
		source: 'src/lib/roles.ts#STATUTS_DU_PROFIL',
		quoi: 'les statuts que reconnaît chaque prédicat (estLocataire, estGestionnaire…)',
		lecteur: 'scripts/generateurs/onglets.py',
	},
	//  Rôles, statuts et texte riche
	attributsRole: {
		source: 'src/lib/roles.ts#ATTRIBUTS_ROLE',
		quoi: "le libellé et la pastille de chaque rôle d'un compte",
		lecteur: 'scripts/generateurs/charte.py',
	},
	attributsStatut: {
		source: 'src/lib/roles.ts#ATTRIBUTS_STATUT',
		quoi: "le libellé, l'abrégé et la pastille de chaque statut d'une personne",
		lecteur: 'scripts/generateurs/charte.py',
	},
	libellesHerites: {
		source: 'src/lib/roles.ts#LIBELLES_HERITES',
		quoi: 'les libellés des anciennes clés de rôle encore servies',
		lecteur: 'scripts/generateurs/charte.py',
	},
	statutsDemandables: {
		source: 'src/lib/roles.ts#STATUTS_DEMANDABLES',
		quoi: "les statuts qu'on peut demander depuis son profil",
		lecteur: 'scripts/generateurs/communaute_profil.py',
	},
	balisesAdmises: {
		source: 'src/lib/sanitize.ts#ALLOWED_TAGS',
		quoi: 'les balises que le texte riche admet',
		lecteur: 'scripts/generateurs/charte.py',
	},
	attributsAdmis: {
		source: 'src/lib/sanitize.ts#ALLOWED_ATTR',
		quoi: 'les attributs que le texte riche admet',
		lecteur: 'scripts/generateurs/charte.py',
	},
	naturesDuFil: {
		source: 'src/lib/flux.ts#NATURES_DU_FIL',
		quoi: "le libellé, la teinte, le pictogramme et l'abrégé de chaque rubrique du fil",
		lecteur: 'scripts/generateurs/charte.py',
	},
	//  Affaires
	statutsTicket: {
		source: 'src/lib/tickets.ts#STATUTS_TICKET',
		quoi: "les statuts du cycle d'une affaire, dans l'ordre, avec libellé et pastille",
		lecteur: 'scripts/generateurs/affaires.py',
	},
	statutsTicketHistoriques: {
		source: 'src/lib/tickets.ts#STATUTS_TICKET_HISTORIQUES',
		quoi: 'les anciens statuts encore affichés, avec libellé et pastille',
		lecteur: 'scripts/generateurs/charte.py',
	},
	statutsTicketSansCycle: {
		source: 'src/lib/tickets.ts#STATUTS_TICKET_SANS_CYCLE',
		quoi: 'les statuts hors du cycle, avec libellé et pastille',
		lecteur: 'scripts/generateurs/charte.py',
	},
	statutsTicketClos: {
		source: 'src/lib/tickets.ts#STATUTS_TICKET_CLOS',
		quoi: 'les statuts qui closent une affaire',
		lecteur: 'scripts/generateurs/affaires.py',
	},
	groupesSuivi: {
		source: 'src/lib/tickets.ts#GROUPES_SUIVI',
		quoi: 'les options du filtre « Suivi » et les statuts que chacune réunit',
		lecteur: 'scripts/generateurs/affaires.py',
	},
	categorieActualite: {
		source: 'src/lib/tickets.ts#CATEGORIE_ACTUALITE',
		quoi: "la catégorie d'une actualité",
		lecteur: 'scripts/generateurs/affaires.py',
	},
	optionsTicket: {
		source: 'src/lib/tickets.ts#OPTIONS_TICKET',
		quoi: "les options de publication qu'une affaire propose",
		lecteur: 'scripts/generateurs/options_affaire.py',
	},
	optionsPublication: {
		source: 'src/lib/options-publication.ts#OPTIONS_PUBLICATION',
		quoi: 'chaque option de publication : pictogramme, geste, état, aide',
		lecteur: 'scripts/generateurs/options_affaire.py',
	},
	categoriesTicket: {
		source: 'src/lib/tickets-categories.ts#CATEGORIES_TICKET',
		quoi: "les catégories d'une affaire, dans l'ordre du site",
		lecteur: 'scripts/generateurs/affaires.py',
	},
	naturesAffaire: {
		source: 'src/lib/tickets-categories.ts#NATURES',
		quoi: "les natures d'une affaire, dans l'ordre du filtre",
		lecteur: 'scripts/generateurs/affaires.py',
	},
	colonnesKanban: {
		source: 'src/lib/kanban.ts#KANBAN_COLS',
		quoi: 'les colonnes du Kanban, dans leur ordre, et leur teinte',
		lecteur: 'scripts/generateurs/affaires.py',
	},
	colonneParStatutTicket: {
		source: 'src/lib/kanban.ts#COLONNE_PAR_STATUT_TICKET',
		quoi: "la colonne du Kanban de chaque statut d'une affaire",
		lecteur: 'scripts/generateurs/affaires.py',
	},
	motColonneVide: {
		source: 'src/lib/kanban.ts#MOT_COLONNE_VIDE',
		quoi: "ce qu'une colonne vide du Kanban affiche",
		lecteur: 'scripts/generateurs/affaires.py',
	},
	//  Accès, baux et prestataires
	typesAcces: {
		source: 'src/lib/types-acces.ts#TYPES_ACCES',
		quoi: "les types d'un accès (badge, télécommande…)",
		lecteur: 'scripts/generateurs/acces_prestataires.py',
	},
	statutsAcces: {
		source: 'src/lib/types-acces.ts#STATUTS_ACCES',
		quoi: "les états d'un accès, avec libellé et pastille",
		lecteur: 'scripts/generateurs/acces_prestataires.py',
	},
	etatsBail: {
		source: 'src/lib/bail.ts#ETATS_BAIL',
		quoi: "le libellé et la pastille de l'état d'un bail",
		lecteur: 'scripts/generateurs/acces_prestataires.py',
	},
	typesPrestataire: {
		source: 'src/lib/prestataires.ts#TYPES_PRESTATAIRE',
		quoi: "les types d'un prestataire",
		lecteur: 'scripts/generateurs/acces_prestataires.py',
	},
	filtresContrat: {
		source: 'src/lib/prestataires.ts#FILTRES_CONTRAT',
		quoi: 'les filtres de la liste des prestataires selon leur contrat',
		lecteur: 'scripts/generateurs/acces_prestataires.py',
	},
	//  Administration et reporting
	libellesTache: {
		source: 'src/lib/taches.ts#LIBELLE_TACHE',
		quoi: 'le nom de chaque tâche planifiée',
		lecteur: 'scripts/generateurs/admin.py',
	},
	statutsTache: {
		source: 'src/lib/taches.ts#STATUTS_TACHE',
		quoi: "le libellé, l'aide et la pastille de l'état d'une tâche planifiée",
		lecteur: 'scripts/generateurs/admin.py',
	},
	etatsVisite: {
		source: 'src/lib/entretien-periodique.ts#ETATS_VISITE',
		quoi: "le libellé et la pastille de l'état d'une visite d'entretien",
		lecteur: 'scripts/generateurs/delegations_cs.py',
	},
	motifsEvolution: {
		source: 'src/lib/reporting.ts#MOTIFS_EVOLUTION',
		quoi: "ce que le signal « a évolué » dit d'une affaire, selon son motif",
		lecteur: 'scripts/generateurs/delegations_cs.py',
	},
	motifEvolutionParDefaut: {
		source: 'src/lib/reporting.ts#MOTIF_EVOLUTION_PAR_DEFAUT',
		quoi: "ce que dit un motif d'évolution inconnu ou absent",
		lecteur: 'scripts/generateurs/delegations_cs.py',
	},
	//  Communauté et profil
	statutsIdee: {
		source: 'src/lib/idees.ts#STATUTS_IDEE',
		quoi: "les états d'une idée, dans l'ordre du cycle",
		lecteur: 'scripts/generateurs/communaute_profil.py',
	},
	statutsAnnonce: {
		source: 'src/lib/annonces.ts#STATUTS_ANNONCE',
		quoi: "les états d'une annonce",
		lecteur: 'scripts/generateurs/communaute_profil.py',
	},
	teinteStatutAnnonce: {
		source: 'src/lib/annonces.ts#TEINTE_STATUT_ANNONCE',
		quoi: "la pastille de chaque état d'une annonce",
		lecteur: 'scripts/generateurs/communaute_profil.py',
	},
	typesAnnonce: {
		source: 'src/lib/annonces.ts#TYPES_ANNONCE',
		quoi: "les types d'annonce",
		lecteur: 'scripts/generateurs/communaute_profil.py',
	},
	categoriesAnnonce: {
		source: 'src/lib/annonces.ts#CATEGORIES_ANNONCE',
		quoi: "les catégories d'annonce",
		lecteur: 'scripts/generateurs/communaute_profil.py',
	},
	trisAnnonce: {
		source: 'src/lib/annonces.ts#TRIS_ANNONCE',
		quoi: 'les tris des annonces',
		lecteur: 'scripts/generateurs/communaute_profil.py',
	},
	optionsTheme: {
		source: 'src/lib/theme.ts#OPTIONS_THEME',
		quoi: 'les choix du thème (automatique, clair, sombre)',
		lecteur: 'scripts/generateurs/communaute_profil.py',
	},
	cookieTheme: {
		source: 'src/lib/theme.ts#COOKIE_THEME',
		quoi: "le nom du cookie d'appareil qui porte le thème",
		lecteur: 'scripts/generateurs/communaute_profil.py',
	},
	themeParDefaut: {
		source: 'src/lib/theme.ts#THEME_PAR_DEFAUT',
		quoi: 'le thème quand aucun choix n’est posé',
		lecteur: 'scripts/generateurs/communaute_profil.py',
	},
	canauxNotifications: {
		source: 'src/lib/preferences.ts#CANAUX_NOTIFS',
		quoi: 'les canaux de notification et la clé de leurs deux cases',
		lecteur: 'scripts/generateurs/communaute_profil.py',
	},
	//  Pied de page et logiciel
	plateforme: {
		source: {
			nom: 'src/lib/plateforme.ts#NOM_PLATEFORME',
			site: 'src/lib/plateforme.ts#SITE_PLATEFORME',
			depotSource: 'src/lib/plateforme.ts#DEPOT_SOURCE',
			licenceSpdx: 'src/lib/plateforme.ts#LICENCE_SPDX',
			licenceNom: 'src/lib/plateforme.ts#LICENCE_NOM',
			licenceUrl: 'src/lib/plateforme.ts#LICENCE_URL',
		},
		quoi: 'le logiciel qui fait tourner le site : nom, site, dépôt, licence',
		lecteur: 'scripts/generateurs/a_propos.py',
	},
	elementsPied: {
		source: 'src/lib/piedDePage.ts#ELEMENTS_PIED',
		sans: ['[].lien.cible'],
		quoi: 'les éléments du pied de page, dans leur ordre par défaut (la cible d’un lien est calculée : non publiée)',
		lecteur: 'scripts/generateurs/a_propos.py',
	},
	clesPied: {
		source: 'src/lib/piedDePage.ts#CLES_PIED',
		quoi: 'les clés de GET /config qui règlent le pied de page',
		lecteur: 'scripts/generateurs/a_propos.py',
	},

	//  ── Lot C : la charte visuelle (jetons CSS, palettes, tracé) ──────────────
	//  Une valeur garde son texte (`var(--…)`, `color-mix(…)`) : l'app résout elle-même
	//  la cascade — au sombre, la charte sombre sur la palette claire, puis la palette
	//  sombre par-dessus.
	jetonsCharte: {
		source: 'src/styles/socle.css@:root',
		quoi: 'les jetons de la charte au clair (couleurs, tailles, rayons…), palette « seine »',
		lecteur: 'scripts/generateurs/palettes.py',
	},
	jetonsCharteSombre: {
		source: "src/styles/palette-sombre.css@:root[data-theme='dark']",
		quoi: 'les jetons que le thème sombre redéfinit',
		lecteur: 'scripts/generateurs/palettes.py',
	},
	palettesClaires: {
		source: "src/styles/palettes.css@:root[data-palette='*']",
		quoi: "les jetons que chaque palette d'une résidence redéfinit au clair, par code",
		lecteur: 'scripts/generateurs/palettes.py',
	},
	palettesSombres: {
		source: "src/styles/palettes.css@:root[data-palette='*'][data-theme='dark']",
		quoi: 'les jetons que chaque palette redéfinit au sombre, par code',
		lecteur: 'scripts/generateurs/palettes.py',
	},
	teinteNature: {
		source: "src/styles/normes.css@[data-nature='*']",
		quoi: "la teinte forte de la gouttière de chaque nature d'affaire",
		lecteur: 'scripts/generateurs/affaires.py',
	},
	tranchesRepartition: {
		source: "src/lib/components/reporting/BarresCroisees.svelte@[data-teinte='*']",
		quoi: "la couleur de chaque tranche d'une répartition du Reporting, selon la teinte servie",
		lecteur: 'scripts/generateurs/delegations_cs.py',
	},
	attributsTrace: {
		source: 'src/lib/icones.ts#ATTRIBUTS_TRACE',
		quoi: 'les attributs du <svg> autour de chaque pictogramme (le trait du site)',
		lecteur: 'scripts/generateurs/pictogrammes.py',
	},
};

export const RETRAITS = {};
