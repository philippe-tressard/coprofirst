/*
 *  **Une urgence de l'accueil est un LIEN** (#779, 30/09/2026).
 *
 *  La carte était un `<fieldset role="link" tabindex="0">` avec un `keydown`
 *  recopié : un rôle interactif sur un élément qui ne l'est pas, déclaré en
 *  exception d'accessibilité depuis le 28/08/2026. Elle porte désormais un vrai
 *  `<a href>` étiré sur la carte. Ce test tient ce que la déclaration ne pouvait
 *  pas tenir : le lien a un nom, une adresse, s'active au clavier — et la carte
 *  entière reste cliquable, sur bureau comme au doigt.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const URGENCE = {
	id: 'tk_7',
	type: 'ticket_ouvert',
	date: '2026-09-30T08:00:00',
	titre: 'Fuite dans la cage d’escalier',
	detail: 'Eau au 2e étage',
	badges: ['#TK-109008', 'Panne', 'urgent'],
	icon: '🛠️',
	meta: { ticket_id: 7, numero: 'TK-109008', perimetre_codes: ['bat:1'] },
};

async function accueil(page: Page) {
	await simulerApi(page, (chemin) =>
		chemin === '/api/flux' ? { items: [URGENCE], sante: {} } : undefined,
	);
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
}

test('l’urgence est un lien nommé par son titre, vers l’affaire', async ({ page }) => {
	await accueil(page);
	const lien = page.getByRole('link', { name: 'Fuite dans la cage d’escalier' });
	await expect(lien).toHaveAttribute('href', '/tickets?open=TK-109008');
	//  Plus aucun rôle posé sur le cadre.
	await expect(page.locator('fieldset.urgence-fieldset[role]')).toHaveCount(0);
});

test('au clavier : Tab atteint le lien, Entrée ouvre l’affaire', async ({ page }) => {
	await accueil(page);
	const lien = page.getByRole('link', { name: 'Fuite dans la cage d’escalier' });
	await lien.focus();
	await expect(lien).toBeFocused();
	await page.keyboard.press('Enter');
	await expect(page).toHaveURL(/\/tickets\?open=TK-109008/);
});

/*  Une ACTUALITÉ urgente garde la mise en forme de sa description (24/10/2026) :
 *  le bandeau rendait l'extrait sans HTML (`detail`), et le gras du code
 *  d'ascenseur disparaissait alors que le fil le rendait. */
const ACTUALITE_URGENTE = {
	id: 'tk_8',
	type: 'publication',
	date: '2026-09-30T08:00:00',
	titre: 'Nouveau code de l’ascenseur',
	detail: 'Le code est 0000.',
	badges: [],
	icon: '📰',
	meta: {
		ticket_id: 8,
		urgente: true,
		full_html: '<p>Le code est <strong>0000</strong>.</p><script>window.__xss = 1</script>',
	},
};

test('une actualité urgente garde sa mise en forme, assainie', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/flux' ? { items: [ACTUALITE_URGENTE], sante: {} } : undefined,
	);
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	await expect(page.locator('.urgence-fieldset strong', { hasText: '0000' })).toBeVisible();
	await expect(page.locator('.urgence-fieldset script')).toHaveCount(0);
});

test('un clic ailleurs sur la carte ouvre aussi l’affaire', async ({ page }) => {
	await accueil(page);
	//  Le texte de détail n'est pas dans le lien : c'est le lien étiré qui le
	//  couvre. Playwright refuse de cliquer un élément recouvert — c'est
	//  justement le but —, donc on clique à ses COORDONNÉES, comme un doigt.
	const zone = await page.locator('.urgence-fieldset .urgence-horaire').boundingBox();
	expect(zone, 'le détail de l’urgence n’est pas rendu').not.toBeNull();
	await page.mouse.click(zone!.x + zone!.width / 2, zone!.y + zone!.height / 2);
	await expect(page).toHaveURL(/\/tickets\?open=TK-109008/);
});
