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
 *   (objet, liste, chaîne, nombre, booléen ; `as const` admis). Le script lit
 *   l'arbre syntaxique de ce seul fichier et n'exécute rien ;
 * - `quoi` — ce que la table dit, en une ligne ;
 * - `lecteur` — le générateur de coprofirst-ios qui la lit.
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
};

export const RETRAITS = {};
