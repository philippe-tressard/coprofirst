/*
 *  **Accorder ou retirer les rôles Opérateur et Admin** dans Admin › Utilisateurs.
 *
 *  🔴 Depuis #2618 (10/11/2026), l'écran ne décide plus : il AFFICHE les gestes
 *  que l'API sert avec chaque compte (`gestes_roles`, `api/app/utils/gestes_roles.py`).
 *  La règle — tout admin accorde Opérateur à un admin, lui-même compris ; Admin et
 *  Opérateur se retirent, à soi-même compris, sauf à leur dernier titulaire actif
 *  (#2029) — s'éprouve contre la route dans `api/tests/test_gestes_roles.py`.
 *  Ce fichier vérifie que l'écran rend ce qui est servi, ni plus ni moins, et le
 *  geste lui-même (confirmation, avertissement à soi-même).
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const OPERATEUR = { ...MEMBRE_CS, role: 'admin', roles: ['admin', 'operateur'] };
const ADMIN_SEUL = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

type Geste = 'ajouter' | 'retirer' | null;

/**  Ce que le serveur SERT pour ce compte — écrit par cas, jamais recalculé ici. */
function gestes(admin: Geste, operateur: Geste, cs: Geste = 'ajouter') {
	return { conseil_syndical: cs, admin, operateur };
}

function ligne(
	id: number,
	prenom: string,
	roles: string[],
	gestes_roles: ReturnType<typeof gestes>,
) {
	return {
		gestes_roles,
		id,
		prenom,
		nom: 'Durand',
		email: `${prenom.toLowerCase()}@exemple.test`,
		statut: 'copropriétaire_résident',
		role: roles.includes('admin') ? 'admin' : 'résident',
		roles,
		actif: true,
		batiment_id: null,
	};
}

//  Deux opérateurs (Moi, Bruno) et trois administrateurs : rien n'est « dernier ».
const COMPTES = [
	ligne(OPERATEUR.id, 'Moi', OPERATEUR.roles, gestes('retirer', 'retirer')),
	ligne(31, 'Alice', ['propriétaire', 'admin'], gestes('retirer', 'ajouter')),
	ligne(32, 'Bruno', ['propriétaire', 'admin', 'operateur'], gestes('retirer', 'retirer')),
	ligne(33, 'Chloe', ['propriétaire', 'résident'], gestes('ajouter', null)),
];

/** Moi, seul administrateur et seul opérateur : rien ne se retire. */
const SEUL_TITULAIRE = [
	ligne(OPERATEUR.id, 'Moi', OPERATEUR.roles, gestes(null, null)),
	COMPTES[3],
];

async function ouvrir(page: Page, moi: typeof OPERATEUR, comptes = COMPTES) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return moi;
		if (chemin === '/api/admin/utilisateurs') return comptes;
	});
	await page.goto('/admin?onglet=utilisateurs');
	await attendreHydratation(page);
}

const rangee = (page: Page, prenom: string) =>
	page.locator('table tbody tr').filter({ hasText: `${prenom} DURAND` });

test('le rôle Opérateur s’accorde à un admin et se retire, à soi-même compris', async ({
	page,
}) => {
	await ouvrir(page, OPERATEUR);
	await expect(page.locator('table tbody tr')).toHaveCount(4);

	const alice = rangee(page, 'Alice');
	await expect(alice.getByRole('button', { name: '+ Opérateur' })).toBeVisible();
	await expect(alice.getByRole('button', { name: '– Admin' })).toBeVisible();

	const bruno = rangee(page, 'Bruno');
	await expect(bruno.getByRole('button', { name: '– Opérateur' })).toBeVisible();
	//  Admin se retire à un opérateur, qui garde sa supervision (#2029).
	await expect(bruno.getByRole('button', { name: '– Admin' })).toBeVisible();

	//  Pas admin : le rôle ne s'accorde pas.
	await expect(rangee(page, 'Chloe').getByRole('button', { name: /Opérateur/ })).toHaveCount(0);
	//  Soi-même : un autre opérateur et un autre admin restent, les gestes sont offerts.
	await expect(rangee(page, 'Moi').getByRole('button', { name: '– Opérateur' })).toBeVisible();
	await expect(rangee(page, 'Moi').getByRole('button', { name: '– Admin' })).toBeVisible();
});

test('l’opérateur qui se retire Admin est prévenu qu’il garde sa supervision', async ({ page }) => {
	await ouvrir(page, OPERATEUR);
	await rangee(page, 'Moi').getByRole('button', { name: '– Admin' }).click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('Retirer le rôle Admin de votre compte');
	await expect(boite).toContainText('que la supervision de la plateforme');
});

test('le dernier administrateur et le dernier opérateur ne se retirent pas le rôle', async ({
	page,
}) => {
	await ouvrir(page, OPERATEUR, SEUL_TITULAIRE);
	await expect(page.locator('table tbody tr')).toHaveCount(2);
	const moi = rangee(page, 'Moi');
	await expect(moi.getByRole('button', { name: '– Opérateur' })).toHaveCount(0);
	await expect(moi.getByRole('button', { name: '– Admin' })).toHaveCount(0);
});

test('le geste demande confirmation et nomme le rôle', async ({ page }) => {
	await ouvrir(page, OPERATEUR);
	await rangee(page, 'Alice').getByRole('button', { name: '+ Opérateur' }).click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('Ajouter le rôle Opérateur');
	await boite.getByRole('button', { name: 'Annuler' }).click();
	await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('un admin qui n’est pas opérateur accorde le rôle, à lui-même compris', async ({ page }) => {
	await ouvrir(page, ADMIN_SEUL, [
		ligne(ADMIN_SEUL.id, 'Moi', ADMIN_SEUL.roles, gestes('retirer', 'ajouter')),
		COMPTES[1],
		//  Bruno est alors le SEUL opérateur : le serveur ne sert pas son retrait.
		ligne(32, 'Bruno', ['propriétaire', 'admin', 'operateur'], gestes('retirer', null)),
		COMPTES[3],
	]);
	await expect(page.locator('table tbody tr')).toHaveCount(4);
	await expect(rangee(page, 'Moi').getByRole('button', { name: '+ Opérateur' })).toBeVisible();
	await expect(rangee(page, 'Alice').getByRole('button', { name: '+ Opérateur' })).toBeVisible();
	//  Bruno est le seul opérateur : il le reste.
	await expect(rangee(page, 'Bruno').getByRole('button', { name: /Opérateur/ })).toHaveCount(0);
});
