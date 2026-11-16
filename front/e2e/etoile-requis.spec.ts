/**
 *  L'astérisque d'un champ obligatoire est COLLÉE à son libellé.
 *
 *  ## 🔴 Pourquoi ce test existe (22/09/2026, signalé à l'écran)
 *
 *  La règle avait été livrée la veille (#1121) et le code l'écrivait bien : rien
 *  ne sépare `{titre}` du composant. Pourtant l'écran affichait
 *  **« PÉRIMÈTRE * »**, « DESCRIPTION * », « SAISI POUR * ».
 *
 *  La cause n'était pas dans les appelants mais **à l'intérieur** du composant :
 *
 *      <span class="requis">
 *        <span aria-hidden="true">*</span>     ← ce saut de ligne EST un espace
 *
 *  Un retour à la ligne entre deux éléments est un nœud de texte blanc, que le
 *  navigateur rend comme une espace. Aucune relecture de code ne le montre —
 *  le code paraît juste, et il l'est au sens de Svelte.
 *
 *  ⚠️ C'est pour cela que ce contrôle est un test de NAVIGATEUR et non un
 *  linter : ce qui est faux ici n'est pas le texte du fichier, c'est ce que le
 *  navigateur en fait. Un contrôle statique aurait dit vert (`standards/04`
 *  §14 : observer la chose, pas son enregistrement).
 *
 *  ## Ce qu'il mesure
 *
 *  L'écran de connexion est **public** : son champ « Email » est obligatoire et
 *  porte l'astérisque. Le texte lu doit donc finir par `EMAIL*` — sans espace,
 *  et en capitales, les deux règles du même lot.
 */
import { attendreHydratation, expect, test } from './aides';

test.describe("L'astérisque des champs obligatoires", () => {
	test('est collée au libellé, sans espace', async ({ page }) => {
		await page.goto('/auth/connexion');
		await attendreHydratation(page);

		const label = page.locator('label[for="email"]');
		await expect(label).toBeVisible();

		//  `innerText` rend le texte TEL QU'AFFICHÉ — capitales comprises, et
		//  espaces tels que le navigateur les a composés. `textContent` rendrait
		//  la source, donc exactement ce que ce test doit refuser de croire.
		//
		//  ⚠️ Le texte de rechange « obligatoire » en est retiré : il est destiné
		//  aux lecteurs d'écran et n'occupe aucune place à l'œil. Le clone est
		//  posé dans le MÊME parent pour hériter des mêmes styles — mesuré hors
		//  contexte, il rendrait autre chose que ce qui s'affiche.
		const affiche = (
			await label.evaluate((n) => {
				const clone = n.cloneNode(true) as HTMLElement;
				clone.querySelectorAll('.sr-only').forEach((e) => e.remove());
				n.after(clone);
				const texte = clone.innerText;
				clone.remove();
				return texte;
			})
		).trim();
		expect(affiche, "le libellé ne porte pas d'astérisque").toContain('*');
		expect(
			affiche,
			`« ${affiche} » — une espace s'est glissée avant l'astérisque (un saut de ligne dans le balisage suffit)`,
		).not.toMatch(/\s\*/);
	});

	test('le mot « obligatoire » est annoncé, la couleur ne suffisant pas', async ({ page }) => {
		await page.goto('/auth/connexion');
		await attendreHydratation(page);

		//  La couleur ne se lit pas au lecteur d'écran, et le rouge seul n'est
		//  jamais une information (`standards/11` §2). Le mot est dans l'arbre
		//  d'accessibilité, hors de l'œil.
		const label = page.locator('label[for="email"]');
		await expect(label.locator('.sr-only')).toHaveText('obligatoire');
	});

	test('elle est ROUGE tant que le champ est vide, et ne l’est plus ensuite', async ({ page }) => {
		await page.goto('/auth/connexion');
		await attendreHydratation(page);

		const etoile = page.locator('label[for="email"] span[class*="requis"]').first();
		const couleur = () => etoile.evaluate((n) => getComputedStyle(n).color);

		const vide = await couleur();
		await page.fill('#email', 'quelqu-un@exemple.test');
		const rempli = await couleur();

		//  🔴 On ne compare pas à une valeur écrite ici : la charte peut changer
		//  de rouge. Ce qui compte est que l'état du champ CHANGE la couleur —
		//  c'est toute la règle, et elle se mesure sans connaître la palette.
		expect(rempli, 'la couleur ne change pas quand le champ se remplit').not.toBe(vide);
	});
});

test.describe('L’étoile dans un libellé qui ENVELOPPE son champ (#1230)', () => {
	//  `label.field` est une colonne flex : un texte et une étoile posés
	//  directement dedans y deviennent deux éléments, et l'étoile tombe SOUS le
	//  libellé (« un * sous Début, c'est quoi ? », signalé le 24/09/2026). Le
	//  remède est un `<span>` qui les tient ensemble ; `lint:champs` l'exige.
	//  Le témoin reprend le balisage d'`EtoileRequis`, et le CSS réel du site.
	const etoile =
		'<span class="requis requis--vide"><span aria-hidden="true">*</span><span class="sr-only">obligatoire</span></span>';

	async function ecart(page: import('@playwright/test').Page, libelle: string) {
		return page.evaluate(
			({ libelle, etoile }) => {
				const temoin = document.createElement('div');
				temoin.innerHTML = `<label class="field">${libelle.replace('ETOILE', etoile)}<input type="date" /></label>`;
				document.querySelector('main, body')!.append(temoin);
				const star = temoin.querySelector('[aria-hidden="true"]')!.getBoundingClientRect();
				const range = document.createRange();
				const texte = [...temoin.querySelectorAll('label, label > span')]
					.flatMap((n) => [...n.childNodes])
					.find((n) => n.nodeType === Node.TEXT_NODE && n.textContent!.trim())!;
				range.selectNodeContents(texte);
				const mot = range.getBoundingClientRect();
				temoin.remove();
				return Math.abs(star.top - mot.top);
			},
			{ libelle, etoile },
		);
	}

	test('tenue par un <span>, l’étoile reste sur la ligne du libellé', async ({ page }) => {
		await page.goto('/auth/connexion');
		await attendreHydratation(page);
		expect(await ecart(page, '<span>Début ETOILE</span>'.replace(' ', ''))).toBeLessThan(4);
	});

	test('posée à nu dans le label, elle tombe — le test voit donc le défaut', async ({ page }) => {
		await page.goto('/auth/connexion');
		await attendreHydratation(page);
		expect(await ecart(page, 'DébutETOILE')).toBeGreaterThan(8);
	});
});

test.describe('L’étoile d’un GROUPE de champs (#1329)', () => {
	//  `LibelleGroupe` affichait son titre tel quel : « Copropriétaire aidé * »,
	//  une étoile tapée, noire, qui ne savait pas si le groupe était rempli.
	//  Depuis le 27/09/2026 elle passe par sa prop `requis`, donc par
	//  `EtoileRequis` — et elle suit l'état des DEUX champs du groupe.
	test('elle est portée par EtoileRequis, et rouge tant qu’un champ du groupe est vide', async ({
		page,
	}) => {
		await page.goto('/auth/inscription');
		await attendreHydratation(page);
		await page.selectOption('#statut', 'aidant');

		const titre = page.locator('#coproprietaire-aide-titre');
		await expect(titre, 'le groupe « Copropriétaire aidé » n’est pas rendu').toBeVisible();
		//  Une expression, pas une chaîne : Playwright normalise les espaces de
		//  l'attendu, et ' *' deviendrait '*' — l'étoile collée, justement.
		await expect(titre).not.toHaveText(/\s\*/);
		//  Le titre du groupe se lit comme le libellé du champ voisin — mêmes
		//  capitales, même espacement (#1329 : il restait en minuscules).
		const allure = (sel: string) =>
			page
				.locator(sel)
				.evaluate((n) => [getComputedStyle(n).textTransform, getComputedStyle(n).letterSpacing]);
		expect(await allure('#coproprietaire-aide-titre')).toEqual(await allure('label[for="statut"]'));
		const etoile = titre.locator('span[class*="requis"]');
		await expect(etoile).toHaveCount(1);
		const couleur = () => etoile.evaluate((n) => getComputedStyle(n).color);

		const vide = await couleur();
		await page.fill('#prenom-aide', 'Jeanne');
		expect(await couleur(), 'un seul champ rempli : le groupe reste incomplet').toBe(vide);
		await page.fill('#nom-aide', 'MARTIN');
		expect(await couleur(), 'le groupe rempli : l’étoile change').not.toBe(vide);
	});
});
