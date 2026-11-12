/**
 * **Les mots anglais d'interface** — refusés dans un libellé que l'on LIT.
 *
 * ## 🔴 Pourquoi (#1579, 02/10/2026)
 *
 * La checklist front (`ux-patterns`) dit « libellés et nommage en français »,
 * et aucun contrôle ne la tenait : `lint:texte` normalise l'Unicode,
 * `check-casse-libelles` juge la casse. Un « Submit » ou un « Loading » écrit par
 * réflexe — un bouton, une infobulle, un toast — passait donc sans un mot.
 *
 * ## Ce que ce module est, et n'est pas
 *
 * Une LISTE de mots d'interface courants (verbes de bouton, états), lue à travers
 * les mêmes **portes** que `lib-vocabulaire` : attributs, notifications,
 * libellés déclarés, et texte du balisage. Il ne devine pas la langue d'une
 * phrase — il refuse des mots précis, ceux qu'on tape sans y penser. Un mot
 * ajouté à la liste se paie par l'inventaire de ses occurrences.
 *
 * ⚠️ Deux pièges mesurés en l'écrivant :
 *
 *  - la frontière `\b` de JavaScript ne voit pas « é » comme une lettre :
 *    « confirmé » contenait « confirm », et « closes » (au féminin pluriel, très
 *    français : « les affaires closes ») contenait « close ». Le motif pose donc
 *    sa frontière sur les lettres Unicode, et la liste n'a ni pluriel implicite
 *    ni `Close` (homographe français) ;
 *  - un identifiant d'icône (`nom: 'home'`) n'est pas un libellé : `Home`,
 *    `Settings` ne sont pas dans la liste.
 *
 * Les exceptions se DÉCLARENT dans `EXCEPTIONS_ANGLAIS`, chacune avec sa raison,
 * et une exception qui ne sert plus fait échouer le contrôle.
 */
import { libellesFautifs, texteVisibleFautif } from './lib-vocabulaire.mjs';

/**
 * Les mots refusés — en minuscules, comparés sans casse.
 *
 * 🔴 « Close » n'y figure pas : « close » est un mot français (« une affaire
 * close »). « Home » et « Settings » non plus : ce sont des noms d'icône.
 */
export const MOTS_ANGLAIS = [
	'submit',
	'cancel',
	'save',
	'delete',
	'loading',
	'error',
	'search',
	'edit',
	'add',
	'remove',
	'back',
	'next',
	'previous',
	'confirm',
	'yes',
	'login',
	'logout',
	'sign in',
	'log in',
	'upload',
	'download',
	'send',
	'update',
	'create',
	'warning',
	'success',
	'reset',
	'apply',
	'retry',
	'refresh',
	'please',
];

/**
 * Les emplacements où le mot est voulu, chacun avec sa raison. `texte` est un
 * fragment de la ligne ou du libellé fautif.
 *
 * 🔴 VIDE au 02/10/2026 : le dépôt est conforme. Une exception qui ne sert plus
 * fait échouer le contrôle — elle couvrirait sinon un défaut réintroduit au même
 * endroit.
 */
export const EXCEPTIONS_ANGLAIS = [];

/** Le motif : un mot de la liste, entouré de tout sauf une lettre, un chiffre, `_` ou `-`. */
export function motifAnglais(mots = MOTS_ANGLAIS) {
	const echappes = mots.map((m) => m.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(' ', '\\s+'));
	return new RegExp(`(?<![\\p{L}\\p{N}_-])(${echappes.join('|')})(?![\\p{L}\\p{N}_-])`, 'iu');
}

/**
 * Les mots anglais d'un fichier, par les deux portes (attributs, texte affiché).
 * `estSvelte` : le texte du balisage ne se lit que dans un `.svelte`.
 *
 * @returns `[{ ligne, porte, texte }]`
 */
export function motsAnglaisFautifs(
	source,
	estSvelte = true,
	exceptions = EXCEPTIONS_ANGLAIS,
	mots = MOTS_ANGLAIS,
) {
	const motif = motifAnglais(mots);
	return [
		...libellesFautifs(source, mots, exceptions, motif),
		...(estSvelte ? texteVisibleFautif(source, mots, exceptions, motif) : []),
	];
}

/**
 * Les cas d'autotest — appelés par `check-vocabulaire-ecran.mjs --selftest`, qui
 * porte le journal (`verifier(titre, obtenu, attendu)`).
 *
 * 🔴 Le premier est le CAS FAUTIF : un contrôle se prouve sur ce qu'il doit
 * refuser avant de servir (`standards/04` §2). Les deux suivants sont les
 * homographes français mesurés à l'écriture — un contrôle qui crie sur du
 * légitime finit désarmé.
 */
export function casAnglais(verifier) {
	const n = (src, svelte = true, exc = []) => motsAnglaisFautifs(src, svelte, exc).length;
	verifier('un bouton « Submit » est refusé', n('<button title="Submit">Valider</button>'), 1);
	verifier(
		'un libellé de bouton « Cancel » est refusé',
		n('<BoutonNouveau libelle="Cancel" />'),
		1,
	);
	verifier('le texte affiché « Loading… » est refusé', n('<p>Loading…</p>'), 1);
	verifier('une notification « Error » est refusée', n("toast('error', 'Error saving')", false), 1);
	verifier('un mot en minuscules est refusé aussi', n('<span>please wait</span>'), 1);
	verifier('un mot composé « Sign in » est refusé', n('<a aria-label="Sign in">x</a>'), 1);
	//  « confirmé » : le `\b` de JavaScript y voyait « confirm ».
	verifier('« confirmé » n’est pas « confirm »', n('<p>Adresse confirmée !</p>'), 0);
	//  « closes » : mot français, et la raison pour laquelle `close` n'est pas listé.
	verifier('« closes » est du français', n('<p>Les affaires closes</p>'), 0);
	verifier('« Enregistrer » passe', n('<button title="Enregistrer">Valider</button>'), 0);
	verifier(
		'un identifiant n’est pas un libellé',
		n('{#each updates as update}<Carte {update} />'),
		0,
	);
	verifier('un commentaire ne compte pas', n('<!-- Submit / Cancel -->\n<p>Valider</p>'), 0);
	verifier('une exception déclarée passe', n('<p>Loading…</p>', true, [{ texte: 'Loading…' }]), 0);
	//  Le cas zéro : une liste vide ne mesure rien et ne doit pas crier.
	verifier(
		'sans mot, rien à relever',
		motsAnglaisFautifs('<p>Loading…</p>', true, [], []).length,
		0,
	);
}

/**
 * Le bilan du balayage : écrit les fautes et rend `true` s'il faut échouer.
 *
 * `fichiersLus` est le témoin du cas zéro (`standards/04` §2) : « aucun mot
 * anglais » ne vaut que si des fichiers ont été lus. `exceptionsVues` : les
 * `texte` d'exception qu'un fichier a bien portés — les autres sont mortes.
 */
export function bilanAnglais(fautifs, exceptionsVues, fichiersLus) {
	if (!fichiersLus) {
		console.error('\n✗ Cas zéro : aucun fichier lu sous `src/` pour les mots anglais.\n');
		return true;
	}
	let echec = false;
	if (fautifs.length) {
		echec = true;
		console.error('\n✗ Mot(s) anglais d’interface dans un libellé que l’on lit :\n');
		for (const f of fautifs)
			for (const o of f.fautes)
				console.error(`   ${f.rel}:${o.ligne}  (${o.porte})  « ${o.texte} »`);
		console.error(
			'\n  Les libellés sont en FRANÇAIS exclusivement (skill ux-patterns, checklist avant commit).' +
				'\n  → traduire, ou déclarer l’emplacement dans `EXCEPTIONS_ANGLAIS`' +
				'\n  (`lib-mots-anglais.mjs`) avec sa raison.\n',
		);
	}
	const mortes = EXCEPTIONS_ANGLAIS.filter((e) => !exceptionsVues.has(e.texte));
	if (mortes.length) {
		echec = true;
		console.error('\n✗ Exception(s) de mots anglais qui ne servent plus :\n');
		for (const e of mortes) console.error(`   « ${e.texte} » — ${e.raison}`);
	}
	return echec;
}
