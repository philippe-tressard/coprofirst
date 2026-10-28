/**
 *  Le VOCABULAIRE de l'onglet « Installations » (R4 #1880) : les états du
 *  registre, les gestes de l'opérateur, et le classement d'une installation dans
 *  la gouttière de sa carte. Les RÈGLES — quel geste s'applique à quel état —
 *  restent au serveur (`registre/decisions.TRANSITIONS`), qui rend les gestes
 *  possibles de chaque fiche : ce module n'en tient que les mots.
 */
import { classeDe, type ClasseGouttiere, type MarqueGouttiere } from '#lib/gouttiere.ts';
import type {
	AlerteRegistre,
	EtatRegistre,
	GesteRegistre,
	RapportInstallation,
} from '#lib/api/index.ts';

/**  Les états, dans l'ordre de vie d'une inscription — filtre en pastilles (≤ 6). */
export const ETATS_REGISTRE: readonly { val: EtatRegistre; label: string }[] = [
	{ val: 'en_attente', label: 'En attente' },
	{ val: 'active', label: 'Active' },
	{ val: 'suspendue', label: 'Suspendue' },
	{ val: 'resiliee', label: 'Résiliée' },
];

export const LIBELLE_ETAT_REGISTRE: Record<EtatRegistre, string> = Object.fromEntries(
	ETATS_REGISTRE.map((e) => [e.val, e.label]),
) as Record<EtatRegistre, string>;

/**  Un geste de l'opérateur : son libellé, la question posée, et s'il se défait. */
export interface GesteDeclare {
	libelle: string;
	icone: string;
	/** Ce que le geste change, dit avant de demander le motif. */
	effet: string;
	/** Résilier ne se défait pas : le bouton le dit par sa couleur. */
	definitif?: boolean;
	/** Le geste attendu — valider, rétablir — se donne à voir en bouton principal. */
	principal?: boolean;
}

export const GESTES_REGISTRE: Record<GesteRegistre, GesteDeclare> = {
	valider: {
		libelle: 'Valider',
		icone: 'check',
		effet: "L'installation passe active : elle sort du mode limité à son prochain bail.",
		principal: true,
	},
	suspendre: {
		libelle: 'Suspendre',
		icone: 'lock',
		effet: 'Lecture seule et export, plus aucun service — à son prochain bail.',
	},
	retablir: {
		libelle: 'Rétablir',
		icone: 'undo-2',
		effet: "L'installation redevient active à son prochain bail.",
		principal: true,
	},
	resilier: {
		libelle: 'Résilier',
		icone: 'ban',
		effet:
			"Définitif : l'installation retombe en mode limité, et l'effacement de ses données revient à son exploitant.",
		definitif: true,
	},
	supprimer: {
		libelle: 'Supprimer',
		icone: 'trash-2',
		effet:
			"Définitif : l'installation quitte la liste ; ses coordonnées et ses rapports sont effacés. Le contrat accepté reste archivé cinq ans après la résiliation, puis s'efface de lui-même.",
		definitif: true,
	},
};

/**  Ce que dit une ligne du journal (`DecisionRegistre.geste`) — un code inconnu
 *   se montre tel quel plutôt que de disparaître. */
const LIBELLES_DECISION: Record<string, string> = {
	inscription: 'Inscription',
	conditions_acceptees: 'Conditions acceptées',
	clone_signale: 'Clone signalé',
	valider: 'Validée',
	suspendre: 'Suspendue',
	retablir: 'Rétablie',
	resilier: 'Résiliée',
	services: 'Services accordés',
	supprimer: 'Supprimée',
	retour_apres_suppression: 'Revenue après sa suppression',
	distribution: 'Canal et version réglés',
	canal_avance: 'Canal avancé',
	coordonnees_effacees: 'Coordonnées effacées',
	contrat_efface: 'Contrat archivé effacé',
};

/**  Le suivi d'une alerte grave au journal (`registre/alertes`) : `alerte_signalee:muette`
 *   — le code est suivi de l'alerte, dont le motif de la ligne porte le libellé. */
const SUIVI_ALERTE: Record<string, string> = {
	alerte_signalee: 'Alerte signalée à l’opérateur',
	alerte_levee: 'Alerte levée',
};

export function libelleDecision(geste: string): string {
	const [suivi] = geste.split(':');
	return LIBELLES_DECISION[geste] ?? SUIVI_ALERTE[suivi] ?? geste;
}

/**  « 1 alerte », « 3 alertes » ; grave dès qu'une l'est — c'est elle qui teinte. */
export function resumeAlertes(alertes: AlerteRegistre[]): { texte: string; grave: boolean } {
	const n = alertes.length;
	return { texte: `${n} alerte${n > 1 ? 's' : ''}`, grave: alertes.some((a) => a.grave) };
}

/**  « Aucun service accordé », « 1 service accordé », « 2 services accordés ». */
export function servicesAccordes(n: number): string {
	return n === 0
		? 'Aucun service accordé'
		: `${n} service${n > 1 ? 's' : ''} accordé${n > 1 ? 's' : ''}`;
}

/**  Le canal qui suit la dernière version publiée (`registre/canaux.CANAL_URGENCE`) ;
 *   tout autre canal d'une installation est une version `X.Y.Z` choisie (#2210). */
export const CANAL_URGENCE = 'urgence';

const CANAUX = [
	{ val: 'main', label: 'Référence' },
	{ val: CANAL_URGENCE, label: 'Canal Urgence' },
	{ val: 'version', label: 'Version fixe' },
] as const;

const MARQUES_CANAL: Record<string, MarqueGouttiere> = {
	main: ['star', 'RÉF.'],
	[CANAL_URGENCE]: ['zap', 'URG.'],
	version: ['pin', 'FIXE'],
};

/**  La gouttière d'une installation : son rôle, lu sur le canal qu'elle suit — une
 *   version choisie, quelle qu'elle soit, se classe sous une seule marque. */
export function classeInstallation(canal: string): ClasseGouttiere | null {
	const famille = canal === 'main' || canal === CANAL_URGENCE ? canal : 'version';
	return classeDe(CANAUX, MARQUES_CANAL, famille);
}

/**  « 2.172.0 », ou ce que le prochain bail porte quand il n'y a rien à installer —
 *   le serveur décide (`registre/canaux.version_cible`), l'écran le dit. */
export function libelleVersionCible(version: string | null): string {
	return version ? `v${version}` : 'aucune — pas de mise à jour automatique';
}

/**  Un point de CONFORMITÉ du rapport nocturne : la phrase qui dit le FAIT dans
 *   chacun des trois états, et ce que le point vérifie.
 *
 *   🔴 Le fait change avec l'état, jamais la coche seule : « Documentation d’API
 *   publiée ✓ » se lirait « elle est publiée, et c'est bien » — l'inverse de la
 *   vérité. Le champ du contrat, lui, ne bouge pas (`documentation_api_coupee`,
 *   contrat versionné du registre) : seul l'écran le dit autrement. */
export interface PointConformite {
	/** Le fait quand le point est conforme… */
	conforme: string;
	/** … quand il est à corriger… */
	aCorriger: string;
	/** … et le seul nom quand la mesure n'a pas pu se faire. */
	inconnu: string;
	/** Ce que le point vérifie, et pourquoi il compte — la bulle de la coche. */
	explication: string;
}

type ClePosture = keyof RapportInstallation['posture'];

/**  La posture, dans l'ordre de la ligne. Chaque champ du contrat vaut `true`
 *   quand le point est SAIN — `documentation_api_coupee` compris. */
export const POSTURE: Record<ClePosture, PointConformite> = {
	documentation_api_coupee: {
		conforme: 'Documentation d’API non publiée',
		aCorriger: 'Documentation d’API publiée',
		inconnu: 'Documentation d’API',
		explication:
			'/docs, /redoc et /openapi.json décrivent chaque route de l’API : une installation en service ne les sert pas (ENABLE_API_DOCS reste à false).',
	},
	cookie_securise: {
		conforme: 'Cookie de session sécurisé',
		aCorriger: 'Cookie de session non sécurisé',
		inconnu: 'Cookie de session',
		explication:
			'Le cookie de session porte le drapeau Secure : il ne voyage que sur une connexion chiffrée (HTTPS). COOKIE_SECURE ne se coupe que pour un essai en local.',
	},
	secret_suffisant: {
		conforme: 'Clé secrète assez longue',
		aCorriger: 'Clé secrète trop courte',
		inconnu: 'Clé secrète',
		explication:
			'La clé qui signe les sessions de chaque copropriété fait au moins 32 caractères : plus courte, elle cède à une recherche exhaustive.',
	},
	lien_source_present: {
		conforme: 'Lien vers le code source présent',
		aCorriger: 'Lien vers le code source absent',
		inconnu: 'Lien vers le code source',
		explication:
			'La licence AGPL (§13) oblige à offrir le code source à qui utilise l’application : un lien doit y mener depuis ses pages.',
	},
};

export const COPIE_HORS_MACHINE: PointConformite = {
	conforme: 'Copie hors machine',
	aCorriger: 'Aucune copie hors machine',
	inconnu: 'Copie hors machine',
	explication:
		'Sur un seul serveur, seule une copie de la sauvegarde posée ailleurs survit à la perte du disque ou de la machine.',
};

/**  Les points de la posture d'un rapport, dans l'ordre de `POSTURE`. */
export function pointsPosture(
	posture: RapportInstallation['posture'],
): { cle: ClePosture; point: PointConformite; conforme: boolean | null }[] {
	return (Object.keys(POSTURE) as ClePosture[]).map((cle) => ({
		cle,
		point: POSTURE[cle],
		conforme: posture[cle],
	}));
}
