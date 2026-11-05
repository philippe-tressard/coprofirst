/*
 *  **Reporting › Renouvellements lit le relevé SERVI** (#2525, 05/11/2026).
 *
 *  Les échéances, l'ordre des contrats (la pire note d'abord), les compteurs du
 *  bandeau et l'année de référence se calculaient dans `#lib/reporting.ts` — avec
 *  l'année du NAVIGATEUR. Ils viennent de `GET /reporting/renouvellements`, que
 *  l'app iOS lit aussi. Le relevé simulé porte des compteurs qu'aucun calcul local
 *  ne retrouverait (un seul contrat, trois « en préavis ») et une année qui n'est
 *  pas celle du poste : si l'écran recalculait, il le dirait autrement.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';
import type { ReleveRenouvellements } from '../src/lib/api';

const ANNEE = 2031;
const PRESTATAIRE = 'Ascenseurs Durand';
const LIBELLE_CONTRAT = 'Entretien ascenseur';
const DIAGNOSTIC = 'Contrôle ascenseur';

const CONTRAT = {
	id: 1,
	copropriete_id: 1,
	prestataire_id: 7,
	prestataire_nom: PRESTATAIRE,
	note_moyenne: 2,
	nb_notations: 3,
	type_equipement: 'ascenseur',
	libelle: LIBELLE_CONTRAT,
	date_debut: `${ANNEE}-01-01`,
	date_fin: `${ANNEE}-12-01`,
	date_preavis: `${ANNEE}-09-01`,
	urgence_echeance: 'annee',
	reconduit: false,
	echu: false,
	actif: true,
	echeance_dans_l_annee: true,
} as unknown as ReleveRenouvellements['contrats'][number];

const DIAG = {
	id: 3,
	code: 'ASC',
	nom: DIAGNOSTIC,
	texte_legislatif: 'Code de la construction',
	frequence: '5 ans',
	ordre: 1,
	non_applicable: false,
	rapports: [],
	permanent: false,
	dernier_rapport_le: `${ANNEE - 5}-06-01`,
	prochaine_echeance: `${ANNEE}-06-01`,
	urgence_echeance: 'annee',
} as unknown as ReleveRenouvellements['diagnostics'][number];

const RELEVE: ReleveRenouvellements = {
	annee: ANNEE,
	preavis_mois: 3,
	compteurs: { contrats_en_preavis: 3, echeances_contrats_annee: 1, audits_a_planifier: 4 },
	contrats: [CONTRAT],
	diagnostics: [DIAG],
};

test('les renouvellements affichent le relevé servi, sans le recalculer', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/reporting/renouvellements' ? RELEVE : undefined,
	);
	await page.goto('/espace-cs/reporting?vue=renouvellements');
	await attendreHydratation(page);

	const compteur = (libelle: RegExp) =>
		page.locator('.kpi-card', { hasText: libelle }).locator('.kpi-value');
	await expect(compteur(/Contrats en préavis/)).toHaveText('3');
	await expect(compteur(new RegExp(`Échéances contrats en ${ANNEE}`))).toHaveText('1');
	await expect(compteur(/Audits à \(re\)planifier/)).toHaveText('4');

	//  La frise et les audits lisent l'année du relevé, pas celle du poste.
	await expect(page.getByText(LIBELLE_CONTRAT)).toBeVisible();
	await expect(page.getByText(PRESTATAIRE)).toBeVisible();
	await expect(page.getByRole('cell', { name: DIAGNOSTIC })).toBeVisible();
	await expect(page.getByText(`À faire en ${ANNEE}`)).toBeVisible();
});
