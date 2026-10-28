/**
 * **Les intitulés qu'une entité déclarée donne à ses sections** — lus dans la
 * déclaration EXÉCUTÉE (`titreEcran`), pour les fichiers qui l'importent.
 *
 * ## Pourquoi (#1329, 27/09/2026)
 *
 * `lint:ordre-sections` ne classait que les libellés génériques de la table
 * (« Titre », « Nature », « Suivi »…) : ceux d'un objet — « Code », « Type »,
 * « État » — lui étaient inconnus, et il les ignorait exprès, faute de savoir
 * à quelle section ils appartiennent. Le formulaire d'accès rangeait ainsi
 * Type · Code · Lot et porteur · Accès · État sans qu'aucun contrôle ne le
 * voie ; remis dans l'ordre du cadre, il repassait l'ancien ordre au vert.
 *
 * Or une entité déclarée DIT cette correspondance : `titreEcran` de chaque
 * section. Ce module la lit — par exécution du module, jamais par un motif qui
 * relirait le TypeScript (`standards/04` §22) — et le contrôle d'ordre s'en sert
 * pour les fichiers qui importent l'entité, et pour eux seuls : « Type » est la
 * Nature d'un accès, pas forcément celle d'un autre écran.
 */
import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { chargerModule } from './lib/charger-module.mjs';

/** `{ NOM_EXPORTÉ → { intitulé → id de section } }` pour toutes les entités. */
export async function titresParEntite(dossierEntites, echouer) {
	const sortie = {};
	for (const nom of readdirSync(dossierEntites)) {
		if (!nom.endsWith('.ts') || nom === 'types.ts') continue;
		const module = await chargerModule(join(dossierEntites, nom), echouer);
		for (const [exporte, valeur] of Object.entries(module)) {
			if (!valeur || !Array.isArray(valeur.sections)) continue;
			const titres = {};
			for (const s of valeur.sections)
				for (const t of [s.titreEcran ?? []].flat()) titres[t] = s.id;
			sortie[exporte] = titres;
		}
	}
	return sortie;
}

/**
 * Les intitulés applicables à UNE source : ceux des entités qu'elle importe
 * (import de valeur depuis `#lib/entites/…`). PURE.
 */
export function titresDeLaSource(source, parEntite) {
	const titres = {};
	for (const m of source.matchAll(
		/import\s+(?!type\b)\{([^}]*)\}\s+from\s+'#lib\/entites\/[^']+'/g,
	)) {
		for (const nom of m[1].split(',').map((n) => n.trim().split(/\s+as\s+/)[0])) {
			Object.assign(titres, parEntite[nom] ?? {});
		}
	}
	return titres;
}
