/*
 *  **Deux champs posés côte à côte ont la même hauteur (10/11/2026).**
 *
 *  Signalé à l'écran sur Admin › Maintenance, « Réglage de la sauvegarde
 *  quotidienne » : la liste des heures et le nombre de versions, alignés par le
 *  bas, n'avaient pas la même hauteur — bords hauts et libellés décalés. Le
 *  navigateur borne seul la hauteur d'un `<select>` natif, un `<input>` la tire
 *  de son remplissage : à règles identiques, deux hauteurs.
 *
 *  La règle vit dans `champs.css` (`.field.champ-en-ligne`), pour toute rangée.
 *  Ce spec la mesure sur l'écran qui l'a révélée, aux deux profils : au
 *  téléphone le champ change de corps, et un plancher mal exprimé y céderait.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

//  La supervision technique est à l'OPÉRATEUR de la plateforme (#1750).
const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin', 'operateur'] };

const SANTE = { taches: [], anomalies_recentes: [], anomalies_fenetre_jours: 7 };

const REGLAGE = { heure_execution: 4, nb_versions_conservees: 7 };

test('la liste des heures et le nombre de versions ont la même hauteur', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/maintenance/sante') return SANTE;
		if (chemin === '/api/admin/sauvegardes/config') return REGLAGE;
		return undefined;
	});
	await page.goto('/admin?onglet=maintenance');

	const formulaire = page.locator('#config-sauvegarde');
	const liste = formulaire.locator('select');
	const nombre = formulaire.locator('input[type="number"]');
	await expect(liste).toBeVisible();
	await expect(nombre).toBeVisible();

	const boites = async () => {
		const [a, b] = await Promise.all([liste.boundingBox(), nombre.boundingBox()]);
		return a && b ? { a, b } : null;
	};

	//  Même hauteur, au demi-pixel : l'écart d'origine était de 2 px ici, et de
	//  plus de 10 px sous Safari.
	await expect
		.poll(async () => {
			const m = await boites();
			return m ? Math.abs(m.a.height - m.b.height) : Number.NaN;
		})
		.toBeLessThan(0.5);

	//  Et quand ils tiennent sur une ligne, ils commencent à la même hauteur :
	//  c'est ce qui aligne leurs libellés.
	await expect
		.poll(async () => {
			const m = await boites();
			if (!m) return Number.NaN;
			const memeLigne = Math.abs(m.a.y + m.a.height - (m.b.y + m.b.height)) < 0.5;
			return memeLigne ? Math.abs(m.a.y - m.b.y) : 0;
		})
		.toBeLessThan(0.5);
});

//  …et leurs libellés ont la typographie des libellés de section du site
//  (10/11/2026, signalé à l'écran juste après l'alignement) : le bloc posait son
//  titre par `SectionFormulaire` sans l'envelopper, donc ses libellés sortaient
//  en taille de texte courant, noirs — PLUS GRANDS que la phrase d'aide au-dessus.
test('les libellés de la rangée sont plus petits que la phrase d’aide', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/maintenance/sante') return SANTE;
		if (chemin === '/api/admin/sauvegardes/config') return REGLAGE;
		return undefined;
	});
	await page.goto('/admin?onglet=maintenance');

	const libelle = page.locator('#config-sauvegarde label.field').first();
	await expect(libelle).toBeVisible();
	const aide = page.locator('section.config-section p.aide').first();

	const taille = (cible: typeof libelle) =>
		cible.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
	await expect.poll(async () => (await taille(libelle)) < (await taille(aide))).toBe(true);
});
