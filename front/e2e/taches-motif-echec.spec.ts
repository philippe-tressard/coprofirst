/*
 *  **Tâches planifiées : une sauvegarde échouée montre son motif (#1681).**
 *
 *  L'historique d'une tâche vient de TROIS tables (`admin.historiqueTache`) :
 *  la maintenance et l'agrégation portent leur motif dans `erreur`, la
 *  sauvegarde dans `message_erreur`. L'écran ne lisait que le premier : le ⚠️
 *  et son infobulle ne s'affichaient jamais sous une sauvegarde en échec —
 *  celle dont on veut justement savoir pourquoi.
 *
 *  Les deux formes sont rendues ici telles que le serveur les écrit.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

//  La supervision technique est à l'OPÉRATEUR de la plateforme (#1750).
const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin', 'operateur'] };

const tache = (nom: string) => ({
	tache: nom,
	noeud: 'rpi1',
	noeuds: [{ noeud: 'rpi1', statut: 'erreur', derniere: '2026-10-04T04:00:00' }],
	noeud_enregistre: true,
	statut: 'erreur',
	derniere: '2026-10-04T04:00:00',
	noeud_en_retard: null,
	statut_en_retard: null,
});

const SANTE = { taches: [tache('backup'), tache('maintenance')], anomalies_recentes: [] };

/** Une ligne `historique_sauvegarde`, telle que `GET /admin/sauvegardes/historique` la rend. */
const SAUVEGARDE_ECHOUEE = {
	id: 9,
	declenchee_par: 'automatique',
	declenchee_par_user_id: null,
	statut: 'echouee',
	noeud: 'rpi1',
	fichier_nom: null,
	fichier_chemin: null,
	taille_octets: null,
	message_erreur: 'Espace disque insuffisant',
	cree_le: '2026-10-04T04:00:00',
	terminee_le: '2026-10-04T04:00:05',
};

/** Une ligne `historique_maintenance` en échec — le témoin de l'autre forme. */
const MAINTENANCE_ECHOUEE = {
	id: 4,
	tache: 'maintenance',
	noeud: 'rpi1',
	portee: 'applicative',
	declenchee_par: 'cron',
	statut: 'erreur',
	tokens_supprimes: 0,
	taille_db_octets: null,
	duree_secondes: 2,
	details: null,
	erreur: 'VACUUM refusé',
	cree_le: '2026-10-04T03:00:00',
	terminee_le: '2026-10-04T03:00:02',
};

test('le motif d’un échec s’affiche, pour la sauvegarde comme pour la maintenance', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/maintenance/sante') return SANTE;
		if (chemin === '/api/admin/sauvegardes/historique') return [SAUVEGARDE_ECHOUEE];
		if (chemin === '/api/admin/maintenance/historique') return [MAINTENANCE_ECHOUEE];
		return undefined;
	});
	await page.goto('/admin?onglet=maintenance');

	const ligne = (libelle: string) => page.locator('tr.cliquable', { hasText: libelle });

	await ligne('Sauvegarde quotidienne').click();
	await expect(page.locator('tr.detail span[title="Espace disque insuffisant"]')).toHaveText('⚠️');

	await ligne('Maintenance').first().click();
	await expect(page.locator('tr.detail span[title="VACUUM refusé"]')).toHaveText('⚠️');
});
