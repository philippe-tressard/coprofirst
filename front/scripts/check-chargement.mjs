#!/usr/bin/env node
/**
 *  Un état de chargement se rend par `EtatListe` — jamais un « Chargement… »
 *  écrit à la main (#1045, point 2, lot B).
 *
 *  ## Pourquoi ce contrôle
 *
 *  `EtatListe` porte les trois états d'une liste — en cours, échec, vide — et
 *  leur rendu. Il existe depuis le 19/08/2026 (#519) ; rien n'obligeait à s'en
 *  servir pour le PREMIER des trois. Le 24/09/2026, le dépôt écrivait encore
 *  **vingt-trois** fois son propre paragraphe d'attente, sous cinq allures :
 *
 *    <p style="color:var(--color-text-muted)">Chargement…</p>   ← 17 fois
 *    <p class="muted">…</p> · <p class="aide">…</p> · <p>…</p> nu
 *    <p class="etat-chargement">…</p>   ← la classe d'EtatListe, RECOPIÉE
 *                                          avec son style dans la page
 *
 *  Plus « Chargement... » en trois points, une seule fois. Aucun n'était faux ;
 *  l'ensemble n'avait pas de forme. C'est `project_le_composant_existait_deja`
 *  une fois de plus : le composant existait, la règle était écrite dans l'audit
 *  du 19/09, et rien ne les faisait appliquer.
 *
 *  ## Ce qu'il refuse
 *
 *  Un NŒUD DE TEXTE qui commence par « Chargement » dans le balisage d'un
 *  `.svelte`, hors d'`EtatListe.svelte` — et, depuis #2975 (24/11/2026), un
 *  paragraphe dont le texte seul finit par « … » : quatre attentes s'écrivaient
 *  sous un autre mot (« Vérification en cours… », « Redirection… »,
 *  « Composition du message… », « Lecture des usages… »), quatre classes locales
 *  pour un même état, et le contrôle ne lisait que « Chargement ». La forme conforme :
 *
 *    <EtatListe chargement />                                  ← « Chargement… »
 *    <EtatListe chargement messageChargement="Chargement des reportings…" />
 *
 *  ⚠️ Il ne regarde PAS ce qui n'est pas un état d'attente affiché :
 *
 *   • le libellé d'un bouton qui attend (`{envoi ? 'Chargement…' : label}`) —
 *     c'est une expression, pas un nœud de texte, et un bouton n'est pas une
 *     liste ;
 *   • un message d'échec (`'Chargement impossible'`), une variable
 *     (`enChargement`), `ChargementPartiel` — des mots, pas un état rendu.
 *
 *  Les commentaires sont neutralisés : le fichier qui explique la règle la cite.
 *
 *  Lancer : node scripts/check-chargement.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = 'src';
const SOURCE = 'lib/components/EtatListe.svelte';
const TEXTE = />\s*Chargement[^<{]*</g;
//  Une attente sous un autre mot (#2975) : un paragraphe dont le texte seul finit
//  par « … » — « Vérification en cours… », « Lecture des usages… ». Une phrase qui
//  porte une expression (`{n}`) ou une balise n'est pas lue, ni un paragraphe sur
//  plusieurs lignes (une énumération en prose : « … une clé de charges… ») : c'est
//  un texte, pas un état. L'ellipse en trois points compte aussi.
const ATTENTE = /<p\b[^>]*>[^<{\n]*(?:…|\.\.\.)[ \t]*<\/p>/g;
const EMPLOI = /<EtatListe\b[^>]*\bchargement\b/;

/**  Les états d'attente écrits à la main dans une source. PURE. */
export function attentesManuelles(source) {
	const code = neutraliserCommentaires(source);
	//  Un « <p>Chargement…</p> » répond aux deux motifs : il ne compte qu'une fois.
	const autres = (code.match(ATTENTE) ?? []).filter((p) => !/>\s*Chargement/.test(p));
	return (code.match(TEXTE) ?? []).length + autres.length;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = attentesManuelles(src);
		console.log(`${r === attendu ? 'PASS' : 'FAIL'}  ${libelle} → ${r}`);
		if (r !== attendu) ko = 1;
	};
	//  🔴 La forme écrite 17 fois le 24/09/2026.
	t('paragraphe à la main', 1, '<p style="color:var(--color-text-muted)">Chargement…</p>');
	t('trois points', 1, '<p class="muted">Chargement...</p>');
	t('message propre à l’écran', 1, '<p>Chargement des reportings…</p>');
	t('forme conforme', 0, '<EtatListe chargement />');
	t('message conforme', 0, '<EtatListe chargement messageChargement="Chargement…" />');
	//  Un bouton qui attend n'est pas une liste : expression, pas nœud de texte.
	t('libellé de bouton', 0, "<button>{envoi ? 'Chargement…' : label}</button>");
	t('message d’échec en script', 0, "<script>e = 'Chargement impossible';</script>");
	t('commentaire ignoré', 0, '<!-- <p>Chargement…</p> -->');
	//  🔴 Les quatre attentes écrites sous un autre mot (#2975).
	t('vérification', 1, '<p class="attente">Vérification en cours…</p>');
	t('redirection', 1, '<p class="muted">Redirection vers vos accès…</p>');
	t('composition', 1, '<p class="apercu-attente">Composition du message…</p>');
	t('lecture', 1, '\t\t\t<p class="aide">Lecture des usages…</p>');
	t('compté une fois', 1, '<p class="muted">Chargement...</p>');
	//  ✅ Une phrase qui finit par « … » mais porte une valeur : un texte, pas une attente.
	t('phrase avec valeur', 0, '<p>Et {n} autres…</p>');
	t('phrase avec balise', 0, '<p>Voir <a href="/x">la suite</a>…</p>');
	t(
		'prose sur plusieurs lignes',
		0,
		'<p class="muted">\n\tUn lot sans propriétaire, une place…\n</p>',
	);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

const fautifs = [];
let emplois = 0;
let ancre = false;
for (const f of fichiers(RACINE)) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const source = readFileSync(f, 'utf8');
	if (rel === SOURCE) {
		ancre = /messageChargement\s*=\s*'Chargement…'/.test(source);
		continue;
	}
	if (EMPLOI.test(neutraliserCommentaires(source))) emplois++;
	const n = attentesManuelles(source);
	if (n) fautifs.push(`${rel} (${n})`);
}

//  🔴 LE CAS ZÉRO (`standards/04` §2) : si `EtatListe` ne porte plus son message
//  par défaut, ou si plus aucun écran ne l'emploie pour attendre, la règle que
//  ce contrôle fait respecter a changé — il ne mesure plus ce qu'il croit.
if (!ancre || emplois === 0) {
	console.error(
		`\n✗ INCONNU : message par défaut ${ancre ? 'trouvé' : 'ABSENT'} dans \`${SOURCE}\`, ` +
			`${emplois} écran(s) qui l’emploient pour attendre.\n\n` +
			'  Le contrôle a perdu son point d’appui : le mettre à jour.\n',
	);
	process.exit(2);
}

if (fautifs.length) {
	console.error(`\n✗ ${fautifs.length} fichier(s) écrivent leur propre attente :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		'\n  → `<EtatListe chargement />`, ou `messageChargement="…"` pour un message\n' +
			'    propre à l’écran. Le rendu de l’attente vit dans un seul composant.\n',
	);
	process.exit(1);
}
console.log(`✓ Chargement : ${emplois} écran(s) attendent par EtatListe, aucun à la main.`);
