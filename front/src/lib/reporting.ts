//  Le vocabulaire du **reporting CS** — écrit une fois pour les six vues qui le
//  partagent (`#lib/components/reporting/`).
//
//  Il vivait dans `espace-cs/+page.svelte`, mêlé à l'état de quatre autres
//  onglets. En sortant la rubrique de la page (#453), ces types et ces calculs
//  ont dû se poser quelque part : les recopier dans chaque vue aurait ouvert
//  exactement la divergence que #415 et #413 ont fermée ailleurs.
//
//  ⚠️ Aucune fonction d'ici ne touche au réseau ni au DOM. Les chargements
//  vivent dans `OngletReporting.svelte`, la mise en forme dans les vues.

import type {
	AffaireOuverte,
	ContratARenouveler,
	DiagnosticAEcheance,
	ReleveRenouvellements,
} from '#lib/api/index.ts';

//  🔴 Le « Suivi des dossiers » (affaires suivies au kanban, rangées par
//  colonne) vivait ici — `ReportDossier`, `dossiersSuivis`, les colonnes et leurs
//  teintes. Il est devenu le « Suivi des affaires » le 16/10/2026 : TOUTES les
//  affaires non closes, relevées par le SERVEUR (`GET /suivi-affaires`), qui
//  porte la règle d'entrée, l'ancienneté et l'export PDF. L'écran ne recalcule rien.

export interface ReportPrestataire {
	id: number;
	nom: string;
	specialite?: string | null;
	type_prestataire?: string | null;
	/**  La moyenne de ses avis, SERVIE par l'API (`PrestataireRead.note_moyenne`, #2507) —
	 *   l'onglet la recalculait des notations, à la main. */
	note_moyenne: number | null;
	nb_notations: number;
}
//  🔴 `ReportContrat` et `DiagType` sont PARTIS le 05/11/2026 (#2525) : la vue
//  Renouvellements lit le RELEVÉ servi (`ReleveRenouvellements`, `#lib/api/reporting.ts`).

/**  Les vues du reporting — la liste sert aussi à valider un `?vue=` d'URL,
 *   et c'est ce qui fait retomber sans bruit un lien `?vue=devis` d'avant le
 *   28/08/2026, date du retrait de « Devis & interventions ».
 *
 *   ⚠️ Ce commentaire a d'abord justifié le retrait par la redondance avec
 *   l'onglet « Prestations » de la page Prestataires — écrit le matin même où un
 *   autre lot supprimait cet onglet. La raison est plus simple, et elle ne
 *   dépend d'aucun autre écran : la prestation ponctuelle n'existe plus comme
 *   objet. Une justification qui s'appuie sur un écran voisin devient fausse
 *   quand celui-ci bouge, sans que rien ne le signale. */
export const REPORT_VUES = [
	//  « Suivi des affaires » — `kanban` jusqu'au 16/10/2026 : un ancien
	//  `?vue=kanban` retombe sans bruit sur cette vue, la première.
	'affaires',
	//  « Analyse des affaires » (`tickets`) a quitté la barre le 17/10/2026 :
	//  redondante avec les répartitions du Suivi des affaires. Un ancien
	//  `?vue=tickets` retombe sans bruit sur la première vue.
	'prestataires',
	'renouvellements',
	//  « Entretien périodique » a quitté la barre le 17/10/2026 (#2043) : c'est
	//  désormais le mode « Suivi entretiens périodiques » du Suivi des affaires,
	//  où `?vue=periodique` mène (`VUE_PERIODIQUE`).
] as const;
export type ReportVue = (typeof REPORT_VUES)[number];

/**  `?vue=relance` — l'adresse de la relance syndic (`HREF_RELANCE_SYNDIC`, le compteur
 *   « N relances » de la pastille Espace CS). La vue « Relance syndic » est devenue le mode « Relancer
 *   le syndic » du Suivi des affaires (#2035) : l'adresse y mène, en ce mode. */
export const VUE_RELANCE = 'relance';

/**  `?vue=periodique` — l'adresse de l'ancienne vue « Entretien périodique » : elle
 *   mène au mode « Suivi entretiens périodiques » du Suivi des affaires (#2043). */
export const VUE_PERIODIQUE = 'periodique';

/**  Ce que le signal « a évolué » dit sous le titre d'une affaire (#2044) — le
 *   motif vient du serveur (`releve.evolution`) : `nouvelle`, ou le type de la
 *   dernière entrée du fil depuis le résumé. Un type inconnu se dit « Du nouveau ». */
//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const MOTIFS_EVOLUTION: Record<string, string> = {
	nouvelle: 'Nouvelle affaire, jamais résumée',
	commentaire: 'Nouvelle suite depuis le dernier résumé',
	etat: 'Changement d’état depuis le dernier résumé',
	reponse: 'Nouveau message depuis le dernier résumé',
	relance: 'Relance envoyée depuis le dernier résumé',
};
/**  Ce que dit un motif inconnu ou absent. */
//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const MOTIF_EVOLUTION_PAR_DEFAUT = 'Du nouveau depuis le dernier résumé';
export function motifEvolution(motif: string | null): string {
	return (motif && MOTIFS_EVOLUTION[motif]) || MOTIF_EVOLUTION_PAR_DEFAUT;
}

/* ── Renouvellements : le relevé, LU ─────────────────────────────────────────
   🔴 Le relevé se calculait ici (#453) : l'année de référence (`anneeCourante`,
   celle du navigateur), le préavis (`PREAVIS_MOIS`), l'échéance et l'urgence d'un
   diagnostic (`diagNextDate`, `diagUrgence`), l'ordre des contrats et des
   diagnostics (`contratsAvecEcheance`, `diagnosticsAvecEcheance`). Ils sont SERVIS
   par `GET /reporting/renouvellements` depuis le 05/11/2026 (#2525) — l'app iOS
   lit le même relevé. Ne reste ici que la conversion des dates ISO en `Date`,
   dont la frise a besoin pour placer ses barres. */

export const MOIS_LABELS = [
	'Janv.',
	'Fév.',
	'Mars',
	'Avr.',
	'Mai',
	'Juin',
	'Juil.',
	'Août',
	'Sept.',
	'Oct.',
	'Nov.',
	'Déc.',
];

const enDate = (iso: string | null | undefined): Date | null => (iso ? new Date(iso) : null);

/** Un contrat du relevé, ses dates converties pour la frise. */
export interface ContratAvecEcheance extends ContratARenouveler {
	dateFin: Date | null;
	datePreavis: Date | null;
	/** `inconnu` quand le terme ne se déduit pas (`urgence_echeance` nul). */
	urgence: 'preavis' | 'annee' | 'futur' | 'inconnu';
}

/** Les contrats du relevé, DANS SON ORDRE (la pire note d'abord). */
export function contratsDuReleve(releve: ReleveRenouvellements | null): ContratAvecEcheance[] {
	return (releve?.contrats ?? []).map((c) => ({
		...c,
		dateFin: enDate(c.date_fin),
		datePreavis: enDate(c.date_preavis),
		urgence: c.urgence_echeance ?? 'inconnu',
	}));
}

/** Un diagnostic du relevé, son échéance convertie. */
export interface DiagAvecEcheance extends DiagnosticAEcheance {
	nextDate: Date | null;
	/** `inconnu` sans échéance connue (permanent, ou sans rapport daté). */
	urgence: 'depasse' | 'annee' | 'futur' | 'inconnu';
}

/** Les diagnostics APPLICABLES du relevé, dans son ordre (l'échéance la plus proche d'abord). */
export function diagnosticsDuReleve(releve: ReleveRenouvellements | null): DiagAvecEcheance[] {
	return (releve?.diagnostics ?? []).map((d) => ({
		...d,
		nextDate: enDate(d.prochaine_echeance),
		urgence: d.urgence_echeance ?? 'inconnu',
	}));
}

//  🔴 `typeEquipementDuContrat` est PARTI le 04/11/2026 (#2507) : l'équipement qu'un
//  contrat couvre — le sien, sinon (« autre ») la spécialité du prestataire — est SERVI
//  par l'API (`equipement_effectif`, `carnet_entretien.type_equipement_resolu`), et
//  l'enregistrement le résout au serveur. Trois règles s'étaient contredites ici le
//  29/08/2026 ; la dernière vivait en deux langues, tenue par un test de concordance.

/** La teinte de l'âge d'une affaire — la tranche vient du serveur, qui garde les seuils
 *  (`TableauAffaires`). */
//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const TEINTE_AGE: Record<AffaireOuverte['anciennete'], string> = {
	ancienne: 'badge-red',
	moyenne: 'badge-orange',
	recente: 'badge-gray',
};

/** Les modes du Suivi des affaires, dans leur ordre (`VueSuiviAffaires`). */
//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const MODES_SUIVI = [
	{ valeur: 'suivi', libelle: 'Suivi affaires' },
	{ valeur: 'entretien', libelle: 'Suivi entretiens périodiques' },
	{ valeur: 'relance', libelle: 'Relancer le syndic' },
];
