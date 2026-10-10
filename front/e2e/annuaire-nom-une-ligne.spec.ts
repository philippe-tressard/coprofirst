/*
 *  **Annuaire : « Mr Prénom NOM » sur UNE ligne** (demandé à l'écran le 10/10/2026).
 *
 *  Dans la grille d'origine, la colonne avait une largeur fixe et le NOM d'un
 *  contact du syndic tombait seul sous la civilité et le prénom. La rangée est
 *  désormais en `flex` : la carte s'élargit à la mesure du nom.
 *
 *  Deux mesures, sur le VRAI écran, API simulée :
 *  • le nom tient sur une ligne (sa hauteur est celle d'UNE ligne) ;
 *  • au téléphone, la page ne défile pas en largeur — un nom trop long pour la
 *    carte s'y replie plutôt que de la faire déborder.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

const ANNUAIRE = {
	cs: { ag_annee: null, ag_date: null, membres: [] },
	syndic: {
		nom_syndic: 'Cabinet Exemple',
		nom_syndic_source: 'saisie',
		adresse: '',
		site_web: null,
		membres: [
			{
				id: 1,
				genre: 'Mr',
				prenom: 'Christophe',
				nom: 'Morin-Legrand',
				fonction: 'Gestionnaire de Copropriétés',
				email: 'gestion@exemple.fr',
				telephone: '01 02 03 04 05',
				est_principal: true,
				photo_url: null,
			},
			{
				id: 2,
				genre: 'Mme',
				prenom: 'Anne',
				nom: 'Durand',
				fonction: 'Assistante',
				email: null,
				telephone: null,
				est_principal: false,
				photo_url: null,
			},
		],
	},
	whatsapp_url: null,
};

test('le nom d’un contact du syndic tient sur une ligne, sans défilement horizontal', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/admin/annuaire') return ANNUAIRE;
	});
	await page.goto('/annuaire');
	await attendreHydratation(page);

	const nom = page.locator('.contact-nom', { hasText: 'MORIN-LEGRAND' });
	await expect(nom).toBeVisible();
	//  Un élément en ligne rend un rectangle par ligne qu'il occupe : un seul,
	//  c'est une seule ligne (la hauteur de ligne vaut `normal`, illisible en px).
	expect(await nom.evaluate((el) => el.getClientRects().length)).toBe(1);

	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde).toBe(false);
});
