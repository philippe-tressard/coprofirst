/*
 *  **À l'impression du reporting, la navigation ne sort pas sur le papier**
 *  (#2306, 30/10/2026).
 *
 *  Les règles `body.print-reporting …` d'`ecrans.css` étaient écrites
 *  `:global(…)` : syntaxe de Svelte, que rien ne traduit dans une feuille
 *  globale — le navigateur les abandonnait, et la barre latérale s'imprimait
 *  avec le rapport. Ce test pose la classe comme `OngletReporting`, passe la
 *  page en média d'impression et lit le style CALCULÉ : c'est la règle telle
 *  que le navigateur l'a gardée, pas telle qu'elle est écrite.
 *  🔒 aussi `npm run lint:global-feuille-globale`, qui refuse la syntaxe.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

test('impression du reporting : la navigation est masquée, l’en-tête du rapport paraît', async ({
	page,
}) => {
	await simulerApi(page, () => undefined);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);
	//  La coque `(app)` n'est pas montée sur un écran public : on y pose les
	//  éléments que les règles visent, tels que la coque les nomme.
	await page.evaluate(() => {
		for (const classe of ['sidebar', 'mobile-topbar', 'app-footer', 'reporting-print-header']) {
			const el = document.createElement('div');
			el.className = classe;
			el.textContent = classe;
			document.body.append(el);
		}
		document.body.classList.add('print-reporting');
	});
	const affichage = (classe: string) =>
		page.locator(`body > .${classe}`).evaluate((el) => getComputedStyle(el).display);

	//  À l'écran, la classe ne change rien (04/08/2026 : elle masquait la navigation).
	expect(await affichage('sidebar')).toBe('block');

	await page.emulateMedia({ media: 'print' });
	for (const classe of ['sidebar', 'mobile-topbar', 'app-footer'])
		expect(await affichage(classe), `${classe} s’imprime`).toBe('none');
	expect(await affichage('reporting-print-header')).toBe('block');
});
