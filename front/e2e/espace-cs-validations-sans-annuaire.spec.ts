/*
 *  **Espace CS : l'onglet Validations n'attend pas l'Annuaire (#1843).**
 *
 *  L'onglet par défaut attendait six lectures, dont trois ne servent qu'à
 *  l'Annuaire — les inscrits, les lots et `/lots/admin/imports`, l'une des
 *  routes les plus lentes du serveur (256 ms de médiane) : +210 ms à chaque
 *  ouverture. Ce test RETIENT les imports : les Validations s'affichent quand
 *  même, et aucune lecture de l'Annuaire n'est demandée tant qu'on ne l'ouvre pas.
 *
 *  Depuis #2522, l'Annuaire ne les demande plus non plus : le rapprochement d'un
 *  nom saisi se demande au serveur, fiche par fiche. Le verrou de #522 — « pas
 *  encore là » ne se lit pas « aucune correspondance » — n'a donc plus d'objet :
 *  il n'y a plus rien à attendre.
 */
import type { Page } from '@playwright/test';
import { expect, retenirApi, simulerApi, test } from './aides';

const COMMANDE = {
	id: 5,
	user_id: 7,
	lot_id: 12,
	type: 'telecommande',
	quantite: 1,
	motif: null,
	statut: 'en_attente',
	traite_par_id: null,
	motif_refus: null,
	cree_le: '2026-10-11T10:00:00',
	traite_le: null,
	demandeur_nom: 'Anne DURAND',
	lot: 'Parking 12',
	batiment: 'Bât. 4',
};
const REFERENCE = ['/api/admin/utilisateurs', '/api/lots/admin/tous', '/api/lots/admin/imports'];

/** Retient `/lots/admin/imports` jusqu'à `relacher()`, et note les chemins demandés. */
async function retenirImports(page: Page) {
	const demandes: string[] = [];
	page.on('request', (r) => demandes.push(new URL(r.url()).pathname));
	await simulerApi(page, (chemin) =>
		chemin === '/api/admin/commandes-acces' ? [COMMANDE] : undefined,
	);
	const relacher = await retenirApi(page, (chemin) => chemin === '/api/lots/admin/imports');
	return { demandes, relacher };
}

test('Espace CS › Validations : affichées sans attendre l’Annuaire', async ({ page }) => {
	const { demandes, relacher } = await retenirImports(page);
	await page.goto('/espace-cs');
	await expect(page.locator('.pending-row', { hasText: 'Anne DURAND' })).toBeVisible();
	expect(demandes.filter((d) => REFERENCE.includes(d))).toEqual([]);
	relacher();
});

test('Espace CS › Annuaire : il se rend sans aucune donnée de référence', async ({ page }) => {
	const { demandes, relacher } = await retenirImports(page);
	await page.goto('/espace-cs/annuaire');
	await expect.poll(() => demandes.includes('/api/admin/annuaire/cs')).toBe(true);
	await expect.poll(() => demandes.includes('/api/admin/annuaire/syndic')).toBe(true);
	expect(demandes.filter((d) => REFERENCE.includes(d))).toEqual([]);
	relacher();
});
