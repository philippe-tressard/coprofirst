/**
 *  La GOUTTIÈRE d'une carte d'affaire : la date, puis la nature — et rien ne
 *  dépasse (maquette B, 10/10/2026 ; #1220 pour le mot de la nature).
 *
 *  ## 🔴 Pourquoi ce test existe
 *
 *  24/09/2026 : la gouttière teintée écrivait sa nature à la verticale, et
 *  « CALENDRIER » dépassait d'une carte d'une ligne. Le mot a été couché, puis
 *  abrégé (ACTU. · CAL. · AFF.) — ce test mesurait qu'il tenait dans la bande.
 *
 *  10/10/2026 : la maquette B (« Gouttière », choisie parmi cinq) y fait monter
 *  la DATE, et y aligne les libellés des filtres. Trois risques neufs, que rien
 *  d'autre ne verrait :
 *    • une date affichée DEUX fois (gouttière et dernière ligne) — deux faits ;
 *    • un mot, un jour ou un libellé plus LARGE que la colonne, avec la police
 *      que le navigateur applique vraiment (`standards/04` §14) ;
 *    • au téléphone, une colonne qui mangerait le titre au lieu de passer
 *      au-dessus de lui.
 *
 *  Les trois natures sont rendues (API simulée, compte CS) : la nature vient du
 *  serveur (`Ticket.natures`), jamais redérivée — le test la lui donne.
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';

const BASE = {
	statut: 'en_cours',
	priorite: 'normale',
	perimetre_cible: [],
	public_cible: null,
	reserve_perimetre: false,
	confidentiel: false,
	epingle: false,
	assiste_ia: false,
	auteur_id: 2,
	auteur_nom: 'Jean-Hervé KERBRAT',
	description: 'Une description de quelques mots.',
	photos_urls: [],
	fichiers_urls: [],
	cree_le: '2026-10-05T09:00:00',
	mis_a_jour_le: '2026-10-09T15:00:00',
};
const AFFAIRES = [
	{
		...BASE,
		id: 1,
		numero: 'TK-1',
		titre: 'Porte du hall',
		categorie: 'panne',
		natures: ['activite'],
	},
	{
		...BASE,
		id: 2,
		numero: 'TK-2',
		titre: 'Ascenseur à l’arrêt',
		categorie: 'travaux',
		debut: '2026-10-12T08:00:00',
		natures: ['calendrier'],
	},
	{
		...BASE,
		id: 3,
		numero: 'TK-3',
		titre: 'Coupure d’eau',
		categorie: 'actualite',
		natures: ['actualite'],
	},
];

const ouvrir = async (page: Page) => {
	await simulerApi(page, (chemin) => (chemin === '/api/tickets' ? AFFAIRES : undefined));
	await page.goto('/tickets');
	await expect(page.locator('.gouttiere')).toHaveCount(AFFAIRES.length);
};

test('chaque carte porte sa date et sa nature dans la gouttière, une fois', async ({ page }) => {
	await ouvrir(page);
	const mesures = await page.locator('.carte-liste[data-nature]').evaluateAll((cartes) =>
		cartes.map((c) => {
			const g = c.querySelector('.gouttiere')!;
			return {
				nature: c.getAttribute('data-nature'),
				abrege: g.querySelector('abbr')?.textContent?.trim(),
				date: g.querySelector('time')?.textContent?.replace(/\s+/g, ' ').trim(),
				dateEnBas: c.querySelectorAll('.ec-date').length,
			};
		}),
	);
	//  La date rendue est celle de `fmtDate` (`mis_a_jour_le`), recollée.
	const attendue = await page.evaluate(async () => {
		const { fmtDate } = await import('/src/lib/date.ts');
		return fmtDate('2026-10-09T15:00:00');
	});
	expect(mesures.map((m) => m.nature).sort()).toEqual(['activite', 'actualite', 'calendrier']);
	for (const m of mesures) {
		expect(m.abrege, `${m.nature} : pas de nature dans la gouttière`).toMatch(/^[A-Z]+\.$/);
		expect(m.date, `${m.nature} : la date de la gouttière`).toBe(attendue);
		expect(m.dateEnBas, `${m.nature} : la date est aussi sur la dernière ligne`).toBe(0);
	}
});

test('rien ne dépasse de la gouttière, ni des libellés alignés sur elle', async ({
	page,
}, info) => {
	await ouvrir(page);
	if (info.project.name !== 'bureau') {
		//  Au téléphone, la colonne devient une LIGNE au-dessus du titre.
		const placement = await page
			.locator('.carte-liste[data-nature]')
			.first()
			.evaluate((c) => {
				const g = c.querySelector('.gouttiere')!.getBoundingClientRect();
				const t = c.querySelector('.ec-titre')!.getBoundingClientRect();
				return {
					basGouttiere: g.bottom,
					hautTitre: t.top,
					largeurTitre: t.width,
					carte: c.clientWidth,
				};
			});
		expect(placement.basGouttiere).toBeLessThanOrEqual(placement.hautTitre + 1);
		expect(placement.largeurTitre, 'le titre a perdu sa largeur').toBeGreaterThan(
			placement.carte / 2,
		);
		return;
	}
	const debords = await page.evaluate(() => {
		const sortie: string[] = [];
		let mesures = 0;
		for (const g of document.querySelectorAll<HTMLElement>('.gouttiere')) {
			const bord = g.getBoundingClientRect().right;
			for (const el of g.querySelectorAll<HTMLElement>('.g-jour, .g-mois, abbr')) {
				mesures++;
				if (el.getBoundingClientRect().right > bord - 2)
					sortie.push(`gouttière : ${el.textContent}`);
			}
		}
		const grille = document.querySelector<HTMLElement>('.filtres-gouttiere')!;
		const colonne = parseFloat(getComputedStyle(grille).gridTemplateColumns);
		const gauche = grille.getBoundingClientRect().left;
		for (const l of grille.querySelectorAll<HTMLElement>('.libelle-devant')) {
			mesures++;
			//  La largeur du TEXTE, pas de la boîte : une boîte de grille se borne à
			//  sa colonne, et le texte qui en sort ne l'élargit pas.
			const r = document.createRange();
			r.selectNodeContents(l);
			if (r.getBoundingClientRect().right > gauche + colonne)
				sortie.push(`libellé : ${l.textContent}`);
		}
		return { sortie, mesures };
	});
	//  Cas zéro : 3 cartes × (jour, mois, nature) et 3 libellés ont été mesurés.
	expect(debords.mesures, 'rien n’a été mesuré').toBe(AFFAIRES.length * 3 + 3);
	expect(debords.sortie, 'ces textes sortent de leur colonne').toEqual([]);
});

/**
 *  🔴 La gouttière ne déborde pas d'une carte COURTE (#1819). Posée en absolu,
 *  elle ne comptait pas dans la hauteur de la carte : sous une affaire sans
 *  texte, un contrat ou un relevé, le mot du classement sortait par le bas
 *  (121 px demandés pour une carte de 82, mesuré au navigateur). Elle est
 *  devenue la première colonne d'une grille : elle fait grandir la carte, et
 *  s'étire jusqu'à son bas.
 */
test('une carte courte grandit avec sa gouttière, qui s’étire jusqu’à son bas', async ({
	page,
}, info) => {
	test.skip(info.project.name !== 'bureau', 'au téléphone, la gouttière est une ligne');
	const COURTE = { ...AFFAIRES[0], id: 9, titre: 'Ampoule', description: '' };
	await simulerApi(page, (chemin) => (chemin === '/api/tickets' ? [COURTE] : undefined));
	await page.goto('/tickets');
	const m = await page.locator('.carte-liste.a-gouttiere').evaluate((c) => {
		const carte = c.getBoundingClientRect();
		const g = c.querySelector<HTMLElement>('.gouttiere')!;
		const bas = Math.max(...[...g.children].map((e) => e.getBoundingClientRect().bottom));
		return {
			basCarte: carte.bottom,
			basGouttiere: g.getBoundingClientRect().bottom,
			basContenu: bas,
		};
	});
	expect(m.basContenu, 'le classement sort sous la carte').toBeLessThanOrEqual(m.basCarte);
	//  La colonne s'étire jusqu'au bas de la carte (au filet près).
	expect(Math.abs(m.basCarte - m.basGouttiere)).toBeLessThanOrEqual(2);
});
