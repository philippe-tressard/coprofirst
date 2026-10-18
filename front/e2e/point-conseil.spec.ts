/*
 *  **Le point CS / Syndic du Suivi des affaires** (#2041, maquettes A1 et C1).
 *
 *  Sur le VRAI écran, API simulée : ouvrir un point (quand, où, qui — un membre
 *  coché, un invité ajouté), puis saisir le compte rendu d'une affaire dans le
 *  tableau ; il paraît dans la ligne et dans le compte rendu global. Les règles
 *  (un point par mode, reprise, non traitées) sont tenues au serveur par
 *  `api/tests/test_points_conseil.py`.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';
import type { CompteRenduPoint, CrAffaire, ParticipantsPoint, SuiviAffaires } from '../src/lib/api';

const AFFAIRE = {
	id: 31,
	numero: 'TK-000031',
	titre: 'Interphone bâtiment C muet',
	descriptif: 'La platine de rue ne sonne plus.',
	categorie: 'panne',
	libelle_categorie: 'Panne',
	statut: 'en_cours',
	libelle_statut: 'Chez le syndic',
	ouverte_le: '2026-07-02',
	age_jours: 106,
	anciennete: 'ancienne' as const,
	perimetre_cible: [],
	jours_sans_avancee: 40,
	a_relancer: true,
	relances: [],
	apercu: 'La platine de rue ne sonne plus.',
	apercu_ia: false,
	batiments: [],
	etat_visite: null,
	a_evolue: false,
	motif_evolution: null,
};

const RELEVE: SuiviAffaires = {
	jour: '2026-10-19',
	total: 1,
	anciennes: 1,
	resumes_disponibles: false,
	delai_jours: 30,
	mode: 'affaires',
	par_categorie: [
		{
			cle: 'panne',
			libelle: 'Panne',
			nombre: 1,
			tranches: [{ cle: 'racine', libelle: 'Résidence', nombre: 1 }],
		},
	],
	par_batiment: [],
	affaires: [AFFAIRE],
};

const ANNUAIRE: ParticipantsPoint = {
	conseil: [{ id: 3, prenom: 'Reine', nom: 'Martin', fonction: null }],
	syndic: [{ id: 7, prenom: 'Paul', nom: 'Bernard', fonction: 'Gestionnaire' }],
	lieux: [{ libelle: 'Résidence', adresse: '1 rue Test' }],
	moyens: [
		{ cle: 'sur_place', libelle: 'Sur place', avec_lieu: true },
		{ cle: 'visio', libelle: 'Visioconférence', avec_lieu: false },
		{ cle: 'telephone', libelle: 'Téléphone', avec_lieu: false },
		{ cle: 'hybride', libelle: 'Sur place et à distance', avec_lieu: true },
	],
};

function compteRendu(cr: CrAffaire | null): CompteRenduPoint {
	return {
		point: {
			id: 5,
			mode: 'affaires',
			etat: 'en_cours',
			debut: '2026-10-19T17:00:00',
			fin: null,
			moyen: 'sur_place',
			a_distance: false,
			lieu: '1 rue Test',
			ou: 'Sur place — 1 rue Test',
			cree_le: '2026-10-19T15:00:00',
			termine_le: null,
			valide_le: null,
		},
		presents: [
			{
				id: 1,
				nature: 'cs',
				membre_cs_id: 3,
				membre_syndic_id: null,
				prenom: 'Reine',
				nom: 'Martin',
				entreprise: null,
				fonction: null,
				telephone: null,
				email: null,
			},
			{
				id: 2,
				nature: 'invite',
				membre_cs_id: null,
				membre_syndic_id: null,
				prenom: 'Jean',
				nom: 'Durand',
				entreprise: 'Étanchéité Sud',
				fonction: null,
				telephone: null,
				email: null,
			},
		],
		abordees: cr ? [{ affaire: { id: 31, numero: 'TK-000031', titre: AFFAIRE.titre }, cr }] : [],
		non_traitees: cr ? [] : [{ id: 31, numero: 'TK-000031', titre: AFFAIRE.titre }],
	};
}

const CR: CrAffaire = {
	ticket_id: 31,
	contenu: '<p>Le syndic relance l’entreprise.</p>',
	brouillon: false,
	conseil_seul: false,
	mis_a_jour_le: '2026-10-19T15:10:00',
};

test('ouvrir un point, puis saisir le compte rendu d’une affaire', async ({ page }) => {
	const envois: { quoi: string; corps: unknown }[] = [];
	page.on('request', (r) => {
		const url = new URL(r.url());
		if (url.pathname.startsWith('/api/points-conseil') && r.method() !== 'GET')
			envois.push({ quoi: `${r.method()} ${url.pathname}`, corps: r.postDataJSON() });
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/suivi-affaires') return RELEVE;
		if (chemin === '/api/points-conseil/participants') return ANNUAIRE;
		if (chemin === '/api/points-conseil') return compteRendu(null);
		if (chemin === '/api/points-conseil/5/affaires/31') return compteRendu(CR);
		return undefined;
	});
	await page.goto('/espace-cs/reporting');
	await attendreHydratation(page);

	await page.getByRole('button', { name: 'Ouvrir un point CS / Syndic' }).click();
	//  Le lieu proposé d'office est celui de la résidence.
	await expect(page.getByLabel('Lieu')).toHaveValue('1 rue Test');
	//  Les intitulés du Quand et du Où sont sur une même ligne (finition du
	//  17/10/2026 : la bascule « Sur place | À distance » décalait celui du lieu).
	if ((page.viewportSize()?.width ?? 0) >= 768) {
		const hauts = await Promise.all(
			['Début', 'Fin', 'Moyen', 'Lieu'].map(async (l) =>
				Math.round(
					(await page.locator('form.point-form label', { hasText: l }).first().boundingBox())?.y ??
						-1,
				),
			),
		);
		expect(new Set(hauts).size, `hauts des intitulés : ${hauts}`).toBe(1);
	}
	//  Sans personne sur place, pas de lieu ; il revient avec « Sur place ».
	await page.getByLabel('Moyen').selectOption('visio');
	await expect(page.getByLabel('Lieu')).toHaveCount(0);
	await page.getByLabel('Moyen').selectOption('sur_place');
	await expect(page.getByLabel('Lieu')).toHaveValue('1 rue Test');

	//  Une rangée par population, chacune nommée.
	for (const nom of ['Conseil syndical', 'Syndic', 'Invités'])
		await expect(page.getByRole('group', { name: nom, exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Reine MARTIN' }).click();
	//  Plusieurs invités, et chacun se retire par la croix des pastilles.
	for (const [prenom, entreprise] of [
		['Jean', 'Étanchéité Sud'],
		['Lise', 'Ascenseurs Test'],
	]) {
		await page.getByRole('button', { name: 'Ajouter un invité' }).click();
		await page.getByLabel('Prénom').fill(prenom);
		await page.getByLabel('Entreprise').fill(entreprise);
		await page
			.getByRole('group', { name: 'Ajouter un invité' })
			.getByRole('button', { name: 'Enregistrer' })
			.click();
	}
	const invites = page.getByRole('group', { name: 'Invités', exact: true });
	await expect(invites.locator('.pastille-retirable')).toHaveCount(2);
	await invites.getByRole('button', { name: 'Retirer Lise' }).click();
	await expect(invites.locator('.pastille-retirable')).toHaveText(['Étanchéité Sud Jean ×']);
	await page
		.locator('form.point-form > .form-actions')
		.getByRole('button', { name: 'Enregistrer' })
		.click();

	await expect.poll(() => envois.map((e) => e.quoi)).toContain('POST /api/points-conseil');
	const ouverture = envois.find((e) => e.quoi === 'POST /api/points-conseil')?.corps as {
		moyen: string;
		lieu: string | null;
		presents: { nature: string; membre_id?: number; entreprise?: string }[];
	};
	expect([ouverture.moyen, ouverture.lieu]).toEqual(['sur_place', '1 rue Test']);
	expect(ouverture.presents).toEqual([
		{ nature: 'cs', membre_id: 3 },
		expect.objectContaining({ nature: 'invite', prenom: 'Jean', entreprise: 'Étanchéité Sud' }),
	]);

	//  Le bandeau dit l'état et les présents ; le CR global, les non traitées.
	const point = page.locator('section.point');
	await expect(point).toContainText('En cours');
	await expect(point).toContainText('Reine MARTIN, Jean DURAND');
	await expect(page.getByRole('region', { name: 'Compte rendu du point' })).toContainText(
		'Non traitées · 1',
	);

	await page.getByRole('button', { name: 'Compte rendu' }).click();
	const editeur = page.locator('.saisie-cr .tiptap');
	await editeur.click();
	await editeur.pressSequentially('Le syndic relance l’entreprise.');
	await page.locator('.saisie-cr').getByRole('button', { name: 'Enregistrer' }).click();

	await expect
		.poll(() => envois.map((e) => e.quoi))
		.toContain('PUT /api/points-conseil/5/affaires/31');
	await expect(page.locator('.saisie-cr')).toHaveCount(0);
	await expect(page.locator('table.affaires .cr')).toContainText('CR saisi');
	const global = page.getByRole('region', { name: 'Compte rendu du point' });
	await expect(global).toContainText('Les affaires abordées · 1');
	await expect(global).toContainText('Le syndic relance l’entreprise.');
	//  L'espace avant la précision d'un présent (v2.174.1) : « Durand(Étanchéité… » se lisait collé.
	await expect(global).toContainText('Jean DURAND (Étanchéité Sud)');
});
