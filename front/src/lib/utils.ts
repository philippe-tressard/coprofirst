/**
 * Supprime toutes les balises HTML d'une chaîne.
 * Utilisé pour générer des aperçus texte depuis un contenu HTML riche (TipTap).
 * Compatible SSR (pas de dépendance DOM).
 */
export function stripHtml(html: string): string {
	return decoderEntites(html.replace(/<[^>]*>/g, '')).trim();
}

/** Les entités nommées que produit l'éditeur ; les numériques se décodent toutes. */
const ENTITES: Record<string, string> = {
	nbsp: ' ',
	amp: '&',
	lt: '<',
	gt: '>',
	quot: '"',
	apos: "'",
};

/**
 * Décode les entités HTML d'un texte, en UNE passe — pendant de `html.unescape`
 * côté serveur (`texte_brut`). Les cinq remplacements en série d'avant laissaient
 * les numériques : l'apostrophe de l'éditeur, `&#x27;`, s'affichait en clair
 * (17/10/2026). Une passe unique ne décode pas deux fois (`&amp;lt;` → `&lt;`).
 */
function decoderEntites(texte: string): string {
	return texte.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (entite, corps: string) => {
		if (corps[0] !== '#') return ENTITES[corps.toLowerCase()] ?? entite;
		const code =
			corps[1] === 'x' || corps[1] === 'X'
				? parseInt(corps.slice(2), 16)
				: parseInt(corps.slice(1), 10);
		return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : entite;
	});
}

/**
 * Montant en euros — format français unique de l'application.
 *
 * `1234` → `1 234 €` · `1234.5` → `1 234,50 €` · `null` → `—`
 *
 * Avant ce helper, le même champ `montant_estime` était formaté de trois façons
 * différentes selon l'écran — parfois sur la même page : `{style:'currency'}`
 * (« 1 234,00 € »), `toLocaleString('fr-FR')` suivi d'un `€` littéral
 * (« 1 234 € »), et un `Intl.NumberFormat` local avec `maximumFractionDigits: 0`
 * (qui arrondissait « 1 234,50 » en « 1 235 € »).
 *
 * `minimumFractionDigits: 0` + `maximumFractionDigits: 2` : les centimes sont
 * affichés quand ils existent — donc aucun arrondi trompeur sur un montant de
 * devis — et masqués sur un montant entier. Le `—` pour une valeur absente suit la
 * convention de `lib/date.ts`.
 */
export function fmtMontant(
	v: number | null | undefined,
	/** « USD » pour ce que facture un fournisseur d'IA : ses grilles sont en dollars. */
	devise: 'EUR' | 'USD' = 'EUR',
	/** 4 pour le coût d'UN appel d'IA (0,0041 $), que deux décimales liraient « 0 $ ». */
	decimales: 2 | 4 = 2,
): string {
	if (v == null) return '—';
	return new Intl.NumberFormat('fr-FR', {
		style: 'currency',
		currency: devise,
		minimumFractionDigits: 0,
		maximumFractionDigits: decimales,
	}).format(v);
}

/**
 * Nombre groupé à la française — format unique de tout nombre affiché.
 *
 * `1234567` → `1 234 567` · `0.5` → `0,5` · `null` → `—`
 *
 * Trois écrans (`BlocUsageIA`, `OngletConsommations`, `ConsommationIA`) écrivaient
 * chacun leur `toLocaleString('fr-FR')`, et un quatrième format de nombre n'avait
 * aucune raison de ne pas suivre (#1576). Le `—` pour une valeur absente suit
 * `fmtMontant` et `lib/date.ts`. 🔒 `npm run lint:dates` refuse la forme à la main.
 */
const NOMBRE = new Intl.NumberFormat('fr-FR');
export function fmtNombre(v: number | null | undefined): string {
	if (v == null) return '—';
	return NOMBRE.format(v);
}

const UNE_DECIMALE = new Intl.NumberFormat('fr-FR', {
	minimumFractionDigits: 1,
	maximumFractionDigits: 1,
});
const DEUX_DECIMALES = new Intl.NumberFormat('fr-FR', {
	minimumFractionDigits: 2,
	maximumFractionDigits: 2,
});

/**
 * Une part d'un tout, en pourcentage — `34 / 10 000` → `0,34 %` · `0` ou dénominateur nul → `—`.
 *
 * Deux décimales : une part de copropriété tient en dix-millièmes, que l'arrondi à l'entier
 * ferait tous valoir « 0 % ». Le format est celui de `fmtNombre`, la virgule comprise.
 */
export function fmtPartEnPourcent(numerateur: number, denominateur: number): string {
	if (!denominateur) return '—';
	return `${DEUX_DECIMALES.format((numerateur / denominateur) * 100)}\u00a0%`;
}

/**
 * Taille en octets — échelle unique de l'application : o · Ko · Mo · Go (base 1024).
 *
 * `512` → `512 o` · `51 200` → `50 Ko` · `1 258 291` → `1,2 Mo` · `3 435 973 837` → `3,20 Go`
 *
 * Deux formateurs écrits à la main disaient la même grandeur de deux façons
 * (#1576) : `taches-colonnes.ts` en Mo / Go (`toFixed(1)` puis `toFixed(2)`, seuil
 * 1024 Mo) et `HistoriqueAnnoncesHall` en Ko / Mo (`Math.round` puis `toFixed(1)`,
 * seuil 1 Mo). L'échelle retenue est leur réunion, et elle rend **le même texte**
 * dans le cas courant de chacun : un Mo ou un Go se lit comme avant (une décimale
 * sous le Go, deux au-delà), un Ko est arrondi à l'entier.
 *
 * Ce qui change, volontairement (autorisé par l'utilisateur, 02/10/2026) :
 * - le séparateur est la **virgule** (« 1,2 Mo », et non « 1.2 Mo ») ;
 * - sous 1 Mo, l'historique des tâches disait « 0,3 Mo » : il dit « 300 Ko » ;
 * - sous 1 Ko, les deux disaient « 0 » : c'est « 512 o » ;
 * - une valeur absente est `—`, comme `fmtMontant`. Le « rien à dire » d'un
 *   poids absent ou nul (`''` dans l'historique des annonces) reste le choix de
 *   l'appelant : ce n'est pas un format.
 *
 * 🔒 `npm run lint:dates` refuse `toFixed(` et une division par 1024 hors d'ici.
 */
/**
 *  Un champ lu par son NOM, quand ce nom est une donnée — la colonne d'une table
 *  déclarée (imports d'accès, historique des tâches) — et non un champ que le type
 *  connaît d'avance. Rend `unknown` : l'appelant décide de ce qu'il en fait.
 *  Écrit ici une fois, plutôt qu'un `any` par écran (#1571).
 */
export const champDe = (objet: object | null | undefined, cle: string): unknown =>
	objet == null ? undefined : (objet as Record<string, unknown>)[cle];

export function fmtOctets(n: number | null | undefined): string {
	if (n == null) return '—';
	if (n < 1024) return `${fmtNombre(Math.round(n))} o`;
	//  Les seuils sont ceux de l'ARRONDI : 1 048 000 octets s'écrivent « 1 023 Ko »
	//  et 1 048 500 « 1,0 Mo », jamais « 1 024 Ko » ni « 1 024,0 Mo ».
	const ko = n / 1024;
	if (ko < 1023.5) return `${fmtNombre(Math.round(ko))} Ko`;
	const mo = ko / 1024;
	if (mo < 1023.95) return `${UNE_DECIMALE.format(mo)} Mo`;
	return `${DEUX_DECIMALES.format(mo / 1024)} Go`;
}

/**
 * Durée en millisecondes, telle qu'un écran la fait attendre (#1632).
 *
 * `340` → `340 ms` · `1 250` → `1,3 s` · `12 400` → `12,4 s` · `null` → `—`
 *
 * Sous la seconde, les millisecondes entières ; au-delà, une décimale — une
 * attente se lit en secondes. Le `—` suit `fmtNombre` et `fmtOctets`.
 */
export function fmtDuree(ms: number | null | undefined): string {
	if (ms == null) return '—';
	if (ms < 999.5) return `${fmtNombre(Math.round(ms))} ms`;
	return `${UNE_DECIMALE.format(ms / 1000)} s`;
}

/**
 * Périmètres — la table a disparu d'ici, et de partout ailleurs.
 *
 * `PERIMETRE_LABELS` vivait juste en dessous : sept clés écrites en dur, arrêtées
 * à `bat:4` quand l'API allait jusqu'à `bat:9`. Un cinquième bâtiment s'affichait
 * « Bât. 5 » côté serveur et **`bat:5` brut** à l'écran, et aucune description
 * n'existait nulle part.
 *
 * L'arborescence vit désormais en base et s'édite depuis l'administration
 * (`/admin/patrimoine`). Le rendu est dans `#lib/perimetres`, alimenté au
 * démarrage par `#lib/stores/perimetres`.
 *
 * Ces réexports existent pour que les cinq pages qui écrivent
 * `import { perimetreLabel } from '#lib/utils.ts'` n'aient pas à changer : le chemin
 * d'import n'est pas la question que ce lot traite.
 */
export {
	perimetreLabel,
	perimetreLabelUn,
	estPerimetreParDefaut,
	perimetreParDefaut,
	perimetreDefautListe,
	perimetreDuBatiment,
	noeudPerimetre,
	tousLesPerimetres,
	concerneTous,
	batimentsCibles,
	type Perimetre,
} from '#lib/perimetres/index.ts';

/**
 * État de la touche Verr. Maj., ou `null` si l'événement ne permet pas de le savoir.
 *
 * `getModifierState()` n'existe que sur les événements clavier et souris : un
 * `FocusEvent` ne l'a pas. Or les trois pages d'authentification câblaient le
 * même handler sur `on:focus` en plus de `on:keydown`/`on:keyup`, et il levait
 * donc une `TypeError` à chaque fois que l'utilisateur cliquait dans le champ
 * mot de passe — sur la connexion, l'inscription et la réinitialisation.
 *
 * Rendre `null` plutôt que lever : au focus, l'état des touches n'est tout
 * simplement pas connaissable, ce n'est pas une erreur. L'appelant conserve
 * alors la valeur qu'il avait.
 */
export function capsLockActif(e: KeyboardEvent | FocusEvent): boolean | null {
	const getModifierState = (e as KeyboardEvent).getModifierState;
	if (typeof getModifierState !== 'function') return null;
	return getModifierState.call(e, 'CapsLock');
}

/**
 * Une note sur 5 rendue en étoiles pleines et vides — `4` → `★★★★☆`.
 *
 * Écrite deux fois dans le dépôt (l'espace CS et la fiche prestataire) jusqu'au
 * 19/08/2026, sous le même nom et avec le même corps.
 */
export function starsDisplay(note: number): string {
	const pleines = Math.round(note);
	return '★'.repeat(pleines) + '☆'.repeat(5 - pleines);
}

/**
 * Relie un calcul SANS dépendance réactive à ce qui doit le déclencher.
 *
 * ```svelte
 * $: minuit = relire(contrats, minuitDuJour);
 * ```
 *
 * 🔴 **Le défaut qu'il corrige.** Un `$:` ne se réexécute que si l'une des
 * variables réactives qu'il cite change. `$: annee = anneeCourante()` n'en cite
 * aucune : Svelte l'exécute une fois et plus jamais. La ligne a **l'air**
 * réactive, elle vaut un `const`, et aucune relecture ne peut le voir — c'est
 * `svelte/no-immutable-reactive-statements` qui l'a trouvé (#549, 29/08/2026).
 *
 * Quatre écritures en souffraient, dont deux avec, juste au-dessus, le
 * commentaire décrivant le rafraîchissement qui n'avait pas lieu :
 *
 * | Écran | Ce qui était figé | Ce que ça donnait |
 * |---|---|---|
 * | Reporting (×3) | l'année de référence | un onglet ouvert la nuit du réveillon annonçait les échéances de l'année passée — le commentaire disait l'empêcher |
 * | Prestataires | minuit du jour | un onglet ouvert la veille classait « en retard » ce qui devenait dû le lendemain |
 * | Sélecteur de périmètre | le périmètre par défaut | `perimetreParDefaut()` lit un état de module posé au chargement de l'arbre : avant lui, `null`, et pour toujours |
 * | Tableau de bord | la salutation | « Bonjour » à 20 h |
 *
 * ⚠️ **`dependance` n'est pas lue, et c'est tout son objet** : elle dit à Svelte
 * de quoi le calcul dépend. La citer est le geste, pas un effet de bord.
 *
 * ⚠️ **Ce n'est pas une horloge.** Le rechargement des données est le seul
 * moment où la page apprend que le temps a passé ; un onglet ouvert et immobile
 * reste en retard. Poser un `setInterval` pour ces quatre cas coûterait plus
 * qu'il ne rapporte — ce qui change est qu'une navigation suffit à corriger.
 */
export function relire<T>(dependance: unknown, calcul: () => T): T {
	void dependance;
	return calcul();
}

/**
 * Les numéros de téléphone d'un champ libre — découpés, nettoyés, DÉDOUBLONNÉS.
 *
 * 🔴 Écrit deux fois avant le 03/09/2026 : `splitTels()` dans les prestataires,
 * et `m.telephone.split(',').filter((t) => t.trim())` recopié dans l'annuaire.
 * Deux écritures de la même notion, qui auraient divergé au premier changement
 * de séparateur.
 *
 * ⚠️ Le dédoublonnage est ce qui manquait aux deux, et il règle DEUX choses à la
 * fois :
 *
 * 1. **le rendu** — un numéro saisi deux fois dans le même champ s'affichait
 *    deux fois, sans que personne y voie autre chose qu'une saisie maladroite ;
 * 2. **la clé de liste** — sans unicité, `{#each … as tel (tel)}` fait lever
 *    `each_key_duplicate` à Svelte et **l'écran entier tombe**. C'est pourquoi
 *    ces cinq boucles étaient restées sans clé : la corriger par la forme aurait
 *    été plus dangereux que le défaut. Dédoublonner à la SOURCE rend la clé
 *    sûre, au lieu de choisir entre les deux.
 */
export function telephonesDe(champ: string | null | undefined): string[] {
	if (!champ) return [];
	const vus = new Set<string>();
	for (const brut of champ.split(',')) {
		const numero = brut.trim();
		if (numero) vus.add(numero);
	}
	return [...vus];
}

/**
 * Libellé français du type d'un lot — « Appartement », « Parking », « Cave ».
 *
 * 🔴 Écrit dans `mon-lot/+page.svelte`, où un commentaire signalait déjà le
 * piège : *« `lotLabel` s'appuie sur `lotTypeLabel`, qui sert encore à
 * l'affichage des accès plus bas. L'emporter dans le composant en aurait fait
 * une deuxième écriture. »* L'extraction de `ModaleAccesBail` (#779) est
 * exactement le geste que ce commentaire redoutait — d'où le passage ici,
 * plutôt qu'une copie de plus.
 *
 * ⚠️ Une valeur inconnue n'est pas remplacée par « — » : un type ajouté côté API
 * doit s'afficher plutôt que disparaître derrière un tiret que personne ne saura
 * interpréter. Elle est seulement mise en forme — soulignés en espaces, initiale
 * en majuscule (`local_commercial` → « Local commercial ») : c'est ce que les six
 * copies recalculées à la main faisaient, et ce que cette fonction taisait
 * jusqu'au 30/09/2026 (#779). 🔒 `npm run lint:type-lot`.
 */
export function lotTypeLabel(t: string | null | undefined): string {
	if (!t) return '—';
	if (t === 'appartement') return 'Appartement';
	if (t === 'parking') return 'Parking';
	if (t === 'cave') return 'Cave';
	const lisible = t.replace(/_/g, ' ');
	return lisible.charAt(0).toUpperCase() + lisible.slice(1);
}

/**
 * Le type d'un lot avec sa précision — « Appartement – T3 ». Six écrans la
 * recomposaient à la main (#779) ; `lotTypeLabel` seul ne dit pas le « T3 ».
 */
export function lotTypeComplet(
	type: string | null | undefined,
	typeAppartement?: string | null,
): string {
	return `${lotTypeLabel(type)}${typeAppartement ? ` – ${typeAppartement}` : ''}`;
}

/**
 * Le libellé d'un étage — « RDC », « 1er », « 2ème », « SS 1 ».
 *
 * 🔴 Écrit **six fois** dans trois écrans, en **trois rendus différents** (#835,
 * 08/09/2026) :
 *
 * | Écran | Rendu d'un sous-sol | Rendu du 2ᵉ |
 * |---|---|---|
 * | `mon-lot` (4 fois) | `-1` | `2` |
 * | `profil` | `SS 1` | `2ème étage` |
 * | `tableau-de-bord` | `-1` | `2ème` |
 *
 * Le même lot s'affichait donc « -1 » sur un écran et « SS 1 » sur un autre. Ce
 * n'est pas une variante de présentation assumée : c'est ce que trois personnes
 * ont écrit séparément en croyant chacune être seule.
 *
 * ⚠️ Le **suffixe** est laissé à l'appelant (`suffixe: false` par défaut). Une
 * ligne de définition affiche « Étage : 2ème » — répéter le mot dans la valeur
 * donnerait « Étage : 2ème étage ». Un fil de texte, lui, en a besoin. C'est la
 * seule divergence légitime des six, et elle devient un paramètre plutôt qu'une
 * copie.
 *
 * ⚠️ `null` et `undefined` rendent une chaîne **vide**, pas « — » : l'appelant
 * décide de ce qu'il affiche à la place, et plusieurs entourent déjà la valeur
 * d'un `{#if}`.
 */
export function etageLabel(
	etage: number | null | undefined,
	{ suffixe = false }: { suffixe?: boolean } = {},
): string {
	if (etage === null || etage === undefined) return '';
	if (etage === 0) return 'RDC';
	if (etage < 0) return `SS ${Math.abs(etage)}`;
	const rang = etage === 1 ? '1er' : `${etage}ème`;
	return suffixe ? `${rang} étage` : rang;
}

/**
 * L'étage à AFFICHER pour un membre : le LOT fait autorité, la saisie prend le relais.
 *
 * Arbitré par Philippe le 09/09/2026 : *« préférer celle du Lot »*. L'étage d'un
 * lot vient du classeur de la copropriété ; celui que le résident saisit est un
 * repère de voisinage qu'il est le seul à pouvoir donner quand aucun lot ne le
 * porte — un locataire, un bailleur qui habite ailleurs.
 *
 * 🔴 **La désignation du logement de référence n'est PAS refaite ici.** Elle vit
 * dans `api/app/utils/etages.py` et voyage dans `est_logement_de_reference`, que
 * `GET /lots/mes-lots` pose sur le lot concerné. Une règle recalculée dans
 * l'écran aurait pris sa deuxième écriture, et la divergence que l'API SIGNALE
 * n'aurait plus été la même que celle que l'écran AFFICHE.
 *
 * ⚠️ Ce fichier a porté cette règle une première fois, sous le nom
 * `etageParDefaut` (08/09/2026) — supprimée le lendemain avec son test, puis
 * redemandée le soir même. Son bloc de documentation avait survécu à la
 * suppression : vingt-six lignes décrivant une fonction absente et citant un test
 * effacé. C'est ce commentaire-ci qui les remplace.
 *
 * ⚠️ `0` est un étage — le rez-de-chaussée. D'où `!= null` et jamais un test de
 * vérité, qui effacerait le RDC.
 */
export function etageDuLot(
	lots: { est_logement_de_reference?: boolean; etage?: number | null }[],
): number | null {
	const reference = lots.find((l) => l.est_logement_de_reference);
	return reference?.etage ?? null;
}

/**
 * « Bât. 4, T4, 2ème » — où habite un membre, tel que la salutation le dit.
 *
 * 🔴 Elle rendait une chaîne VIDE dès que le compte n'avait aucun lot rattaché :
 * un résident inscrit la veille lisait « Bonsoir Thomas · Copropriétaire
 * résident » quand son voisin lisait son bâtiment, son type et son étage.
 * Signalé par Philippe le 09/09/2026, sur un compte de test.
 *
 * Rien ne manquait pourtant : son bâtiment ET son étage étaient saisis à
 * l'inscription, sur le COMPTE. Cette règle ne lisait que le PATRIMOINE, comme
 * les autres écrans passés à `Lot.etage` — **un compte sans lot devenait
 * invisible à lui-même**, et rien ne pouvait le signaler : une chaîne vide n'est
 * pas une erreur, c'est une ligne un peu plus courte.
 *
 * ⚠️ Elle vit ICI et non dans le tableau de bord : c'est une règle du PRODUIT —
 * comment le site nomme le logement de quelqu'un —, pas une règle d'écran, et le
 * second écran qui en aura besoin l'aurait recopiée.
 */
export function libelleLogement(
	lots: {
		type?: string;
		batiment_nom?: string | null;
		type_appartement?: string | null;
		etage?: number | null;
	}[],
	compte: { batiment_nom?: string | null; etage?: number | null } | null | undefined,
): string {
	const appt = lots.find((l) => l.type === 'appartement');
	if (appt) {
		const parts: string[] = [];
		if (appt.batiment_nom) parts.push(appt.batiment_nom);
		else if (compte?.batiment_nom) parts.push(compte.batiment_nom);
		if (appt.type_appartement) parts.push(appt.type_appartement);
		if (appt.etage != null) parts.push(etageLabel(appt.etage));
		return parts.join(', ');
	}
	//  Le repli sur le COMPTE. Le séparateur diffère exprès de celui du cas
	//  nominal : ce n'est pas la même phrase — elle porte un ÉTAT en son milieu, et
	//  « Bât. 3, sans lot, RDC » se lirait comme une énumération de trois choses de
	//  même nature.
	const parts: string[] = [];
	if (compte?.batiment_nom) parts.push(compte.batiment_nom);
	parts.push('sans lot');
	//  ⚠️ `!= null` : `0` est le rez-de-chaussée. Rien n'est écrit quand l'étage
	//  n'a pas été saisi — une mention « étage inconnu » n'apprendrait rien à qui
	//  la lit sur SON écran.
	if (compte?.etage != null) parts.push(etageLabel(compte.etage));
	//  Ni bâtiment ni étage : « sans lot » tout seul est un reproche, pas une
	//  information. Mieux vaut ne rien dire.
	return parts.length > 1 ? parts.join(' — ') : '';
}

/**
 * Les bornes d'un étage saisi — au-delà, c'est une faute de frappe.
 *
 * 🔴 Écrites en clair dans `min="-2" max="50"` sur DEUX écrans (inscription et
 * profil), et un troisième champ s'y est ajouté le 09/09/2026 (l'étage d'un
 * logement, #835). Elles sont recopiées côté serveur dans
 * `api/app/utils/etages.py` — les contextes de build sont `./api` et `./front`,
 * seule la copie est possible — et `api/tests/test_etage_label.py` échoue si les
 * deux dérivent.
 */
export const ETAGE_MIN = -2;
export const ETAGE_MAX = 50;

/**
 * « Bât. 3 — 2ème » : où se trouve un membre, en une chaîne.
 *
 * 🔴 Écrite **trois fois** dans `espace-cs/+page.svelte` — vue édition, vue
 * lecture, résumé replié — et déjà divergente : deux employaient un tiret cadratin
 * (`—`), la troisième un demi-cadratin (`–`). Personne ne peut voir cet écart, et
 * personne ne peut le corriger : il faudrait d'abord savoir qu'il existe.
 *
 * 🔴 Les trois écrivaient aussi `Étage ${m.etage}` en clair, donc « Étage 0 » pour
 * un rez-de-chaussée et « Étage -1 » pour un sous-sol. Le libellé d'étage a UNE
 * source (`etageLabel`) depuis #835 ; ces trois-là ne la connaissaient pas, parce
 * que le contrôle d'alors ne cherchait que les comparaisons à zéro.
 *
 * ⚠️ Rend une chaîne **vide** quand on ne sait rien, jamais « — » : c'est
 * l'appelant qui décide de ce qu'il affiche à la place, et les trois sites
 * entourent déjà la valeur d'un `{#if}`.
 */
export function localisationMembre(m: {
	batiment_nom?: string | null;
	etage?: number | null;
}): string {
	const parts = [];
	if (m.batiment_nom) parts.push(`Bât. ${m.batiment_nom}`);
	//  ⚠️ `!= null` et non un test de vérité : `0` est le rez-de-chaussée.
	if (m.etage != null) parts.push(etageLabel(m.etage, { suffixe: true }));
	return parts.join(' — ');
}

/**
 * Une valeur SAISIE en nombre, ou `null` si le champ est vide (#1516).
 *
 * 🔴 Un `<input type="number" bind:value>` vidé rend `null` (Svelte), pas `''` :
 * `v === '' ? null : Number(v)` envoyait alors `Number(null)`, soit **0** — un
 * relevé à 0 m³, un nombre de lots à 0. Et `v ? Number(v) : null` effaçait un
 * **0** réellement saisi. Vide (`''`, `null`, `undefined`, blancs) → `null` ;
 * tout le reste → `Number(v)`, 0 compris. 🔒 `npm run lint:nombre-saisi`.
 */
export function nombreOuNull(v: unknown): number | null {
	if (v === null || v === undefined || (typeof v === 'string' && v.trim() === '')) return null;
	return Number(v);
}
