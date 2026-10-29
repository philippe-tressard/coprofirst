/**
 * Pré-remplissage du kanban à partir des prestataires — la DÉCISION, isolée.
 *
 * 🔴 Depuis le 23/09/2026 (#1193), elle pose des **affaires Entretien** « Chez
 * le prestataire » (`POST /tickets/lot`) : les événements du calendrier sont
 * devenus des affaires au lot 5b2 de #1092, et le bouton avait disparu avec eux.
 * Les sources sont les contrats et les affaires Entretien récurrentes ; la clé
 * anti-doublon lit les TITRES des affaires de l'exercice.
 *
 * 🆕 Depuis le 28/09/2026 (#1445), la visite d'un contrat PART AVEC SON
 * CONTRAT (`contrat_id`) : l'affaire dit qu'elle est sous contrat, et le
 * serveur lit alors le rythme sur lui. Elle ne porte donc plus de fréquence
 * propre — et ne redevient pas une source l'année suivante
 * (`sourcesDesAffaires` ne retient que les affaires récurrentes), ce qui
 * évitait déjà le double compte par le titre.
 *
 * Extrait de `calendrier/+page.svelte` le 28/08/2026 (#605), pour trois raisons
 * qui vont ensemble :
 *
 *   1. **Deux boucles quasi identiques** y construisaient les mêmes événements à
 *      partir de deux sources — les contrats d'entretien et les événements de
 *      maintenance existants. Elles avaient déjà divergé : l'une calculait le
 *      périmètre du bâtiment, l'autre posait `perimetre: ev.perimetre ?? ''`,
 *      c'est-à-dire **une chaîne vide** quand la source n'en portait pas. Une
 *      seule fonction, deux appels : la divergence n'a plus où se loger.
 *   2. **Rien ne l'éprouvait.** `annualFreq` et `spreadMonth` sont des fonctions
 *      pures dont une erreur produit des cartes au mauvais mois — ce qui ne se
 *      voit qu'en regardant le kanban, donc jamais.
 *   3. La page est à 848 lignes, au-dessus du seuil de modularité : la règle est
 *      « on découpe QUAND on y touche ».
 *
 * « Pur » veut dire ici : aucun appel réseau, aucune lecture de store, aucun
 * effet. L'appelant résout le périmètre (qui dépend de données chargées) et
 * passe une source déjà normalisée. Éprouvé par
 * `node scripts/check-init-prestataires.mjs --selftest`.
 */

/**
 * Au-delà, on ne pré-remplit pas : une maintenance mensuelle ferait douze cartes
 * dans une colonne qui en compte déjà.
 *
 * ⚠️ Ce plafond était **muet** jusqu'au 28/08/2026 : une source trop fréquente
 * disparaissait sans être comptée ni nommée, et le message final annonçait
 * « aucune source éligible » — ce qui se lit comme « il n'y a rien », alors que
 * la vérité est « il y a quelque chose, et je l'ai écarté ». `planifier` les
 * rend désormais dans `horsPlafond`.
 */
export const OCCURRENCES_MAX_AN = 4;

/** Une source de pré-remplissage, déjà normalisée par l'appelant. */
export interface SourceRecurrente {
	/** Le libellé SANS numéro d'occurrence — il est ajouté ici. */
	titre: string;
	frequence_type: string | null;
	frequence_valeur: number | null;
	prestataire_id: number | null;
	/**  Le contrat d'où vient cette visite, quand il y en a un (#605, point 2).
	 *   `null` pour une source qui est un événement de maintenance saisi à la main. */
	contrat_id: number | null;
	/** Déjà résolu par l'appelant : le calcul dépend de données chargées. */
	perimetre: string;
	description: string | null;
}

export interface VisitePlanifiee {
	titre: string;
	/** Le code de périmètre de la source — `''` quand elle n'en a pas. */
	perimetre: string;
	prestataire_id: number | null;
	/** La source, quand la visite vient d'un contrat — pour le compte rendu. */
	contrat_id: number | null;
	debut: string;
	description: string | null;
	/** La récurrence de la source : l'affaire Entretien la porte (#1092). */
	frequence_type: string | null;
	frequence_valeur: number | null;
}

/** Ce que `POST /tickets/lot` reçoit pour une visite — rien d'autre, aucun canal. */
export function versAffaire(v: VisitePlanifiee) {
	return {
		titre: v.titre,
		description: v.description,
		debut: v.debut,
		perimetre_cible: v.perimetre ? [v.perimetre] : [],
		prestataire_id: v.prestataire_id,
		contrat_id: v.contrat_id,
		frequence_type: v.frequence_type,
		frequence_valeur: v.frequence_valeur,
	};
}

export interface Plan {
	aCreer: VisitePlanifiee[];
	/** Combien existaient déjà — ce qui n'est PAS une erreur, mais se dit. */
	ignores: number;
	/** Les sources écartées faute de tenir sous le plafond, avec leur fréquence. */
	horsPlafond: { titre: string; parAn: number }[];
	/** Les sources sans fréquence exploitable : elles ne se pré-remplissent pas. */
	sansFrequence: number;
	/**  Les contrats ÉCHUS, écartés avant même d'être des sources (#605, point 1).
	 *
	 *   Comptés ici pour la même raison que `horsPlafond` : une décision qui
	 *   écarte silencieusement se lit comme une absence de matière. « Aucune
	 *   source » et « j'en ai écarté trois » ne veulent pas dire la même chose. */
	echus: number;
}

/**
 * Le nombre de passages par an, ou `0` si la fréquence n'est pas exploitable.
 *
 * ⚠️ Le cas zéro est explicite : une valeur nulle ou négative donnerait
 * `12 / 0 = Infinity`, qui passe le test « > 0 » et ne serait écarté que par
 * hasard, au plafond. Un garde qui tient par accident tient jusqu'au jour où le
 * plafond bouge.
 */
export function frequenceAnnuelle(type: string | null, valeur: number | null): number {
	if (!type || !valeur || valeur <= 0) return 0;
	if (type === 'fois_par_an') return valeur;
	if (type === 'mois') return Math.floor(12 / valeur);
	if (type === 'semaines') return Math.floor(52 / valeur);
	return 0;
}

/** Le mois (1-12) de la `index`-ième occurrence sur `total` dans l'année. */
export function moisOccurrence(total: number, index: number): number {
	if (total <= 0) return 1;
	return 1 + index * Math.floor(12 / total);
}

/**
 * Le titre d'une occurrence — numéroté **à partir de deux**.
 *
 * Une visite annuelle unique ne porte pas de « (1/1) » : un numéro qui ne
 * distingue rien ajoute du bruit à toutes les cartes pour n'en séparer aucune.
 * À partir de deux, quatre cartes « Otis — Ascenseur A » devenaient
 * indiscernables dans la colonne, sauf à ouvrir chacune pour lire sa date.
 */
export function titreOccurrence(base: string, index: number, total: number): string {
	return total >= 2 ? `${base} (${index + 1}/${total})` : base;
}

/**
 * Le titre débarrassé de son numéro d'occurrence.
 *
 * 🔴 C'est ce qui rend le numéro rétro-compatible, et ce n'est pas un détail :
 * la détection des doublons rapproche les candidats des événements DÉJÀ créés,
 * par leur titre. Sans cette normalisation, l'arrivée du numéro aurait fait
 * échouer toutes les correspondances d'un coup — et le premier clic après la
 * mise en production aurait **recréé l'intégralité de l'exercice en double**.
 *
 * ⚠️ Un libellé de contrat qui se terminerait vraiment par « (1/2) » verrait son
 * suffixe retiré ici. La conséquence est bornée : deux titres partageraient une
 * clé de doublon. C'est assumé — l'inverse (ne rien normaliser) casse un cas
 * certain pour protéger un cas improbable.
 */
export function titreBase(titre: string): string {
	return titre.replace(/\s*\(\d+\/\d+\)\s*$/, '');
}

/**
 * La clé qui dit « cette occurrence existe déjà » : titre de base + mois.
 *
 * ⚠️ Elle est **fragile** : elle repose sur une chaîne d'affichage, que renommer
 * un contrat ou son prestataire fait perdre — le clic suivant recréerait les
 * visites de ce contrat. Une clé par source (`contrat:N#i`) l'a doublée du
 * 01/09 au 23/09/2026 ; une affaire ne portant pas de contrat, elle n'avait
 * plus rien à relire (#1193). Renommer un contrat en cours d'exercice demande
 * donc de retirer à la main les visites en double.
 */
export function clePlanifiee(titre: string, mois: number): string {
	return `${titreBase(titre)}||${mois}`;
}

/** Une affaire déjà posée, telle que l'API la rend — seuls ces champs comptent. */
export interface VisiteExistante {
	titre: string;
	/** Absent d'une affaire sans date : lu par un test de vérité, comme `null`. */
	debut?: string | null;
	categorie?: string;
}

/**
 * Les clés des visites DÉJÀ posées pour un exercice : titre de base + mois.
 *
 * 🔴 C'est elle qui décide si le clic recrée ou non l'exercice entier. Une
 * affaire Entretien de l'exercice compte, **archivée comprise** : une visite
 * faite et close reste faite — l'ancien filtre sur les événements archivés ne
 * se transpose pas.
 */
export function clesDesAffaires(affaires: VisiteExistante[], exercice: number): Set<string> {
	return new Set(
		affaires
			.filter(
				(a) =>
					a.categorie === 'entretien' && !!a.debut && new Date(a.debut).getFullYear() === exercice,
			)
			.map((a) => clePlanifiee(a.titre, new Date(a.debut as string).getMonth())),
	);
}

/**
 * Le plan de pré-remplissage : ce qui serait créé, ce qui existe, ce qui est
 * écarté et pourquoi. **Ne crée rien** — c'est l'appelant qui écrit.
 *
 * @param sources      les sources normalisées, contrats et événements confondus
 * @param clesExistantes les clés (`clePlanifiee`) déjà présentes pour l'exercice
 * @param exercice     l'année visée
 */
/**  Ce que la page sait et que ce module ne peut pas savoir : le nom d'un
 *   prestataire, et le périmètre d'un bâtiment. Les deux dépendent de données
 *   chargées par l'écran.
 *
 *   Un objet de rappels plutôt que les données elles-mêmes : passer la liste des
 *   prestataires et l'arbre des périmètres obligerait ce module à connaître leurs
 *   structures, et à recopier `perimetreDuBatiment` — qui vit ailleurs et sert
 *   déjà à d'autres écrans. */
export interface ContexteSources {
	nomPrestataire: (id: number | null | undefined) => string;
	perimetreDuBatiment: (id: number | null | undefined) => string;
}

/**  Un contrat tel que `GET /prestataires/contrats` le rend — les seuls champs lus.
 *
 *   `echu` est **dérivé par le serveur** (`utils/echeance_contrat.py`), jamais
 *   saisi : date de début + durée initiale, reportée d'un an tant qu'elle est
 *   passée. Le refaire ici en ferait une seconde règle. */
export interface ContratSource {
	id: number;
	libelle: string;
	prestataire_id: number | null;
	batiment_id: number | null;
	frequence_type: string | null;
	frequence_valeur: number | null;
	notes: string | null;
	echu: boolean;
}

/**  Une affaire Entretien récurrente — l'autre source, qui remplace les
 *   événements de maintenance saisis à la main (#1193). */
export interface AffaireSource {
	titre: string;
	categorie: string;
	/** Les champs facultatifs sont lus par un test de vérité ou `?? null` : absents
	 *  d'un `Ticket`, ils s'y lisent comme `null`. */
	prestataire_id?: number | null;
	perimetre_cible?: string[] | null;
	frequence_type?: string | null;
	frequence_valeur?: number | null;
	description?: string | null;
	archivee?: boolean;
}

/**
 * Les contrats, normalisés en sources — **et les échus écartés, comptés**.
 *
 * ## 🔴 Pourquoi cette fonction existe (#605, points 1 et 4)
 *
 * Ces vingt lignes vivaient dans `calendrier/+page.svelte`, où **rien ne les
 * éprouvait** — c'est le point 4 du ticket, qui reprochait exactement cela aux
 * fonctions de calcul avant leur extraction. Le filtre `echu` y a été ajouté sans
 * qu'aucun test ne puisse dire s'il écarte ce qu'il faut, ni s'il écarte trop.
 *
 * ⚠️ **`echu` est FAUX sous reconduction tacite, et c'est voulu.** Un contrat
 * d'entretien qu'on n'a pas dénoncé COURT : il doit continuer à générer ses
 * visites. Le seul geste qui l'arrête est l'archivage (`actif = false`), que
 * l'API filtre déjà en amont. `echu` ne vaut donc que pour les contrats **sans**
 * reconduction tacite — le mandat de syndic, aujourd'hui —, dont le terme ne
 * bouge pas et dont le dépassement dit que la copropriété doit voter.
 *
 * C'est la réponse à la question posée le 28/08/2026 (*« un prestataire non
 * renouvelé est-il écarté ? »*), et elle tient en une phrase : **oui s'il est
 * archivé ou si son type ne se reconduit pas ; non s'il se reconduit tacitement,
 * parce qu'alors il n'est pas expiré.**
 */
export function sourcesDesContrats(
	contrats: ContratSource[],
	ctx: ContexteSources,
): { sources: SourceRecurrente[]; echus: number } {
	const sources: SourceRecurrente[] = [];
	let echus = 0;
	for (const c of contrats) {
		if (c.echu) {
			echus++;
			continue;
		}
		sources.push({
			titre: `${ctx.nomPrestataire(c.prestataire_id)} — ${c.libelle}`,
			frequence_type: c.frequence_type ?? null,
			frequence_valeur: c.frequence_valeur ?? null,
			prestataire_id: c.prestataire_id ?? null,
			contrat_id: c.id,
			perimetre: ctx.perimetreDuBatiment(c.batiment_id),
			description: c.notes ?? null,
		});
	}
	return { sources, echus };
}

/**
 * Les affaires Entretien récurrentes, normalisées en sources.
 *
 * ⚠️ Les visites que ce module a lui-même posées portent la récurrence de leur
 * source, et sont donc des affaires Entretien récurrentes : sans le filtre sur
 * `dejaSources` (les titres des contrats), chaque contrat compterait deux fois
 * dès la deuxième année. Un même titre ne fait qu'une source.
 */
export function sourcesDesAffaires(
	affaires: AffaireSource[],
	dejaSources: Set<string>,
): SourceRecurrente[] {
	const vues = new Set(dejaSources);
	const sources: SourceRecurrente[] = [];
	for (const a of affaires) {
		const titre = titreBase(a.titre);
		if (a.categorie !== 'entretien' || !a.prestataire_id || !a.frequence_type) continue;
		if (a.archivee || vues.has(titre)) continue;
		vues.add(titre);
		sources.push({
			titre,
			frequence_type: a.frequence_type,
			frequence_valeur: a.frequence_valeur ?? null,
			prestataire_id: a.prestataire_id,
			contrat_id: null,
			perimetre: a.perimetre_cible?.[0] ?? '',
			description: a.description ?? null,
		});
	}
	return sources;
}

export function planifier(
	sources: SourceRecurrente[],
	clesExistantes: Set<string>,
	exercice: number,
	echus = 0,
): Plan {
	const plan: Plan = { aCreer: [], ignores: 0, horsPlafond: [], sansFrequence: 0, echus };

	for (const source of sources) {
		const parAn = frequenceAnnuelle(source.frequence_type, source.frequence_valeur);
		if (parAn <= 0) {
			plan.sansFrequence++;
			continue;
		}
		if (parAn > OCCURRENCES_MAX_AN) {
			plan.horsPlafond.push({ titre: source.titre, parAn });
			continue;
		}
		for (let i = 0; i < parAn; i++) {
			const mois = moisOccurrence(parAn, i);
			//  La clé de titre se calcule sur le mois EN BASE 0, comme les affaires lues.
			const dejaLa = clesExistantes.has(clePlanifiee(source.titre, mois - 1));
			if (dejaLa) {
				plan.ignores++;
				continue;
			}
			plan.aCreer.push({
				titre: titreOccurrence(source.titre, i, parAn),
				perimetre: source.perimetre,
				prestataire_id: source.prestataire_id || null,
				contrat_id: source.contrat_id,
				debut: `${exercice}-${String(mois).padStart(2, '0')}-15T09:00`,
				description: source.description || null,
				frequence_type: source.frequence_type,
				frequence_valeur: source.frequence_valeur,
			});
		}
	}
	return plan;
}

/**
 * Le message qui rend compte du plan — y compris de ce qui a été ÉCARTÉ.
 *
 * Il vit ici et non dans la page parce que c'est la contrepartie du plafond :
 * une décision qui écarte silencieusement se lit comme une absence de matière.
 */
export function resumePlan(plan: Plan, exercice: number): string {
	const parts: string[] = [];
	if (plan.ignores > 0) parts.push(`${plan.ignores} existant(s) ignoré(s)`);
	if (plan.horsPlafond.length > 0) {
		const detail = plan.horsPlafond.map((h) => `${h.titre} (${h.parAn}/an)`).join(', ');
		parts.push(
			`${plan.horsPlafond.length} écarté(s) au-delà de ${OCCURRENCES_MAX_AN}/an : ${detail}`,
		);
	}
	if (plan.sansFrequence > 0) parts.push(`${plan.sansFrequence} sans fréquence exploitable`);
	if (plan.echus > 0) parts.push(`${plan.echus} contrat(s) échu(s) écarté(s)`);

	if (plan.aCreer.length === 0) {
		return parts.length === 0
			? `Aucune source de maintenance récurrente pour ${exercice}.`
			: `Rien à créer pour ${exercice} — ${parts.join(' · ')}.`;
	}
	const entete = `Créer ${plan.aCreer.length} visite(s) prestataire pour ${exercice} (affaires Entretien) ?`;
	return parts.length === 0 ? entete : `${entete}\n(${parts.join('\n')})`;
}
