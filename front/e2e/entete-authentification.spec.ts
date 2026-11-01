/*
 *  **Les écrans sans session ont UN en-tête : celui de la connexion** (#2357, 30/10/2026).
 *
 *  Demandé au contrôle visuel de #2313 : « la page d'inscription doit ressembler
 *  à la connexion ». L'inscription montrait 🏢 et « Créer un compte » en titre,
 *  le nom de la résidence dessous ; les écrans de mot de passe 🔑, la
 *  vérification d'adresse 📧. Tous passent désormais par `EnteteAuthentification` :
 *  la marque de la résidence, son nom en titre, le geste en phrase.
 *
 *  Le nom attendu n'est pas écrit ici : c'est celui que l'onglet porte
 *  (`<title>… — nom`), lu dans la même configuration. Sur les deux profils, rien
 *  ne déborde, et le logo se centre sous le titre.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal } from './defilement';

const ECRANS: [chemin: string, sousTitre: string][] = [
	['/auth/connexion', 'Votre espace numérique de résidence'],
	['/auth/inscription', 'Créer un compte'],
	['/auth/mot-de-passe-oublie', 'Mot de passe oublié'],
	['/auth/reinitialisation-mdp?token=jeton-temoin', 'Nouveau mot de passe'],
	['/auth/verifier-email?token=jeton-temoin', 'Vérification de l’adresse e-mail'],
];

for (const [chemin, sousTitre] of ECRANS) {
	test(`${chemin.split('?')[0]} : logo, nom de la résidence, puis « ${sousTitre} »`, async ({
		page,
	}) => {
		await simulerApi(page);
		await page.goto(chemin);
		await attendreHydratation(page);

		const entete = page.locator('.auth-header');
		await expect(entete).toHaveCount(1);
		//  La marque de la charte (icône ou logo téléversé), jamais un émoji.
		await expect(entete.locator('.auth-logo').locator('svg, img')).toHaveCount(1);
		await expect(entete).not.toContainText(/[🏢🔑📧]/u);

		const nom = (await page.title()).split(' — ').at(-1)!;
		expect(nom, 'l’onglet ne porte pas le nom de la résidence').not.toBe('');
		await expect(entete.getByRole('heading', { level: 1 })).toHaveText(nom);
		await expect(entete.locator('p')).toHaveText(sousTitre);

		const l = (await entete.locator('.auth-logo').boundingBox())!;
		const t = (await entete.locator('h1').boundingBox())!;
		const ecart = Math.abs(l.x + l.width / 2 - (t.x + t.width / 2));
		expect(ecart, 'le logo n’est pas centré sous le titre').toBeLessThanOrEqual(1);

		await attendreSansDefilementHorizontal(page);
	});
}
