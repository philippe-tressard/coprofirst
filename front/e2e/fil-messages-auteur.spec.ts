/*
 *  **Chaque message du fil d'une affaire nomme son auteur** (#2680).
 *
 *  L'écran lisait `msg.auteur`, un objet que `MessageRead` n'a jamais servi :
 *  sur `/tickets/{id}`, toutes les bulles avaient un nom VIDE, et ses propres
 *  messages n'étaient jamais posés à droite (`own`). Le nom est désormais SERVI
 *  (`auteur_nom`, `utils/noms.nom_auteur`, tenu par `test_fil_messages_auteur.py`) ;
 *  l'écran le lit tel quel, et range à droite ceux que le serveur dit siens
 *  (`est_auteur`) — il ne compare pas les identifiants lui-même (`lint:droits`).
 *
 *  API simulée, compte témoin (`MEMBRE_CS`, id 1).
 */
import { MEMBRE_CS, attendreHydratation, expect, simulerApi, test } from './aides';

const AFFAIRE = {
	id: 7,
	numero: 'TK-109008',
	titre: 'Portillon bloqué',
	description: 'Le portillon du parking ne se referme plus.',
	categorie: 'etude_travaux',
	statut: 'en_cours',
	priorite: 'normale',
	auteur_id: 2,
	auteur_nom: 'Alice DURAND',
	cree_le: '2026-09-29T10:00:00',
	mis_a_jour_le: '2026-09-29T10:00:00',
	perimetre_cible: [],
	photos_urls: [],
	fichiers_urls: [],
};

/** Trois messages tels que le serveur les sert : un voisin, le témoin, un auteur détaché. */
const MESSAGES = [
	{
		auteur_id: 2,
		auteur_nom: 'Alice DURAND',
		est_auteur: false,
		contenu: '<p>Il bloque encore.</p>',
	},
	{
		auteur_id: MEMBRE_CS.id,
		auteur_nom: 'CS TÉMOIN',
		est_auteur: true,
		contenu: '<p>Devis demandé.</p>',
	},
	{ auteur_id: null, auteur_nom: 'Un résident', est_auteur: false, contenu: '<p>Merci.</p>' },
].map((m, i) => ({
	...m,
	id: 80 + i,
	ticket_id: 7,
	auteur_qualite: null,
	interne: false,
	cree_le: `2026-09-30T0${i + 1}:00:00`,
	fichiers_urls: [],
}));

test.beforeEach(async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/7') return AFFAIRE;
		if (chemin === '/api/tickets/7/messages') return MESSAGES;
	});
	await page.goto('/tickets/7');
	await attendreHydratation(page);
});

test("chaque bulle nomme l'auteur que le serveur sert", async ({ page }) => {
	const noms = page.locator('.message-bubble .msg-header strong');
	await expect(noms).toHaveText(['Alice DURAND', 'CS TÉMOIN', 'Un résident']);
});

test('seuls les messages du lecteur sont marqués comme les siens', async ({ page }) => {
	const bulles = page.locator('.message-bubble');
	await expect(bulles).toHaveCount(3);
	await expect(page.locator('.message-bubble.own')).toHaveCount(1);
	await expect(page.locator('#msg-81')).toHaveClass(/(^|\s)own(\s|$)/);
	await page.screenshot({
		path: `test-results/fil-messages-auteur-${test.info().project.name}.png`,
		fullPage: true,
	});
});
