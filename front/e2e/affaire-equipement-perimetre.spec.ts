/*
 *  **Équipement ⇄ périmètre : choisir l'un PROPOSE l'autre** (#2442, arbitré le
 *  01/11/2026). L'équipement et le périmètre restent deux notions — le QUOI et
 *  le OÙ —, et l'administration les relie (« Périmètres concernés ») là où ils
 *  se recouvrent : l'ascenseur du bâtiment 1.
 *
 *  Les règles sont pures (`perimetrePropose`, `equipementPropose` de
 *  `#lib/formulaire-affaire`) ; ce qui ne se voit qu'à l'écran est leur
 *  BRANCHEMENT (`PropositionCroisee`) : dans les deux sens, et jamais par-dessus
 *  un choix déjà fait.
 */
import type { Locator, Page } from '@playwright/test';
import type { Perimetre } from '../src/lib/perimetres';
import { noeud } from './perimetres-temoins';
import { attendreHydratation, EQUIPEMENTS_TEMOINS, expect, simulerApi, test } from './aides';

const ARBRE: Perimetre[] = [
	noeud({
		id: 1,
		code: 'résidence',
		libelle: 'Résidence',
		portee_globale: true,
		concerne_tous: true,
		par_defaut: true,
	}),
	noeud({ id: 2, code: 'bat:1', libelle: 'Bâtiment 1', ordre: 1, batiment_id: 1 }),
];

/** L'ascenseur se trouve au bâtiment 1 ; la plomberie, nulle part en particulier. */
const EQUIPEMENTS = EQUIPEMENTS_TEMOINS.map((e) =>
	e.code === 'ascenseur' ? { ...e, perimetres: ['bat:1'] } : e,
);

async function nouvellePanne(
	page: Page,
	arbre: Perimetre[] = ARBRE,
): Promise<{ batiment: Locator; equipement: Locator }> {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/perimetres') return arbre;
		if (chemin === '/api/equipements') return EQUIPEMENTS;
		return undefined;
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();
	await page
		.getByText(/Ascenseur, chauffage, éclairage/)
		.first()
		.click();
	const formulaire = page.getByRole('group', { name: /^Nouvelle affaire$/ });
	//  La section Équipement est pliée (facultative) : on l'ouvre comme le conseil.
	await formulaire
		.locator('section.section-formulaire', {
			has: page.locator('.section-titre-texte', { hasText: /^Équipement$/ }),
		})
		.locator('.section-titre-texte')
		.click();
	return {
		batiment: formulaire.getByRole('button', { name: 'Bâtiment 1' }),
		equipement: formulaire.locator('select[id$="-equipement"]'),
	};
}

test('l’équipement propose le seul périmètre où il se trouve', async ({ page }) => {
	const { batiment, equipement } = await nouvellePanne(page);
	await expect(batiment).not.toHaveClass(/active/);
	await equipement.selectOption('ascenseur');
	await expect(batiment).toHaveClass(/active/);
});

test('le périmètre propose le seul équipement qui s’y trouve', async ({ page }) => {
	const { batiment, equipement } = await nouvellePanne(page);
	await batiment.click();
	await expect(equipement).toHaveValue('ascenseur');
});

test('jamais par-dessus un choix déjà fait, dans un sens comme dans l’autre', async ({ page }) => {
	const { batiment, equipement } = await nouvellePanne(page);
	await equipement.selectOption('plomberie');
	await batiment.click();
	await expect(equipement).toHaveValue('plomberie');
	//  Le périmètre est choisi : changer d'équipement ne le touche plus.
	await equipement.selectOption('ascenseur');
	await expect(batiment).toHaveClass(/active/);
	await equipement.selectOption('toiture');
	await expect(batiment).toHaveClass(/active/);
});

/*
 *  🔒 **Le périmètre par défaut est SERVI, jamais recalculé** (#2514). L'AFUL est
 *  aussi une racine à portée globale : seul le serveur les départage
 *  (`code_par_defaut`), et il le dit par `par_defaut`. Le site prenait la première
 *  racine servie — ici l'AFUL, et le formulaire s'ouvrait sur elle.
 */
test('le formulaire s’ouvre sur le périmètre que le serveur désigne', async ({ page }) => {
	const aful = noeud({ id: 3, code: 'aful', libelle: 'AFUL', portee_globale: true });
	await nouvellePanne(page, [aful, ...ARBRE]);
	const formulaire = page.getByRole('group', { name: /^Nouvelle affaire$/ });
	await expect(formulaire.getByRole('button', { name: 'Résidence' })).toHaveClass(/active/);
	await expect(formulaire.getByRole('button', { name: 'AFUL' })).not.toHaveClass(/active/);
});
