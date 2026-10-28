#!/usr/bin/env node
/*
 *  **Le client TypeScript est la SEULE porte d'entrée de l'API.**
 *
 *  Refuse un appel `api.get/post/patch/put/delete` écrit ailleurs que dans
 *  `src/lib/api/` : une route recopiée dans un écran est une seconde écriture du
 *  contrat, libre de diverger de la première sans que rien ne lève.
 *
 *  ## Pourquoi ce contrôle (#801, 06/09/2026)
 *
 *  Le ticket relevait « 48 méthodes du client que personne n'appelle » et
 *  proposait de les trier pour supprimer les reliquats. Le tri a montré autre
 *  chose : **la moitié n'était pas morte, elle était CONTOURNÉE**. L'écran
 *  écrivait `api.get('/admin/modeles-email')` à la main pendant que
 *  `admin.emailTemplates()` faisait exactement cela, deux fichiers plus loin.
 *
 *  🔴 Et la cause était presque toujours la même : une méthode **trop pauvre**.
 *  `telemetryDashboard()` ne savait pas porter `?scope=` ; `traiterCompte()`
 *  rendait `{}` au lieu de `any`, donc l'écran qui lisait `res.auto_match` ne
 *  compilait pas. Une méthode qui ne couvre pas le besoin ne fait pas contourner
 *  un peu — elle fait recopier la route en entier.
 *
 *  Trois recopies étaient de vraies bombes à retardement :
 *    • `/admin/utilisateurs/{id}/accueil-arrivant` — écrit TROIS fois, corps
 *      compris, et il déclenche des e-mails. Un champ ajouté à deux endroits sur
 *      trois serait parti sans que rien ne lève ;
 *    • `/auth/batiments` et `/admin/utilisateurs` — deux écrans chacun ;
 *    • `ajouter-role` / `retirer-role` — l'URL était construite dans un ternaire,
 *      donc invisible à toute recherche par route. La forme la plus tenace du
 *      contournement : la chaîne recopiée ne ressemble même plus à une route.
 *
 *  ## ⚠️ ZÉRO EXCEPTION, et c'est délibéré
 *
 *  Le ticket refusait à juste titre de geler 48 cas dans une liste de
 *  tolérances — « une tolérance qui ne sert plus finit par en couvrir une qui
 *  compte ». Ce contrôle est posé APRÈS que le compte soit tombé à zéro, donc il
 *  n'a rien à tolérer. Le jour où une exception paraît nécessaire, la vraie
 *  question sera : quelle méthode du client manque, ou est trop pauvre ?
 *
 *  ## 🔴 Il ne voyait PAS les `fetch()` directs, et il le disait — de travers
 *
 *  Cet en-tête affirmait, jusqu'au 12/09/2026 : *« un `fetch()` direct… il y en
 *  a **un**, dans `client.ts` »*. Il y en avait **six**, et quatre étaient des
 *  contournements :
 *
 *  | où | ce que c'était |
 *  |---|---|
 *  | `stores/pageConfig.ts` | `fetch('/api/config')` — la route écrite deux fois, et `config.get` morte de ce fait |
 *  | `mentions-legales`, `politique-de-confidentialite`, `admin` | `fetch('/api/config/legal')` **trois fois**, chacun avec son `try`/`catch` muet, parce que le client n'offrait pas la méthode |
 *
 *  ⚠️ **Un angle mort déclaré dans un commentaire n'est pas surveillé.** Celui-ci
 *  l'était depuis l'origine, avec un compte — et le compte était faux dès qu'un
 *  écran a écrit son propre `fetch`. C'est la même famille que le contrôle qui
 *  se croyait « le seul endroit où cette règle s'écrit » : la seule prose qui
 *  parlait du sujet disait que le problème n'existait pas.
 *
 *  Le compte est à **deux** depuis le 12/09/2026, tous deux nommés dans
 *  `FETCH_LEGITIMES` ci-dessous — et le contrôle échoue si l'un d'eux cesse de
 *  servir, donc la liste ne peut pas pourrir.
 *
 *  ## 🔴 Il ne voyait pas non plus les routes qui ne sont pas des APPELS (#1578)
 *
 *  Jusqu'au 02/10/2026, il ne cherchait que `api.<verbe>(` et `fetch('/api/…`.
 *  Une route vers l'API qui sert d'ADRESSE — un `href` de téléchargement, le
 *  `src` d'une image, une constante — lui échappait, et il y en avait cinq :
 *
 *  | où | route | dans le client ? |
 *  |---|---|---|
 *  | `SectionContratReference` | `/documents/{id}/télécharger` | **oui** — `documents.downloadUrl`, recopiée |
 *  | `LiensGuide` et la FAQ | `/manuel/pdf` | non — et écrite deux fois |
 *  | `LienConsignes` | `/admin/fiche-arrivant` | non |
 *  | `OngletWhatsApp` | `/config/whatsapp-qr` | non |
 *
 *  Une adresse est une écriture du contrat au même titre qu'un appel : la route
 *  renommée côté serveur laisse un lien mort, et rien ne lève. Le contrôle
 *  refuse donc toute chaîne qui COMMENCE par `/api` hors du client (`ROUTE`
 *  ci-dessous) ; le client rend l'adresse (`…Url()`), l'écran l'appelle.
 *
 *  Les commentaires sont blanchis par `lib-commentaires` — y compris le
 *  commentaire Svelte de plusieurs lignes, que l'ancien filtre « la ligne
 *  commence par `//` ou `*` » laissait passer.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = 'src';
const CLIENT = 'src/lib/api';

//  `api.get(`, `api.post<T>(`… — le point d'entrée générique, quel que soit le
//  verbe. On ne cherche PAS l'URL : c'est l'appel lui-même qui n'a pas sa place
//  hors du client, même vers une route qu'il déclare déjà.
//
//  ⚠️ `(?<![.\w])` — le `api` doit être une variable, pas la PROPRIÉTÉ d'un
//  objet. `imports-acces.ts` déclare des modèles portant un champ `api` (les
//  huit gestes d'un import, déjà pris dans le client), et `modele.api.patch(id,
//  …)` est justement l'inverse d'un contournement : c'est le paramétrage qui
//  supprime la duplication entre l'import Vigik et l'import télécommandes. Sans
//  cette garde, le contrôle refusait le code le mieux factorisé de l'écran.
//  ⚠️ `<.*?>` et non `<[^>]*>` — le second s'arrête au PREMIER `>`, donc un
//  générique imbriqué lui échappait : `api.get<Record<string, string>>('/x')`
//  ne matchait pas, et deux appels de `admin/+page.svelte` passaient sous un
//  contrôle qui annonçait « aucun appel hors du client » (#1031).
//
//  🔴 C'est le faux vert de `standards/04` §2 : un motif trop étroit ne rend
//  pas un verdict prudent, il rend un verdict FAUX — et il le rend en vert.
//  L'auto-test ne couvrait que le cas simple, donc il le confirmait.
//
//  Le `.*?` non gourmand s'étend par retour arrière jusqu'au `>` qui précède la
//  parenthèse : il traverse donc les `>` internes sans avoir à équilibrer les
//  chevrons, et reste borné à la ligne (`.` n'inclut pas le saut de ligne).
const APPEL = /(?<![.\w])api\.(get|post|patch|put|delete)\s*(?:<.*?>)?\s*\(/g;

//  Un `fetch(` vers l'API : chaîne commençant par `/api/`, ou un identifiant
//  qui la porte (`ENDPOINT`, `apiBase`). On ne cherche pas « tout `fetch` » :
//  une page a le droit d'appeler un service tiers.
const FETCH_API =
	/(?<![.\w])fetch\s*\(\s*[`'"]\s*\/api\/|(?<![.\w])fetch\s*\(\s*(?:ENDPOINT|`\$\{apiBase\})/g;

//  Une chaîne qui COMMENCE par `/api` — `'/api/x'`, `"/api/x"`, `` `/api/${id}` ``,
//  `'/api'` seul ou suivi d'une requête : une route ou la base de l'API, écrite
//  hors du client. Le guillemet est exigé JUSTE AVANT `/api` : une chaîne dont
//  `/api` n'est que la suite (`'https://tiers/api/x'`, un service tiers) n'est
//  pas visée, ni `'/apiculture'` grâce au regard avant.
const ROUTE = /[`'"]\/api(?=[/`'"?])/;

/**
 * Le `fetch()` direct qui ne PEUT pas passer par le client, avec sa raison.
 * `src/lib/server/config-site.ts` en était un second jusqu'au 17/10/2026 : il lit
 * l'API par `node:http`, pour porter l'hôte de la page (#2053). Le contrôle échoue si l'une de ces entrées cesse de servir.
 *
 * ⚠️ La route que ces fichiers écrivent (`ROUTE`) y est admise pour la même
 * raison : `telemetry.ts` nomme `/api/telemetry/collect` pour `sendBeacon`.
 */
const FETCH_LEGITIMES = {
	'src/lib/telemetry.ts':
		'repli de `navigator.sendBeacon` — un envoi `keepalive` au déchargement de ' +
		'la page, que le client (avec son renouvellement de session sur 401) ne peut pas porter',
};

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (/\.(svelte|ts)$/.test(e)) acc.push(p);
	}
	return acc;
}

/**
 * Ce qu'un fichier écrit de l'API hors du client, ligne par ligne. PURE.
 *
 * `nature` : `appel` (`api.<verbe>(`), `fetch` (`fetch` vers l'API) ou `route`
 * (une chaîne qui commence par `/api`). Une ligne qui porte un `fetch('/api/…')`
 * le compte une fois, en `fetch` : c'est le même geste.
 *
 * Les commentaires sont blanchis d'abord : ce contrôle en cite plusieurs dans
 * son propre en-tête, et les fichiers du client aussi — les compter ferait
 * échouer sur de la prose.
 */
function analyser(source) {
	const lignes = neutraliserCommentaires(source).split('\n');
	const trouves = [];
	for (let i = 0; i < lignes.length; i++) {
		const ligne = i + 1;
		APPEL.lastIndex = 0;
		let m;
		while ((m = APPEL.exec(lignes[i]))) {
			trouves.push({ ligne, nature: 'appel', quoi: `api.${m[1]}(…)` });
		}
		FETCH_API.lastIndex = 0;
		if (FETCH_API.test(lignes[i])) {
			trouves.push({ ligne, nature: 'fetch', quoi: "fetch('/api/…') écrit à la main" });
		} else if (ROUTE.test(lignes[i])) {
			trouves.push({ ligne, nature: 'route', quoi: "route '/api/…' écrite à la main" });
		}
	}
	return trouves;
}

//  ── Cas zéro : le contrôle doit REFUSER un appel hors du client ──────────────
//  Sans lui, un motif qui ne correspond plus à rien rendrait un vert parfait.
function selftest() {
	const doitRefuser = [
		["api.get<any[]>('/admin/utilisateurs')", 1],
		['const r = await api.post(`/x/${id}/y`, data);', 1],
		['api.delete(url); api.patch(url, d);', 2],
		//  L'URL dans un ternaire : la forme qui avait échappé au relevé manuel.
		['const updated = await api.post<any>(endpoint, { role });', 1],
		//  🔴 Le générique IMBRIQUÉ, qui passait sous le contrôle jusqu'au
		//  19/09/2026 (#1031) : le motif s'arrêtait au premier `>`, donc ces deux
		//  lignes-là — les vraies, telles qu'elles étaient écrites dans
		//  `admin/+page.svelte` — ne matchaient pas, et le contrôle annonçait
		//  « aucun appel hors du client ».
		["cfg = { ...cfg, ...(await api.get<Record<string, string>>('/config/admin')) };", 1],
		["const c = await api.get<Record<string, string>>('/config/admin');", 1],
		//  Deux niveaux d'imbrication, pour que le cas ne soit pas tenu par
		//  chance : un générique dont l'argument est lui-même paramétré.
		['const m = await api.get<Map<string, Array<number>>>(url);', 1],
		//  🔴 Les cinq routes de #1578, telles qu'elles étaient écrites : des
		//  ADRESSES, pas des appels — l'ancien motif n'en voyait aucune.
		['<a href="/api/documents/{documentId}/télécharger">Télécharger</a>', 1],
		['<a href="/api/manuel/pdf" target="_blank" rel="noopener">en PDF</a>.', 1],
		["const ADRESSE = '/api/admin/fiche-arrivant';", 1],
		['src="/api/config/whatsapp-qr?t={waQrTimestamp}"', 1],
		['<a href={`/api/documents/${id}/telecharger`}>', 1],
		//  La base elle-même, recopiée dans un écran.
		["const base = '/api';", 1],
		//  Un `fetch('/api/…')` se compte une fois, pas deux (fetch + route).
		["const r = await fetch('/api/config');", 1],
	];
	const doitAccepter = [
		//  L'adresse rendue par le client : la forme voulue.
		'<a href={manuel.pdfUrl()} target="_blank" rel="noopener">',
		'src={configApi.whatsappQrUrl(waQrTimestamp)}',
		//  Un fichier statique, un service tiers, un mot qui commence par « api ».
		'<a href="/manuel-utilisateur.html" target="_blank">',
		"const url = 'https://tiers.example/api/v1/x';",
		"const mot = '/apiculture';",
		//  🔴 Un commentaire Svelte de plusieurs lignes : l'ancien filtre (« la
		//  ligne commence par `//` ou `*` ») l'aurait compté.
		'<!--  le lien était écrit\n      href="/api/manuel/pdf"\n      ici -->',
		"//  l'écran écrivait api.get('/admin/modeles-email') en dur",
		' *  `api.post` rend `{}` sans argument de type',
		'adminApi.emailTemplates()',
		'await configApi.testerSmtp(email)',
		//  🔴 Le cas qui a fait resserrer le motif : un modèle d'import porte ses
		//  huit gestes dans un champ `api`, tous pris dans le client. C'est le
		//  paramétrage qui supprime la duplication Vigik / télécommandes, pas un
		//  contournement — et la version large du contrôle le refusait.
		'await modele.api.patch(editId, { …champs });',
		'const r = await this.api.get(id);',
	];
	let ko = 0;
	for (const [src, attendu] of doitRefuser) {
		const n = analyser(src).length;
		if (n !== attendu) {
			console.error(`  ✗ aurait dû trouver ${attendu} appel(s) : ${src} (trouvé ${n})`);
			ko++;
		}
	}
	for (const src of doitAccepter) {
		const n = analyser(src).length;
		if (n !== 0) {
			console.error(`  ✗ aurait dû ignorer : ${src}`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : le contrôle refuse bien un appel hors du client.');
}

selftest();

const ecarts = [];
const fetchsVus = new Set();
for (const p of fichiers(RACINE)) {
	const chemin = p.split('\\').join('/');
	if (chemin.startsWith(CLIENT + '/') || chemin === CLIENT) continue;
	for (const t of analyser(readFileSync(p, 'utf8'))) {
		//  Un `api.<verbe>(` n'a AUCUNE exception ; un `fetch` ou une route,
		//  seulement dans les fichiers déclarés — et c'est le `fetch` qui prouve
		//  que l'entrée sert encore.
		if (t.nature !== 'appel' && chemin in FETCH_LEGITIMES) {
			if (t.nature === 'fetch') fetchsVus.add(chemin);
			continue;
		}
		ecarts.push(`${chemin}:${t.ligne} — ${t.quoi}`);
	}
}

//  Une entrée qui ne sert plus laisserait repasser un contournement dans ce
//  fichier-là sans que personne l'ait décidé (`standards/04` §40).
const inutiles = Object.keys(FETCH_LEGITIMES).filter((f) => !fetchsVus.has(f));
if (inutiles.length) {
	console.error(
		`\n✗ ${inutiles.length} entrée(s) de FETCH_LEGITIMES ne servent plus :\n\n` +
			inutiles.map((f) => `   ${f}`).join('\n') +
			"\n\n  Le fichier n'appelle plus `fetch` vers l'API : retirer l'entrée.\n",
	);
	process.exit(1);
}

if (ecarts.length) {
	console.error(`\n✗ ${ecarts.length} appel(s) à l'API écrit(s) hors de ${CLIENT}/ :\n`);
	for (const e of ecarts) console.error(`  ${e}`);
	console.error(
		`\n  La route appartient au client. Deux gestes possibles, jamais un troisième :\n` +
			`    • la méthode existe   → l'appeler (import depuis '#lib/api') ;\n` +
			`    • elle n'existe pas, ou ne couvre pas le besoin (paramètre manquant,\n` +
			`      retour non typé) → l'AJOUTER ou l'ENRICHIR dans src/lib/api/, puis l'appeler.\n`,
	);
	process.exit(1);
}

console.log(`✓ Aucun appel à l'API hors de ${CLIENT}/ — le client reste la seule porte d'entrée.`);
