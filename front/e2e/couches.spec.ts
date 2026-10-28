/**
 *  Deux couches superposées — une photo ouverte depuis une modale — et le
 *  document qu'elles se partagent : le défilement du fond, et la touche Échap.
 *
 *  ## 🔴 Pourquoi ce test existe (#1042, 24/09/2026)
 *
 *  `Modale` et `Lightbox` écrivaient chacune `body.style.overflow`, l'une avec un
 *  compteur, l'autre avec un booléen. La visionneuse fermée rendait donc le
 *  défilement à une page encore couverte par la modale. Et les deux écoutaient
 *  Échap sur `window` : une seule pression fermait les deux, saisie comprise.
 *
 *  `npm run lint:couches` impose le passage par `#lib/couche.ts` ; ce test
 *  mesure que le module fait ce qu'il promet, DANS un navigateur — le verrou
 *  est un style du document, et Échap un vrai évènement clavier.
 *
 *  ⚠️ Il importe le module par le serveur de développement (`webServer` de
 *  `playwright.config.ts`) : les écrans qui ouvrent une modale sont derrière une
 *  connexion, donc le témoin se pose dans une page publique
 *  (`standards/05-tests-et-garde-fous.md` §13).
 */
import { attendreHydratation, expect, test } from './aides';

type Temoin = { overflow: string; fermees: string[] };
/** Le témoin que `beforeEach` pose sur `window`. */
type Couches = { poser: (nom: string) => void; fermees: string[] };

test.describe('Les couches superposées', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/auth/connexion');
		await attendreHydratation(page);
		await page.evaluate(async () => {
			const { poserCouche } = await import('/src/lib/couche.ts');
			const w = window as unknown as Record<string, unknown>;
			const fermees: string[] = [];
			const retraits: Record<string, () => void> = {};
			const poser = (nom: string) => {
				retraits[nom] = poserCouche(() => {
					fermees.push(nom);
					retraits[nom]();
				});
			};
			w.__couches = { poser, retraits, fermees };
		});
	});

	const lire = (page: import('@playwright/test').Page) =>
		page.evaluate((): Temoin => ({
			overflow: document.body.style.overflow,
			fermees: [...(window as unknown as { __couches: Couches }).__couches.fermees],
		}));

	test('Échap ne ferme que la couche du dessus, et le fond reste bloqué dessous', async ({
		page,
	}) => {
		await page.evaluate(() => {
			const c = (window as unknown as { __couches: Couches }).__couches;
			c.poser('modale');
			c.poser('photo');
		});
		expect((await lire(page)).overflow).toBe('hidden');

		await page.keyboard.press('Escape');
		let t = await lire(page);
		expect(t.fermees, 'une pression a fermé plus d’une couche').toEqual(['photo']);
		expect(t.overflow, 'la photo fermée a rendu le défilement sous la modale').toBe('hidden');

		await page.keyboard.press('Escape');
		t = await lire(page);
		expect(t.fermees).toEqual(['photo', 'modale']);
		expect(t.overflow, 'plus aucune couche : le défilement doit revenir').toBe('');

		//  Pile vide : l'écouteur est retiré, Échap ne rappelle plus rien.
		await page.keyboard.press('Escape');
		expect((await lire(page)).fermees).toEqual(['photo', 'modale']);
	});

	test('une couche du dessous démontée la première ne vole pas Échap au-dessus', async ({
		page,
	}) => {
		await page.evaluate(() => {
			const c = (window as unknown as { __couches: Couches }).__couches;
			c.poser('modale');
			c.poser('photo');
			//  Navigation : la modale se démonte sans être fermée — deux fois,
			//  comme `fermer` puis `onDestroy`. Le retrait doit être idempotent.
			c.retraits.modale();
			c.retraits.modale();
		});
		expect((await lire(page)).overflow, 'le retrait répété a sous-compté').toBe('hidden');

		await page.keyboard.press('Escape');
		const t = await lire(page);
		expect(t.fermees).toEqual(['photo']);
		expect(t.overflow).toBe('');
	});
});
