/*
 *  **Playwright — la vérification de l'écran, enfin exécutable.**
 *
 *  ## Pourquoi (06/09/2026)
 *
 *  Le projet n'avait AUCUN test de navigateur : `api/tests/` couvre le serveur,
 *  les linters lisent la source, `svelte-check` lit les types. Tout ce qui ne se
 *  voit qu'à l'écran — un lien d'évitement qui prend le focus, une carte qui se
 *  replie, un titre qui disparaît sur téléphone — n'était vérifiable que par un
 *  coup d'oeil humain. C'est ce que dit le post-check P7, et c'est la raison
 *  pour laquelle plusieurs défauts d'interface ont été trouvés par l'utilisateur
 *  et non par un contrôle (#787, #802, la vignette du calendrier).
 *
 *  ## Ce que ces tests peuvent voir, et ce qu'ils ne peuvent pas
 *
 *  🔴 **Le site est derrière une connexion.** Sans session, seuls `/auth/*` et le
 *  squelette sont atteignables — c'est le périmètre de ce premier lot. Couvrir
 *  les écrans applicatifs demande un compte de test et une décision sur l'endroit
 *  où vivent ses identifiants : cela ne s'improvise pas dans un fichier versionné
 *  (`standards/03` §2). Voir `e2e/README.md`.
 *
 *  ⚠️ `vite dev` proxifie `/api` vers `localhost:8000`. Sans API lancée, les
 *  appels échouent — les tests d'ici n'en font aucun, et un test qui en ferait
 *  devrait le déclarer plutôt que d'attendre un serveur qui n'est pas là.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

/** Le processus existe-t-il encore ? `kill(pid, 0)` interroge sans rien envoyer. */
function vivant(pid: number): boolean {
	try {
		process.kill(pid, 0);
		return true;
	} catch {
		return false;
	}
}

/*
 *  ## 🔴 Un serveur À SOI, sur un port à soi (#1150, 25/09/2026)
 *
 *  Le port était 5173 — celui de `npm run dev` — avec `reuseExistingServer:
 *  true`. Toute exécution trouvant quelque chose sur ce port s'y branchait sans
 *  un mot : le serveur de développement du poste, ou celui d'une AUTRE session,
 *  dans un autre worktree. Deux conséquences, mesurées :
 *
 *  1. **L'intermittence.** Deux exécutions qui se chevauchent : la seconde
 *     réutilise le serveur de la première, qui l'arrête en finissant — et la
 *     seconde tombe en `ERR_CONNECTION_REFUSED` sur un test différent à chaque
 *     fois (squelette, message-erreur-401, etoile-requis : les trois du ticket).
 *     Reproduit à coup sûr ; jamais en isolé, jamais en CI — c'est ce qui l'a
 *     fait prendre pour une affaire de charge.
 *  2. **Le faux vert**, plus grave : un serveur réutilisé sert le code de
 *     CELUI QUI L'A LANCÉ. Le rejeu de la CI pouvait donc valider l'arbre d'un
 *     autre worktree, et `rejouer-ci.sh` dire vert sur ce qu'il n'avait pas lu.
 *
 *  D'où : un port par exécution, choisi par le processus principal et transmis
 *  aux workers par l'environnement (ils relisent ce fichier, et héritent de
 *  `process.env` — un choix refait ici donnerait un port par worker). Jamais
 *  de réutilisation : un port déjà pris est une ERREUR explicite, pas un
 *  serveur qu'on emprunte. `--strictPort` empêche Vite de se replier en
 *  silence sur un port voisin pendant que Playwright interroge le premier.
 *
 *  ⚠️ Le port ne protège qu'ENTRE deux dossiers. Dans le MÊME, deux exécutions
 *  partagent aussi `test-results/`, que Playwright vide en démarrant : la
 *  seconde effaçait les traces que la première écrivait (`ENOENT … .trace`,
 *  mesuré le même jour). La seconde est donc REFUSÉE, avec le pid de la
 *  première — un verrou posé par le seul processus principal, puisque lui seul
 *  n'a pas encore de port. Un verrou dont le processus est mort ne retient rien.
 */
/*
 *  ## Le port se DEMANDE au système, il ne se déduit pas (#2051, 17/10/2026)
 *
 *  Il valait `5300 + pid % 600` : la plage couvrait 5432, le port du
 *  PostgreSQL que la suite exige sur le poste (#1747). Une relance (#1809)
 *  tombée dessus a rendu un faux rouge — « Port 5432 is already in use » — sur
 *  un lot qui ne touchait aucun écran. Écarter 5432 ne protégerait que de lui :
 *  un port demandé au système (`listen(0)`) n'est jamais un port tenu. On le
 *  relâche aussitôt pour Vite ; si un autre le prend dans l'intervalle,
 *  `--strictPort` le dit au lieu de servir ailleurs. Synchrone parce que la
 *  config l'est : un enfant Node écoute, imprime le port, et se ferme.
 *  `lint:e2e-serveur` refuse un port déduit.
 */
function portLibre(): number {
	const sonde =
		"const s = require('node:net').createServer();" +
		"s.listen(0, '127.0.0.1', () => { process.stdout.write(String(s.address().port)); s.close(); });";
	const port = Number(execFileSync(process.execPath, ['-e', sonde], { encoding: 'utf8' }).trim());
	if (!Number.isInteger(port) || port <= 0) throw new Error(`Port e2e illisible : « ${port} ».`);
	return port;
}

if (!process.env.E2E_PORT) {
	const verrou = fileURLToPath(new URL('.e2e-en-cours', import.meta.url));
	const tenant = existsSync(verrou) ? Number(readFileSync(verrou, 'utf8')) : 0;
	if (tenant && tenant !== process.pid && vivant(tenant)) {
		throw new Error(
			`Une exécution e2e tourne déjà dans ce dossier (pid ${tenant}). ` +
				`Deux exécutions ici partagent test-results/ et s'effacent l'une l'autre : attendre la fin.`,
		);
	}
	writeFileSync(verrou, String(process.pid));
	process.on('exit', () => {
		if (existsSync(verrou) && readFileSync(verrou, 'utf8') === String(process.pid)) rmSync(verrou);
	});
	process.env.E2E_PORT = String(portLibre());
}
const PORT = Number(process.env.E2E_PORT);
//  🔴 UNE adresse, IPv4, la même pour Vite (`--host`, plus bas) et pour les
//  tests (#1732, 08/10/2026). Avec `localhost`, Vite écoutait sur `::1` seul et
//  le navigateur tentait aussi `127.0.0.1` : connexions refusées par
//  intermittence, un spec différent à chaque passage. `lint:e2e-serveur` refuse
//  `localhost` ici.
const BASE = `http://127.0.0.1:${PORT}`;

/*
 *  ## Le nombre de workers, réglable par `E2E_WORKERS` (#1665, 04/10/2026)
 *
 *  Sur un poste déjà occupé par d'autres sessions, les workers se disputent la
 *  machine : quatre specs d'administration tombaient en délai d'hydratation,
 *  vertes seules et vertes à un worker (335/335). `rejouer-ci.sh` mesure la
 *  charge et pose la variable ; absente — en CI —, c'est le défaut de Playwright.
 *  Une valeur illisible est une ERREUR : l'ignorer rejouerait en silence dans
 *  les conditions qu'on voulait éviter.
 */
const WORKERS_DEMANDES = process.env.E2E_WORKERS;
if (WORKERS_DEMANDES && !/^[1-9][0-9]*$/.test(WORKERS_DEMANDES)) {
	throw new Error(`E2E_WORKERS doit être un entier positif, reçu « ${WORKERS_DEMANDES} ».`);
}

export default defineConfig({
	testDir: './e2e',
	//  Pas de test « flaky » toléré en silence : un test d'interface qui échoue
	//  une fois sur deux ne dit rien, et on finit par ne plus le lire.
	retries: 0,
	workers: WORKERS_DEMANDES ? Number(WORKERS_DEMANDES) : undefined,
	//  ⚠️ Le rapport HTML ne s'ouvre PAS tout seul : en session non interactive il
	//  bloquerait sur un serveur qui attend une touche.
	//  `rapport-hydratation` : le bilan des durées d'hydratation du passage (#1475).
	reporter: [
		['list'],
		['html', { open: 'never', outputFolder: 'e2e-rapport' }],
		['./e2e/rapport-hydratation.ts'],
	],
	use: {
		baseURL: BASE,
		//  La trace n'est gardée que sur échec : c'est là qu'elle sert, et elle
		//  pèse quelques mégaoctets par test.
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
	},
	projects: [
		{ name: 'bureau', use: { ...devices['Desktop Chrome'] } },
		//  🔴 Le mobile n'est PAS une option. La responsivité est une exigence
		//  permanente (`standards/11` §10), et c'est sur téléphone que le titre des
		//  cartes disparaissait (#453, `EnteteCarte`).
		{ name: 'mobile', use: { ...devices['Pixel 5'] } },
	],
	webServer: {
		command: `npm run dev -- --host 127.0.0.1 --port ${PORT} --strictPort`,
		url: BASE,
		reuseExistingServer: false,
		timeout: 120_000,
		//  La sortie du serveur est LUE (#1421) : c'est là que Vite annonce qu'il
		//  recharge la page en plein test (« optimized dependencies changed.
		//  reloading »). L'étape de CI la cherche et échoue en nommant la
		//  dépendance — sans cela, le rechargement ne se voyait que par des tests
		//  qui tombaient au hasard.
		stdout: 'pipe',
	},
});
