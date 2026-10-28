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
}
export interface ReportContrat {
	id: number;
	prestataire_id: number;
	type_equipement: string;
	libelle: string;
	numero_contrat?: string | null;
	date_debut: string;
	duree_initiale_valeur?: number | null;
	duree_initiale_unite?: string | null;
	frequence_type?: string | null;
	frequence_valeur?: number | null;
	prochaine_visite?: string | null;
	/**  L'échéance DÉDUITE par l'API (`utils/echeance_contrat.py`), reportée d'un
	 *   an tant qu'elle est passée. À ne pas confondre avec `prochaine_visite`,
	 *   qui est une date de visite saisie à la main. */
	date_fin?: string | null;
	/**  Le terme initial est passé : le contrat court par reconduction tacite. */
	reconduit?: boolean;
	/**  Le terme est passé et RIEN ne l'a prolongé — un mandat de syndic qui a
	 *   cessé. Exclusif de `reconduit` : voir `SANS_RECONDUCTION_TACITE`. */
	echu?: boolean;
	actif: boolean;
}
export interface DiagRapport {
	id: number;
	titre: string;
	date_rapport?: string | null;
}
export interface DiagType {
	id: number;
	code: string;
	nom: string;
	texte_legislatif: string;
	frequence?: string | null;
	non_applicable: boolean;
	rapports: DiagRapport[];
}

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

/**  `?vue=relance` — l'adresse de la relance syndic (`HREF_RELANCE_SYNDIC`, l'alerte
 *   du tableau de bord). La vue « Relance syndic » est devenue le mode « Relancer
 *   le syndic » du Suivi des affaires (#2035) : l'adresse y mène, en ce mode. */
export const VUE_RELANCE = 'relance';

/**  `?vue=periodique` — l'adresse de l'ancienne vue « Entretien périodique » : elle
 *   mène au mode « Suivi entretiens périodiques » du Suivi des affaires (#2043). */
export const VUE_PERIODIQUE = 'periodique';

/**  Ce que le signal « a évolué » dit sous le titre d'une affaire (#2044) — le
 *   motif vient du serveur (`releve.evolution`) : `nouvelle`, ou le type de la
 *   dernière entrée du fil depuis le résumé. Un type inconnu se dit « Du nouveau ». */
const MOTIFS_EVOLUTION: Record<string, string> = {
	nouvelle: 'Nouvelle affaire, jamais résumée',
	commentaire: 'Nouvelle suite depuis le dernier résumé',
	etat: 'Changement d’état depuis le dernier résumé',
	reponse: 'Nouveau message depuis le dernier résumé',
	relance: 'Relance envoyée depuis le dernier résumé',
};
export function motifEvolution(motif: string | null): string {
	return (motif && MOTIFS_EVOLUTION[motif]) || 'Du nouveau depuis le dernier résumé';
}

/* ── Renouvellements : calculs ────────────────────────────────────────────
   L'année de référence est une FONCTION, pas une constante. Elle était figée au
   chargement de la page, qui ne vivait que le temps d'un onglet ; ce module-ci
   est chargé une fois pour toute la session — un onglet laissé ouvert la nuit du
   réveillon aurait continué d'annoncer les échéances de l'année passée. */
export const PREAVIS_MOIS = 3;
export function anneeCourante(): number {
	return new Date().getFullYear();
}

/**
 * Minuit du jour — la borne d'un « en retard », qui n'est PAS l'instant.
 *
 * ⚠️ Une échéance prévue aujourd'hui n'est pas en retard, et elle l'aurait été
 * dès 00 h 01 avec un `new Date()` nu.
 *
 * ⚠️ À employer via `relire(donnees, minuitDuJour)` : appelée dans un `$:` qui
 * ne cite aucune variable réactive, elle serait figée au chargement de l'onglet
 * (`#lib/utils.relire`).
 */
export function minuitDuJour(): Date {
	const d = new Date();
	d.setHours(0, 0, 0, 0);
	return d;
}

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

/**
 * L'échéance du contrat — LUE, non plus calculée ici.
 *
 * 🔴 Ce calcul vivait dans ce fichier, et l'API en ignorait tout : la fiche de la
 * résidence affichait `prochaine_visite` sous le mot « échéance » et le tableau
 * de bord lisait une colonne héritée. Trois valeurs pour une même question, sur
 * le même contrat (relevé le 29/08/2026, sur une remarque de l'utilisateur à
 * propos de la reconduction tacite).
 *
 * La règle vit maintenant dans `api/app/utils/echeance_contrat.py`, seule
 * écriture, éprouvée par `api/tests/test_echeance_contrat.py` — y compris les
 * cas que cette version-ci traitait mal : le 31 janvier + 1 mois, et le terme
 * qui tombe le jour même.
 *
 * ⚠️ Cette fonction reste, et c'est délibéré : elle est le point où l'on
 * convertit la chaîne ISO en `Date`, ce dont le reste du module a besoin. La
 * supprimer aurait dispersé ce `new Date(…)` dans les appelants.
 */
export function contratDateFin(c: ReportContrat): { date: Date; reconduit: boolean } | null {
	if (!c.date_fin) return null;
	return { date: new Date(c.date_fin), reconduit: c.reconduit ?? false };
}

export function contratDatePreavis(dateFin: Date): Date {
	const d = new Date(dateFin);
	d.setMonth(d.getMonth() - PREAVIS_MOIS);
	return d;
}

export function contratUrgence(dateFin: Date): 'preavis' | 'annee' | 'futur' {
	const now = new Date();
	const preavis = contratDatePreavis(dateFin);
	if (preavis <= now) return 'preavis';
	if (dateFin.getFullYear() === anneeCourante()) return 'annee';
	// Préavis dans l'année courante même si fin l'année suivante
	if (preavis.getFullYear() === anneeCourante()) return 'annee';
	return 'futur';
}

export function diagNextDate(dt: DiagType): Date | null {
	if (!dt.frequence || dt.non_applicable) return null;
	const match = dt.frequence.match(/(\d+)/);
	if (!match) return null;
	const freqAns = parseInt(match[1]);
	const lastRapport = dt.rapports.find((r) => r.date_rapport);
	if (!lastRapport || !lastRapport.date_rapport) return null;
	const d = new Date(lastRapport.date_rapport);
	d.setFullYear(d.getFullYear() + freqAns);
	return d;
}

export function diagUrgence(nextDate: Date): 'depasse' | 'annee' | 'futur' {
	const now = new Date();
	if (nextDate <= now) return 'depasse';
	if (nextDate.getFullYear() === anneeCourante()) return 'annee';
	return 'futur';
}

// ── Dérivations partagées (#453, 27/08/2026) ─────────────────────────────────
//
// Ces deux fonctions vivaient en `$:` dans `VueRenouvellements.svelte`. Le
// découpage de ce fichier en trois — les compteurs, la frise, les audits — les
// aurait fait recopier DEUX fois : le parent en a besoin pour ses compteurs,
// chaque enfant pour son tableau.
//
// ⚠️ Un découpage qui duplique n'est pas un découpage. Elles montent donc ici,
// avec le reste des calculs purs : lisibles et testables sans écran, comme le
// dit l'en-tête de ce module.

/** Un contrat enrichi de son échéance, de son préavis et de sa note. */
export interface ContratAvecEcheance extends ReportContrat {
	dateFin: Date | null;
	datePreavis: Date | null;
	urgence: 'preavis' | 'annee' | 'futur' | 'inconnu';
	reconduit: boolean;
	prestataireNom: string;
	noteMoy: number | null;
	nbNotations: number;
}

/**
 * Les contrats, enrichis et TRIÉS — la pire note d'abord, puis par date de fin.
 *
 * Le tri par note est délibéré et vient avant la date : un contrat mal noté qui
 * arrive à échéance est la décision la plus urgente à prendre, pas la plus
 * proche. Une note absente vaut 6, donc passe en dernier — jamais devant un
 * prestataire réellement mal noté.
 */
export function contratsAvecEcheance(
	contrats: ReportContrat[],
	prestataires: ReportPrestataire[],
	notes: Map<number, { moy: number; nb: number }>,
): ContratAvecEcheance[] {
	return contrats
		.map((c) => {
			const result = contratDateFin(c);
			const fin = result?.date ?? null;
			const reconduit = result?.reconduit ?? false;
			const preavis = fin ? contratDatePreavis(fin) : null;
			const urgence: 'preavis' | 'annee' | 'futur' | 'inconnu' = fin
				? contratUrgence(fin)
				: 'inconnu';
			const prest = prestataires.find((p) => p.id === c.prestataire_id);
			const noteInfo = notes.get(c.prestataire_id) ?? null;
			return {
				...c,
				dateFin: fin as Date | null,
				datePreavis: preavis,
				urgence,
				reconduit,
				prestataireNom: prest?.nom ?? `#${c.prestataire_id}`,
				noteMoy: noteInfo?.moy ?? (null as number | null),
				nbNotations: noteInfo?.nb ?? 0,
			};
		})
		.sort((a, b) => {
			//  Pire note en premier ; `null` = pas de note = en dernier.
			const noteA = a.noteMoy ?? 6;
			const noteB = b.noteMoy ?? 6;
			if (noteA !== noteB) return noteA - noteB;
			if (!a.dateFin && !b.dateFin) return 0;
			if (!a.dateFin) return 1;
			if (!b.dateFin) return -1;
			return a.dateFin.getTime() - b.dateFin.getTime();
		});
}

/** Un diagnostic enrichi de sa prochaine échéance. */
export interface DiagAvecEcheance extends DiagType {
	nextDate: Date | null;
	urgence: 'depasse' | 'annee' | 'futur' | 'inconnu';
	lastRapportDate: string | null;
	isPermanent: boolean;
}

/**
 * Les diagnostics APPLICABLES, enrichis et triés par prochaine échéance.
 *
 * ⚠️ Un diagnostic « permanent » n'a pas d'échéance : il est marqué comme tel
 * plutôt qu'écarté, sinon il disparaîtrait de l'écran sans que rien ne dise
 * pourquoi. Les non applicables, eux, sont bien exclus — c'est une décision de
 * la copropriété, pas une absence de donnée.
 */
export function diagnosticsAvecEcheance(types: DiagType[]): DiagAvecEcheance[] {
	return types
		.filter((dt) => !dt.non_applicable)
		.map((dt) => {
			const isPermanent = dt.frequence ? dt.frequence.toLowerCase().includes('permanent') : false;
			const next = isPermanent ? null : diagNextDate(dt);
			const urgence: 'depasse' | 'annee' | 'futur' | 'inconnu' = next
				? diagUrgence(next)
				: 'inconnu';
			const lastRapport = dt.rapports.find((r) => r.date_rapport);
			return {
				...dt,
				nextDate: next as Date | null,
				urgence,
				lastRapportDate: lastRapport?.date_rapport ?? null,
				isPermanent,
			};
		})
		.sort((a, b) => {
			if (!a.nextDate && !b.nextDate) return 0;
			if (!a.nextDate) return 1;
			if (!b.nextDate) return -1;
			return a.nextDate.getTime() - b.nextDate.getTime();
		});
}

/**
 * De quel ÉQUIPEMENT parle un contrat — une seule règle, pour tous les usages.
 *
 * 🔴 Il y en avait TROIS, et elles se contredisaient (signalé à l'écran le
 * 29/08/2026, sur deux symptômes qui n'avaient pas l'air liés) :
 *
 * | Endroit | Règle appliquée | Ce que ça donnait |
 * |---|---|---|
 * | Groupement des cartes | `prestataire.specialite ?? contrat.type_equipement` | un contrat **Syndic** rangé sous « Autre », le cabinet ayant gardé sa spécialité `autre` |
 * | Formulaire d'édition | `contrat.type_equipement`, brut | un contrat de **VMC** affiché « Autre » en édition, alors que sa carte disait VMC |
 * | Enregistrement | le contrat, sauf `autre` → la spécialité | la seule des trois qui était juste |
 *
 * ⚠️ **Le CONTRAT fait foi, le prestataire est un repli.** Un contrat dit ce
 * qu'il couvre ; une entreprise dit ce qu'elle sait faire. Quand l'utilisateur
 * range un contrat sous « Syndic », c'est une décision — la spécialité du
 * cabinet ne doit pas la recouvrir. Le groupement faisait l'inverse, si bien
 * qu'aucune correction du contrat ne pouvait se voir.
 *
 * ⚠️ Le repli reste utile : la plupart des contrats sont créés avec la valeur
 * par défaut `autre`, et la spécialité du prestataire est alors la meilleure
 * information disponible. Il ne s'applique QUE là — jamais par-dessus un choix.
 */
export function typeEquipementDuContrat(
	contrat: { type_equipement?: string | null; prestataire_id?: number | null },
	prestataires: { id: number; specialite?: string | null }[],
): string {
	const propre = contrat.type_equipement;
	if (propre && propre !== 'autre') return propre;
	const prest = prestataires.find((p) => p.id === contrat.prestataire_id);
	return prest?.specialite || propre || 'autre';
}
