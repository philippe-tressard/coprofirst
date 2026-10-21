/*
 *  **Espace CS › Reporting › Suivi des affaires, mode « Suivi entretiens
 *  périodiques »** (#2043, 17/10/2026) — il remplace la vue « Entretien
 *  périodique », et `?vue=periodique` y mène.
 *
 *  En tête, le bilan des visites de l'année (`GET /tickets/entretiens-periodiques`) ;
 *  dessous, les affaires d'entretien périodique NON CLOSES (`GET /suivi-affaires?mode=entretien`),
 *  l'état de leur visite à la place de la catégorie. Les états sont calculés au
 *  SERVEUR (`utils/entretien_periodique`) ; l'écran ne fait que les nommer.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';
import type { EntretienPeriodiqueResponse, SuiviAffaires } from '../src/lib/api';

const VISITE = {
	statut: 'chez_prestataire',
	ferme_le: null,
	prestataire_nom: 'DURAND',
	contrat_libelle: 'Entretien toitures',
};

const REPONSE: EntretienPeriodiqueResponse = {
	exercice: 2026,
	visites: [
		{
			...VISITE,
			id: 47,
			numero: 'TK-E00047',
			titre: 'Toitures — Entretien toitures',
			statut: 'résolu',
			debut: '2026-01-15T00:00:00',
			ferme_le: '2026-01-20T09:00:00',
			etat: 'realisee',
		},
		{
			...VISITE,
			id: 48,
			numero: 'TK-E00048',
			titre: 'Toitures — Entretien toitures',
			debut: '2026-07-15T00:00:00',
			etat: 'non_realisee',
		},
		{
			...VISITE,
			id: 90,
			numero: 'TK-000090',
			titre: 'Portes — Maintenance',
			debut: '2026-12-01T00:00:00',
			etat: 'a_venir',
		},
	],
};

const AFFAIRE = {
	descriptif: '',
	categorie: 'entretien',
	libelle_categorie: 'Entretien',
	statut: 'chez_prestataire',
	libelle_statut: 'Chez le prestataire',
	perimetre_cible: [],
	jours_sans_avancee: 10,
	a_relancer: false,
	relances: [],
	apercu: '',
	apercu_ia: false,
	batiments: [],
	a_evolue: true,
	motif_evolution: 'nouvelle',
	confidentiel: false,
	public_cible: [],
	reserve_perimetre: false,
	etat_par_defaut: 'en_cours',
	groupe: null,
	fusionnees: [],
};

const RELEVE: SuiviAffaires = {
	jour: '2026-10-17',
	total: 2,
	anciennes: 1,
	fusionnees: 0,
	resumes_disponibles: true,
	delai_jours: 30,
	mode: 'entretien',
	par_categorie: [
		{
			cle: 'entretien',
			libelle: 'Entretien',
			nombre: 2,
			tranches: [{ cle: 'racine', libelle: 'Résidence', nombre: 2, teinte: 'p1' }],
		},
	],
	par_batiment: [
		{
			cle: 'racine',
			libelle: 'Résidence',
			nombre: 2,
			tranches: [{ cle: 'entretien', libelle: 'Entretien', nombre: 2, teinte: 's8' }],
		},
	],
	affaires: [
		{
			...AFFAIRE,
			id: 48,
			numero: 'TK-E00048',
			titre: 'Toitures — Entretien toitures',
			ouverte_le: '2026-01-05',
			age_jours: 285,
			anciennete: 'ancienne',
			etat_visite: 'non_realisee',
		},
		{
			...AFFAIRE,
			id: 90,
			numero: 'TK-000090',
			titre: 'Portes — Maintenance',
			ouverte_le: '2026-10-01',
			age_jours: 16,
			anciennete: 'recente',
			etat_visite: 'a_venir',
		},
	],
};

test('le mode entretien : le bilan des visites, puis les entretiens non clos', async ({ page }) => {
	const lus: string[] = [];
	page.on('request', (r) => {
		const url = new URL(r.url());
		if (url.pathname === '/api/suivi-affaires') lus.push(url.searchParams.get('mode') ?? '');
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/entretiens-periodiques') return REPONSE;
		if (chemin === '/api/suivi-affaires') return RELEVE;
		return undefined;
	});
	await page.goto('/espace-cs/reporting?vue=periodique');
	await attendreHydratation(page);

	//  L'ancienne adresse ouvre le mode, et la barre n'a plus de vue à part.
	await expect(page.getByRole('button', { name: 'Suivi entretiens périodiques' })).toHaveAttribute(
		'aria-pressed',
		'true',
	);
	await expect(page.getByRole('button', { name: /Entretien périodique/ })).toHaveCount(0);
	await expect.poll(() => lus).toContain('entretien');

	//  Le bilan : une réalisée, une en retard — signalée —, une à venir.
	//  Le libellé EXACT : « Réalisées » est contenu dans « Non réalisées ».
	const compteur = (libelle: string) =>
		page.locator('.kpi-card').filter({ has: page.getByText(libelle, { exact: true }) });
	await expect(compteur('Réalisées')).toContainText('1');
	await expect(compteur('Non réalisées')).toContainText('1');
	await expect(compteur('Non réalisées')).toHaveClass(/kpi-alert/);
	await expect(compteur('À venir')).toContainText('1');
	await expect(compteur('À planifier')).toContainText('0');

	//  Le tableau : l'état de la visite à la place de la catégorie, et pas de résumé.
	//  L'en-tête se masque au téléphone (une fiche par ligne) : on lit la cellule.
	await expect(page.locator('table.affaires thead th', { hasText: 'Visite' })).toHaveCount(1);
	const lignes = page.locator('table.affaires tbody tr');
	await expect(lignes).toHaveCount(2);
	await expect(lignes.nth(0)).toContainText('⚠️ Non réalisée');
	await expect(lignes.nth(1)).toContainText('⏳ À venir');
	await expect(page.getByRole('button', { name: /Résumer les affaires/ })).toHaveCount(0);

	//  Les visites RÉALISÉES, que le tableau des non closes ne montre plus, se
	//  listent dans leur section — avant le point CS / Syndic (17/10/2026).
	const realisees = page.getByRole('region', { name: /Visites réalisées/ });
	await expect(realisees.locator('tbody tr')).toHaveCount(1);
	await expect(realisees).toContainText('TK-E00047');
	await expect(realisees).toContainText('DURAND');
	await expect(realisees).not.toContainText('TK-E00048');
	await expect
		.poll(() =>
			page.evaluate(() => {
				const titres = [...document.querySelectorAll('h3')];
				const visites = titres.find((h) => h.textContent?.includes('Visites réalisées'));
				const point = titres.find((h) => h.textContent?.includes('Point CS / Syndic'));
				return Boolean(
					visites &&
					point &&
					visites.compareDocumentPosition(point) & Node.DOCUMENT_POSITION_FOLLOWING,
				);
			}),
		)
		.toBe(true);
});

test('sans entretien en cours, le mode le dit et garde son sélecteur', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/entretiens-periodiques') return { exercice: 2026, visites: [] };
		if (chemin === '/api/suivi-affaires')
			return {
				...RELEVE,
				total: 0,
				anciennes: 0,
				fusionnees: 0,
				par_categorie: [],
				par_batiment: [],
				affaires: [],
			};
		return undefined;
	});
	await page.goto('/espace-cs/reporting?vue=periodique');
	await attendreHydratation(page);
	await expect(page.getByText('Aucun entretien périodique en cours')).toBeVisible();
	//  Aucune visite réalisée : la section se tait, le compteur dit déjà 0.
	await expect(page.getByRole('region', { name: /Visites réalisées/ })).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Suivi affaires' })).toBeVisible();
});
