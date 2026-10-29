/*
 *  **Les listes et les cartes se lisent au thème sombre** (#2174, lot S4b).
 *
 *  La zone : la page Affaires (liste, carte dépliée et ses trois étapes, Archives,
 *  recherche), le kanban, l'accueil (fil d'activité, bandeau Épinglé, kanban
 *  condensé) et les cartes de la communauté. Chaque écran est rendu avec l'API
 *  simulée, passé au sombre forcé, et chacun de ses textes mesuré sur le fond
 *  qu'il a vraiment (`contraste-ecran`). Aucun ne doit tomber sous l'AA, aucune
 *  surface ne doit rester claire.
 *
 *  ## Les écarts DÉCLARÉS — et chacun doit encore servir
 *
 *  Un écart qui existe aussi au CLAIR n'est pas un défaut du sombre : il se
 *  corrige dans son ticket, et il se déclare ici avec lui, sur l'écran où il se
 *  voit. Le test de cet écran échoue s'il ne le relève plus — on le retire alors.
 *  Les deux de #2296 (pastilles de périmètre, colonnes vides repliées) sont
 *  corrigés : la même zone est relevée au CLAIR, plus bas, sans aucun écart.
 */
import { expect, simulerApi, test, attendreHydratation } from './aides';
import { forcerTheme, releverContrastes } from './contraste-ecran';
import type { Page } from '@playwright/test';
import { AFFAIRE, ETAT_SYNTHESE, FIL } from './affaire-close-donnees';

const ACCUEIL = 'l’accueil : fil, Épinglé et kanban';
const DEPLIEE = 'une affaire dépliée, ses étapes et sa synthèse';

/**
 *  Un écart : l'écran où il se voit, ce qu'il touche (un `contraste` ou une
 *  `surface` claire), le motif qui le reconnaît dans le relevé, et sa raison.
 *  `profil` : il ne se voit que là (au téléphone, le kanban d'accueil défile
 *  colonne par colonne et n'en replie aucune).
 */
type Ecart = {
	ecran: string;
	genre: 'contraste' | 'surface';
	motif: RegExp;
	raison: string;
	profil?: string;
};
const ECARTS: Ecart[] = [
	{
		ecran: DEPLIEE,
		genre: 'surface',
		//  La frise et le rythme de la synthèse : des MARQUES de données, pas des
		//  fonds — claires au sombre, elles ressortent comme elles le doivent.
		motif: /(frise|histogramme|graphique-cle)[^—]* — fond/,
		raison: 'marques de données de la synthèse (frise, rythme, légende)',
	},
];

const affaire = (id: number, extra: Record<string, unknown>) => ({
	...AFFAIRE,
	id,
	numero: `TK-${id}`,
	priorite: 'normale',
	assiste_ia: true,
	...extra,
});
const AFFAIRES = [
	{ ...AFFAIRE, photos_urls: ['/uploads/demande.jpg'] },
	affaire(43, { titre: 'Ascenseur bloqué', statut: 'ouvert', priorite: 'haute', epingle: true }),
	affaire(44, {
		titre: 'Ravalement',
		categorie: 'etude_travaux',
		statut: 'en_ag',
		public_cible: ['locataires'],
	}),
	affaire(45, {
		titre: 'Bruit nocturne',
		categorie: 'nuisance',
		statut: 'en_cours',
		reserve_perimetre: true,
	}),
	affaire(46, {
		titre: 'Taille des haies',
		categorie: 'espaces_verts',
		statut: 'chez_prestataire',
		suivi_kanban: true,
	}),
	affaire(47, {
		titre: 'Coupure d’eau',
		categorie: 'actualite',
		statut: 'ouvert',
		natures: ['actualite'],
	}),
	affaire(48, {
		titre: 'Badge perdu',
		categorie: 'acces_accueil',
		statut: 'annulé',
		confidentiel: true,
	}),
	affaire(49, {
		titre: 'Ancienne fuite',
		categorie: 'sinistre',
		archivee: true,
		cree_le: '2025-03-01T10:00:00',
	}),
];
const TROUVEE = {
	ticket_id: 43,
	ou: 'suite',
	date: '2026-10-19T08:00:00',
	auteur: 'CS Témoin',
	extrait: [
		{ texte: 'Le plombier confirme une ', surligne: false },
		{ texte: 'fuite', surligne: true },
	],
};

const ligne = (a: (typeof AFFAIRES)[number]) => ({
	numero: a.numero,
	categorie: a.categorie,
	statut: a.statut,
	priorite: a.priorite,
	perimetre_cible: [],
	public_cible: null,
	assiste_ia: true,
});
/** Une carte du fil par type de rubrique : chacun a sa teinte (`#lib/flux`). */
const TYPES = ['annonce', 'idee', 'sondage_ouvert', 'point_conseil', 'diagnostic', 'annuaire'];
const FLUX = {
	items: [
		{
			id: 'tk_43',
			type: 'ticket_ouvert',
			date: '2026-10-28T10:00:00',
			titre: 'Ascenseur bloqué',
			detail: 'Cabine arrêtée au 3ᵉ.',
			badges: ['#TK-43', 'Panne', 'urgent'],
			meta: { ticket_id: 43, auteur: 'CS Témoin', affaire: ligne(AFFAIRES[1]) },
		},
		{
			id: 'tk_42',
			type: 'ticket_resolu',
			date: '2026-10-28T09:00:00',
			titre: AFFAIRE.titre,
			detail: 'Résolu en 08j',
			badges: ['#TK-142'],
			meta: {
				ticket_id: 42,
				auteur: 'CS Témoin',
				affaire: ligne(AFFAIRES[0]),
				evol_contenu: 'Raccord remplacé.',
				demande: { le: AFFAIRE.cree_le, photos_urls: [], fichiers_urls: [] },
			},
		},
		...TYPES.map((type, i) => ({
			id: `${type}_${i}`,
			type,
			date: '2026-10-28T08:00:00',
			titre: `Rubrique ${type}`,
			detail: 'Un extrait du contenu.',
			badges: [],
			meta: { auteur: 'CS Témoin', perimetre_codes: ['bat:1'] },
		})),
		{
			id: 'pu_9',
			type: 'publication',
			date: '2026-10-20T08:00:00',
			titre: 'Règlement des caves',
			detail: 'À relire.',
			badges: [],
			meta: { auteur: 'CS Témoin', epingle: true },
		},
	],
	sante: { tickets_ouverts: 3 },
	delai_recent_jours: 30,
};
const CIBLAGE = { perimetre_cible: ['bat:1'], public_cible: ['locataires'], assiste_ia: true };
const COMMUNAUTE: Record<string, unknown> = {
	'/api/annonces': [
		{
			...CIBLAGE,
			id: 3,
			titre: 'Vélo enfant',
			description: 'Bon état',
			type_annonce: 'vente',
			statut: 'reserve',
			categorie: 'divers',
			prix: 40,
			negotiable: true,
			photos: ['/uploads/velo.jpg'],
			auteur_prenom: 'Jeanne',
			auteur_nom: 'MARTIN',
			est_auteur: true,
			archivee: false,
			cree_le: '2026-10-26T10:00:00',
		},
	],
	'/api/idees': [
		{
			...CIBLAGE,
			id: 4,
			titre: 'Un composteur',
			description: 'Dans la cour',
			statut: 'retenue',
			nb_votes: 2,
			mon_vote: true,
			auteur_id: 9,
			cree_le: '2026-10-26T10:00:00',
		},
	],
	'/api/sondages': [
		{
			...CIBLAGE,
			id: 5,
			question: 'Repeindre le hall ?',
			cloture: true,
			cloture_le: '2026-10-20T10:00:00',
			nb_votants: 3,
			auteur_id: 9,
			cree_le: '2026-10-10T10:00:00',
		},
	],
};
const PHOTO = `<svg xmlns="http://www.w3.org/2000/svg" width="40" height="30"><rect width="40" height="30" fill="#b9c6d6"/></svg>`;

async function simuler(page: Page) {
	await page.route('**/uploads/**', (r) =>
		r.fulfill({ contentType: 'image/svg+xml', body: PHOTO }),
	);
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/flux') return FLUX;
		if (chemin === '/api/tickets') return AFFAIRES;
		if (chemin === '/api/tickets/recherche') return [TROUVEE];
		if (chemin === '/api/tickets/42/evolutions') return FIL;
		if (chemin === '/api/tickets/42/synthese') return ETAT_SYNTHESE;
		const fiche = chemin.match(/^\/api\/tickets\/(\d+)$/);
		if (fiche) return AFFAIRES.find((a) => a.id === Number(fiche[1]));
		return COMMUNAUTE[chemin];
	});
}

const ECRANS: {
	titre: string;
	route: string;
	temoin: string;
	geste?: (p: Page) => Promise<void>;
}[] = [
	{ titre: 'la liste des affaires', route: '/tickets', temoin: '.carte-liste .ec-tags' },
	{
		titre: DEPLIEE,
		route: '/tickets',
		temoin: '.carte-corps',
		geste: async (p) => {
			await p.locator('.carte-liste').first().click();
			await p.getByRole('button', { name: /La synthèse/ }).click();
		},
	},
	{ titre: 'les Archives', route: '/tickets/archives', temoin: '.carte-liste' },
	{
		titre: 'un résultat de recherche',
		route: '/tickets',
		temoin: 'mark',
		geste: (p) => p.getByRole('searchbox').fill('fuite'),
	},
	{ titre: 'le kanban', route: '/tickets/kanban', temoin: '.kanban-card' },
	{ titre: ACCUEIL, route: '/tableau-de-bord', temoin: '.flux-groupes .ec-tags' },
	{ titre: 'les petites annonces', route: '/annonces', temoin: '.carte-liste .ec-tags' },
	{ titre: 'la boîte à idées', route: '/idees', temoin: '.carte-liste .ec-tags' },
	{ titre: 'les sondages', route: '/sondages', temoin: '.ec-tags' },
];

/** Relève un écran au thème donné et confronte le relevé aux écarts déclarés. */
async function releverEcran(
	page: Page,
	e: (typeof ECRANS)[number],
	theme: 'clair' | 'sombre',
	ecarts: Ecart[],
) {
	await simuler(page);
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(e.route);
	await attendreHydratation(page);
	await forcerTheme(page, theme);
	await e.geste?.(page);
	//  Cas zéro : l'écran a rendu ce qu'on vient mesurer.
	await expect(page.locator(e.temoin).first()).toBeVisible();
	await page.mouse.move(0, 0);

	const { contrastes, surfacesClaires, mesures } = await releverContrastes(page);
	expect(mesures, 'aucun texte mesuré : le relevé est passé à vide').toBeGreaterThan(0);
	//  Une surface claire n'est une faute qu'au sombre.
	const releve = { contraste: contrastes, surface: theme === 'sombre' ? surfacesClaires : [] };
	for (const genre of ['contraste', 'surface'] as const) {
		const declares = ecarts.filter((x) => x.genre === genre);
		expect(
			releve[genre].filter((l) => !declares.some((x) => x.motif.test(l))),
			genre === 'contraste' ? `texte(s) sous l’AA au ${theme}` : 'surface(s) restée(s) claire(s)',
		).toEqual([]);
		for (const x of declares)
			expect(
				releve[genre].some((l) => x.motif.test(l)),
				`écart déclaré qui ne sert plus — le retirer : ${x.raison}`,
			).toBe(true);
	}
}

const ecartsDe = (ecarts: Ecart[], ecran: string, profil: string) =>
	ecarts.filter((x) => x.ecran === ecran && (!x.profil || x.profil === profil));

test.describe('@sombre listes et cartes', () => {
	for (const e of ECRANS)
		test(`${e.titre} : lisible au sombre`, ({ page }, info) =>
			releverEcran(page, e, 'sombre', ecartsDe(ECARTS, e.titre, info.project.name)));
});

/*  **Et au CLAIR** (#2296) : les mêmes écrans, le même relevé. Le thème clair
    tient l'AA à l'écran comme dans la table des paires — aucun écart déclaré. */
test.describe('@clair listes et cartes', () => {
	for (const e of ECRANS)
		test(`${e.titre} : lisible au clair`, ({ page }) => releverEcran(page, e, 'clair', []));
});
