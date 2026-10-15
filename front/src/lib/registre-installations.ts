/**
 *  Le VOCABULAIRE de l'onglet « Installations » (R4 #1880) : les états du
 *  registre, les gestes de l'opérateur, et le classement d'une installation dans
 *  la gouttière de sa carte. Les RÈGLES — quel geste s'applique à quel état —
 *  restent au serveur (`registre/decisions.TRANSITIONS`), qui rend les gestes
 *  possibles de chaque fiche : ce module n'en tient que les mots.
 */
import { classeDe, type ClasseGouttiere, type MarqueGouttiere } from '$lib/gouttiere';
import type { AlerteRegistre, EtatRegistre, GesteRegistre } from '$lib/api';

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

const CANAUX = [
	{ val: 'main', label: 'Référence' },
	{ val: 'replica', label: 'Réplique' },
] as const;

const MARQUES_CANAL: Record<string, MarqueGouttiere> = {
	main: ['star', 'RÉF.'],
	replica: ['layers', 'RÉPL.'],
};

/**  La gouttière d'une installation : son rôle, lu sur le canal qu'elle suit. */
export function classeInstallation(canal: string): ClasseGouttiere | null {
	return classeDe(CANAUX, MARQUES_CANAL, canal);
}
