/**
 * Ce build est-il celui de cette source ? (#2976)
 *
 * Cinq contrôles lisent le build du front (`build/`, `.svelte-kit/output/`) :
 * `lint:poids-ouverture`, `lint:version-servie`, `lint:csp`, `lint:sw`, `e2e:sw`.
 * Lancés seuls au poste sur le build d'une version précédente, ils jugeaient ce
 * build-là sans le dire : `lint:poids-ouverture` rendait « ✓ », et
 * `lint:version-servie` accusait son extracteur (« il capture autre chose que la
 * version du paquet ») alors qu'il lisait juste la version… du build précédent.
 * En CI, `npm run build` les précède : le défaut ne se voyait qu'au poste.
 *
 * La question se pose par les DATES : un build plus ancien que le fichier de
 * source le plus récent (`src/`, `static/`, `package.json`, la configuration de
 * Vite) n'est pas celui de cette source. Un `git checkout`, un `merge` ou une
 * édition rajeunissent les fichiers qu'ils touchent ; en CI, le build suit le
 * clone. Un build PÉRIMÉ rend INCONNU — jamais OK, jamais une fausse accusation.
 *
 * Lancer : node scripts/lib-build-a-jour.mjs --selftest
 */
import { existsSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = fileURLToPath(new URL('..', import.meta.url));

/** Ce dont le build est fait — un fichier plus récent que lui le rend périmé. */
export const SOURCES_DU_BUILD = [
	'src',
	'static',
	'package.json',
	'vite.config.ts',
	'tsconfig.json',
];

/** Code de sortie d'un contrôle qui n'a pas pu mesurer (le motif de `check-csp-servie`). */
export const CODE_INCONNU = 2;

/**
 * PURE — le verdict, à partir de deux dates (millisecondes).
 * @param {number | null} dateBuild  date du build lu, `null` s'il manque
 * @param {{ date: number, chemin: string } | null} plusRecente  le fichier de source le plus récent
 * @returns {{ etat: 'a-jour' | 'perime' | 'inconnu', raison: string }}
 */
export function verdictBuild(dateBuild, plusRecente) {
	if (dateBuild === null) return { etat: 'inconnu', raison: 'aucun build à lire' };
	if (!plusRecente) return { etat: 'inconnu', raison: 'aucune source lue — la portée est cassée' };
	if (plusRecente.date > dateBuild) {
		const ecart = Math.round((plusRecente.date - dateBuild) / 60000);
		return {
			etat: 'perime',
			raison:
				`le build est plus ancien que la source (${plusRecente.chemin}, ` +
				`${ecart} min plus récent) — relancer \`npm run build\``,
		};
	}
	return { etat: 'a-jour', raison: '' };
}

/** Le fichier le plus récent sous `chemins` (relatifs à `racine`), `node_modules` exclus. */
export function sourceLaPlusRecente(racine = RACINE, chemins = SOURCES_DU_BUILD) {
	let meilleur = null;
	const visiter = (chemin) => {
		if (!existsSync(chemin)) return;
		const info = statSync(chemin);
		if (info.isDirectory()) {
			for (const nom of readdirSync(chemin)) if (nom !== 'node_modules') visiter(join(chemin, nom));
		} else if (!meilleur || info.mtimeMs > meilleur.date) {
			meilleur = { date: info.mtimeMs, chemin: relative(racine, chemin) };
		}
	};
	for (const c of chemins) visiter(join(racine, c));
	return meilleur;
}

/**
 * Le build lu par un contrôle est-il celui de cette source ? `ecrit` : un fichier
 * que le build ÉCRIT à chaque fois (le manifeste de Vite, `build/index.js`) —
 * jamais un dossier : les fichiers de `static/` y sont copiés, et une copie peut
 * garder la date de l'original.
 */
export function etatDuBuild(ecrit, racine = RACINE) {
	const date = existsSync(ecrit) ? statSync(ecrit).mtimeMs : null;
	return verdictBuild(date, sourceLaPlusRecente(racine));
}

/**
 * La garde, telle que les contrôles l'appellent : rend `true` si le build est à
 * jour ; sinon écrit `INCONNU : …` et rend `false` — au contrôle de sortir en
 * `CODE_INCONNU`. Un build ABSENT reste l'affaire de chaque contrôle (son message
 * dit déjà quoi faire) : seule la péremption se juge ici.
 */
export function buildDeCetteSource(ecrit, nomDuControle) {
	if (!existsSync(ecrit)) return true;
	const { etat, raison } = etatDuBuild(ecrit);
	if (etat === 'a-jour') return true;
	console.error(
		`\nINCONNU : ${nomDuControle} — ${raison}.\n  Ce contrôle n'a pas jugé ce build.\n`,
	);
	return false;
}

function selftest() {
	let ko = 0;
	const t = (quoi, obtenu, attendu) => {
		const ok = obtenu === attendu;
		if (!ok) ko++;
		console.log(`${ok ? '✓' : '✗'} ${quoi}${ok ? '' : ` — obtenu ${obtenu}, attendu ${attendu}`}`);
	};
	const H = 3_600_000;
	const src = (date, chemin = 'src/a') => ({ date, chemin });
	t('build après la source : à jour', verdictBuild(10 * H, src(9 * H)).etat, 'a-jour');
	t('build à la même date : à jour', verdictBuild(10 * H, src(10 * H)).etat, 'a-jour');
	//  Le cas fautif de #2976 : le build de la version précédente, la source a bougé.
	t(
		'source plus récente : périmé',
		verdictBuild(9 * H, src(10 * H, 'package.json')).etat,
		'perime',
	);
	t(
		'la raison nomme le fichier',
		verdictBuild(9 * H, src(10 * H, 'package.json')).raison.includes('package.json'),
		true,
	);
	t('pas de build : inconnu', verdictBuild(null, src(1)).etat, 'inconnu');
	t('aucune source : inconnu, jamais à jour', verdictBuild(10 * H, null).etat, 'inconnu');
	//  Cas zéro : la vraie source se lit.
	t('la source du front est lue', sourceLaPlusRecente() !== null, true);
	console.log(ko ? `== ${ko} ÉCHEC(S) ==` : '== TOUS OK ==');
	process.exit(ko ? 1 : 0);
}

if (process.argv[1] === fileURLToPath(import.meta.url) && process.argv.includes('--selftest')) {
	selftest();
}
