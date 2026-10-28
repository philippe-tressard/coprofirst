/**
 * Garde-fou — **un événement dispatché doit être traité par quelqu'un**.
 *
 * ## Pourquoi (#505)
 *
 * Le 19/08/2026, l'utilisateur signale à l'écran : « Anomalie de mon commentaire…
 * Je ne peux plus annuler. » `evol_annuler` était dispatché par `EvolForm`,
 * relayé par `CarteTicket`, **transféré** par `ListeTickets` (`on:evol_annuler`
 * nu) — et personne ne l'attrapait au bout. Le formulaire de correction restait
 * ouvert, le bouton Annuler ne faisait rien. Le défaut a vécu neuf jours.
 *
 * Rien ne pouvait le voir :
 *   - `svelte-check` ne dit rien : le code est valide des deux côtés ;
 *   - un événement **non écouté** n'est pas une erreur en Svelte, c'est un silence ;
 *   - le **transfert** (`on:X` sans accolades) rend la chaîne plausible à la
 *     relecture : on voit l'événement passer, on suppose qu'il arrive.
 *
 * Même famille que les classes employées sans définition (`lint:classes-nues`) :
 * ce qui manque n'est visible qu'en **croisant deux fichiers**, jamais en lisant
 * l'un des deux.
 *
 * ⚠️ Le relevé qui a fondé ce contrôle a trouvé **trois autres orphelins** que
 * personne ne cherchait : `RubriqueHistorique` dispatchait `supprimer` sur cinq
 * écrans, et seuls les deux du ticket l'écoutaient. Le bouton 🗑️ s'affichait
 * pour tout administrateur sur le Calendrier, les Actualités et l'Espace CS ;
 * le clic ne faisait rien. La correction d'un seul cas aurait laissé les trois.
 *
 * ## Ce que ce contrôle cherche
 *
 * Pour chaque `dispatch('X')` d'un composant, il suit la chaîne de ses points
 * d'usage : `on:X={…}` **traite**, `on:X` **nu** transfère (l'événement remonte,
 * on continue chez le parent). Il échoue si, au bout de tous les chemins, aucun
 * appelant ne traite l'événement.
 *
 * 🔴 **Il résout les ALIAS d'import et indexe par CHEMIN.** Ces deux points ne
 * sont pas des détails : la première version indexait par nom de fichier — les
 * ~30 routes s'appellent toutes `+page.svelte` et s'écrasaient — et cherchait
 * `<NomDuFichier` alors que `ApercuDiffusion.svelte` est importé sous le nom
 * `ApercuDiffusionModale`. Résultat : **quatre faux positifs sur quatre**. Le
 * self-test ci-dessous éprouve les deux cas, parce qu'un contrôle qui se trompe
 * finit désarmé (`standards/04`).
 *
 * ## Ce qu'il ne cherche PAS
 *
 * Les événements volontairement optionnels, déclarés dans `TOLERANCES` avec leur
 * raison. Une tolérance muette redevient l'angle mort qu'on ferme — et une
 * tolérance qui ne sert plus fait échouer le contrôle.
 *
 * Éprouvé en réintroduisant chaque forme, une par une — voir `--selftest`.
 */
import {
	readFileSync,
	readdirSync,
	statSync,
	mkdtempSync,
	mkdirSync,
	writeFileSync,
	rmSync,
} from 'node:fs';
import { join, relative, basename, dirname } from 'node:path';
import { tmpdir } from 'node:os';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**
 * Événements dispatchés que PERSONNE n'a à traiter, **avec la raison**.
 * Clé : `Composant.evenement`. Une tolérance qui ne sert plus fait échouer.
 */
const TOLERANCES = {
	'PerimetrePicker.change':
		"Doublon d'une valeur déjà transmise par `bind:value` — Svelte met à jour la " +
		'variable liée avant même le dispatch. Le garder coûte zéro et permet à un ' +
		'appelant futur de réagir sans modifier le composant.',
	'DestinatairePicker.change': 'Idem `PerimetrePicker` : `bind:value` transmet déjà la valeur.',
	'RichEditor.change': 'Idem : `bind:value` transmet déjà la valeur.',
	'FichiersUpload.change': 'Idem, via `bind:urls` / `bind:fichiers`.',
	'ImageUpload.change': 'Idem, via `bind:value`.',
};

/**
 * 🔴 **Capacités : la prop et l'écouteur vont ENSEMBLE, ou ni l'un ni l'autre.**
 *
 * La règle « l'événement est-il traité quelque part ? » ne suffit pas, et c'est
 * le relevé de #505 qui l'a montré : `RubriqueHistorique` dispatche `supprimer`,
 * deux appelants sur cinq l'écoutent — donc l'événement **est** traité, et le
 * contrôle ci-dessus le déclare bon. Pourtant le bouton 🗑️ s'affichait sur les
 * trois autres écrans et n'y faisait **rien**.
 *
 * Ce qui manquait n'était pas un écouteur mais une **déclaration** : le geste
 * n'existe côté serveur que pour les tickets. Une capacité se déclare donc par
 * une prop, et le contrôle vérifie que les deux moitiés ne se séparent jamais.
 *
 * Ajouter une paire ici quand un composant ouvre un geste qui n'a pas de sens
 * partout. Une paire dont le composant a disparu fait échouer le contrôle.
 */
const PAIRES_CAPACITE = {
	RubriqueHistorique: { prop: 'avecSuppression', evenement: 'supprimer' },
};

function fichiersSvelte(dir, out = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiersSvelte(p, out);
		else if (e.endsWith('.svelte')) out.push(p);
	}
	return out;
}

/** Les `dispatch('X')` d'un fichier, avec leur ligne. */
function evenementsDispatches(texte) {
	const out = new Map();
	const re = /dispatch\(\s*['"]([A-Za-z_][\w-]*)['"]/g;
	let m;
	while ((m = re.exec(texte))) {
		if (!out.has(m[1])) out.set(m[1], texte.slice(0, m.index).split('\n').length);
	}
	return out;
}

/** Les composants importés : nom LOCAL -> chemin du composant. L'alias compte. */
function importsDe(racine, chemin, texte) {
	const out = new Map();
	const re = /import\s+([A-Za-z_$][\w$]*)\s+from\s+['"]([^'"]+\.svelte)['"]/g;
	let m;
	while ((m = re.exec(texte))) {
		const [, local, spec] = m;
		const abs = spec.startsWith('#lib/')
			? join(racine, 'lib', spec.slice(5))
			: join(dirname(chemin), spec);
		out.set(local, abs.replace(/\\/g, '/'));
	}
	return out;
}

/**
 * Les usages de `<Composant …>`, avec le contenu complet de la balise.
 * Une balise peut s'étendre sur plusieurs lignes : on lit jusqu'au `>` qui ferme,
 * en ignorant les `>` qui vivent à l'intérieur d'une expression `{…}`.
 */
function usagesDe(nom, texte) {
	const out = [];
	const re = new RegExp(`<${nom}(?=[\\s/>])`, 'g');
	let m;
	while ((m = re.exec(texte))) {
		let prof = 0,
			fin = -1;
		for (let k = m.index; k < texte.length; k++) {
			const c = texte[k];
			if (c === '{') prof++;
			else if (c === '}') prof--;
			else if (c === '>' && prof === 0) {
				fin = k;
				break;
			}
		}
		if (fin > 0) out.push(texte.slice(m.index, fin + 1));
	}
	return out;
}

/** `traite` | `transfere` | `absent` pour un événement dans une balise. */
function commentTraite(balise, evt) {
	if (new RegExp(`\\bon:${evt}\\s*=`).test(balise)) return 'traite';
	if (new RegExp(`\\bon:${evt}(?![\\w:=-])`).test(balise)) return 'transfere';
	return 'absent';
}

/** Analyse une arborescence `.svelte`. Rend le relevé, sans rien afficher. */
function analyser(racine, tolerances) {
	const source = new Map(); // CHEMIN -> texte (jamais le basename : les routes s'appellent toutes `+page`)
	for (const f of fichiersSvelte(racine))
		source.set(f.replace(/\\/g, '/'), readFileSync(f, 'utf8'));
	const importsPar = new Map();
	for (const [chemin, texte] of source) importsPar.set(chemin, importsDe(racine, chemin, texte));

	function estTraite(emetteur, evt, vus = new Set()) {
		if (vus.has(emetteur)) return false;
		vus.add(emetteur);
		let vuQuelquePart = false;
		for (const [chemin, texte] of source) {
			if (chemin === emetteur) continue;
			for (const [local, cible] of importsPar.get(chemin)) {
				if (cible !== emetteur) continue;
				for (const balise of usagesDe(local, texte)) {
					vuQuelquePart = true;
					const etat = commentTraite(balise, evt);
					if (etat === 'traite') return true;
					if (etat === 'transfere' && estTraite(chemin, evt, new Set(vus))) return true;
				}
			}
		}
		//  Composant qu'aucun fichier n'instancie : cul-de-sac, pas un orphelin.
		//  Le code mort relève d'un autre contrôle.
		return !vuQuelquePart;
	}

	const orphelins = [];
	const servies = new Set();
	let nbDispatch = 0;
	for (const [chemin, texte] of source) {
		for (const [evt, ligne] of evenementsDispatches(texte)) {
			nbDispatch++;
			const cle = `${basename(chemin, '.svelte')}.${evt}`;
			if (tolerances[cle]) {
				servies.add(cle);
				continue;
			}
			if (!estTraite(chemin, evt)) {
				orphelins.push({ cle, fichier: relative(racine, chemin).replace(/\\/g, '/'), ligne, evt });
			}
		}
	}
	const mortes = Object.keys(tolerances).filter((c) => !servies.has(c));

	//  ── Capacités : la prop et l'écouteur, ensemble ou pas du tout ───────────
	const depareillees = [];
	const pairesVues = new Set();
	for (const [composant, { prop, evenement }] of Object.entries(PAIRES_CAPACITE)) {
		const cible = [...source.keys()].find((c) => basename(c, '.svelte') === composant);
		if (!cible) continue; // composant absent : signalé plus bas
		pairesVues.add(composant);
		for (const [chemin, texte] of source) {
			if (chemin === cible) continue;
			for (const [local, ref] of importsPar.get(chemin)) {
				if (ref !== cible) continue;
				for (const balise of usagesDe(local, texte)) {
					const declare = new RegExp(`\\b${prop}\\b`).test(balise);
					const ecoute = commentTraite(balise, evenement) !== 'absent';
					if (declare !== ecoute) {
						depareillees.push({
							fichier: relative(racine, chemin).replace(/\\/g, '/'),
							composant,
							prop,
							evenement,
							declare,
							ecoute,
						});
					}
				}
			}
		}
	}
	const pairesMortes = Object.keys(PAIRES_CAPACITE).filter((c) => !pairesVues.has(c));
	return {
		orphelins,
		mortes,
		servies,
		nbDispatch,
		nbFichiers: source.size,
		depareillees,
		pairesMortes,
	};
}

// ── Self-test : chaque forme réintroduite volontairement ─────────────────────
if (process.argv[2] === '--selftest') {
	const tmp = mkdtempSync(join(tmpdir(), 'chk-evt-'));
	const ecrire = (rel, contenu) => {
		const p = join(tmp, rel);
		mkdirSync(dirname(p), { recursive: true });
		writeFileSync(p, contenu, 'utf8');
	};
	let st = 0;
	const t = (libelle, attendu, obtenu) => {
		if (attendu === obtenu) console.log(`PASS  ${libelle} → ${obtenu}`);
		else {
			console.log(`FAIL  ${libelle}  attendu=${attendu} obtenu=${obtenu}`);
			st = 1;
		}
	};

	//  1. dispatch jamais écouté → REFUSÉ
	ecrire(
		'lib/Muet.svelte',
		`<script>const dispatch = createEventDispatcher();</script><button on:click={() => dispatch('perdu')}>x</button>`,
	);
	ecrire('routes/a/+page.svelte', `<script>import Muet from '#lib/Muet.svelte';</script><Muet />`);
	//  2. chaîne avec transfert NU qui aboutit → ACCEPTÉ (le cas de #505, corrigé)
	ecrire(
		'lib/Bas.svelte',
		`<script>const dispatch = createEventDispatcher();</script><button on:click={() => dispatch('remonte')}>x</button>`,
	);
	ecrire(
		'lib/Milieu.svelte',
		`<script>import Bas from '#lib/Bas.svelte';</script><Bas on:remonte />`,
	);
	ecrire(
		'routes/b/+page.svelte',
		`<script>import Milieu from '#lib/Milieu.svelte';</script><Milieu on:remonte={() => {}} />`,
	);
	//  3. chaîne avec transfert NU qui n'aboutit PAS → REFUSÉ (le défaut exact de #505)
	ecrire(
		'lib/BasKo.svelte',
		`<script>const dispatch = createEventDispatcher();</script><button on:click={() => dispatch('orphelin')}>x</button>`,
	);
	ecrire(
		'lib/MilieuKo.svelte',
		`<script>import BasKo from '#lib/BasKo.svelte';</script><BasKo on:orphelin />`,
	);
	ecrire(
		'routes/c/+page.svelte',
		`<script>import MilieuKo from '#lib/MilieuKo.svelte';</script><MilieuKo />`,
	);
	//  4. composant importé sous ALIAS, écouté → ACCEPTÉ (le faux positif corrigé)
	ecrire(
		'lib/VraiNom.svelte',
		`<script>const dispatch = createEventDispatcher();</script><button on:click={() => dispatch('valide')}>x</button>`,
	);
	ecrire(
		'routes/d/+page.svelte',
		`<script>import ToutAutreNom from '#lib/VraiNom.svelte';</script><ToutAutreNom on:valide={() => {}} />`,
	);
	//  5. deux routes homonymes `+page.svelte` → l'une écoute (l'indexation par
	//     basename les écrasait, et déclarait l'événement orphelin à tort)
	ecrire(
		'lib/Homonyme.svelte',
		`<script>const dispatch = createEventDispatcher();</script><button on:click={() => dispatch('vu')}>x</button>`,
	);
	ecrire(
		'routes/e/+page.svelte',
		`<script>import Homonyme from '#lib/Homonyme.svelte';</script><Homonyme on:vu={() => {}} />`,
	);

	//  8-10. Capacités : le composant réel de PAIRES_CAPACITE, avec trois appelants
	ecrire(
		'lib/RubriqueHistorique.svelte',
		`<script>const dispatch = createEventDispatcher();</script><button on:click={() => dispatch('supprimer')}>x</button>`,
	);
	ecrire(
		'routes/f/+page.svelte',
		`<script>import RubriqueHistorique from '#lib/RubriqueHistorique.svelte';</script><RubriqueHistorique avecSuppression on:supprimer={() => {}} />`,
	);
	ecrire(
		'routes/g/+page.svelte',
		`<script>import RubriqueHistorique from '#lib/RubriqueHistorique.svelte';</script><RubriqueHistorique />`,
	);
	ecrire(
		'routes/h/+page.svelte',
		`<script>import RubriqueHistorique from '#lib/RubriqueHistorique.svelte';</script><RubriqueHistorique avecSuppression />`,
	);
	ecrire(
		'routes/i/+page.svelte',
		`<script>import RubriqueHistorique from '#lib/RubriqueHistorique.svelte';</script><RubriqueHistorique on:supprimer={() => {}} />`,
	);

	const r = analyser(tmp, {});
	const orph = new Set(r.orphelins.map((o) => o.cle));
	t('dispatch jamais écouté', true, orph.has('Muet.perdu'));
	t('transfert nu qui aboutit', false, orph.has('Bas.remonte'));
	t('transfert nu qui n’aboutit pas (#505)', true, orph.has('BasKo.orphelin'));
	t('composant importé sous ALIAS', false, orph.has('VraiNom.valide'));
	t('routes homonymes +page.svelte', false, orph.has('Homonyme.vu'));

	const dep = r.depareillees.map((d) => `${d.fichier}|${d.declare}|${d.ecoute}`);
	t(
		'capacité déclarée ET écoutée',
		false,
		dep.some((x) => x.startsWith('routes/f/')),
	);
	t(
		'capacité ni déclarée ni écoutée',
		false,
		dep.some((x) => x.startsWith('routes/g/')),
	);
	t(
		'déclarée SANS écouteur → geste sans effet',
		true,
		dep.some((x) => x.startsWith('routes/h/')),
	);
	t(
		'écoutée SANS déclaration → geste invisible',
		true,
		dep.some((x) => x.startsWith('routes/i/')),
	);

	//  6. une tolérance qui ne sert plus fait échouer
	const r2 = analyser(tmp, { 'Disparu.jamais': 'motif obsolète' });
	t('tolérance qui ne sert plus', true, r2.mortes.includes('Disparu.jamais'));
	//  7. une tolérance servie éteint bien le signalement
	const r3 = analyser(tmp, { 'Muet.perdu': 'volontaire' });
	t('tolérance servie', false, new Set(r3.orphelins.map((o) => o.cle)).has('Muet.perdu'));

	rmSync(tmp, { recursive: true, force: true });
	console.log(
		st === 0
			? '\n✓ Autotest : les orphelins sont refusés, les chaînes complètes acceptées, alias et homonymes compris.'
			: '\n✗ Autotest en échec',
	);
	process.exit(st);
}

const { orphelins, mortes, servies, nbDispatch, nbFichiers, depareillees, pairesMortes } = analyser(
	RACINE,
	TOLERANCES,
);

let echec = false;
if (orphelins.length) {
	echec = true;
	console.error(`\n✗ ${orphelins.length} événement(s) dispatché(s) que personne ne traite :\n`);
	for (const o of orphelins) {
		console.error(`  ${o.fichier}:${o.ligne} — dispatch('${o.evt}')`);
		console.error(`      aucun appelant ne pose \`on:${o.evt}={…}\` au bout de la chaîne.`);
		console.error(
			`      → soit le geste est mort (le corriger), soit c'est voulu (le déclarer dans TOLERANCES).\n`,
		);
	}
}
if (mortes.length) {
	echec = true;
	console.error(`\n✗ ${mortes.length} tolérance(s) qui ne servent plus — les retirer :\n`);
	for (const c of mortes) console.error(`  ${c}`);
	console.error('');
}
if (depareillees.length) {
	echec = true;
	console.error(`
✗ ${depareillees.length} capacité(s) dépareillée(s) — la prop et l'écouteur vont ENSEMBLE :
`);
	for (const d of depareillees) {
		console.error(`  ${d.fichier} — <${d.composant}>`);
		console.error(
			d.declare
				? `      déclare \`${d.prop}\` mais n'écoute pas \`on:${d.evenement}\` — le geste serait proposé sans effet.`
				: `      écoute \`on:${d.evenement}\` mais ne déclare pas \`${d.prop}\` — le geste ne s'affichera jamais.`,
		);
		console.error('');
	}
}
if (pairesMortes.length) {
	echec = true;
	console.error(`
✗ ${pairesMortes.length} paire(s) de capacité dont le composant a disparu — les retirer :
`);
	for (const c of pairesMortes) console.error(`  ${c}`);
	console.error('');
}
if (echec) process.exit(1);

console.log(
	`✓ Événements : ${nbDispatch} dispatch(s) dans ${nbFichiers} composants — tous traités au bout de leur chaîne, ` +
		`${servies.size} tolérance(s) et ${Object.keys(PAIRES_CAPACITE).length} capacité(s) déclarée(s), toutes appariées.`,
);
