/*
 *  **Une erreur vue à l'écran laisse une trace côté serveur** (#1631, 02/10/2026).
 *
 *  Le 16/09/2026, une clé `{#each}` répétée a figé un écran pendant que le
 *  serveur était vert : la cause ne se lisait que dans la console du résident.
 *  Ces tests tiennent les trois bouts — le signalement part dans le lot de la
 *  mesure d'audience, il ne porte jamais le message brut, et l'administrateur
 *  le lit dans l'onglet Télémétrie, téléphone compris.
 */
import {
	attendreHydratation,
	deplierSectionTelemetrie,
	type Evenement,
	expect,
	lotsEnvoyes,
	MEMBRE_CS,
	simulerApi,
	TABLEAU_TELEMETRIE_VIDE,
	test,
	viderLaFile,
} from './aides';
import { attendreSansDefilementHorizontal, elargirLeTexte } from './defilement';

const erreurs = (recus: Evenement[]) => recus.filter((e) => e.action === 'erreur');

test('une réponse 5xx se signale par son statut et son chemin, identifiants masqués', async ({
	page,
}) => {
	await simulerApi(page);
	const recus = await lotsEnvoyes(page);
	await page.route(
		(url) => url.pathname === '/api/signalements',
		(route) =>
			route.fulfill({ status: 502, contentType: 'application/json', body: '{"detail":"x"}' }),
	);
	await page.goto('/sondages');
	await attendreHydratation(page);
	await expect(page.locator('.etat-erreur').first()).toBeVisible();

	await viderLaFile(page);
	await expect.poll(() => erreurs(recus).map((e) => e.detail)).toContain('HTTP 502 /signalements');
	expect(erreurs(recus).every((e) => e.page === '/sondages')).toBe(true);
});

test('une exception se signale par son nom, sans ce qui est entre guillemets ni les nombres', async ({
	page,
}) => {
	await simulerApi(page);
	const recus = await lotsEnvoyes(page);
	await page.goto('/sondages');
	await attendreHydratation(page);

	//  Un `ErrorEvent` posté à la main : ce que le navigateur fait d'une exception
	//  non rattrapée, sans en lever une — le `test` des specs en ferait un échec.
	await page.evaluate(() => {
		const erreur = new TypeError('Lecture de « saisie privée » impossible au rang 42');
		for (let i = 0; i < 3; i++) {
			window.dispatchEvent(new ErrorEvent('error', { error: erreur, message: erreur.message }));
		}
	});
	await viderLaFile(page);

	await expect.poll(() => erreurs(recus).length).toBe(1);
	expect(erreurs(recus)[0].detail).toBe('TypeError: Lecture de … impossible au rang #');
});

test('une erreur d’un script étranger ne s’impute pas au site', async ({ page }) => {
	//  03/10/2026 : `t().filter is not a function`, du code ES5 qu'aucun fichier
	//  servi ne contient (`erreurDuSite`, `#lib/telemetry`). Trois provenances
	//  étrangères, puis une erreur du site : seule la dernière se compte — sans
	//  elle, un filtre qui tairait TOUT passerait ce test.
	await simulerApi(page);
	const recus = await lotsEnvoyes(page);
	await page.goto('/sondages');
	await attendreHydratation(page);

	await page.evaluate(() => {
		const poster = (erreur: unknown, filename?: string) =>
			window.dispatchEvent(
				new ErrorEvent('error', { error: erreur, message: String(erreur), filename }),
			);
		poster(new TypeError('extension masquée'), 'webkit-masked-url://hidden/');
		poster(new TypeError('script de l’arête'), `${location.origin}/cdn-cgi/scripts/x.js`);
		//  Une `Error` d'un AUTRE contexte JavaScript — le `object:` du relevé.
		const cadre = document.createElement('iframe');
		document.body.append(cadre);
		const Etrangere = (cadre.contentWindow as unknown as { TypeError: TypeErrorConstructor })
			.TypeError;
		poster(new Etrangere('autre contexte'));
		cadre.remove();
		poster(new TypeError('erreur du site'), `${location.origin}/_app/immutable/x.js`);
	});
	await viderLaFile(page);

	await expect.poll(() => erreurs(recus).length).toBe(1);
	expect(erreurs(recus)[0].detail).toBe('TypeError: erreur du site');
});

test('l’administrateur lit les erreurs dans l’onglet Télémétrie, sans défilement horizontal', async ({
	page,
}) => {
	const codeLong = 'svelte:each_key_duplicate_avec_un_nom_tres_long_qui_ne_se_coupe_nulle_part';
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
		if (chemin === '/api/telemetry/dashboard')
			return {
				...TABLEAU_TELEMETRIE_VIDE,
				erreurs: [
					{
						page: '/tickets/12',
						code: codeLong,
						total: 3,
						premiere_le: '2026-10-02T08:00:00',
						derniere_le: '2026-10-02T09:30:00',
					},
				],
			};
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);

	const section = await deplierSectionTelemetrie(page, 'Erreurs vues par les résidents');
	const ligne = section.getByRole('row', { name: new RegExp(codeLong) });
	await expect(ligne).toBeVisible();
	await expect(ligne.getByRole('cell').nth(1)).toHaveText('3');
	//  Au téléphone, un code long fait défiler la CARTE et jamais la page : les
	//  cellules ne vont pas à la ligne et la carte défile (`normes.css`, la règle
	//  de tous les tableaux). ⚠️ Mesuré sur la page : le tableau, lui, SORT de sa
	//  carte par construction — c'est la carte qui défile.
	await elargirLeTexte(page);
	await attendreSansDefilementHorizontal(page);
});

test('une erreur sur la page de connexion part au journal, hors du squelette de l’application', async ({
	page,
}) => {
	//  #2066 : l'envoi n'était armé que par le squelette `(app)`. Sur `/auth/*`,
	//  la file ne partait qu'au vingtième événement — jamais — et les erreurs non
	//  rattrapées n'étaient pas même écoutées : le journal ne voyait rien des
	//  écrans qu'on ouvre juste après une MEP.
	const recus = await lotsEnvoyes(page);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	await page.evaluate(() => {
		const erreur = new TypeError('connexion impossible');
		window.dispatchEvent(new ErrorEvent('error', { error: erreur, message: erreur.message }));
	});
	await viderLaFile(page);

	await expect
		.poll(() => erreurs(recus).map((e) => e.detail))
		.toContain('TypeError: connexion impossible');
	expect(erreurs(recus).every((e) => e.page === '/auth/connexion')).toBe(true);
});

test('un rejet de promesse non rattrapé sur la page de connexion part aussi au journal', async ({
	page,
}) => {
	//  #2066 : le second écouteur posé par `initTelemetry`, `unhandledrejection`.
	//  Posté à la main, avec une promesse déjà tenue : un vrai rejet non rattrapé
	//  ferait échouer le `test` des specs.
	const recus = await lotsEnvoyes(page);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	await page.evaluate(() => {
		window.dispatchEvent(
			new PromiseRejectionEvent('unhandledrejection', {
				promise: Promise.resolve(),
				reason: new RangeError('délai dépassé'),
			}),
		);
	});
	await viderLaFile(page);

	await expect
		.poll(() => erreurs(recus).map((e) => e.detail))
		.toContain('RangeError: délai dépassé');
});
