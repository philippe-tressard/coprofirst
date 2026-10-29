/**
 *  Les teintes tenues en TypeScript se RÉSOLVENT en couleurs dans le navigateur
 *  (mode sombre, #2174 — lot S2).
 *
 *  ## Pourquoi un test de navigateur
 *
 *  Le code désigne désormais ses teintes par un jeton (`'var(--teinte-6)'`), dont
 *  `socle.css` porte la valeur — parfois par un renvoi (`--kanban-ag` →
 *  `--teinte-6`, `--teinte-13` → `--color-jaune-texte`). `lint:variables-css` dit
 *  que chaque nom est DÉFINI ; il ne dit pas que la chaîne aboutit à une couleur.
 *  Une variable qui ne se résout pas laisse la propriété à sa valeur initiale :
 *  une pastille de périmètre sans fond, sans un mot (`standards/04` §14 : observer
 *  la chose, pas son enregistrement).
 *
 *  La palette est lue dans `teinte.ts`, module pur sans import `#lib` : un
 *  import qui tire le dossier des bibliothèques casserait la collecte de toute la
 *  suite.
 *
 *  L'écran de connexion est public et charge `socle.css` comme tout écran.
 */
import { PALETTE_PERIMETRE, TEINTE_COPROPRIETE } from '../src/lib/perimetres/teinte';
import { attendreHydratation, expect, test } from './aides';

test.describe('Les teintes désignées par un jeton', () => {
	test('la palette des périmètres : treize aplats distincts, plus le gris de la copropriété', async ({
		page,
	}) => {
		await page.goto('/auth/connexion');
		await attendreHydratation(page);

		const teintes = [...PALETTE_PERIMETRE, TEINTE_COPROPRIETE];
		const couleurs = await page.evaluate((valeurs) => {
			return valeurs.map((valeur) => {
				const sonde = document.createElement('i');
				sonde.style.backgroundColor = valeur;
				document.body.append(sonde);
				const rendu = getComputedStyle(sonde).backgroundColor;
				sonde.remove();
				return rendu;
			});
		}, teintes);

		expect(couleurs, 'cas zéro : la palette n’est pas vide').toHaveLength(14);
		expect(couleurs, 'une variable sans valeur rend transparent').not.toContain('rgba(0, 0, 0, 0)');
		expect(new Set(couleurs).size, 'quatorze teintes, toutes distinctes').toBe(14);
		//  Les valeurs d'avant le lot : la première, le renvoi de la treizième, le gris.
		expect(couleurs[0]).toBe('rgb(239, 68, 68)'); //  #ef4444
		expect(couleurs[12]).toBe('rgb(161, 98, 7)'); //  #a16207, par `--color-jaune-texte`
		expect(couleurs[13]).toBe('rgb(107, 114, 128)'); //  #6b7280
	});

	test('un renvoi se résout : une étape du kanban a la teinte de sa palette', async ({ page }) => {
		await page.goto('/auth/connexion');
		await attendreHydratation(page);

		const rendu = await page.evaluate(() => {
			const lire = (jeton: string) => {
				const sonde = document.createElement('i');
				sonde.style.color = `var(${jeton})`;
				document.body.append(sonde);
				const couleur = getComputedStyle(sonde).color;
				sonde.remove();
				return couleur;
			};
			return {
				ag: lire('--kanban-ag'),
				palette: lire('--teinte-6'),
				annule: lire('--kanban-annule'),
				fil: lire('--fil-rouge'),
				orange: lire('--color-orange'),
			};
		});

		expect(rendu.ag).toBe(rendu.palette);
		expect(rendu.ag).toBe('rgb(139, 92, 246)'); //  #8b5cf6
		expect(rendu.annule).toBe('rgb(156, 163, 175)'); //  #9ca3af
		expect(rendu.fil).toBe('rgb(185, 28, 28)'); //  #b91c1c
		expect(rendu.orange).toBe('rgb(194, 65, 12)'); //  #c2410c
	});
});
