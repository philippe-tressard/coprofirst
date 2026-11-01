/*
 *  Aides partagées des tests de navigateur.
 */
import { test as base, expect, type Locator, type Page, type Route } from '@playwright/test';

/**
 * **Le `test` de tous les specs — une exception de la page le fait échouer.**
 *
 * 🔴 #1475 (01/10/2026). Une exception levée par un effet Svelte interrompt la
 * mise à jour en cours : les effets suivants restent figés, sans un mot. Le
 * tableau de bord affichait ainsi « Bonsoir » sans prénom — les rôles et
 * l'avatar à jour, le titre non —, parce que l'API simulée rendait `[]` pour
 * le fil et que `RaccourcisRapides` lisait `undefined.tickets_ouverts`. Le test
 * tombait au hasard (selon que l'utilisateur arrivait avant ou après le fil),
 * et sa cause était une exception que personne n'écoutait : seuls deux specs
 * le faisaient, chacun pour lui.
 *
 * Une exception non rattrapée est donc un ÉCHEC, quel que soit le test.
 * 🔒 `npm run lint:e2e-test` refuse un spec qui importerait `test` directement
 * de `@playwright/test` — il échapperait à cette règle.
 */
export const test = base.extend<{ sansExceptionDePage: void }>({
	sansExceptionDePage: [
		async ({ page }, use) => {
			const exceptions: string[] = [];
			//  Le message ET le premier cadre de la pile : sans lui, on sait qu'un
			//  `undefined` a été lu, pas où. (En dev, Svelte ajoute au message la
			//  pile des COMPOSANTS, sur plusieurs lignes : d'où le premier « at ».)
			page.on('pageerror', (e) => {
				const cadre = (e.stack ?? '').split('\n').find((l) => l.trim().startsWith('at '));
				exceptions.push(`${e.message} — ${cadre?.trim() ?? '?'}`);
			});
			await use();
			expect(exceptions, 'exception non rattrapée dans la page').toEqual([]);
		},
		{ auto: true },
	],
});
export { expect };

/**
 * **Attendre que la page soit HYDRATÉE**, et pas seulement affichée.
 *
 * Les écrans sont rendus côté serveur : le formulaire de connexion existe dans
 * le HTML avant que le moindre gestionnaire ne soit posé. Un test qui remplit
 * ce formulaire trop tôt le SOUMET NATIVEMENT — la page se recharge, le
 * gestionnaire `preventDefault` n'a jamais existé, et le test échoue sur un
 * bandeau qui n'apparaîtra jamais. Même chose pour une image injectée avant que
 * la surveillance des images protégées ne soit en place : le test mesurerait
 * alors le moment de l'hydratation, pas la règle qu'il annonce.
 *
 * Le repère est posé par `#lib/imagesProtegees.ts`, depuis le `onMount` du
 * layout racine : quand il est là, le script du layout a tourné. Écrit ici une
 * fois — deux fichiers de test l'attendent, et un sélecteur recopié dans chacun
 * divergerait au premier renommage.
 */
export async function attendreHydratation(page: Page): Promise<void> {
	const debut = Date.now();
	try {
		await page.locator('html[data-images-surveillees="oui"]').waitFor({ timeout: 10000 });
	} finally {
		//  La durée est notée réussite OU échec (#1475) : un dépassement sous la
		//  charge d'un rejeu complet ne se diagnostique qu'en le comparant aux
		//  durées des tests verts du même rejeu. Bilan : `e2e/rapport-hydratation.ts`.
		test
			.info()
			.annotations.push({ type: TYPE_HYDRATATION, description: String(Date.now() - debut) });
	}
}

/**
 * **Déplier une étape d'une affaire dépliée** — « La suite », « La synthèse »
 * (`RubriqueEtape`, maquette G du 16/10/2026).
 *
 * Une carte d'affaire s'ouvre sur sa DEMANDE seule : la suite et la synthèse
 * sont pliées, et une seule étape s'ouvre à la fois. Un test qui touche à une
 * entrée du fil l'ouvre d'abord — écrit ici une fois, parce que trois specs le
 * font et qu'un sélecteur recopié divergerait au premier renommage.
 */
export async function deplierEtape(page: Page, titre: string): Promise<void> {
	const tete = page.locator('.encart-tete', { hasText: titre }).first();
	await tete.click();
	await expect(tete).toHaveAttribute('aria-expanded', 'true');
}

/** Le type de l'annotation que lit `rapport-hydratation.ts` — écrit une fois. */
export const TYPE_HYDRATATION = 'hydratation-ms';

/**
 * Un membre du conseil syndical — le compte simulé des écrans authentifiés.
 *
 * Le CS voit tout : un test qui le prend ne saute aucun onglet réservé.
 */
export const MEMBRE_CS = {
	id: 1,
	nom: 'Témoin',
	prenom: 'CS',
	email: 'temoin@exemple.test',
	statut: 'copropriétaire_résident',
	role: 'conseil_syndical',
	roles: ['conseil_syndical'],
	actif: true,
};

/**
 * Les réponses dont la FORME ne se devine pas au chemin — un objet qui porte des
 * listes. L'heuristique (« liste vide », « objet vide » pour la configuration)
 * leur donnait une forme que le serveur ne rend jamais, et l'écran levait une
 * exception que rien n'écoutait (#1475). Chacune reprend le type de son client.
 */
/**
 * Le tableau de bord de télémétrie VIDE (`TableauTelemetrie`) — exporté : un spec
 * qui teste un panneau en remplit un champ et garde les autres, sinon l'onglet
 * lirait `undefined.par_profil` et lèverait une exception.
 */
export const TABLEAU_TELEMETRIE_VIDE = {
	scope: 'jour',
	kpi: { vues: 0, pages: 0 },
	chart: [],
	chart_label: 'Vues par heure',
	top_pages: [],
	top_users: [],
	erreurs: [],
	performance: { indicateurs: [], pages: [] },
	gestes: [],
	arrivees: [],
	adoption: {
		periode: 'aujourd’hui',
		global: { libelle: 'Tous les comptes', actifs: 0, comptes: 0, taux: null },
		refus: 0,
		par_profil: [],
		par_type: [],
		par_batiment: [],
	},
	retour: {
		comptes_mesures: 0,
		refus: 0,
		dormants: [
			{ seuil: 60, nombre: 0 },
			{ seuil: 90, nombre: 0 },
		],
		liste_dormants: [],
		arrivants: {
			periode: '30 derniers jours',
			fenetre_jours: 7,
			valides: 0,
			revenus: 0,
			jamais_revenus: 0,
			en_attente: 0,
			taux: null,
		},
	},
	filtre_gestionnaire: {
		propose: false,
		gestionnaire_designe: true,
		applique: 'avec',
		non_distingue_jusqu_au: null,
	},
};

/**
 * Déplie une SECTION de l'onglet Télémétrie et la rend (03/10/2026) : les panneaux
 * sont des `<details>` repliés à l'arrivée, sauf « Indicateurs et fréquentation » — lire un
 * tableau demande d'abord d'ouvrir sa section, comme le fait l'administrateur.
 */
export async function deplierSectionTelemetrie(
	page: Page,
	titre: string | RegExp,
): Promise<Locator> {
	const section = page.locator('details.card', {
		has: page.locator('summary', { hasText: titre }),
	});
	await section.locator('summary').click();
	await expect(section).toHaveAttribute('open', '');
	return section;
}

/**
 * Quelques équipements, de la forme que rend `GET /equipements` (#2442) — ceux que
 * les specs citent. Ils s'administrent en base : sans eux, sélecteurs et libellés
 * resteraient vides. Une spec qui en veut d'autres les rend par `simulerApi`.
 */
export const EQUIPEMENTS_TEMOINS = (
	[
		['ascenseur', 'Ascenseur', 'arrow-up-down', 'ASC.', false],
		['plomberie', 'Plomberie', 'droplet', 'PLOMB.', false],
		['extincteurs', 'Extincteurs', 'fire-extinguisher', 'EXTINC.', false],
		['toiture', 'Toiture', 'home', 'TOIT.', false],
		['assurance', 'Assurance', 'shield', 'ASSUR.', true],
		['syndic', 'Syndic', 'building-2', 'SYNDIC', true],
		['autre', 'Autre', 'wrench', 'AUTRE', true],
	] as const
).map(([code, libelle, icone, abreviation, systeme], i) => ({
	id: i + 1,
	code,
	libelle,
	icone,
	abreviation,
	description: null,
	ordre: i + 1,
	actif: true,
	systeme,
	pour_affaires: code !== 'assurance' && code !== 'syndic',
	perimetres: [] as string[],
}));

const REPONSES_PAR_DEFAUT: Record<string, unknown> = {
	//  `Equipement[]` : le cache des équipements, chargé par la mise en page (#2442).
	'/api/equipements': EQUIPEMENTS_TEMOINS,
	//  `TableauTelemetrie` : l'onglet Télémétrie lit `adoption.par_profil`…
	'/api/telemetry/dashboard': TABLEAU_TELEMETRIE_VIDE,
	//  `FluxResponse` : `RaccourcisRapides` lit `sante.tickets_ouverts`.
	'/api/flux': { items: [], sante: {}, delai_recent_jours: 30 },
	//  `santeMaintenance` : `TachesPlanifiees` lit `taches`, `anomalies_recentes`
	//  et la fenêtre qui les borne.
	'/api/admin/maintenance/sante': {
		taches: [],
		anomalies_recentes: [],
		anomalies_fenetre_jours: 7,
	},
	//  `PointCourant`, `ParticipantsPoint` : le point CS / Syndic du Suivi des
	//  affaires (#2041) — sans point ouvert, et un annuaire vide.
	'/api/points-conseil/courant': { compte_rendu: null, reprise: null },
	'/api/points-conseil/participants': {
		conseil: [],
		syndic: [],
		lieux: [],
		moyens: [],
		etats_validation: [],
		categories_seance: [],
	},
	'/api/points-conseil/historique': [],
	//  `TextesLegauxSource` : l'administration lit la source des textes légaux et
	//  leur constat (#2065) — relus, rien à signaler.
	'/api/config/textes-legaux': {
		textes: { mentions_legales: '', politique_confidentialite: '' },
		champs: [],
		contact: '',
		etat: { a_relire: false, textes: [] },
	},
	//  `ConsommationIA`.
	'/api/config/llm-consommation': { mois: [], limites: [], mois_courant: '' },
	//  `PaletteCopropriete[]` : les palettes offertes sous le logo (#2379).
	'/api/config/palettes': [],
	//  `ServiceCopropriete[]` : l'administration grise l'onglet d'un service coupé.
	'/api/config/services': [],
	//  `JournalEnvoiWhatsApp[]`, `MessagePlanifieWhatsApp[]` : l'onglet WhatsApp.
	'/api/config/whatsapp-logs': [],
	'/api/config/whatsapp-scheduled': [],
	//  `JournalCourriels` : Espace CS › Courriels (#1447).
	'/api/courriels-affaires': { limite: 20, messages: [] },
	//  `PropositionsLocation` : « Mes lots » d'un locataire lit ses trois listes.
	'/api/lots/ma-location/propositions': {
		proprietaire: null,
		appartement: [],
		cave: [],
		parking: [],
	},
	//  `bailleur.monBail()` rend `null` sans bail — une liste vide passerait pour un bail.
	'/api/bailleur/mon-bail': null,
	//  `InscriptionInstallation` : la carte Installation lit `etat` et `raison` (#1878).
	'/api/admin/installation/inscription': {
		etat: 'limitee',
		raison: 'installation non inscrite au registre',
		identifiant: null,
		canal: null,
		version_cible: null,
		epoque: null,
		echeance: null,
		renouvellement_en_retard: false,
		inscrite_le: null,
		dernier_renouvellement_le: null,
		dernier_rapport_le: null,
		derniere_erreur: null,
		contact: null,
		conditions_acceptees: null,
		conditions_en_vigueur: 1,
		peut_s_inscrire: true,
		essai_refuse: false,
		registre_url: 'https://registre.example',
	},
	//  `ConsignesArrivant` : Espace CS › Annuaire lit `consignes` (#1727).
	'/api/admin/consignes-arrivant': { consignes: [], personnalisees: false },
	//  `reglement.acces()` : Ma résidence le lit pour montrer l'onglet Règlement.
	'/api/reglement/acces': { acces: true },
	//  `EtatReglement` : l'onglet Règlement lit `texte_disponible` et `lien_reglement`.
	'/api/reglement': {
		disponible: false,
		texte_disponible: false,
		lien_reglement: null,
		categorie_id: null,
		categorie_ag_id: null,
		provenance: null,
	},
	//  `EtatTranscriptions` : l'administration lit la section des PV d'AG (29/10/2026).
	'/api/reglement/transcriptions': { disponible: false, pvs: [] },
};

/**
 * **Rendre un écran authentifié avec l'API simulée.**
 *
 * Tout est derrière une connexion : un test qui chercherait l'écran sans compte
 * serait sauté, donc faux vert (`cible-tactile.spec.ts`). On rend le VRAI écran,
 * avec `MEMBRE_CS` pour `/api/auth/me`, `REPONSES_PAR_DEFAUT` pour leurs
 * chemins, un objet vide pour la configuration, et une liste vide pour le
 * reste — sauf ce que `reponses` rend pour un chemin.
 *
 * ⚠️ Le CHEMIN doit commencer par `/api/` : un motif `/api/` n'importe où
 * intercepte aussi le module source `/src/lib/api/…`, et la page tombe en 500.
 * Écrit ici une fois : trois tests le recopiaient, avec son piège.
 */
export async function simulerApi(
	page: Page,
	reponses: (chemin: string) => unknown = () => undefined,
): Promise<void> {
	await page.route(
		(url) => url.pathname.startsWith('/api/'),
		(route) => {
			const chemin = new URL(route.request().url()).pathname;
			let corps = reponses(chemin);
			if (corps === undefined) {
				if (chemin === '/api/auth/me') corps = MEMBRE_CS;
				else if (chemin in REPONSES_PAR_DEFAUT) corps = REPONSES_PAR_DEFAUT[chemin];
				else if (/config|pages|parametres|sante|epingles/.test(chemin)) corps = {};
				else corps = [];
			}
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify(corps),
			});
		},
	);
}

/**
 * **Retenir des lectures de l'API jusqu'à `relacher()`** — pour prouver qu'un
 * écran n'attend pas ce qu'il n'affiche pas (#1842, #1843, #1845).
 *
 * `retenu` choisit les chemins ; `corps` rend, une fois relâchée, la réponse de
 * chacun (une liste vide par défaut). À appeler APRÈS `simulerApi` : Playwright
 * essaie les routes de la plus récente à la plus ancienne. Écrite ici : deux
 * specs en recopiaient le mécanisme, et un troisième le prenait.
 */
export async function retenirApi(
	page: Page,
	retenu: (chemin: string) => boolean,
	corps: (chemin: string) => unknown = () => [],
): Promise<() => void> {
	return retenirRoute(
		page,
		(url) => retenu(url.pathname),
		(route) =>
			route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify(corps(new URL(route.request().url()).pathname)),
			}),
	);
}

/**
 * **Le module d'un composant, reconnu à son URL — lui seul** (#1940, 14/10/2026).
 *
 * Sous Vite, un composant qui porte un `<style>` part en DEUX demandes au même
 * chemin : le module, puis sa feuille (`…svelte?svelte&type=style&lang.css`).
 * Les specs comparaient le seul chemin et comptaient donc les deux : « le survol
 * précharge exactement une fois » réussissait quand `expect.poll` lisait entre
 * les deux demandes, et échouait sinon — au hasard, une fois en CI (#1939).
 * Ce prédicat était recopié dans quatre specs.
 */
export function estLeModule(url: URL | string, composant: string): boolean {
	const u = typeof url === 'string' ? new URL(url) : url;
	return u.pathname.endsWith(`/${composant}`) && !u.searchParams.has('svelte');
}

/**
 * **Retenir le module d'un composant chargé au geste jusqu'à `relacher()`** — pour
 * voir l'attente que l'écran annonce pendant qu'il arrive (`ChargementDiffere`).
 * Écrit trois fois à l'identique avant #1940.
 */
export function retenirModule(page: Page, composant: string): Promise<() => void> {
	return retenirRoute(
		page,
		(url) => estLeModule(url, composant),
		(route) => route.continue(),
	);
}

/** Le mécanisme commun : la requête attend `relacher()`, puis `suite` la traite. */
async function retenirRoute(
	page: Page,
	retenue: (url: URL) => boolean,
	suite: (route: Route) => Promise<void>,
): Promise<() => void> {
	let relacher: () => void = () => {};
	const relache = new Promise<void>((r) => (relacher = r));
	await page.route(retenue, async (route) => {
		await relache;
		await suite(route);
	});
	return () => relacher();
}

/**
 * **La boîte d'un élément, une fois qu'il a fini d'entrer** (#1625).
 *
 * 🔴 Une boîte de dialogue entre en 200 ms, de 96 % à 100 % (`modale-entree`,
 * `composants.css`). `boundingBox()` lu dans ce laps la mesure RÉDUITE : la marge
 * gauche des boutons de la confirmation, exactement 12 px à l'arrêt, en valait
 * 11,5 — et `>= 12` échouait une fois sur trente, sur des machines au repos, sans
 * jamais échouer deux rejeux de suite au même endroit. Le test mesurait
 * l'animation, pas la règle qu'il annonce.
 *
 * On attend donc que les animations finies de l'élément, de ses ancêtres et de
 * ses descendants se terminent (celles qui bouclent, un indicateur d'attente,
 * ne finiront jamais : elles sont laissées), puis que deux lectures successives
 * donnent la même boîte. La seconde lecture couvre ce que la première ne voit
 * pas — une mise en page encore en mouvement sans animation CSS.
 *
 * L'assertion du test ne s'affaiblit pas : elle porte sur la boîte à l'arrêt.
 */
export async function boiteStable(cible: Locator) {
	await cible.evaluate(async (el) => {
		const finies = () =>
			document.getAnimations().filter((a) => {
				const t = a.effect?.target;
				const fini = a.effect?.getComputedTiming().iterations !== Infinity;
				return fini && t && (t.contains(el) || el.contains(t));
			});
		await Promise.all(finies().map((a) => a.finished.catch(() => undefined)));
	});
	let precedente: string | null = null;
	let boite: Awaited<ReturnType<Locator['boundingBox']>> = null;
	await expect
		.poll(
			async () => {
				boite = await cible.boundingBox();
				const lue = JSON.stringify(boite);
				const stable = boite !== null && lue === precedente;
				precedente = lue;
				return stable;
			},
			{ message: 'la boîte ne se stabilise pas', intervals: [50], timeout: 5000 },
		)
		.toBe(true);
	return boite!;
}

/**
 * **Choisir une pastille de choix comme au doigt** — on clique la PASTILLE
 * visible (`label.pastille`) qui porte le radio, puis on vérifie qu'il est
 * coché. Jamais `radio.check({ force: true })` : le radio est masqué à 1 px, et
 * il sortait de la fenêtre du profil bureau depuis la v2.131.0 (#1810). Écrite
 * ici : deux specs la prennent (correction d'une actualité en affaire).
 */
export async function choisirPastille(page: Page, nom: RegExp | string) {
	const radio = page.getByRole('radio', { name: nom });
	await page.locator('label.pastille', { has: radio }).click();
	await expect(radio).toBeChecked();
}

export type Evenement = { page: string; action: string; detail?: string };

/**
 * **Les événements que le navigateur poste à la mesure d'audience** — route
 * enregistrée APRÈS `simulerApi`, donc essayée d'abord. Écrite ici : deux specs
 * la lisent (erreurs, durées d'affichage).
 */
export async function lotsEnvoyes(page: Page): Promise<Evenement[]> {
	const recus: Evenement[] = [];
	await page.route(
		(url) => url.pathname === '/api/telemetry/collect',
		(route) => {
			recus.push(...(JSON.parse(route.request().postData() ?? '{}').events ?? []));
			return route.fulfill({ status: 204 });
		},
	);
	return recus;
}

/** La file part au déchargement de la page — sans attendre ses 30 secondes. */
export async function viderLaFile(page: Page) {
	await page.evaluate(() => window.dispatchEvent(new Event('beforeunload')));
}
