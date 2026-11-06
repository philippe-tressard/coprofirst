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
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';
import { REFERENTIELS_TEMOINS } from './referentiels-temoins';

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
	//  Servis par l'API (#2508) : la colonne de la carte, et le glissement pour CE lecteur.
	colonne_kanban: 'cs',
	peut_deplacer_au_kanban: true,
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
		//  Relue au lâcher (#2508) : la page reprend ce que le serveur sert.
		if (chemin === '/api/tickets/7') return AFFAIRE;
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

/*
 *  🔒 **L'état qui CLÔT se lit au serveur** (#2511) : glisser une carte en
 *  « Terminé » propose la fusion de ses liées si le référentiel dit que l'état
 *  posé clôt l'affaire (`statuts[].clos`) — le site ne le recalcule plus.
 */
const LIEE = {
	id: 8,
	numero: 'TK-124302',
	titre: 'Gâche du local poussettes',
	statut: 'ouvert',
	close: false,
	cree_le: '2026-09-21T10:00:00',
	fusionnee: false,
	fusionnable: true,
	motif: null,
	conciliation: null,
};

async function glisserEnTermine(
	page: Page,
	referentiel?: (r: typeof REFERENTIELS_TEMOINS) => typeof REFERENTIELS_TEMOINS,
): Promise<string[]> {
	const appels: string[] = [];
	await simulerApi(page, (chemin) => {
		appels.push(chemin);
		if (chemin === '/api/tickets') return [AFFAIRE];
		if (chemin === '/api/tickets/7') return AFFAIRE;
		if (chemin === '/api/tickets/7/fusion') return [LIEE];
		if (chemin === '/api/tickets/referentiels' && referentiel)
			return referentiel(REFERENTIELS_TEMOINS);
	});
	await page.goto('/tickets/kanban');
	await attendreHydratation(page);
	const carte = page.locator('.kanban-card', { hasText: AFFAIRE.titre });
	await expect(carte).toBeVisible();
	await carte.dragTo(page.getByRole('group', { name: 'Terminé' }));
	return appels;
}

test('glisser en « Terminé » propose la fusion des liées : l’état clôt, dit le serveur', async ({
	page,
}) => {
	await glisserEnTermine(page);
	const dialogue = page.getByRole('dialog');
	await expect(dialogue).toContainText(LIEE.numero);
	await expect(dialogue).toContainText('(Résolu)');
});

test('un état que le serveur ne dit pas clos ne propose aucune fusion', async ({ page }) => {
	const appels = await glisserEnTermine(page, (r) => ({
		...r,
		statuts: r.statuts.map((s) => (s.code === 'résolu' ? { ...s, clos: false } : s)),
	}));
	await expect.poll(() => appels.includes('/api/tickets/7/evolutions')).toBe(true);
	expect(appels).not.toContain('/api/tickets/7/fusion');
	await expect(page.getByRole('dialog')).toHaveCount(0);
});
