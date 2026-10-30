/*
 *  **Un séparateur ne finit jamais une ligne** (#2360, 30/10/2026).
 *
 *  La forme du dépôt, `{#if x}&nbsp;— {x}{/if}`, collait le séparateur au mot
 *  d'avant : au téléphone, la fiche d'un prestataire lisait « 📞 01 23 45 67 89 — »
 *  puis, seul à la ligne, le nom du contact. La règle (`#lib/separateurs`) :
 *  sécable avant, insécable après — le séparateur ouvre la ligne suivante.
 *
 *  Le contrôle de source (`lint:espace-blocs`) refuse les formes fautives ; ce
 *  test mesure la coupure RENDUE, de la largeur de la carte jusqu'à 120 px
 *  (`coupure-de-ligne.ts`). Le salut de l'accueil passe par la même mesure
 *  (`salut-accueil.spec.ts`).
 */
import { separateursEnFinDeLigne } from './coupure-de-ligne';
import { expect, simulerApi, test } from './aides';

const PLOMBIER = {
	id: 2,
	nom: 'Plomberie Martin',
	specialite: 'plomberie',
	type_prestataire: 'maintenance_depannage',
	contacts: [{ telephone: '01 23 45 67 89', prenom: 'Hélène', nom: 'Dupré', fonction: 'Gérante' }],
	actif: true,
};

test('la ligne de contact d’un prestataire ne finit jamais sur son tiret', async ({ page }) => {
	await page.setViewportSize({ width: 360, height: 740 });
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/prestataires') return [PLOMBIER];
		if (chemin === '/api/prestataires/contrats') return [];
	});
	await page.goto('/prestataires');
	const contact = page.locator('#presta-2 .prest-contact').first();
	await expect(contact).toContainText('Hélène');
	//  Le texte RENDU : le tiret est précédé d'une espace sécable, suivi d'une insécable.
	await expect
		.poll(async () => ((await contact.textContent()) ?? '').replace(/[ \t\n]+/g, ' ').trim())
		.toBe('📞 01 23 45 67 89 —\u00a0Hélène DUPRÉ\u00a0(Gérante)');

	const mesure = await separateursEnFinDeLigne(contact);
	//  Cas zéro : un tiret lu, et des largeurs où la ligne s'est bien coupée.
	expect(mesure.separateurs).toBe(1);
	expect(mesure.largeursCoupees).toBeGreaterThan(5);
	expect(mesure.fautifs).toEqual([]);
});
