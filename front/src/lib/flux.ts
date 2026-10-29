/**
 * Règles du fil d'activité — partagées par le tableau de bord et ses cartes.
 *
 * Tout ce qui décide de l'apparence ou du classement d'une ligne du fil vit ici,
 * et nulle part ailleurs. Les deux blocs de carte du fil (« récent » et
 * « ancien ») avaient dupliqué ces tables et ces helpers : chaque évolution
 * devait alors être écrite deux fois, et c'est ainsi qu'un bloc a fini par
 * afficher moins d'informations que l'autre.
 *
 * Le partage compte surtout pour les TROIS REGISTRES du fil (urgences /
 * épinglé / chronologie) : leurs filtres doivent rester mutuellement exclusifs.
 * Une seule fonction décide donc de chaque appartenance.
 */
import type { FluxItem } from '#lib/api/index.ts';
import { estTicketClos } from '#lib/tickets.ts';
import { equipLabel } from '#lib/prestataires.ts';
import { parAttribut } from '#lib/table-statuts.ts';
import { fmtDateLong } from '#lib/date.ts';
import type { ClasseGouttiere } from '#lib/gouttiere.ts';

// ── Apparence par type d'élément ──────────────────────────────────────────
//
// ⚠️ CES TROIS TABLES DOIVENT COUVRIR TOUS LES TYPES QUE L'API ÉMET.
//
// Elles n'en couvraient que dix pour quinze : `prestataire`, `document`,
// `diagnostic`, `faq` et `annuaire` — les cinq rubriques ajoutées au fil depuis —
// retombaient sur les valeurs par défaut, c'est-à-dire **gris de bordure sur fond
// gris**, illisible, avec le nom technique brut en guise de libellé
// (« PRESTATAIRE »). Signalé par l'utilisateur le 08/08/2026 ; personne ne
// l'avait vu parce qu'une pastille grise ressemble à une pastille.
// `api/tests/test_flux_apparence.py` échoue désormais si un type émis par le
// backend n'a pas ses trois entrées.
//
// CONTRASTE. Six des sept couleurs d'origine échouaient déjà au niveau AA
// (4.5:1) : l'ambre était à 2,07 et l'émeraude à 2,41 — le gris sur gris à 1,15
// n'était que le cas extrême. Les textes sont passés en teintes foncées (700/800)
// sur des fonds clairs (50) : les douze sont désormais entre 4,75 et 10,2.
//
// JETONS (#2174, S2). Couleurs et fonds se désignent par `var(--fil-…)` : la
// valeur vit dans `socle.css`, où le thème sombre la redéfinit. Le contraste se
// mesure donc sur la valeur RÉSOLUE (`api/tests/test_flux_apparence.py`).
//
// DIFFÉRENCIATION. Les onze teintes sont réparties sur la roue, écart minimal
// 17°. L'émeraude 163° a été libérée avec la rubrique « devis » ; elle était à
// 12° de la sarcelle de `prestataire`, un rapprochement voulu tant que les deux
// rubriques partageaient la page /prestataires.
/*  ── Les quatorze rubriques du fil, chacune écrite UNE fois ──────────────────
    Le libellé, la teinte et le fond vivaient dans trois tables parallèles de
    quatorze clés. Ajouter une rubrique demandait trois gestes, et l'oubli du
    troisième rendait une carte au fond blanc — lisible, donc invisible.

    🔴 L'ordre ci-dessous est celui de la ROUE CHROMATIQUE (0° → 295°), pas
    celui du produit : deux rubriques voisines dans le fil ne doivent pas se
    ressembler. Les degrés restent notés parce que c'est la seule chose qui
    permet d'insérer une quinzième teinte sans refaire le tour.                */
const {
	libelle: L,
	couleur: C,
	fond: F,
	icone: I,
	abrege: A,
} = parAttribut({
	ticket_resolu: {
		libelle: 'Affaire résolue',
		couleur: 'var(--fil-rouge)',
		fond: 'var(--fil-rouge-fond)',
		icone: 'circle-check',
		abrege: 'AFF.',
	}, //   0° rouge
	ticket_ouvert: {
		libelle: 'Affaire',
		couleur: 'var(--fil-rouge)',
		fond: 'var(--fil-rouge-fond)',
		icone: 'wrench',
		abrege: 'AFF.',
	},
	ticket_mis_a_jour: {
		libelle: 'Affaire mise à jour',
		couleur: 'var(--fil-rouge)',
		fond: 'var(--fil-rouge-fond)',
		icone: 'refresh-cw',
		abrege: 'AFF.',
	},
	annonce: {
		libelle: 'Petite annonce',
		couleur: 'var(--color-orange)',
		fond: 'var(--color-orange-fond)',
		icone: 'heart-handshake',
		abrege: 'ANN.',
	}, //  17° orange
	//  40° ambre — ajouté le 17/10/2026 (#2042) : le compte rendu validé d'un
	//  point CS / Syndic, une entrée par point, lue du conseil et du syndic.
	point_conseil: {
		libelle: 'Point CS / Syndic',
		couleur: 'var(--fil-ambre)',
		fond: 'var(--fil-ambre-fond)',
		icone: 'users',
		abrege: 'CS/SYN.',
	},
	diagnostic: {
		libelle: 'Diagnostic',
		couleur: 'var(--fil-olive)',
		fond: 'var(--fil-olive-fond)',
		icone: 'activity',
		abrege: 'DIAG.',
	}, //  86° olive
	annuaire: {
		libelle: 'Annuaire',
		couleur: 'var(--fil-vert)',
		fond: 'var(--fil-vert-fond)',
		icone: 'users',
		abrege: 'ANNU.',
	}, // 142° vert
	prestataire: {
		libelle: 'Prestataire',
		couleur: 'var(--fil-sarcelle)',
		fond: 'var(--fil-sarcelle-fond)',
		icone: 'hard-hat',
		abrege: 'PREST.',
	}, // 175° sarcelle
	idee: {
		libelle: 'Boîte à idées',
		couleur: 'var(--fil-cyan)',
		fond: 'var(--fil-cyan-fond)',
		icone: 'lightbulb',
		abrege: 'IDÉE',
	}, // 193° cyan
	//  214° bleu Seine, la couleur de la charte
	publication: {
		libelle: 'Actualité',
		couleur: 'var(--color-primary)',
		fond: 'var(--color-primary-light)',
		icone: 'newspaper',
		abrege: 'ACTU.',
	},
	document: {
		libelle: 'Document',
		couleur: 'var(--fil-indigo)',
		fond: 'var(--fil-indigo-fond)',
		icone: 'file-text',
		abrege: 'DOC.',
	}, // 245° indigo
	sondage_clos: {
		libelle: 'Sondage clos',
		couleur: 'var(--fil-violet)',
		fond: 'var(--fil-violet-fond)',
		icone: 'bar-chart-3',
		abrege: 'SOND.',
	}, // 263° violet
	sondage_ouvert: {
		libelle: 'Sondage',
		couleur: 'var(--fil-violet)',
		fond: 'var(--fil-violet-fond)',
		icone: 'bar-chart-3',
		abrege: 'SOND.',
	},
	faq: {
		libelle: 'Question fréquente',
		couleur: 'var(--fil-fuchsia)',
		fond: 'var(--fil-fuchsia-fond)',
		icone: 'help-circle',
		abrege: 'FAQ',
	}, // 295° fuchsia
	question_reglement: {
		libelle: 'Question au règlement',
		couleur: 'var(--fil-rose)',
		fond: 'var(--fil-rose-fond)',
		icone: 'book-open',
		abrege: 'RÈGL.',
	}, // 330° rose — ajouté le 11/10/2026, entre le fuchsia et le rouge
});

export const TYPE_LABELS: Record<string, string> = L;
/**  Ce qui CLASSE une carte du fil dans sa gouttière (10/10/2026, maquette B du
 *   fil, choisie à l'écran) : le pictogramme et l'abrégé de sa rubrique, le
 *   libellé entier en infobulle. Écrits dans la table des rubriques, avec le
 *   libellé et la teinte — une rubrique neuve sans marque ne compile pas. */
export function classeFlux(type: string): ClasseGouttiere | null {
	return I[type] ? { icone: I[type], abrege: A[type], libelle: typeLibelle(type) } : null;
}
export const TYPE_COLORS: Record<string, string> = C;
export const TYPE_BG: Record<string, string> = F;

//  Les défauts restent des VALEURS DE REPLI, pas une apparence acceptable : un
//  type inconnu doit se voir comme tel plutôt que passer pour une rubrique
//  normale. Ils sont lisibles (contraste 7,6:1) — c'est le garde-fou de test,
//  pas le repli, qui empêche un type d'y rester.
const COULEUR_INCONNUE = 'var(--fil-inconnu)';
const FOND_INCONNU = 'var(--fil-inconnu-fond)';

export function typeCouleur(type: string): string {
	return TYPE_COLORS[type] ?? COULEUR_INCONNUE;
}
export function typeFond(type: string): string {
	return TYPE_BG[type] ?? FOND_INCONNU;
}
export function typeLibelle(type: string): string {
	return TYPE_LABELS[type] ?? type;
}

export function badgeClass(type: string, badge: string): string {
	const b = badge.toLowerCase();
	if (b.includes('résolu') || b.includes('réalisé') || b.includes('accepté')) return 'badge-green';
	if (b.includes('urgent') || b.includes('refusé')) return 'badge-red';
	if (b.includes('en cours') || b.includes('en attente') || b === 'panne') return 'badge-orange';
	if (b.includes('clôturé')) return 'badge-gray';
	if (b.startsWith('#')) return 'badge-gray';
	if (type === 'sondage_ouvert') return 'badge-purple';
	return 'badge-blue';
}

// ── Liens ─────────────────────────────────────────────────────────────────
// `null` = cet élément n'est affiché sur aucune page : on n'affiche alors PAS de
// lien, plutôt qu'un `href="#"` ou une route inexistante. Un document de catégorie
// non exposée (fiche synthétique, attestation de lot…) est dans ce cas — le fil
// pointait auparavant vers `/documents`, qui renvoyait un 404 (26/07/2026).
/**
 * La clé d'un élément du fil — **jamais son `id` seul**.
 *
 * 🔴 Le fil AGRÈGE PLUSIEURS TABLES : `publication`, `ticket_mis_a_jour`,
 * `annonce`, `sondage_ouvert`, `sondage_clos`, `evenement`… Chaque élément porte
 * l'`id` de sa propre table, donc deux éléments de types différents peuvent
 * avoir le MÊME `id` — et `sondage_ouvert` / `sondage_clos` d'un même sondage en
 * sont un cas garanti.
 *
 * Rendus par `{#each … (item.id)}`, ces deux éléments donnaient deux clés
 * égales, donc `each_key_duplicate` : erreur **fatale** de Svelte, qui tue le
 * composant racine. L'écran cesse alors de répondre — et plus aucune navigation
 * ne passe ensuite, sur aucune page (16/09/2026, troisième incident du jour de
 * la même famille).
 *
 * ⚠️ Toute liste du fil passe par ici. Un `(item.id)` réécrit dans un écran
 * ramènerait le défaut : `npm run lint:cles-listes` le refuse.
 */
export function cleFluxItem(item: FluxItem): string {
	return `${item.type}:${item.id}`;
}

export function typeLink(item: FluxItem): string | null {
	if (item.type === 'sondage_ouvert' || item.type === 'sondage_clos') return '/sondages';
	if (['ticket_ouvert', 'ticket_resolu', 'ticket_mis_a_jour'].includes(item.type)) {
		const numero = item.meta?.numero as string | undefined;
		return numero ? `/tickets?open=${numero}` : '/tickets';
	}
	return item.lien ?? null;
}

export function typeVoirLabel(item: FluxItem): string {
	if (['ticket_ouvert', 'ticket_resolu', 'ticket_mis_a_jour'].includes(item.type))
		return "Voir l'affaire →";
	if (item.type === 'publication') return "Voir l'actualité →";
	if (item.type === 'sondage_ouvert' || item.type === 'sondage_clos') return 'Voir le sondage →';
	if (item.type === 'annonce') return "Voir l'annonce →";
	if (item.type === 'idee') return "Voir l'idée →";
	return 'Voir →';
}

// ── Nouveauté ─────────────────────────────────────────────────────────────
// `date` est celle de l'ANNONCE (le backend ne la recalcule pas sur une simple
// modification de marqueur, cf. flux.py) : décocher « Épinglé » ne redonne donc
// pas la pastille NEW à une actualité de l'an dernier.
export function isNew(item: { cree_le?: string; date: string }): boolean {
	const dateTs = new Date(item.date).getTime();
	const creeTs = item.cree_le ? new Date(item.cree_le).getTime() : dateTs;
	const ref = Math.max(dateTs, creeTs);
	const diff = Date.now() - ref;
	return diff >= 0 && diff < 48 * 3600 * 1000;
}

// ── Les trois registres du fil ────────────────────────────────────────────
// Chaque ligne appartient à UN registre et un seul :
//   1. 🔴 Urgences en cours — « qu'est-ce qui brûle ? »
//   2. 📌 Épinglé          — « qu'est-ce qu'il ne faut pas perdre de vue ? »
//   3. Chronologie         — « quoi de neuf ? »
//
// Pourquoi épinglé n'est PAS fusionné dans les urgences : l'urgence s'auto-périme
// (les états clos sortent du filtre), pas l'épinglage. Un épinglé y resterait
// indéfiniment et le bandeau rouge mourrait d'habitude ; et le plafond de 3 des
// urgences ferait évincer une urgence réelle par un élément épinglé.

/**  Un TICKET urgent du fil — la moitié de `estUrgent` que `FluxCard` réécrivait.
 *
 *  🔴 Le composant testait `item.type === 'ticket_ouvert' &&
 *  item.badges?.includes('urgence')` pour poser sa classe, pendant que
 *  `estUrgent` — juste en dessous — écrivait la même condition. Deux écritures,
 *  et la seconde ne couvrait que les tickets : un lecteur pouvait croire que
 *  `estUrgent` s'en servait.
 *
 *  ⚠️ Le badge lu est `'urgent'` et non plus `'urgence'` : c'est l'API qui le
 *  pose désormais depuis la PRIORITÉ (`badges_ticket`, `flux/commun.py`), la
 *  catégorie « urgence » ayant été retirée (migration 0177). Les deux moitiés du
 *  pont voyagent ensemble — c'est la leçon de #806 sur les liens que l'API
 *  fabrique vers le front. */
export function estTicketUrgent(item: FluxItem): boolean {
	return item.type === 'ticket_ouvert' && (item.badges?.includes('urgent') ?? false);
}

/** Le registre le plus grave l'emporte : un élément urgent ET épinglé n'apparaît
 *  qu'en urgence. Il retombera dans le bandeau épinglé en cessant d'être urgent. */
export function estUrgent(item: FluxItem): boolean {
	return (
		estTicketUrgent(item) ||
		(item.type === 'publication' && Boolean(item.meta?.urgente) && item.meta?.statut !== 'resolu')
	);
}

export function estEpingle(item: FluxItem): boolean {
	return Boolean(item.meta?.epingle) && !estUrgent(item);
}

/** Reste en tête de la chronologie malgré son âge : ce qui n'est pas terminé
 *  n'est pas de l'histoire ancienne. */
export function estNonResolu(item: FluxItem): boolean {
	if (item.type === 'ticket_ouvert') {
		//  La cinquième liste de statuts de tickets, et la seule qui oubliait
		//  `annulé` : un ticket annulé restait donc en tête de la chronologie
		//  indéfiniment, comme s'il attendait encore quelque chose. `#lib/tickets`
		//  porte la question une fois pour toutes (#415).
		return !estTicketClos((item.meta?.statut as string) ?? '');
	}
	return false;
}

/**
 * Date qui décide de l'ancienneté d'une ligne du fil.
 *
 * ## 🔴 Elle lisait la NAISSANCE de l'objet, pas la date de l'annonce (#529)
 *
 * Signalé à l'écran le 20/08/2026 : *« le dernier commentaire semble ne pas être
 * visible »*. Un commentaire ajouté aujourd'hui sur un ticket ouvert en mars
 * était classé **en mars** — donc rangé dans les Archives (au-delà de trente
 * jours), voire hors de la fenêtre de chargement.
 *
 * La cause : cette fonction rendait `item.cree_le`, la naissance de l'OBJET,
 * alors que `item.date` porte celle de l'ANNONCE — ce que le commentaire de
 * `isNew`, vingt lignes plus haut, disait déjà en toutes lettres.
 *
 * ⚠️ **Six producteurs sur dix calculent une `date` différente de `cree_le`**,
 * et chacun l'a fait exprès :
 *
 * | Carte | `date` | `cree_le` |
 * |---|---|---|
 * | ticket mis à jour | l'évolution | l'ouverture du ticket |
 * | évolution d'événement | l'évolution | la création de l'événement |
 * | sondage clos | la clôture | la création |
 * | petite annonce | la mise à jour | le dépôt |
 * | actualité | la publication | la rédaction |
 *
 * Le serveur faisait donc le bon calcul, six fois, et l'écran le jetait.
 *
 * ## ✅ L'événement classe sur sa TENUE depuis le 20/08/2026 (#524)
 *
 * Il restait classé sur sa date d'annonce. L'AG du **22 juin** s'affichait et se
 * rangeait au **1er mars**, jour de sa saisie — donc elle descendait dans le fil
 * à mesure qu'elle APPROCHAIT, et disparaissait de la fenêtre de chargement
 * alors qu'elle n'avait pas encore eu lieu.
 *
 * 🔴 Toutes les entités n'ont pas la même « bonne » date, et c'est le fond du
 * sujet. Une règle unique serait fausse pour au moins un type :
 *
 * | Objet | Ce qui le classe | Pourquoi |
 * |---|---|---|
 * | **événement** | `meta.debut` | on cherche « quoi ENSUITE » |
 * | publication | l'annonce | on cherche « quoi de NEUF » |
 * | ticket | la clôture, sinon la dernière activité | idem |
 *
 * D'où une **table déclarative** plutôt qu'une cascade de `if` : le jour où une
 * entité veut une autre date, elle le DIT, et la fonction ne bouge pas. C'est la
 * forme retenue pour l'archivage (#515) et pour les périodes par nœud (#542).
 */
//  L'événement, seul type qui déclarait sa date, est parti le 23/09/2026 : c'est
//  une affaire (#1092). La table reste — un type à venir s'y déclarera.
const DATE_QUI_CLASSE: Record<string, (item: FluxItem) => string | undefined> = {};

export function dateDeReference(item: FluxItem): number {
	const cloture = (item.meta?.cloture_le || item.meta?.ferme_le) as string | undefined;
	if (cloture) return new Date(cloture).getTime();

	//  La date DÉCLARÉE par le type, quand il en déclare une.
	const declaree = DATE_QUI_CLASSE[item.type]?.(item);
	if (declaree) return new Date(declaree).getTime();

	//  `date` d'abord : c'est la date de l'ANNONCE, celle que le serveur a
	//  calculée pour cette carte. `cree_le` n'est qu'un repli pour les cartes
	//  qui ne portent pas de date propre.
	return new Date(item.date || item.cree_le || 0).getTime();
}

/** Plafond SOUPLE : on avertit celui qui épingle, on ne masque jamais un
 *  élément épinglé — le cacher trahirait la promesse du marqueur. Au-delà,
 *  le bandeau devient une seconde chronologie et ne signale plus rien. */
export const PLAFOND_EPINGLES = 5;

/** `totalApresEpinglage` = ce que deviendrait le total si l'on validait la case
 *  cochée, toutes rubriques confondues. `null` = rien à signaler. */
export function avertissementEpinglage(totalApresEpinglage: number): string | null {
	if (totalApresEpinglage <= PLAFOND_EPINGLES) return null;
	return `Cela porterait à ${totalApresEpinglage} le nombre d'éléments épinglés. Au-delà de ${PLAFOND_EPINGLES}, le bandeau « Épinglé » cesse d'attirer l'œil : épingler dix éléments revient à n'en épingler aucun.`;
}

/**
 * Les pastilles d'une entrée du fil. Le serveur rend l'équipement d'un
 * prestataire en VALEUR (`meta.specialite`) : il se traduit ici, par la table
 * unique (`equipLabel`) — il s'affichait « interphone_digicode » (26/09/2026).
 */
export function badgesDuFlux(item: FluxItem): string[] {
	const equipement = item.type === 'prestataire' ? item.meta?.specialite : null;
	return equipement ? [equipLabel(String(equipement))] : item.badges;
}

/**
 * Un groupe de la frise du fil : l'intitulé de son jour (« Aujourd'hui »,
 * « Hier », puis la date longue), ou `null` pour un groupe qui n'en affiche
 * pas — le bandeau Épinglé. Rendu par `FriseDuFil`.
 */
export interface GroupeDuFil {
	label: string | null;
	items: FluxItem[];
}

/**
 * Les éléments du fil groupés par JOUR, dans l'ordre où ils arrivent.
 *
 * Elle vivait dans la page d'accueil, qui l'appliquait au fil récent et aux
 * Archives : c'est une règle du fil, pas de l'écran (#779).
 */
export function grouperParJour(items: FluxItem[]): GroupeDuFil[] {
	const groupes = new Map<string, FluxItem[]>();
	const aujourdhui = new Date();
	aujourdhui.setHours(0, 0, 0, 0);
	const hier = new Date(aujourdhui);
	hier.setDate(hier.getDate() - 1);
	for (const item of items) {
		const jour = new Date(item.date);
		jour.setHours(0, 0, 0, 0);
		const label =
			jour.getTime() === aujourdhui.getTime()
				? "Aujourd'hui"
				: jour.getTime() === hier.getTime()
					? 'Hier'
					: fmtDateLong(item.date);
		if (!groupes.has(label)) groupes.set(label, []);
		groupes.get(label)!.push(item);
	}
	return Array.from(groupes, ([label, items]) => ({ label, items }));
}
