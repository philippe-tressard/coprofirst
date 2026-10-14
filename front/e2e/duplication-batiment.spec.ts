/*
 *  **Dupliquer un bâtiment crée son bâtiment (#1945).**
 *
 *  Signalé le 14/10/2026 : aucun écran ne crée de bâtiment, et tous ceux de la
 *  copropriété ont déjà leur périmètre. La boîte de duplication proposait donc
 *  une liste dont chaque choix était refusé par le serveur — « Bâtiment 1 →
 *  Bâtiment 5 » n'aboutissait jamais.
 *
 *  Le VRAI onglet Admin › Périmètres, API simulée. Ce que l'administrateur doit
 *  voir :
 *  - quand aucun bâtiment n'est libre, pas de liste : le numéro du bâtiment à
 *    créer, seul, et la copie part avec `nouveau_batiment` ;
 *  - quand un bâtiment existe sans périmètre, il est proposé à côté de
 *    « Nouveau bâtiment » — et un bâtiment déjà représenté ne l'est jamais.
 *  Sur bureau et sur téléphone.
 */
import type { Page } from '@playwright/test';
import { expect, MEMBRE_CS, simulerApi, test } from './aides';
import type { Batiment } from '../src/lib/api';
import type { Perimetre } from '../src/lib/perimetres';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

function noeud(champs: Partial<Perimetre> & Pick<Perimetre, 'id' | 'code' | 'libelle'>): Perimetre {
	return {
		parent: null,
		libelle_court: champs.libelle,
		description: '',
		icone: null,
		batiment_id: null,
		profondeur: 0,
		ordre: 0,
		actif: true,
		portee_globale: false,
		concerne_tous: false,
		selectionnable: true,
		privatif: false,
		hors_copropriete: false,
		utilise: false,
		nb_descendants: 0,
		dupliquable: false,
		...champs,
	};
}

const ARBRE: Perimetre[] = [
	noeud({
		id: 1,
		code: 'batiments',
		libelle: 'Bâtiments',
		selectionnable: false,
		nb_descendants: 2,
	}),
	noeud({
		id: 2,
		code: 'bat:1',
		libelle: 'Bâtiment 1',
		parent: 'batiments',
		profondeur: 1,
		batiment_id: 1,
		nb_descendants: 1,
		dupliquable: true,
	}),
	noeud({ id: 3, code: 'bat:1/hall', libelle: 'Hall', parent: 'bat:1', profondeur: 2 }),
];

function batiment(id: number, numero: string): Batiment {
	return {
		id,
		numero,
		nb_etages: 5,
		specificites: null,
		nb_appartements: 10,
		nb_caves: 0,
		nb_parkings: 0,
		nb_locaux_commerciaux: 0,
	};
}

/** Ouvre la duplication de « Bâtiment 1 » et rend le corps de la copie envoyé. */
async function ouvrir(page: Page, batiments: Batiment[]) {
	let envoye: Record<string, unknown> | null = null;
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/perimetres') return ARBRE;
		if (chemin === '/api/copropriete/batiments') return batiments;
		if (chemin === '/api/perimetres/2/dupliquer') return ARBRE[1];
		return undefined;
	});
	page.on('request', (r) => {
		if (r.method() === 'POST' && r.url().endsWith('/api/perimetres/2/dupliquer'))
			envoye = r.postDataJSON();
	});
	await page.goto('/admin?onglet=perimetres');
	await page.locator('.ref-tete', { hasText: 'Bâtiment 1' }).click();
	await page.getByRole('button', { name: 'Dupliquer avec ses sous-périmètres' }).click();
	const boite = page.getByRole('group', { name: /Copie de Bâtiment 1/ });
	//  Cas zéro : sans la boîte, aucune absence de liste ne prouverait rien.
	await expect(boite).toBeVisible();
	return { boite, envoye: () => envoye };
}

test('aucun bâtiment libre : la copie demande le numéro du bâtiment à créer', async ({ page }) => {
	const { boite, envoye } = await ouvrir(page, [batiment(1, '1')]);
	await expect(boite.locator('select')).toHaveCount(0);

	const numero = boite.getByLabel(/Numéro du nouveau bâtiment/);
	await expect(numero).toBeVisible();
	await boite
		.getByLabel(/Libellé/)
		.first()
		.fill('Bâtiment 5');
	const enregistrer = boite.getByRole('button', { name: 'Enregistrer' });
	await expect(enregistrer, 'sans numéro, la copie ne peut pas partir').toBeDisabled();

	await numero.fill('5');
	await enregistrer.click();
	await expect.poll(envoye).toMatchObject({
		libelle: 'Bâtiment 5',
		batiment_id: null,
		nouveau_batiment: '5',
	});
});

test('un bâtiment sans périmètre est proposé, jamais celui déjà représenté', async ({ page }) => {
	const { boite, envoye } = await ouvrir(page, [batiment(1, '1'), batiment(2, '2')]);
	const choix = boite.locator('select');
	await expect(choix.locator('option')).toHaveText(['Nouveau bâtiment', 'Bât. 2']);

	await boite
		.getByLabel(/Libellé/)
		.first()
		.fill('Bâtiment 2');
	await choix.selectOption({ label: 'Bât. 2' });
	await expect(boite.getByLabel(/Numéro du nouveau bâtiment/)).toHaveCount(0);
	await boite.getByRole('button', { name: 'Enregistrer' }).click();
	await expect.poll(envoye).toMatchObject({ batiment_id: 2, nouveau_batiment: null });
});
