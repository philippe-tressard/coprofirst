/**
 * Le cœur PUR du contrôle des arbitrages d'interface : constantes, lecture du
 * registre, fautes de forme / de numéro / de renvoi, citations du dépôt. Rien n'y
 * est lu ni écrit : `check-arbitrages.mjs` lit le dépôt, `check-arbitrages.selftest.mjs`
 * éprouve chaque refus. Le « pourquoi » est dans l'en-tête de `check-arbitrages.mjs`.
 */
export const REGISTRE = '.claude/skills/ux-patterns/ARBITRAGES.md';
export const PACKAGE = 'front/package.json';

/** Les n° 1 à 21 viennent de l'ancien tableau et sont cités ailleurs : ils restent. */
export const ENTREES_MINIMUM = 21;
/** Cas zéro du balayage des citations : un dépôt qui en lit moins n'est pas le dépôt. */
export const FICHIERS_MINIMUM = 200;
/** Le fichier qui doit encore citer un arbitrage — sinon le balayage est aveugle. */
export const TEMOIN = 'CLAUDE.md';
/**
 * Fichiers qui CITENT la forme refusée sans la porter — ce contrôle et son
 * auto-test. Une exception qui n'est plus lue par le balayage fait échouer.
 */
export const EXCEPTIONS = {
	'front/scripts/check-arbitrages.selftest.mjs':
		'ses cas d’auto-test citent un numéro absent exprès',
};
export const EXTENSIONS_TEXTE = /\.(md|py|ts|mjs|js|svelte|css|sh|yml|yaml|json|html|toml|txt)$/;
export const TAILLE_MAX = 2_000_000;

const STATUTS = /^(en vigueur|révisé|à arbitrer|ouvert|remplacé par n° (\d+))$/;
const TITRE = /^### n° (\d+) · (.+?) — (\S.*)$/;
const DATE = /^\d{1,2}(?:-\d{1,2})?\/\d{2}\/\d{4}/;
const CHAMP = /^- \*\*(Décidé|Pourquoi|Écarté|Tenu par|Historique)\*\*\s*:/;
const REQUIS = ['Décidé', 'Pourquoi', 'Tenu par'];
const CITATION = /arbitrages?\s+n°\s?(\d+(?:\s*(?:,|et)\s*\d+)*)/gi;

// ── 1. Le registre : forme, numéros, renvois ─────────────────────────────────

/** Les lignes du registre HORS blocs de code (le gabarit du « Format » y vit). PURE. */
function lignesHorsCode(texte) {
	let dansCode = false;
	return texte.split('\n').map((l, i) => {
		if (/^\s*```/.test(l)) {
			dansCode = !dansCode;
			return [i + 1, ''];
		}
		return [i + 1, dansCode ? '' : l.replace(/\r$/, '')];
	});
}

/** Les entrées du registre : titre, provenance, champs (texte continué jusqu'au suivant). PURE. */
function decouper(texte) {
	const entrees = [];
	const fautes = [];
	let cour = null;
	let champ = null;
	for (const [n, l] of lignesHorsCode(texte)) {
		if (/^###\s/.test(l)) {
			cour = { ligne: n, titre: l, numero: null, statut: null, provenance: null, champs: {} };
			champ = null;
			const m = TITRE.exec(l);
			if (!m || !STATUTS.test(m[2])) {
				fautes.push(
					`${REGISTRE}:${n} — titre hors forme « ${l.slice(0, 80)} » : attendu ` +
						'`### n° N · <en vigueur | révisé | remplacé par n° X | à arbitrer | ouvert> — <titre>`',
				);
			} else {
				cour.numero = Number(m[1]);
				cour.statut = m[2];
			}
			entrees.push(cour);
			continue;
		}
		if (!cour) continue;
		if (/^(##\s|---\s*$)/.test(l)) {
			cour = null;
			continue;
		}
		const c = CHAMP.exec(l);
		if (c) {
			champ = c[1];
			cour.champs[champ] = l;
		} else if (champ && l.trim() && !/^- \*\*/.test(l)) {
			cour.champs[champ] += ` ${l.trim()}`;
		} else if (!l.trim()) {
			champ = null;
		} else if (cour.provenance === null && !champ) {
			cour.provenance = l;
		}
	}
	return { entrees, fautes };
}

/**
 * Tous les `n° N` lus hors blocs de code, avec leur ligne. PURE.
 * (« Les n° 1 à 21 », « (n° 19) », « remplacé par n° 39 ».)
 */
function renvoisInternes(texte) {
	const renvois = [];
	for (const [n, l] of lignesHorsCode(texte)) {
		if (/^###\s/.test(l)) continue; // le titre est jugé par `decouper`
		for (const m of l.matchAll(/\bn°\s?(\d+)/g)) renvois.push([n, Number(m[1])]);
	}
	return renvois;
}

/** Le script `lint:xxx` d'un jeton « Tenu par », ou null. */
function scriptNomme(jeton) {
	const m = /^(?:npm run )?(lint:[\w:-]+)$/.exec(jeton);
	return m ? m[1] : null;
}

/** Ce jeton désigne-t-il un FICHIER DE TEST ? Rend ses chemins candidats, ou null. */
function candidatsTest(jeton) {
	const j = jeton.replace(/^\.\//, '');
	if (/^e2e\/[\w.-]+$/.test(j)) {
		const avecExt = /\.spec\.ts$/.test(j) ? j : `${j}.spec.ts`;
		return [`front/${avecExt}`];
	}
	if (/(^|\/)(test_\w+\.py|[\w.-]+\.spec\.ts)$/.test(j)) {
		return j.includes('/')
			? [j, `front/${j}`, `api/tests/${j}`]
			: [`api/tests/${j}`, `front/e2e/${j}`];
	}
	return null;
}

/**
 * Les fautes du registre. PURE : rien n'est lu ici.
 *
 * @param {string} texte          le registre
 * @param {{scripts: Record<string, string>, fichiers: Set<string>, minimum?: number}} monde
 */
export function fautesDuRegistre(texte, { scripts, fichiers, minimum = 0 }) {
	const { entrees, fautes } = decouper(texte);
	if (entrees.length < minimum) {
		fautes.push(
			`${REGISTRE} — ${entrees.length} entrée(s) lue(s), ${minimum} attendues au moins ` +
				'(les n° 1 à 21 sont figés) : registre vide ou illisible',
		);
	}

	// 2. Numérotation : continue, sans répétition.
	const vus = new Set();
	let attendu = 1;
	for (const e of entrees) {
		if (e.numero === null) {
			attendu++;
			continue;
		}
		if (vus.has(e.numero)) fautes.push(`${REGISTRE}:${e.ligne} — le n° ${e.numero} est répété`);
		else if (e.numero !== attendu) {
			fautes.push(
				`${REGISTRE}:${e.ligne} — numérotation non continue : le n° ${attendu} était attendu, ` +
					`le n° ${e.numero} est lu`,
			);
		}
		vus.add(e.numero);
		attendu = e.numero + 1;
	}

	for (const e of entrees) {
		if (e.numero === null) continue;
		const ou = `${REGISTRE}:${e.ligne} (n° ${e.numero})`;
		const remplace = /^remplacé par n° (\d+)$/.exec(e.statut);

		// 4. Le remplaçant existe, et n'est pas l'entrée elle-même.
		if (remplace) {
			const x = Number(remplace[1]);
			if (x === e.numero) fautes.push(`${ou} — « remplacé par » elle-même`);
			else if (!entrees.some((o) => o.numero === x)) {
				fautes.push(`${ou} — remplacé par le n° ${x}, qui n'est pas dans le registre`);
			}
		}

		// 3. Provenance : date · ticket · par · §.
		const champsProv = (e.provenance ?? '').split(' · ');
		if (e.provenance === null || champsProv.length < 4 || champsProv.some((c) => !c.trim())) {
			fautes.push(`${ou} — ligne de provenance absente ou incomplète (date · ticket · par · §)`);
		} else if (!DATE.test(champsProv[0])) {
			fautes.push(
				`${ou} — la provenance ne commence pas par une date (jj/mm/aaaa) : « ${champsProv[0]} »`,
			);
		}

		// 3. Champs requis, sauf `ouvert` et `remplacé` (rien de décidé, ou plus rien).
		const dispense = e.statut === 'ouvert' || remplace;
		if (!dispense) {
			for (const nom of REQUIS) {
				if (!e.champs[nom]) fautes.push(`${ou} — champ « ${nom} » absent`);
			}
		}

		// 6. Le contrôle nommé existe.
		for (const m of (e.champs['Tenu par'] ?? '').matchAll(/`([^`]+)`/g)) {
			const jeton = m[1].trim();
			const script = scriptNomme(jeton);
			if (script) {
				if (!(script in scripts)) {
					fautes.push(
						`${ou} — « Tenu par » nomme \`${jeton}\` : aucun script « ${script} » dans package.json`,
					);
				}
				continue;
			}
			const cands = candidatsTest(jeton);
			if (cands && !cands.some((c) => fichiers.has(c))) {
				fautes.push(
					`${ou} — « Tenu par » nomme \`${jeton}\` : fichier de test introuvable (${cands.join(' | ')})`,
				);
			}
		}
	}

	// 4 bis. Tout « n° N » du registre désigne une entrée.
	for (const [n, num] of renvoisInternes(texte)) {
		if (!vus.has(num))
			fautes.push(`${REGISTRE}:${n} — renvoi au n° ${num}, qui n'est pas dans le registre`);
	}
	return fautes;
}

// ── 2. Les citations « arbitrage n° N » du dépôt ─────────────────────────────

/** Les numéros cités par « arbitrage n° N », avec leur ligne. PURE. */
export function citations(texte) {
	const trouvees = [];
	texte.split('\n').forEach((l, i) => {
		for (const m of l.matchAll(CITATION)) {
			for (const num of m[1].match(/\d+/g)) trouvees.push([i + 1, Number(num)]);
		}
	});
	return trouvees;
}

/** Les fautes de citation de `contenus` (chemin → texte) contre les numéros connus. PURE. */
export function fautesDeCitation(contenus, numeros) {
	const fautes = [];
	for (const [chemin, texte] of Object.entries(contenus)) {
		if (chemin in EXCEPTIONS) continue;
		for (const [n, num] of citations(texte)) {
			if (!numeros.has(num)) {
				fautes.push(`${chemin}:${n} — cite l'arbitrage n° ${num}, absent du registre`);
			}
		}
	}
	return fautes;
}
