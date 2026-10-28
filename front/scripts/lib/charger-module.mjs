/**
 * **Charger un module `#lib` depuis un contrôle** — une seule façon de le faire.
 *
 * ## Pourquoi ce module (15/09/2026)
 *
 * Quatre contrôles chargent un module de `src/lib` pour l'EXÉCUTER plutôt que de
 * le relire (`standards/04` §22 : un motif d'extraction ne se relit pas, il
 * s'exécute). Ils le faisaient chacun à leur façon, et **deux d'entre eux
 * cassaient dès que leur module importait un voisin** :
 *
 * | Forme | Conséquence |
 * |---|---|
 * | `esbuild.transform` seul | les `import` restent non résolus ; le data-URI ne sait pas d'où il vient |
 * | `esbuild.build({ bundle })` | suit les imports relatifs — mais pas l'alias `#lib` |
 *
 * 🔴 Constaté en ajoutant un `import { parAttribut } from '#lib/table-statuts.ts'`
 * à `lib/tickets.ts` : `lint:filtre-statuts` est tombé sur son **cas zéro**, en
 * annonçant « ne se transpile pas ». Il avait raison, et c'est exactement
 * `standards/04` §16 — **le contrôle partageait la faiblesse de ce qu'il
 * contrôle** : il ne savait résoudre que ce que le module n'importait pas.
 *
 * ⚠️ Un contrôle qui casse quand le code se factorise décourage la
 * factorisation. C'est le pire des effets, parce qu'il est silencieux : on
 * n'écrit pas l'import, et personne ne saura jamais pourquoi.
 *
 * La règle la plus déployée — le bundle — est donc **enrichie** de l'alias, et
 * devient la seule.
 */
import { existsSync } from 'node:fs';

/**
 * Le module tel que le SITE l'exécute — imports résolus, TypeScript effacé.
 *
 * @param source chemin absolu du point d'entrée (`.ts`)
 * @param echouer la fonction d'échec de l'appelant : c'est lui qui décide du
 *   code de sortie et du vocabulaire, ce module ne fait que charger.
 */
export async function chargerModule(source, echouer) {
	if (!existsSync(source)) {
		echouer(`Cas zéro : ${source} est introuvable — contrôle inopérant.`);
	}
	const esbuild = await import('esbuild');
	try {
		const { outputFiles } = await esbuild.build({
			entryPoints: [source],
			bundle: true,
			write: false,
			format: 'esm',
			platform: 'neutral',
			//  `#lib/…` se résout par le champ `imports` de `package.json`, que esbuild
			//  lit comme Vite et Node : aucun alias à répéter ici.
			logLevel: 'silent',
		});
		//  Import par data: URL — aucun fichier temporaire à nettoyer, et la
		//  source du dépôt n'est jamais réécrite.
		const code = outputFiles[0].text;
		return await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
	} catch (e) {
		echouer(`Cas zéro : ${source} ne se charge pas (${e.message}).`);
	}
}
