#!/usr/bin/env node
/**
 * Garde-fou — **le registre des arbitrages d'interface** tient sa forme et ses
 * renvois (`.claude/skills/ux-patterns/ARBITRAGES.md`, 18/10/2026).
 *
 * ## Pourquoi il existe
 *
 * Le registre remplace le tableau « Ce qui est tranché » de la skill `ux-patterns` :
 * 65 décisions, chacune avec sa date, son ticket, son auteur, son pourquoi, ce qui
 * a été écarté et le contrôle qui la tient. Les numéros 1 à 21 sont cités ailleurs
 * (« arbitrage n° 21 », `CLAUDE.md`). Sans contrôle, trois choses dérivent au
 * premier lot (`standards/05`) :
 *
 *   • la **forme** — un titre qu'un `grep "^### n° [0-9]"` ne trouve plus, une
 *     entrée sans « Pourquoi » : l'arbitrage perd la raison qui le rendait
 *     discutable ;
 *   • les **numéros** — un trou, un doublon, ou une citation (« arbitrage n° 40 »
 *     dans une skill, un commentaire de composant) vers une entrée qui n'existe
 *     pas ou plus : la consigne renvoie alors à rien ;
 *   • le champ **« Tenu par »** — il nomme le contrôle qui fait respecter la
 *     décision. Un `npm run lint:xxx` renommé ou un test supprimé laisse une
 *     décision *affirmée tenue* qui ne l'est plus : le pire faux vert, celui qui
 *     se lit comme une garantie (`standards/04`).
 *
 * ## Ce qu'il refuse
 *
 *   1. un titre hors de la forme `### n° N · <statut> — <titre>`, avec statut ∈
 *      {en vigueur, révisé, remplacé par n° X, à arbitrer, ouvert} ;
 *   2. une numérotation non continue (1, 2, 3…), ou un numéro répété ;
 *   3. une entrée sans ligne de provenance (date · ticket · par · §), ou sans
 *      « Décidé », « Pourquoi », « Tenu par » — sauf `ouvert` et `remplacé par`,
 *      qui ne décident rien ou plus rien ;
 *   4. un `remplacé par n° X` vers une entrée absente (ou vers elle-même), et
 *      tout « n° N » du registre qui ne désigne aucune entrée ;
 *   5. tout « arbitrage n° N » cité dans le dépôt versionné (consignes, skills,
 *      code, tests) vers un numéro absent du registre ;
 *   6. un `npm run lint:xxx` (ou `lint:xxx`) nommé dans « Tenu par » qui n'est pas
 *      un script de `package.json`, et un fichier de test (`test_*.py`,
 *      `*.spec.ts`, `e2e/…`) qui n'existe pas.
 *
 * ## Qu'il ne juge pas
 *
 * Que le contrôle nommé soit **bon** : il dit seulement qu'il existe (même
 * limite que `lint:ci`). Les noms de composants (`CarteListe`…) ne sont pas
 * vérifiés — ni un « Tenu par » écrit « aucun garde-fou nommé », qui est une
 * réponse honnête.
 *
 * ## Fiabilité (`standards/04`)
 *
 * Cas zéro : un registre qui compte moins de 21 entrées (les n° 1 à 21 sont
 * figés), un dépôt dont le balayage lit moins de `FICHIERS_MINIMUM` fichiers, ou
 * un balayage qui ne retrouve plus la citation de `CLAUDE.md` (le témoin) **échouent** —
 * ils ne rendent jamais « aucune faute ». Git absent : INCONNU, pas OK.
 *
 * Lancer : node scripts/check-arbitrages.mjs [--selftest]
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { autotest } from './check-arbitrages.selftest.mjs';
import {
	ENTREES_MINIMUM,
	EXCEPTIONS,
	EXTENSIONS_TEXTE,
	FICHIERS_MINIMUM,
	PACKAGE,
	REGISTRE,
	TAILLE_MAX,
	TEMOIN,
	citations,
	fautesDeCitation,
	fautesDuRegistre,
} from './lib-arbitrages.mjs';

const RACINE_DEPOT = fileURLToPath(new URL('../..', import.meta.url));

// ── 4. Le dépôt ──────────────────────────────────────────────────────────────

function inconnu(message) {
	//  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.
	console.error(`\n✗ lint:arbitrages — INCONNU : ${message}\n`);
	return 1;
}

function controler() {
	let fichiers;
	try {
		fichiers = execFileSync('git', ['ls-files', '-z'], {
			cwd: RACINE_DEPOT,
			encoding: 'utf8',
			maxBuffer: 64 * 1024 * 1024,
		})
			.split('\0')
			.filter(Boolean);
	} catch (e) {
		return inconnu(`\`git ls-files\` impossible (${e.message.split('\n')[0]})`);
	}
	if (!existsSync(join(RACINE_DEPOT, REGISTRE))) return inconnu(`${REGISTRE} introuvable`);
	let scripts;
	try {
		scripts = JSON.parse(readFileSync(join(RACINE_DEPOT, PACKAGE), 'utf8')).scripts ?? {};
	} catch (e) {
		return inconnu(`${PACKAGE} illisible : ${e.message}`);
	}

	const texte = readFileSync(join(RACINE_DEPOT, REGISTRE), 'utf8');
	const ensemble = new Set(fichiers);
	const fautes = fautesDuRegistre(texte, { scripts, fichiers: ensemble, minimum: ENTREES_MINIMUM });
	const numeros = new Set([...texte.matchAll(/^### n° (\d+) · /gm)].map((m) => Number(m[1])));

	const contenus = {};
	for (const f of fichiers) {
		if (!EXTENSIONS_TEXTE.test(f)) continue;
		const abs = join(RACINE_DEPOT, f);
		if (!existsSync(abs) || statSync(abs).size > TAILLE_MAX) continue;
		contenus[f] = readFileSync(abs, 'utf8');
	}
	const lus = Object.keys(contenus).length;
	if (lus < FICHIERS_MINIMUM) {
		return inconnu(
			`${lus} fichier(s) lu(s) pour les citations, ${FICHIERS_MINIMUM} attendus au moins`,
		);
	}
	if (citations(contenus[TEMOIN] ?? '').length === 0) {
		return inconnu(`${TEMOIN} ne cite plus aucun « arbitrage n° N » : le balayage serait aveugle`);
	}
	for (const f of Object.keys(EXCEPTIONS)) {
		if (!(f in contenus)) fautes.push(`exception « ${f} » : fichier absent du dépôt`);
	}
	fautes.push(...fautesDeCitation(contenus, numeros));

	if (fautes.length) {
		console.error('✗ Registre des arbitrages d’interface — forme ou renvois cassés :\n');
		for (const f of fautes) console.error(`  • ${f}`);
		console.error(
			`\n   Le format et les statuts sont décrits dans ${REGISTRE} (« Le format »).\n` +
				'   Un numéro ne se réutilise jamais, une entrée ne s’efface pas : elle passe\n' +
				'   `remplacé par n° X`.\n',
		);
		return 1;
	}
	console.log(
		`✓ Arbitrages : ${numeros.size} entrée(s) de forme valide et continue, « Tenu par » résolu, ` +
			`citations de ${lus} fichier(s) toutes présentes au registre.`,
	);
	return 0;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
	process.exit(process.argv.includes('--selftest') ? autotest() : controler());
}
