/**
 * Refuse un relais qui **perd un champ** de la charge utile d'un formulaire (#529).
 *
 * ## Le défaut, signalé à l'écran le 20/08/2026
 *
 * > *« J'ai créé une réponse au ticket en changeant le périmètre : celui-ci n'a
 * >   pas été pris en compte. »*
 *
 * `CarteTicket` proposait bien la section Périmètre, `EvolForm` la collectait et
 * l'émettait dans son `dispatch('submit', …)` — et `tickets/+page.svelte` la
 * **jetait**, en recopiant la charge utile champ par champ à partir d'un type
 * local qui l'ignorait. Ce type portait pourtant le commentaire *« même contrat
 * que la fiche détail »*, ce qui était faux : la fiche relaie la charge entière.
 *
 * 🔴 **Rien ne lève.** Le formulaire annonce l'enregistrement, le serveur
 * enregistre une évolution parfaitement valide, et seul le périmètre affiché
 * ensuite trahit la perte. Aucun test fonctionnel ne voit cela, et une relecture
 * ne le trouve pas : il faut comparer deux fichiers distants de quatre cents
 * lignes. C'est le profil d'erreur qu'un contrôle attrape et qu'un humain non.
 *
 * ## Ce qu'il compare
 *
 * Pour chaque paire déclarée dans `RELAIS` : les clés que le **formulaire** émet,
 * contre les clés que le **relais** transmet. Un manque est refusé.
 *
 * ✅ Un relais qui ÉTALE la charge (`{ ...data, … }`) la transmet ENTIÈRE : c'est
 * la forme que ce contrôle recommande, puisqu'elle ne peut rien oublier. Le
 * relais de la liste des affaires l'a adoptée le 23/09/2026 (#1091) — il
 * énumérait ses champs, et en avait perdu trois fois.
 *
 * ⚠️ Un champ légitimement absent se **déclare**, avec sa raison — parce que
 * l'écran ne le propose pas, ou parce que l'entité ne le connaît pas. Une
 * absence non déclarée n'est pas une décision, c'est un oubli qui lui ressemble.
 *
 * ## Ce qu'il ne fait PAS
 *
 * Il ne vérifie pas que le champ transmis est *correct*, ni qu'il arrive au
 * serveur. Il vérifie qu'il n'est pas **perdu en route** — le seul défaut de
 * cette famille qui soit invisible à l'exécution.
 *
 * Test : node front/scripts/check-charge-utile.mjs --selftest
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**
 * Les relais surveillés.
 *
 * `source` : le fichier qui ÉMET, et le nom de l'appel qui porte la charge.
 * `relais` : le fichier qui la retransmet, et l'appel d'API concerné.
 * `absents` : les clés dont l'absence est ASSUMÉE, avec leur raison.
 */
const RELAIS = [
	{
		nom: 'ticket — liste',
		source: 'src/lib/components/EvolForm.svelte',
		emission: "dispatch('submit'",
		//  Les gestes de la liste vivent dans `#lib/affaires-en-liste` (15/10/2026),
		//  que la page Affaires et le lien direct d'une affaire emploient.
		relais: 'src/lib/affaires-en-liste.ts',
		appel: 'ticketsApi.addEvolution(',
		absents: {},
	},
	//  La Suite d'une affaire — actualité comprise — et sa CORRECTION passent par
	//  UN montage depuis le 01/10/2026 (#1520) : `SuiteAffaire` relaie la charge
	//  à ses trois hôtes en y ajoutant les options. Il relayait par
	//  `ActualiteEnListe`, qui ne monte plus le formulaire lui-même.
	{
		nom: 'affaire et actualité — SuiteAffaire',
		source: 'src/lib/components/EvolForm.svelte',
		emission: "dispatch('submit'",
		relais: 'src/lib/components/SuiteAffaire.svelte',
		appel: "dispatch('submit'",
		absents: {},
	},
	//  ✅ « ticket — Espace CS » a quitté ce relevé le 28/08/2026 : le relais
	//  n'existe plus. L'onglet « Tickets résidence » — redondant avec `/tickets`,
	//  et second rendu à la main d'une entité déclarée — a été retiré, et avec lui
	//  le formulaire d'évolution qu'il ouvrait. Ses SIX champs déclarés absents
	//  disaient à eux seuls l'écart : un commentaire posé depuis l'Espace CS ne
	//  pouvait ni se diffuser, ni préciser un périmètre, là où le même geste sur
	//  `/tickets` le peut. C'est cet écran-là qui avait tort.
];

/** Le marqueur d'un `...charge` de premier niveau : tout ce qui est émis passe. */
export const ETALEMENT = '...';

/** Les clés d'un objet littéral, à partir de la position d'une parenthèse ouvrante. */
export function clesDeLObjet(source, depuis) {
	const debut = source.indexOf('{', depuis);
	if (debut < 0) return [];
	let prof = 0;
	let fin = debut;
	for (let i = debut; i < source.length; i++) {
		if (source[i] === '{') prof++;
		else if (source[i] === '}') {
			prof--;
			if (prof === 0) {
				fin = i;
				break;
			}
		}
	}
	//  🔴 Les commentaires sont NEUTRALISÉS AVANT le découpage, pas après.
	//
	//  Première version : je découpais sur les virgules du texte brut, puis je
	//  retirais les commentaires de chaque fragment. Une virgule DANS un
	//  commentaire coupait donc au mauvais endroit — et le champ qui suivait
	//  disparaissait du relevé. C'est arrivé sur `EvolForm` lui-même, dont le
	//  commentaire « … plus aucun périmètre », et seul le premier … » a fait
	//  perdre `perimetre_cible` : le contrôle écrit pour trouver un champ perdu
	//  perdait ce champ-là, silencieusement, exactement comme le code qu'il
	//  surveille.
	//
	//  Le contenu est remplacé par des espaces et non supprimé : les positions
	//  restent justes, donc les fragments aussi.
	const corps = neutraliserCommentaires(source.slice(debut + 1, fin));
	//  Seulement les clés du PREMIER niveau : une clé imbriquée appartient à un
	//  autre objet et n'a rien à voir avec le contrat de ce relais.
	const cles = [];
	let p = 0;
	let ligneDebut = 0;
	for (let i = 0; i < corps.length; i++) {
		const c = corps[i];
		if ('{(['.includes(c)) p++;
		else if ('})]'.includes(c)) p--;
		else if (c === ',' && p === 0) {
			cles.push(corps.slice(ligneDebut, i));
			ligneDebut = i + 1;
		}
	}
	cles.push(corps.slice(ligneDebut));
	return cles
		.map((m) => {
			const net = m.trim();
			//  Un ÉTALEMENT de premier niveau transmet la charge entière.
			if (net.startsWith('...')) return ETALEMENT;
			//  ⚠️ La forme RACCOURCIE (`contenu,` au lieu de `contenu: contenu`)
			//  est une clé comme une autre. La première version de ce contrôle
			//  ne la voyait pas — et `contenu` est justement le champ le plus
			//  souvent écrit ainsi.
			const m2 = /^([A-Za-z_$][\w$]*)\s*(:|$)/.exec(net);
			return m2 ? m2[1] : null;
		})
		.filter(Boolean);
}

function selftest() {
	let ko = 0;
	const t = (libelle, attendu, source, depuis = 0) => {
		const obtenu = clesDeLObjet(source, depuis).join(',');
		if (obtenu === attendu) console.log(`PASS  ${libelle}`);
		else {
			console.log(`FAIL  ${libelle} — attendu « ${attendu} », obtenu « ${obtenu} »`);
			ko = 1;
		}
	};

	t('objet simple', 'a,b', 'f({ a: 1, b: 2 })');
	t('valeurs avec appels', 'type,contenu', 'f({ type: x.type, contenu: g(y) || undefined })');
	//  🔴 Un objet imbriqué garde SA clé de premier niveau, sans livrer les
	//  siennes. Ma première version de ce cas attendait « a,c » : elle se
	//  trompait, `b` EST une clé du premier niveau.
	t('objet imbriqué : sa clé, pas les siennes', 'a,b,c', 'f({ a: 1, b: { z: 9 }, c: 3 })');
	t('tableau en valeur', 'urls', 'f({ urls: [1, 2, 3] })');
	//  🔴 Un champ CITÉ en commentaire ne compte pas comme transmis : c'est la
	//  faute que `check-html.mjs` avait, corrigée le 20/08.
	t('champ cité en commentaire', 'a', 'f({ a: 1, /* b: 2 */ })');
	t('commentaire de ligne', 'a', 'f({ a: 1,\n\t// perimetre_cible: manquant\n })');
	//  🔴 LE cas qui a fait échouer la première version de ce contrôle : une
	//  virgule DANS un commentaire coupait le découpage, et le champ suivant
	//  disparaissait du relevé.
	t(
		'virgule dans un commentaire',
		'a,b',
		'f({ a: 1,\n\t//  un texte avec une virgule, et une suite\n\tb: 2 })',
	);
	t('virgule dans un commentaire de bloc', 'a,b', 'f({ a: 1, /* virgule, ici */ b: 2 })');
	//  L'étalement est une clé comme une autre pour le relevé : c'est `main` qui
	//  en déduit que tout passe.
	t('étalement de la charge', '...,contenu', 'f({ ...data, contenu: data.contenu || undefined })');

	console.log(
		ko === 0
			? '\n✓ Autotest : les clés du premier niveau sont lues, les commentaires ignorés.'
			: '\n✗ Autotest en échec',
	);
	return ko;
}

function main() {
	if (process.argv.includes('--selftest')) return selftest();

	const erreurs = [];
	for (const r of RELAIS) {
		const src = readFileSync(join(RACINE, r.source), 'utf8');
		const iEmis = src.indexOf(r.emission);
		if (iEmis < 0) {
			erreurs.push(`${r.nom} : « ${r.emission} » introuvable dans ${r.source}`);
			continue;
		}
		const emis = new Set(clesDeLObjet(src, iEmis));

		const rel = readFileSync(join(RACINE, r.relais), 'utf8');
		const iRel = rel.indexOf(r.appel);
		if (iRel < 0) {
			erreurs.push(`${r.nom} : « ${r.appel} » introuvable dans ${r.relais}`);
			continue;
		}
		const transmis = new Set(clesDeLObjet(rel, iRel));

		for (const cle of emis) {
			if (transmis.has(cle) || transmis.has(ETALEMENT)) continue;
			if (cle in r.absents) continue;
			erreurs.push(
				`${r.nom} : le formulaire émet « ${cle} », le relais ne le transmet pas.\n` +
					`      ${r.relais}`,
			);
		}
		//  Une absence déclarée qui n'a plus lieu d'être doit FAIRE ÉCHOUER :
		//  sinon la liste des tolérances grossit sans que personne ne la relise.
		for (const cle of Object.keys(r.absents)) {
			if (!emis.has(cle)) {
				erreurs.push(
					`${r.nom} : « ${cle} » est déclaré absent, mais le formulaire ne l'émet plus — retirer la déclaration.`,
				);
			} else if (transmis.has(cle) || transmis.has(ETALEMENT)) {
				erreurs.push(
					`${r.nom} : « ${cle} » est déclaré absent ET transmis — retirer la déclaration.`,
				);
			}
		}
	}

	if (!erreurs.length) {
		console.log(
			`✓ Charge utile : ${RELAIS.length} relais vérifié(s) — aucun champ perdu en route.`,
		);
		return 0;
	}
	console.error('');
	console.error('✗ Un champ collecté par le formulaire est PERDU par son relais :');
	console.error('');
	for (const e of erreurs) console.error(`    ${e}`);
	console.error('');
	console.error('  Rien ne lèvera : le formulaire annoncera l’enregistrement et le serveur');
	console.error('  enregistrera un objet valide. Seul l’écran, plus tard, trahira la perte.');
	console.error('');
	console.error('  Transmettre le champ, ou déclarer son absence dans `RELAIS[].absents`');
	console.error('  avec la raison — l’écran ne le propose pas, l’entité ne le connaît pas.');
	console.error('');
	return 1;
}

//  🔴 `main()` ne s'exécute QUE si ce fichier est lancé, jamais s'il est
//  importé. Sans cette garde, `import { clesDeLObjet }` déclencherait l'analyse
//  du dépôt entier et sortirait — un module qu'on ne peut pas importer est un
//  module qu'on ne peut pas éprouver. C'est la même faute que celle trouvée le
//  matin même sur `lib-parite.sh`, dont le self-test sourcé détournait celui de
//  son appelant.
//  ⚠️ `process.argv[1]` est `undefined` quand Node est lancé avec `--eval` :
//  la garde doit le supporter, sinon le module devient inimportable dans le
//  contexte même où l'on veut l'éprouver.
const _lance = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (import.meta.url === _lance) process.exit(main());
