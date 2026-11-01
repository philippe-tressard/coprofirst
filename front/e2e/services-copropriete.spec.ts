/*
 *  **Admin › Services : les services de la copropriété sur un seul écran (#1718).**
 *
 *  Le VRAI écran, API simulée. Ce que l'administrateur doit voir : une carte par
 *  service, telle que le registre du serveur la décrit (rien n'est écrit dans
 *  l'écran) ; l'état en pastille, ce qui manque quand un service activé ne peut
 *  pas fonctionner ; une case qui écrit la clé d'activation et relit l'état ; et
 *  l'envoi des courriels SANS case — il porte les courriels de sécurité. Sur
 *  bureau et sur téléphone, sans défilement horizontal.
 */
import { expect, simulerApi, test, MEMBRE_CS } from './aides';
import type { ServiceCopropriete } from '../src/lib/api';
import { attendreSansDefilementHorizontal } from './defilement';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

function service(champs: Partial<ServiceCopropriete> & { code: string }): ServiceCopropriete {
	return {
		libelle: champs.code,
		description: 'Ce que fait le service.',
		perte: 'Ce qu’on perd en le coupant.',
		plafond: '',
		onglet: 'ia',
		onglet_dedie: false,
		icone: 'settings',
		coupable: true,
		cle_actif: `${champs.code}_cle`,
		etat: 'actif',
		manque: [],
		autorise: true,
		refus: '',
		...champs,
	};
}

test('Admin › Services : état, manque, bascule et infrastructure sans case', async ({ page }) => {
	let whatsapp: ServiceCopropriete['etat'] = 'incomplet';
	const ecrits: Record<string, string>[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PUT' && new URL(r.url()).pathname === '/api/config') {
			ecrits.push(r.postDataJSON());
		}
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/services')
			return [
				service({
					code: 'assistant_ia',
					libelle: 'Assistant IA',
					icone: 'lightbulb',
					cle_actif: 'llm_actif',
					plafond: 'Par usage : un nombre d’appels par mois.',
				}),
				service({
					code: 'diffusion',
					libelle: 'Diffusion sur le groupe WhatsApp',
					icone: 'whatsapp',
					onglet: 'whatsapp',
					onglet_dedie: true,
					cle_actif: 'whatsapp_enabled',
					etat: whatsapp,
					manque: whatsapp === 'incomplet' ? ['l’adresse du relais WhatsApp'] : [],
				}),
				service({
					code: 'envoi_courriels',
					libelle: 'Envoi des courriels',
					onglet: 'smtp',
					coupable: false,
					cle_actif: null,
				}),
			];
		return undefined;
	});
	await page.goto('/admin?onglet=services');

	const carte = (titre: string) => page.locator('section[data-service]', { hasText: titre });
	await expect(page.locator('section[data-service]')).toHaveCount(3);
	await expect(carte('Assistant IA').locator('.badge')).toHaveText('Activé');
	await expect(carte('Assistant IA')).toContainText('Plafond');
	await expect(carte('WhatsApp').locator('.badge')).toHaveText('Activé, incomplet');
	await expect(carte('WhatsApp')).toContainText('Il manque l’adresse du relais WhatsApp');

	//  L'infrastructure se montre, elle ne se coupe pas.
	await expect(carte('Envoi des courriels').locator('input[type="checkbox"]')).toHaveCount(0);
	await expect(carte('Envoi des courriels')).toContainText('Ne se coupe pas');

	//  Le lien mène à l'onglet de réglages déclaré par le registre.
	await expect(carte('WhatsApp').locator('a.reglages')).toHaveAttribute(
		'href',
		'/admin?onglet=whatsapp',
	);

	//  L'onglet de réglages d'un service dédié se grise quand il est coupé — pas avant.
	const ongletWhatsApp = page.locator('a.tab-btn[href="/admin?onglet=whatsapp"]');
	await expect(ongletWhatsApp).not.toHaveClass(/eteint/);

	//  Couper : la clé d'activation part à `PUT /config`, puis l'état se relit.
	whatsapp = 'coupe';
	await carte('WhatsApp').getByLabel('Activé').uncheck();
	await expect.poll(() => ecrits).toEqual([{ whatsapp_enabled: '0' }]);
	await expect(carte('WhatsApp').locator('.badge')).toHaveText('Coupé');
	await expect(carte('WhatsApp').getByLabel('Activé')).not.toBeChecked();
	await expect(ongletWhatsApp).toHaveClass(/eteint/);
	//  Grisé, pas fermé : il s'ouvre, dit l'état, et ne porte AUCUNE case d'activation.
	await ongletWhatsApp.click();
	await expect(page.locator('.etat-service .badge')).toHaveText('Coupé');
	await expect(page.getByLabel(/Activer l'envoi WhatsApp/)).toHaveCount(0);

	await attendreSansDefilementHorizontal(page);
	await page.screenshot({ path: test.info().outputPath('services.png'), fullPage: true });
});

test('Admin › Services : sur une réplique, un service non autorisé par la référence est grisé', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/services')
			return [
				service({
					code: 'assistant_ia',
					libelle: 'Assistant IA',
					cle_actif: 'llm_actif',
					etat: 'coupe',
					autorise: false,
					refus:
						'Non autorisé par la référence : inscription en attente de validation par la référence.',
				}),
				service({
					code: 'verification_version',
					libelle: 'Vérification de la version',
					etat: 'coupe',
				}),
			];
		return undefined;
	});
	await page.goto('/admin?onglet=services');
	const carte = (titre: string) => page.locator('section[data-service]', { hasText: titre });
	await expect(carte('Assistant IA').getByLabel('Activé')).toBeDisabled();
	await expect(carte('Assistant IA')).toContainText('Non autorisé par la référence');
	await expect(carte('Vérification de la version').getByLabel('Activé')).toBeEnabled();
});
