/**
 * Le vocabulaire des prestataires et des contrats — **une seule fois**.
 *
 * ## Pourquoi ce module (20/08/2026)
 *
 * La table des types d'équipement vivait dans `prestataires/+page.svelte`, et
 * elle recopiait `TypeEquipement` côté serveur. Relevé du jour :
 *
 * | Écran | Ce qu'il montrait |
 * |---|---|
 * | Prestataires → Contrats | un libellé, pour **15** des **17** valeurs |
 * | Reporting → Prestataires | la valeur BRUTE : `chauffage_collectif` |
 * | Reporting → Renouvellements | la valeur BRUTE, **trois fois** |
 *
 * 🔴 Deux valeurs manquaient à la recopie — `assurance` et `syndic` — et elles
 * ne sont pas anodines : ce sont précisément les deux que la fiche de
 * copropriété DÉSIGNE (#553). Un contrat d'assurance s'affichait donc
 * « assurance », en minuscules, à côté de quinze libellés soignés.
 *
 * Et deux écrans sur trois n'affichaient aucun libellé du tout. Ce n'est pas une
 * faute d'inattention : c'est ce que produit une table qui vit dans UN écran —
 * les autres n'y ont pas accès, alors ils s'en passent.
 *
 * ## Ce que le garde-fou vérifie
 *
 * `api/tests/test_types_equipement.py` compare cette liste à `TypeEquipement`.
 * Il ne compare jamais deux copies l'une à l'autre : l'énumération du serveur
 * est **l'unique arbitre**. Même forme que `test_statuts_tickets.py` (#415), née
 * du même défaut — cinq listes, chacune cohérente avec elle-même, aucune juste.
 */
import { contientTousLesMots, replier } from '$lib/texte';
import { stripHtml } from '$lib/utils';
import type { ContactPrestataire, ContratEntretien, Prestataire } from '$lib/api';

/**  Un type d'équipement, tel que l'écran le nomme.
 *
 *   ⚠️ `val` doit correspondre EXACTEMENT à `TypeEquipement` côté serveur : c'est
 *   la valeur qui part dans la charge utile. Le libellé, lui, n'est lu que par
 *   des humains. */
export type TypeEquipementOption = { val: string; label: string };

/**  Les 18 types d'équipement, dans l'ordre de l'énumération serveur.
 *
 *   🔴 `assurance` et `syndic` ne sont pas des « équipements », et le nom de
 *   l'énumération est donc un peu court. Ce qu'elle classe réellement, c'est
 *   « de quoi parle ce contrat » — et un contrat d'assurance ou un mandat de
 *   syndic en relèvent. En créer une seconde pour deux valeurs aurait donné deux
 *   nomenclatures à tenir d'accord. */
export const EQUIPEMENTS: readonly TypeEquipementOption[] = [
	{ val: 'ascenseur', label: '\u{1F6D7} Ascenseur' },
	{ val: 'chauffage_collectif', label: '\u{1F525} Chauffage collectif' },
	{ val: 'eau', label: '\u{1F4A7} Eau' },
	{ val: 'electricite', label: '⚡ Électricité' },
	{ val: 'espaces_verts', label: '\u{1F33F} Espaces verts' },
	{ val: 'extincteurs', label: '\u{1F9EF} Extincteurs' },
	{ val: 'interphone_digicode', label: '\u{1F4DE} Interphone/Digicode' },
	{ val: 'menuiseries', label: '\u{1FA9F} Menuiseries' },
	{ val: 'nettoyage', label: '\u{1F9F9} Nettoyage' },
	{ val: 'plomberie', label: '\u{1F6BF} Plomberie' },
	{ val: 'pompe', label: '⚙️ Pompe' },
	{ val: 'porte_parking', label: '\u{1F697} Porte parking' },
	{ val: 'serrurerie', label: '\u{1F511} Serrurerie' },
	{ val: 'toiture', label: '\u{1F3E0} Toiture' },
	{ val: 'vmc', label: '\u{1F4A8} VMC' },
	{ val: 'assurance', label: '\u{1F6E1}\u{FE0F} Assurance' },
	{ val: 'syndic', label: '\u{1F4BC} Syndic' },
	{ val: 'autre', label: '\u{1F527} Autre' },
];

/**  Ce qui classe un CONTRAT sans être un équipement sur lequel on intervient.
 *   Même liste côté serveur : `utils/intervenant.HORS_EQUIPEMENT`
 *   (`test_types_equipement.py` les compare). */
export const HORS_EQUIPEMENT: readonly string[] = ['assurance', 'syndic'];

/**  Les équipements qu'une AFFAIRE peut désigner (#1097) : la table des
 *   contrats, moins ce qui n'est pas un équipement. Dérivée, jamais recopiée. */
export const EQUIPEMENTS_AFFAIRE: readonly TypeEquipementOption[] = EQUIPEMENTS.filter(
	(e) => !HORS_EQUIPEMENT.includes(e.val),
);

/**
 *  Un contact RENSEIGNÉ : au moins une de ses valeurs est saisie. Les contacts
 *  sont FACULTATIFS depuis le 25/09/2026 (#1327) — `contactJoignable`, qui
 *  exigeait un nom et un moyen de joindre (#1229), est retiré avec la règle.
 *  Un contact vide ne part pas : il n'est qu'une ligne de saisie restée blanche.
 */
export function contactRenseigne(c: Record<string, string | null | undefined>): boolean {
	return Object.values(c).some((v) => v?.trim());
}

/**  Une ligne de contact telle que le formulaire d'une fiche la saisit.
 *   ⚠️ `type` et non `interface` : seul un type littéral est assignable au
 *   `Record<string, …>` de `contactsAEnvoyer` et `contactRenseigne`. */
export type ContactSaisi = {
	telephone: string;
	prenom: string;
	nom: string;
	fonction: string;
	email: string;
};

/**  Une ligne de contact vide. Elle était écrite cinq fois — quatre dans la page
 *   des prestataires, une dans `ChampsPrestataire` : un champ ajouté au contact
 *   aurait dû l'être aux cinq endroits (#779, 01/10/2026). */
export function contactVide(): ContactSaisi {
	return { telephone: '', prenom: '', nom: '', fonction: '', email: '' };
}

/**  Les contacts d'une fiche, prêts à corriger : les siens ; à défaut, un par
 *   numéro de l'ancien champ `telephone` (« 01…,06… ») ; à défaut, une ligne
 *   vide — la saisie en propose toujours au moins une. */
export function contactsDepuis(
	p: Partial<Pick<Prestataire, 'contacts' | 'telephone'>> = {},
): ContactSaisi[] {
	const contacts: ContactSaisi[] = p.contacts?.length
		? p.contacts.map((c: ContactPrestataire) => ({
				telephone: c.telephone ?? '',
				prenom: c.prenom ?? '',
				nom: c.nom ?? '',
				fonction: c.fonction ?? '',
				email: c.email ?? '',
			}))
		: String(p.telephone ?? '')
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean)
				.map((telephone) => ({ ...contactVide(), telephone }));
	return contacts.length ? contacts : [contactVide()];
}

/**
 *  Ce qui part à l'enregistrement d'une fiche : tout contact renseigné — il ne
 *  partait qu'avec un TÉLÉPHONE, et un contact joignable par e-mail seul
 *  disparaissait en silence (#1229) —, et le téléphone de la fiche, composé des
 *  seuls numéros saisis.
 */
export function contactsAEnvoyer<C extends Record<string, string | null | undefined>>(
	saisis: C[],
): { contacts: C[]; telephone: string | null } {
	const contacts = saisis.filter(contactRenseigne);
	const numeros = contacts.map((c) => c.telephone?.trim()).filter(Boolean);
	return { contacts, telephone: numeros.join(',') || null };
}

/**  Le libellé d'un type d'équipement.
 *
 *   ⚠️ Le repli rend la valeur BRUTE plutôt qu'un tiret : une valeur inconnue
 *   signale une divergence avec le serveur, et l'afficher telle quelle la rend
 *   visible. Un `—` la masquerait, et le garde-fou étant côté tests, l'écran
 *   serait le seul endroit où elle pourrait encore se voir. */
export function equipLabel(val: string | null | undefined): string {
	if (!val) return '—';
	return EQUIPEMENTS.find((e) => e.val === val)?.label ?? val;
}

/**  Les catégories de prestataire, telles que l'écran les propose.
 *
 *   ⚠️ Même contrainte que ci-dessus : `val` correspond à `TypePrestataire`.
 *
 *   🔴 Une catégorie dit le MÉTIER de l'entreprise, jamais le cadre d'une
 *   intervention (#1444, 28/09/2026). « Contrat récurrent » et « Dépannage »
 *   en étaient deux, et Otis — qui entretient sous contrat ET dépanne hors
 *   contrat — ne tenait dans aucune. « Sous contrat » se DÉDUIT des contrats de
 *   la fiche (`FILTRES_CONTRAT`, pastille de `CartePrestataire`). */
export const TYPES_PRESTATAIRE: readonly { val: string; label: string; desc: string }[] = [
	//  🔧 et non 📍 (#1045) : 📍 désigne un LIEU physique (CLAUDE.md, règle 4), et
	//  un dépannage n'en est pas un. `lint:pictogrammes` le refuse désormais.
	{
		val: 'maintenance_depannage',
		label: '\u{1F527} Maintenance & dépannage',
		desc: 'Entretien, réparations',
	},
	{ val: 'travaux', label: '\u{1F3D7}\u{FE0F} Travaux', desc: 'Interventions importantes' },
	{ val: 'reglementaire', label: '\u{1F4CB} Réglementaire', desc: 'Contrôles obligatoires' },
	{
		val: 'etudes_expertise',
		label: '\u{1F4D0} Études & expertise',
		desc: 'Diagnostics, maîtrise d’œuvre',
	},
	{ val: 'gestion', label: '\u{1F3E2} Gestion', desc: 'Syndic, gestion locative' },
];

/**  Le libellé d'une catégorie de prestataire — la valeur brute en repli, pour
 *   la même raison qu'`equipLabel` : une valeur inconnue signale une divergence
 *   avec le serveur. Le reporting affichait la valeur brute en toute occasion
 *   (`contrat_recurrent`), et la page en avait sa propre copie (#1444). */
export function typePrestataireLabel(val: string | null | undefined): string {
	if (!val) return '—';
	return TYPES_PRESTATAIRE.find((t) => t.val === val)?.label ?? val;
}

/**  Les contrats sous lesquels un prestataire peut intervenir (#1445) : les
 *   siens, en cours, et qui portent sur un ÉQUIPEMENT — une assurance ou un
 *   mandat de syndic ne cadrent pas une intervention. Même règle au serveur :
 *   `utils/intervenant.contrat_valide`. */
export function contratsDuPrestataire<
	C extends { prestataire_id?: number | null; type_equipement?: string | null },
>(contrats: C[], prestataireId: number | null): C[] {
	if (prestataireId === null) return [];
	return contrats.filter(
		(c) => c.prestataire_id === prestataireId && !HORS_EQUIPEMENT.includes(c.type_equipement ?? ''),
	);
}

/**  Un contrat tel que les formulaires d'affaire le chargent — pour proposer
 *   l'intervenant (#1097) et le cadre de son intervention (#1445). */
export interface ContratEnCours {
	id: number;
	prestataire_id: number;
	libelle: string;
	actif?: boolean;
	type_equipement?: string | null;
	frequence_type?: string | null;
	frequence_valeur?: number | null;
}

/**  Le contrat dont un formulaire d'affaire lit le rythme (#1445) : celui de
 *   la liste chargée, à défaut celui que le serveur a joint à l'affaire —
 *   un contrat archivé depuis n'est plus dans la liste. `null` hors contrat. */
export function contratDeLaSaisie<C>(
	contrats: (C & { id: number })[],
	contratId: number | null,
	joint: C | null | undefined,
): C | null {
	if (contratId === null) return null;
	return contrats.find((c) => c.id === contratId) ?? joint ?? null;
}

/**  Le filtre « sous contrat » de l'annuaire. Il ne se SAISIT pas : il se lit
 *   sur les contrats actifs de la fiche (#1444) — le cadre d'une intervention
 *   n'est pas une catégorie de l'entreprise. */
export const FILTRES_CONTRAT: readonly { val: string; label: string }[] = [
	{ val: 'sous_contrat', label: '\u{1F4C4} Sous contrat' },
	{ val: 'sans_contrat', label: 'Sans contrat' },
];

/**  Les filtres de l'annuaire — une chaîne vide : pas de filtre.
 *
 *   🔴 Le filtre par ÉQUIPEMENT a cédé la place à la recherche libre le
 *   28/09/2026 (demandé à l'écran) : douze pastilles sur une rangée qui défilait,
 *   pour une information que la recherche trouve aussi — « ascenseur » retrouve
 *   le prestataire dont c'est l'équipement (`texteCherchable`). */
export interface FiltresPrestataires {
	type: string;
	contrat: string;
	recherche: string;
}

export function filtresVides(): FiltresPrestataires {
	return { type: '', contrat: '', recherche: '' };
}

/**  Un filtre au moins est-il posé ? — « Aucun prestataire pour ces critères ». */
export function filtresActifs(f: FiltresPrestataires): boolean {
	return !!(f.type || f.contrat || f.recherche.trim());
}

/**  Ce qu'on cherche d'un prestataire : tout ce que sa carte montre — nom,
 *   catégorie, équipement, coordonnées, contacts, description —, déplié par
 *   `replier` (sans accents ni casse).
 *
 *   ⚠️ La règle vit ICI et non au serveur, à la différence des affaires :
 *   l'annuaire est chargé en entier et n'a ni suites ni messages à lire. Elle
 *   ne cherche donc que dans ce que l'écran a déjà reçu. */
export interface PrestataireCherchable {
	nom?: string | null;
	specialite?: string | null;
	type_prestataire?: string | null;
	telephone?: string | null;
	email?: string | null;
	adresse?: string | null;
	description?: string | null;
	contacts?:
		| {
				prenom?: string | null;
				nom?: string | null;
				fonction?: string | null;
				telephone?: string | null;
				email?: string | null;
		  }[]
		| null;
}

export function texteCherchable(p: PrestataireCherchable): string {
	const morceaux = [
		p.nom,
		p.specialite ? equipLabel(p.specialite) : '',
		p.type_prestataire ? typePrestataireLabel(p.type_prestataire) : '',
		p.telephone,
		p.email,
		p.adresse,
		p.description ? stripHtml(p.description) : '',
		...(p.contacts ?? []).flatMap((c) => [c.prenom, c.nom, c.fonction, c.telephone, c.email]),
	];
	return replier(morceaux.filter(Boolean).join(' '));
}

/**  Tous les mots, n'importe où — `contientTousLesMots` (`$lib/texte`), appliqué
 *   à une fiche. Une recherche vide laisse tout passer. */
export function correspondRecherche(p: PrestataireCherchable, recherche: string): boolean {
	return contientTousLesMots(texteCherchable(p), recherche);
}

/**  Les prestataires qui passent les filtres. « Sous contrat » se lit sur les
 *   CONTRATS (actifs : l'API n'en sert pas d'autres), jamais sur la fiche. */
export function filtrerPrestataires<
	P extends PrestataireCherchable & { id: number; type_prestataire?: string | null },
>(prestataires: P[], contrats: { prestataire_id: number }[], f: FiltresPrestataires): P[] {
	const sousContrat = new Set(contrats.map((c) => c.prestataire_id));
	return prestataires.filter(
		(p) =>
			(!f.type || p.type_prestataire === f.type) &&
			(!f.contrat || (f.contrat === 'sous_contrat') === sousContrat.has(p.id)) &&
			correspondRecherche(p, f.recherche),
	);
}

/**  Les unités de fréquence — celles du contrat, qui fixe le rythme d'un
 *   prestataire (#1092, 23/09/2026). `nombre` : le libellé du nombre à saisir,
 *   absent quand il n'y en a pas (« mensuelle »). Lues par `ChampFrequence`,
 *   et côté serveur par `utils/intervenant.FREQUENCES` — mêmes valeurs. */
export const FREQUENCES: readonly { val: string; label: string; nombre?: string }[] = [
	{ val: 'semaines', label: 'Toutes les X semaines', nombre: 'Toutes les … sem.' },
	{ val: 'mois', label: 'Mensuelle' },
	{ val: 'fois_par_an', label: 'X fois par an', nombre: '… fois/an' },
	{ val: 'ans', label: 'Tous les X ans', nombre: 'Tous les … ans' },
];

/**  L'intervenant d'une affaire, tel que la fiche l'affiche : « Otis · ↺ Mensuel ».
 *   Vide sans intervenant — la ligne ne s'affiche pas (#1092, lot 5).
 *
 *   Sous contrat (#1445), le rythme est celui du contrat, et le cadre se dit :
 *   « Otis · ↺ Mensuel · sous contrat n° C-42 » — le numéro pour le conseil
 *   seul, que le serveur ne sert qu'à lui. */
export function intervenantAffiche(t: {
	prestataire_nom?: string | null;
	frequence_type?: string | null;
	frequence_valeur?: number | null;
	contrat?:
		| ({ numero_contrat?: string | null; libelle?: string | null } & Parameters<
				typeof frequenceLabel
		  >[0])
		| null;
}): string {
	if (!t.prestataire_nom) return '';
	const rythme = frequenceLabel(t.contrat ?? t);
	return [t.prestataire_nom, rythme, t.contrat ? cadreSousContrat(t.contrat) : '']
		.filter(Boolean)
		.join(' · ');
}

/**  « sous contrat n° C-42 », « sous contrat « Ascenseur » », ou « sous contrat »
 *   quand le lecteur n'a ni l'un ni l'autre. Même forme qu'au carnet
 *   (`carnet_entretien.cadre_intervention`). */
export function cadreSousContrat(c: {
	numero_contrat?: string | null;
	libelle?: string | null;
}): string {
	if (c.numero_contrat) return `sous contrat n° ${c.numero_contrat}`;
	return c.libelle ? `sous contrat « ${c.libelle} »` : 'sous contrat';
}

/**  La fréquence d'un contrat, en une expression courte.
 *
 *   Rend une chaîne vide quand aucune fréquence n'est définie : l'appelant
 *   n'affiche alors pas de pastille, plutôt qu'une pastille vide. */
export function frequenceLabel(c: {
	frequence_type?: string | null;
	frequence_valeur?: number | null;
}): string {
	const n = c.frequence_valeur ?? 0;
	if (c.frequence_type === 'semaines') return `↺ ${n} sem.`;
	if (c.frequence_type === 'mois') return '↺ Mensuel';
	if (c.frequence_type === 'fois_par_an') return `↺ ${n}×/an`;
	if (c.frequence_type === 'ans') return `↺ tous les ${n} an${n > 1 ? 's' : ''}`;
	return '';
}

/**
 * **La forme du formulaire d'un contrat** — vierge, ou repris d'un existant.
 *
 * ## 🔴 Pourquoi ici (15/09/2026)
 *
 * Les **treize mêmes clés** étaient énumérées **trois fois** dans
 * `prestataires/+page.svelte` : la déclaration, `resetContratForm()` et
 * `startEditContrat()`. Ce n'est pas trois fois la même ligne, c'est trois fois
 * la même **structure** — et ajouter un champ demandait de le poser aux trois
 * endroits.
 *
 * ⚠️ Un champ posé sur deux des trois donne un formulaire qui enregistre à la
 * création et oublie à l'édition — ou l'inverse, selon l'endroit manqué. Et
 * **en silence** : une clé absente d'un objet JavaScript ne lève rien.
 *
 * C'est le même défaut que le calendrier portait le matin même, avec deux
 * écritures au lieu de trois (`$lib/evenement-formulaire`).
 */
export interface FormulaireContratData {
	copropriete_id: number;
	/**  Le PÉRIMÈTRE remplace `batiment_id`, qui n'était rempli par aucun champ
	 *   (10/09/2026). Le serveur en dérive le bâtiment. */
	perimetre_cible: string[];
	prestataire_id: string;
	type_equipement: string;
	libelle: string;
	numero_contrat: string;
	date_debut: string;
	duree_initiale_valeur: string | number;
	duree_initiale_unite: string;
	frequence_type: string;
	frequence_valeur: string | number;
	prochaine_visite: string;
	notes: string;
}

/**
 * Un formulaire de contrat VIERGE.
 *
 * :param perimetreDefaut: la liste par défaut, passée par l'appelant — elle vient
 *   de l'arborescence administrée (`$lib/perimetres`), que ce module n'a pas à
 *   connaître.
 */
export function contratVierge(perimetreDefaut: string[]): FormulaireContratData {
	return {
		copropriete_id: 1,
		perimetre_cible: perimetreDefaut,
		prestataire_id: '',
		type_equipement: 'autre',
		libelle: '',
		numero_contrat: '',
		//  La date du jour : un contrat se saisit le jour où on le reçoit, et
		//  corriger une date pré-remplie coûte moins que la saisir.
		date_debut: new Date().toISOString().slice(0, 10),
		duree_initiale_valeur: '',
		duree_initiale_unite: 'mois',
		frequence_type: '',
		frequence_valeur: '',
		prochaine_visite: '',
		notes: '',
	};
}

/**
 * Le formulaire d'un contrat EXISTANT, pour le corriger.
 *
 * :param typeEquipement: résolu par l'appelant, qui seul a la liste des
 *   prestataires sous la main — le type se déduit du prestataire quand le
 *   contrat ne le porte pas.
 */
export function contratDepuis(
	c: ContratEntretien,
	perimetreDefaut: string[],
	typeEquipement: string,
): FormulaireContratData {
	return {
		copropriete_id: c.copropriete_id,
		//  ⚠️ Une liste VIDE retombe sur le défaut : un contrat sans périmètre
		//  enregistré ne doit pas ouvrir le formulaire sur une rangée muette.
		perimetre_cible: c.perimetre_cible?.length ? c.perimetre_cible : perimetreDefaut,
		prestataire_id: String(c.prestataire_id ?? ''),
		type_equipement: typeEquipement,
		libelle: c.libelle,
		numero_contrat: c.numero_contrat ?? '',
		date_debut: c.date_debut,
		duree_initiale_valeur: c.duree_initiale_valeur ?? '',
		duree_initiale_unite: c.duree_initiale_unite ?? 'mois',
		frequence_type: c.frequence_type ?? '',
		frequence_valeur: c.frequence_valeur ?? '',
		prochaine_visite: c.prochaine_visite ?? '',
		notes: c.notes ?? '',
	};
}

/**
 * La FICHE d'un prestataire, vierge ou d'après un prestataire existant.
 *
 * Écrite à la façon de `contratVierge` / `contratDepuis` : l'objet vide était
 * recopié deux fois dans la page, et la correction énumérait ses champs à part —
 * l'adresse et la description (#1327) auraient dû s'ajouter aux trois endroits.
 */
export function prestataireDepuis(p: Partial<Prestataire> = {}) {
	return {
		nom: p.nom ?? '',
		specialite: p.specialite ?? '',
		type_prestataire: p.type_prestataire ?? 'maintenance_depannage',
		email: p.email ?? '',
		adresse: p.adresse ?? '',
		description: p.description ?? '',
		//  Jamais relue du serveur : la marque ne s'écrit que si l'assistant
		//  sert pendant CETTE saisie (`marquer`, sens unique).
		assiste_ia: false,
	};
}

/** L'état du formulaire d'un prestataire, tel que `prestataireDepuis` le rend. */
export type FormulairePrestataire = ReturnType<typeof prestataireDepuis>;
