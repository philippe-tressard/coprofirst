/**
 * Refuse un appel d'API dont l'échec devient une **collection vide** (#522).
 *
 * ## Le défaut, en trois caractères
 *
 * `.catch(() => [])` transforme toute erreur — session expirée, 500, réseau —
 * en tableau vide. L'écran rend alors **exactement la même chose** que s'il n'y
 * avait rien. Le 19/08/2026, l'utilisateur a cru deux sondages et trois annonces
 * détruits, et en a demandé la restauration : ils étaient intacts en base.
 *
 * 🔴 **Une sortie vide n'est pas un constat** (`standards/04` §1). Un écran qui
 * affirme une absence qu'il n'a pas constatée provoque la réaction qu'une perte
 * réelle provoquerait — avec au bout le risque d'écraser des données saines.
 *
 * ## Pourquoi ce contrôle est ÉTROIT, et doit le rester
 *
 * Le dépôt compte une cinquantaine de `catch` silencieux parfaitement
 * légitimes : marquage de lecture, télémétrie, révocation de jeton, fermeture
 * d'un menu. Les refuser tous ferait désarmer le contrôle dans la semaine — le
 * ticket le disait avant même qu'il existe :
 *
 * > « Le relevé doit précéder la règle : tous les `catch` silencieux ne sont pas
 * >   fautifs. Un contrôle qui les refuserait tous serait désarmé dans la
 * >   semaine. »
 *
 * Il ne vise donc que **deux** formes, celles qui se rendent à l'écran comme une
 * absence :
 *   1. `.catch(() => [])` — une **collection vide** substituée à l'échec ;
 *   2. `try { x = await … } catch { }` — la même faute écrite autrement (#1459) :
 *      le `catch` est vide ou ne contient qu'un commentaire, et le `try`
 *      **affecte**, après son premier `await`, une variable qu'il n'a pas
 *      déclarée. L'écran lit alors cette variable à sa valeur initiale —
 *      souvent `[]` ou `''` — comme si le serveur l'avait rendue.
 *      Elle a vidé les suites d'une affaire chez tous les copropriétaires
 *      (TK-124285, 29/09/2026), et elle comptait **quatorze** occurrences que la
 *      forme 1 ne voyait pas — dont trois formulaires d'administration qui,
 *      affichés vides, auraient écrasé la configuration à l'enregistrement.
 * `.catch(() => {})` et un `catch` vide qui n'affecte rien (on ignore, aucune
 * valeur n'est lue) ne sont pas concernés.
 *
 * ## Le remède, quand il échoue
 *
 * `#lib/chargement.ts` → `essayer(promesse, repli)` rend `[valeur, erreur]`.
 * Puis, selon la nature de la donnée :
 *   - **liste affichée**   → `EtatListe` (l'échec passe AVANT le vide) ;
 *   - **donnée de référence** (un `<select>`, une table de correspondance)
 *     → `ChargementPartiel`, car un sélecteur vide et un sélecteur en échec ne
 *       se rendent pas de la même façon.
 *
 * Test : node front/scripts/check-catch-vide.mjs --selftest
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { litteralApres } from './lib-lecture-source.mjs';

const RACINE = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SRC = join(RACINE, 'src');

/**
 * Les formes refusées : un `catch` qui rend une collection vide.
 *
 * ⚠️ `null` en fait partie quand la valeur est ensuite lue comme un objet —
 * mais `null` sert aussi de « pas de valeur » légitime (un `get()` optionnel),
 * et le distinguer demanderait de suivre l'usage. Le relevé du 20/08/2026 n'a
 * trouvé que deux `.catch(() => null)`, tous deux sur un objet unique et non
 * sur une liste : hors périmètre, assumé, et écrit ici pour que le prochain
 * relevé sache que la question a été posée.
 */
const MOTIF = /\.catch\(\s*\(\s*\)\s*=>\s*(\[\s*\]|\(\s*\{\s*\}\s*\))\s*\)/g;

/**
 * Les exceptions DÉCLARÉES. Vide aujourd'hui, et c'est le point : le lot #522
 * a converti les quinze appels existants, il n'en reste aucun à tolérer.
 *
 * 🔴 Une exception non écrite n'est pas une exception, c'est un oubli qui
 * ressemble à une décision. Toute entrée ajoutée ici porte sa raison — et le
 * contrôle ÉCHOUE si une exception cesse de servir, pour qu'une tolérance
 * devenue inutile ne survive pas à ce qui la justifiait.
 */
const EXCEPTIONS = [];

/**
 * Les `catch` muets DÉCLARÉS de la forme 2 : un fichier, la variable affectée,
 * et la raison pour laquelle sa valeur initiale ne ment pas. Relevé du
 * 30/09/2026 (#1459). Même règle que `EXCEPTIONS` : une entrée qui ne sert plus
 * fait échouer.
 */
const MUETS_DECLARES = [
	{
		fichier: 'src/lib/components/TexteMarkdown.svelte',
		affecte: 'html',
		raison:
			'le moteur Markdown n’a pas pu se charger : le texte SOURCE reste affiché tel quel — exact, seulement moins lisible (#1930)',
	},
	{
		fichier: 'src/lib/api/client.ts',
		affecte: 'rawDetail',
		raison: 'lit le corps d’une réponse DÉJÀ en échec ; le repli est le libellé par défaut',
	},
	{
		fichier: 'src/lib/components/Reponses.svelte',
		affecte: 'content',
		raison:
			'vide le champ APRÈS un envoi réussi ; en échec le parent affiche l’erreur et le texte reste',
	},
	{
		fichier: 'src/lib/components/OngletSmtp.svelte',
		affecte: 'valeurs',
		raison: 'relecture après un enregistrement RÉUSSI : les champs portent déjà ce qui a été saisi',
	},
	{
		fichier: 'src/lib/components/PageLegale.svelte',
		affecte: 'customHtml',
		raison:
			'la page a son texte légal par défaut ; un incident affiché sur une page légale serait pire',
	},
	{
		fichier: 'src/lib/stores/perimetres.ts',
		affecte: 'charge',
		raison:
			'drapeau de cache laissé faux pour RÉESSAYER ; les écrans retombent sur le libellé brut',
	},
];

function fichiers(dossier) {
	const out = [];
	for (const e of readdirSync(dossier)) {
		const p = join(dossier, e);
		if (statSync(p).isDirectory()) out.push(...fichiers(p));
		else if (/\.(svelte|ts)$/.test(e)) out.push(p);
	}
	return out;
}

/**
 * Les occurrences fautives d'un contenu. **Pure** : éprouvable sans dépôt.
 *
 * ⚠️ Les commentaires sont retirés AVANT la recherche. Sans cela, ce contrôle
 * refuserait `chargement.ts`, `erreurs.ts` et `EtatListe.svelte` — les trois
 * fichiers qui expliquent le défaut en le citant. Un contrôle qui interdit d'en
 * parler oblige à taire la raison, et c'est la raison qui se perd en premier.
 */
export function occurrences(contenu) {
	return [...neutraliserCommentaires(contenu).matchAll(MOTIF)].map((m) => m[0]);
}

/** Les noms qu'un motif de déclaration introduit : `x`, `{ a, b: c }`, `[d, e]`. */
function nomsDeclares(bloc) {
	const noms = new Set();
	for (const d of bloc.matchAll(/\b(?:const|let|var)\s+(\{[^}]*\}|\[[^\]]*\]|[\w$]+)/g)) {
		for (const n of d[1].matchAll(/[A-Za-z_$][\w$]*(?=\s*[,}\]=]|\s*$)/g)) noms.add(n[0]);
	}
	return noms;
}

/**
 * Forme 2 — les `try` dont le `catch` est muet et qui affectent, après leur
 * premier `await`, une variable déclarée ailleurs. **Pure**.
 *
 * ⚠️ Lu sur la source NEUTRALISÉE : un `catch` qui ne contient qu'un
 * commentaire y est vide, et c'est voulu — un commentaire explique le silence,
 * il ne le rompt pas.
 *
 * @returns {{ ligne: number, affecte: string[] }[]}
 */
export function catchMuets(contenu) {
	const src = neutraliserCommentaires(contenu);
	const trouves = [];
	for (const m of src.matchAll(/\btry\s*\{/g)) {
		const bloc = litteralApres(src, m.index);
		if (!bloc) continue;
		const finTry = src.indexOf(bloc, m.index) + bloc.length;
		if (!/^\s*catch\s*(\([^)]*\))?\s*\{/.test(src.slice(finTry))) continue;
		const corpsCatch = litteralApres(src, finTry);
		if (!corpsCatch || corpsCatch.slice(1, -1).trim() !== '') continue;
		const premierAwait = bloc.search(/\bawait\b/);
		if (premierAwait < 0) continue;
		const declares = nomsDeclares(bloc);
		const affecte = new Set();
		//  Depuis le début de l'INSTRUCTION qui porte le premier `await` : dans
		//  `x = await f()`, l'affectation précède le mot-clé.
		const debut = Math.max(...[';', '{', '}', '\n'].map((c) => bloc.lastIndexOf(c, premierAwait)));
		const apres = bloc.slice(debut);
		const motif =
			/(?:^|[;{}()\n])\s*(\[[^\]=]*\]|[A-Za-z_$][\w$]*)(?:\.[\w$]+|\[[^\]]*\])*\s*=(?![=>])/g;
		for (const a of apres.matchAll(motif)) {
			for (const n of a[1].matchAll(/[A-Za-z_$][\w$]*/g)) {
				if (!declares.has(n[0])) affecte.add(n[0]);
			}
		}
		if (affecte.size) {
			trouves.push({ ligne: src.slice(0, m.index).split('\n').length, affecte: [...affecte] });
		}
	}
	return trouves;
}

function selftest() {
	let ko = 0;
	const t = (libelle, attendu, contenu) => {
		const obtenu = occurrences(contenu).length;
		if (obtenu === attendu) console.log(`PASS  ${libelle}`);
		else {
			console.log(`FAIL  ${libelle} — attendu ${attendu}, obtenu ${obtenu}`);
			ko = 1;
		}
	};

	t('le cas du 19/08 : liste avalée', 1, 'const x = await api.list().catch(() => []);');
	t('espaces à l’intérieur', 1, 'api.list().catch( ( ) => [ ] )');
	t('objet vide, même faute', 1, 'api.get().catch(() => ({}));');
	//  🔴 Ce qu'il ne doit PAS refuser — sinon il est désarmé dans la semaine.
	t('catch qui ignore, sans valeur lue', 0, 'marquerLu(id).catch(() => {});');
	t('catch avec un vrai traitement', 0, 'api.list().catch((e) => { toast(e); return []; });');
	t('repli sur null (hors périmètre, assumé)', 0, 'api.get().catch(() => null);');
	t('try/catch ordinaire', 0, 'try { f(); } catch { /* rien */ }');
	//  🔴 Les fichiers qui EXPLIQUENT le défaut le citent : les refuser
	//  obligerait à taire la raison, et la raison se perd en premier.
	t('cité dans un commentaire de ligne', 0, '// on écrivait .catch(() => []) ici');
	t('cité dans un commentaire de bloc', 0, '/* .catch(() => []) était la faute */');
	t('cité dans un commentaire Svelte', 0, '<!-- .catch(() => []) -->');
	//  Une URL contient `//` : le retrait des commentaires ne doit pas tronquer
	//  la ligne et faire disparaître un appel fautif placé après.
	t(
		'URL puis appel fautif sur la même ligne',
		1,
		"const u = 'https://x.fr'; api.list().catch(() => []);",
	);

	//  ── Forme 2 (#1459) ──
	const m = (libelle, attendu, contenu) => {
		const obtenu = catchMuets(contenu)
			.flatMap((x) => x.affecte)
			.join(',');
		if (obtenu === attendu) console.log(`PASS  ${libelle}`);
		else {
			console.log(`FAIL  ${libelle} — attendu « ${attendu} », obtenu « ${obtenu} »`);
			ko = 1;
		}
	};
	m(
		'le cas de TK-124285 : suites avalées',
		'evolutions',
		'try { evolutions = await api.evolutions(id); } catch { /* silencieux */ }',
	);
	m('catch vide sans commentaire', 'liste', 'try { liste = await f(); } catch {}');
	m('catch (e) vide', 'liste', 'try { liste = await f(); } catch (e) {\n}');
	m('valeur tirée entre parenthèses', 'html', "try { html = (await f())[cle] ?? ''; } catch {}");
	m('déstructuration', 'a,b', 'try { [a, b] = await Promise.all([f(), g()]); } catch {}');
	m(
		'dérivée d’une constante attendue',
		'actifs',
		'try { const tous = await f(); actifs = tous.filter((u) => u.actif); } catch {}',
	);
	m(
		'champ d’un formulaire rempli dans une boucle',
		'form',
		'try { const d = await f(); Object.keys(form).forEach((k) => { if (d[k]) form[k] = d[k]; }); } catch {}',
	);
	m('sur plusieurs lignes', 'x', 'try {\n\tx = await f();\n} catch {\n\t// rien\n}');
	//  🔴 Ce qu'il ne doit PAS refuser.
	m(
		'catch qui traite l’échec',
		'',
		'try { x = await f(); } catch (e) { erreur = messageErreur(e); }',
	);
	m('rien n’est affecté', '', 'try { await marquerLu(id); } catch {}');
	m(
		'seules des variables locales',
		'',
		'try { const r = await f(); let n = r.length; n = 2; } catch {}',
	);
	m('affectation AVANT l’await', '', 'try { enCours = true; await f(); } catch {}');
	m(
		'comparaison, pas affectation',
		'',
		'try { const r = await f(); if (r.a === 1) g(); } catch {}',
	);
	m('pas de await : synchrone', '', 'try { base = decodeURIComponent(base); } catch {}');
	m('accolade dans une chaîne du try', 'x', "try { x = await f('}'); } catch { }");

	console.log(
		ko === 0
			? '\n✓ Autotest : la forme fautive est refusée, les catch légitimes passent.'
			: '\n✗ Autotest en échec',
	);
	return ko;
}

function main() {
	if (process.argv.includes('--selftest')) return selftest();

	const coupables = [];
	const muets = [];
	const exceptionsVues = new Set();
	const muetsVus = new Set();
	for (const f of fichiers(SRC)) {
		const rel = relative(RACINE, f).replace(/\\/g, '/');
		const contenu = readFileSync(f, 'utf8');
		for (const { ligne, affecte } of catchMuets(contenu)) {
			const nonDeclares = affecte.filter((v) => {
				const d = MUETS_DECLARES.find((x) => x.fichier === rel && x.affecte === v);
				if (d) muetsVus.add(d);
				return !d;
			});
			if (nonDeclares.length) muets.push(`${rel}:${ligne}  (${nonDeclares.join(', ')})`);
		}
		const trouve = occurrences(contenu);
		if (!trouve.length) continue;
		if (EXCEPTIONS.includes(rel)) {
			exceptionsVues.add(rel);
			continue;
		}
		coupables.push([rel, trouve.length]);
	}

	//  Une exception qui ne sert plus doit FAIRE ÉCHOUER : sinon la liste des
	//  tolérances grossit sans que personne ne la relise, et le contrôle finit
	//  par autoriser plus que ce qu'on croit. Même règle que `check-html.mjs`.
	const mortes = [
		...EXCEPTIONS.filter((e) => !exceptionsVues.has(e)),
		...MUETS_DECLARES.filter((d) => !muetsVus.has(d)).map((d) => `${d.fichier} (${d.affecte})`),
	];
	if (mortes.length) {
		console.error('✗ Exception(s) déclarée(s) qui ne servent plus — les retirer :');
		for (const m of mortes) console.error(`    ${m}`);
		return 1;
	}

	if (muets.length) {
		console.error('');
		console.error(
			'✗ Un `catch` muet laisse l’écran lire une valeur que le serveur n’a pas rendue :',
		);
		console.error('');
		for (const x of muets) console.error(`    ${x}`);
		console.error('');
		console.error('  Remède : `essayer()` de `#lib/chargement` et son erreur rendue à l’écran —');
		console.error('  ou, si la valeur initiale ne ment pas, une entrée dans MUETS_DECLARES,');
		console.error('  avec sa raison.');
		console.error('');
	}
	if (!coupables.length) {
		if (muets.length) return 1;
		console.log('✓ Aucun appel dont l’échec se rendrait comme une absence.');
		return 0;
	}
	console.error('');
	console.error('✗ Un échec d’appel devient une collection vide — donc une ABSENCE à l’écran :');
	console.error('');
	for (const [f, n] of coupables) console.error(`    ${f}  (${n})`);
	console.error('');
	console.error('  Un écran qui affirme une absence qu’il n’a pas constatée provoque la');
	console.error('  réaction qu’une perte réelle provoquerait (vécu le 19/08/2026).');
	console.error('');
	console.error('  Remède : `essayer()` de `#lib/chargement`, puis `EtatListe` pour une');
	console.error('  liste affichée, ou `ChargementPartiel` pour une donnée de référence.');
	console.error('');
	return 1;
}

process.exit(main());
