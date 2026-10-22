/*
 *  **Le glissement d'une carte du kanban se lit avant le lâcher** (#2170,
 *  audit `apple-design` du 23/10/2026).
 *
 *  Rien ne changeait pendant le glissement : on ne savait où la carte tombait
 *  qu'au lâcher. La colonne survolée se marque désormais, celle d'où la carte
 *  vient ne s'allume pas, et la carte saisie s'efface à demi ; tout s'éteint
 *  au lâcher — et à l'abandon (`dragend`).
 *
 *  Le geste au DOIGT (glisser-déposer HTML5 sur un téléphone) ne se prouve pas
 *  ici : c'est le contrôle visuel du ticket.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

const AFFAIRE = {
	id: 7,
	numero: 'TK-124301',
	titre: 'Porte du local vélos',
	description: 'La gâche ne tient plus.',
	categorie: 'panne',
	statut: 'ouvert',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	suivi_kanban: true,
	natures: ['activite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-20T10:00:00',
};

test.use({ viewport: { width: 1400, height: 900 } });

test('la colonne survolée se marque pendant le glissement, et s’éteint au lâcher', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [AFFAIRE];
	});
	await page.goto('/tickets/kanban');
	await attendreHydratation(page);
	const carte = page.locator('.kanban-card', { hasText: AFFAIRE.titre });
	const origine = page.getByRole('group', { name: 'CS (en cours)' });
	const cible = page.getByRole('group', { name: 'Syndic (en cours)' });
	await expect(carte).toBeVisible();

	const depart = await carte.boundingBox();
	const arrivee = await cible.boundingBox();
	if (!depart || !arrivee) throw new Error('carte ou colonne sans boîte');
	await page.mouse.move(depart.x + depart.width / 2, depart.y + depart.height / 2);
	await page.mouse.down();
	//  Passer d'abord sur la colonne d'origine : elle ne s'allume pas.
	await page.mouse.move(depart.x + depart.width / 2 + 5, depart.y + depart.height / 2, {
		steps: 3,
	});
	await expect(carte).toHaveClass(/kanban-card-saisie/);
	await expect(origine).not.toHaveClass(/kanban-col-cible/);

	await page.mouse.move(arrivee.x + arrivee.width / 2, arrivee.y + 40, { steps: 10 });
	await expect(cible).toHaveClass(/kanban-col-cible/);

	//  Au lâcher, tout s'éteint.
	await page.mouse.up();
	await expect(cible).not.toHaveClass(/kanban-col-cible/);
	await expect(carte).not.toHaveClass(/kanban-card-saisie/);
});
