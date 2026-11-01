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
import { noeud } from './perimetres-temoins';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

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

// ── Copier sous d'autres périmètres, et les flèches de niveau (#2450) ─────────
//
//  Même onglet, même arbre simulé : « Hall » se copie sous « Bâtiment 2 », et
//  sa flèche ← le sort de « Bâtiment 1 ». Ce que la boîte MONTRE est ce qui
//  PART : la case cochée est le parent envoyé, la flèche grisée n'envoie rien.

const ARBRE_COPIE: Perimetre[] = [
	...ARBRE.slice(0, 2),
	noeud({
		id: 3,
		code: 'bat:1/hall',
		libelle: 'Hall',
		parent: 'bat:1',
		profondeur: 2,
		copiable: true,
		deplacements: ['gauche'],
	}),
	noeud({ id: 4, code: 'bat:2', libelle: 'Bâtiment 2', parent: 'batiments', profondeur: 1 }),
];

/** Ouvre « Hall » et rend les corps envoyés aux routes `copier` et `deplacer`. */
async function ouvrirHall(page: Page) {
	const envoyes: Record<string, unknown> = {};
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/perimetres') return ARBRE_COPIE;
		if (chemin === '/api/perimetres/3/copier') return [ARBRE_COPIE[2]];
		if (chemin === '/api/perimetres/3/deplacer') return ARBRE_COPIE[2];
		return undefined;
	});
	page.on('request', (r) => {
		const geste = r.url().match(/\/api\/perimetres\/3\/(copier|deplacer)$/)?.[1];
		if (r.method() === 'POST' && geste) envoyes[geste] = r.postDataJSON();
	});
	await page.goto('/admin?onglet=perimetres');
	await page.locator('.ref-tete', { hasText: 'Hall' }).click();
	return () => envoyes;
}

test('copier sous d’autres périmètres : la case cochée est le parent envoyé', async ({ page }) => {
	const envoyes = await ouvrirHall(page);
	await page.getByRole('button', { name: 'Copier sous d’autres périmètres' }).click();
	const groupe = page.getByRole('group', { name: /Sous les périmètres/ });
	//  Ni la source, ni son parent actuel : le serveur les refuserait.
	await expect(groupe.getByRole('checkbox')).toHaveCount(2);
	await expect(groupe.locator('label')).toHaveText(['Bâtiments', 'Bâtiment 2']);
	const enregistrer = page.getByRole('button', { name: 'Enregistrer' });
	await expect(enregistrer, 'sans case cochée, rien ne part').toBeDisabled();

	await groupe.getByLabel('Bâtiment 2').check();
	await enregistrer.click();
	await expect.poll(() => envoyes().copier).toEqual({ parents: ['bat:2'] });
});

test('les flèches : seules celles que le serveur accepte sont actives', async ({ page }) => {
	const envoyes = await ouvrirHall(page);
	await expect(page.getByRole('button', { name: 'Monter', exact: true })).toBeDisabled();
	await expect(page.getByRole('button', { name: /Descendre d’un niveau/ })).toBeDisabled();
	await page.getByRole('button', { name: /Remonter d’un niveau/ }).click();
	await expect.poll(() => envoyes().deplacer).toEqual({ sens: 'gauche' });
});
