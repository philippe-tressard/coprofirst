/**
 * **Lire une table de `#lib` sans l'exécuter** — le lecteur de `tables-clients.mjs` (#2634).
 *
 * Une table publiée est une constante EXPORTÉE dont la valeur se lit sur l'arbre
 * syntaxique TypeScript, sans rien exécuter. Ce qui se lit :
 *
 * - les littéraux : chaîne, nombre (négatif compris), booléen, `null`, objet, liste ;
 *   `as`, `satisfies` et les parenthèses s'effacent ;
 * - un IDENTIFIANT : une autre constante du même fichier (exportée ou non), ou un nom
 *   IMPORTÉ d'un module de `src/lib` — lue à son tour selon les mêmes règles ; la
 *   propriété abrégée `{ id }` aussi ;
 * - un gabarit `${…}` et une concaténation `'…' + '…'` dont chaque morceau se lit en
 *   chaîne ou en nombre ;
 * - un étalement `...AUTRE` dans une liste (une liste) ou dans un objet (un objet).
 *
 * Tout le reste — appel, fonction, accès à une propriété, clé calculée, import hors
 * de `src/lib` — est REFUSÉ : la table publiée est ce que le site écrit, jamais ce
 * qu'il calcule. Les seuls fichiers ouverts sont ceux de `src/lib` que la table
 * nomme ou importe, par le lecteur `lire(chemin)` que l'appelant fournit.
 */
import ts from 'typescript';

/** Une erreur qui se dit sans pile : c'est une faute de déclaration, pas un bogue. */
export class Refus extends Error {}

/** `src/lib/<chemin>.ts#EXPORT` : la forme d'une source déclarée. */
export const SOURCE = /^src\/lib\/[\w/.-]+\.ts#[A-Z][A-Z0-9_]*$/;

/** Le module de `src/lib` qu'un import nomme depuis `depuis`, ou `null` hors de `src/lib`. PURE. */
export function moduleImporte(specificateur, depuis) {
	let relatif;
	if (/^[#$]lib\//.test(specificateur)) relatif = `src/lib/${specificateur.slice(5)}`;
	else if (specificateur.startsWith('.')) {
		const morceaux = depuis.split('/').slice(0, -1);
		for (const m of specificateur.split('/')) {
			if (m === '..') morceaux.pop();
			else if (m !== '.') morceaux.push(m);
		}
		relatif = morceaux.join('/');
	} else return null;
	if (!/\.ts$/.test(relatif)) relatif += '.ts';
	return /^src\/lib\/[\w/.-]+\.ts$/.test(relatif) && !relatif.includes('..') ? relatif : null;
}

/** Les constantes et les imports nommés d'un texte TypeScript. PURE. */
export function declarations(texte, chemin) {
	const fichier = ts.createSourceFile(
		chemin,
		texte,
		ts.ScriptTarget.Latest,
		true,
		ts.ScriptKind.TS,
	);
	const constantes = new Map();
	const imports = new Map();
	for (const instr of fichier.statements) {
		if (ts.isImportDeclaration(instr)) {
			const liens = instr.importClause?.namedBindings;
			if (!liens || !ts.isNamedImports(liens) || !ts.isStringLiteral(instr.moduleSpecifier))
				continue;
			for (const e of liens.elements)
				imports.set(e.name.text, {
					specificateur: instr.moduleSpecifier.text,
					nom: (e.propertyName ?? e.name).text,
				});
			continue;
		}
		if (!ts.isVariableStatement(instr)) continue;
		const exportee = instr.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword) ?? false;
		const constante = (instr.declarationList.flags & ts.NodeFlags.Const) !== 0;
		for (const d of instr.declarationList.declarations)
			if (ts.isIdentifier(d.name))
				constantes.set(d.name.text, { noeud: d.initializer, exportee, constante });
	}
	return { constantes, imports };
}

/**
 * Le lecteur de constantes d'un ensemble de fichiers : `valeur(chemin, nom, exigerExport, sans)`.
 * `sans` : les propriétés NON publiées de la table (`[].lien.cible`), sautées sans être
 * lues — une exclusion qui ne rencontre aucune propriété est refusée.
 * `lire(chemin)` rend le texte d'un fichier de `src/lib` ; chaque fichier est lu une fois.
 */
export function lecteur(lire) {
	const modules = new Map();
	const valeurs = new Map();
	const enCours = new Set();

	const module = (chemin) => {
		if (!modules.has(chemin)) modules.set(chemin, declarations(lire(chemin), chemin));
		return modules.get(chemin);
	};

	const valeur = (chemin, nom, exigerExport, sans = null) => {
		const cle = `${chemin}#${nom}`;
		const { constantes, imports } = module(chemin);
		const d = constantes.get(nom);
		if (!d) {
			const imp = imports.get(nom);
			if (!imp || exigerExport) throw new Refus(`${cle} : introuvable`);
			const autre = moduleImporte(imp.specificateur, chemin);
			if (!autre) throw new Refus(`${cle} : importé hors de src/lib (« ${imp.specificateur} »)`);
			return valeur(autre, imp.nom, true);
		}
		if (!d.constante || !d.noeud) throw new Refus(`${cle} : pas une constante initialisée`);
		if (exigerExport && !d.exportee) throw new Refus(`${cle} : pas une constante exportée`);
		if (sans) {
			const exclus = new Map(sans.map((s) => [`$${s}`, false]));
			const v = litteral(d.noeud, cle, (n) => valeur(chemin, n, false), '$', exclus);
			const inutiles = [...exclus].filter(([, sert]) => !sert).map(([s]) => s.slice(1));
			if (inutiles.length)
				throw new Refus(
					`${cle} : exclusion « ${inutiles.join(', ')} » sans propriété — elle ne sert plus`,
				);
			return v;
		}
		if (valeurs.has(cle)) return valeurs.get(cle);
		if (enCours.has(cle)) throw new Refus(`${cle} : définition circulaire`);
		enCours.add(cle);
		const v = litteral(d.noeud, cle, (n) => valeur(chemin, n, false));
		enCours.delete(cle);
		valeurs.set(cle, v);
		return v;
	};
	return valeur;
}

/** Un morceau de chaîne : une chaîne ou un nombre, rien d'autre. PURE. */
function morceau(v, ou, texte) {
	if (typeof v === 'string' || typeof v === 'number') return String(v);
	throw new Refus(`${ou} : « ${texte} » ne se lit pas en chaîne`);
}

/** Le nom d'une propriété d'objet littéral, ou `null` s'il est calculé. PURE. */
function nomDePropriete(nom) {
	if (!nom) return null;
	if (ts.isIdentifier(nom) || ts.isStringLiteral(nom) || ts.isNumericLiteral(nom)) return nom.text;
	return null;
}

/**
 * La valeur JSON d'un initialiseur ; `resoudre(nom)` rend celle d'un identifiant.
 * Tout nœud hors des formes admises est refusé. PURE (hors `resoudre`).
 */
export function litteral(
	noeud,
	ou,
	resoudre = (nom) => {
		throw new Refus(`${ou} : identifiant « ${nom} » sans lecteur`);
	},
	ici = '$',
	exclus = null,
) {
	const lire = (n, sous = ici) => litteral(n, ou, resoudre, sous, exclus);
	while (
		ts.isAsExpression(noeud) ||
		ts.isSatisfiesExpression(noeud) ||
		ts.isParenthesizedExpression(noeud) ||
		ts.isTypeAssertionExpression(noeud)
	)
		noeud = noeud.expression;
	if (ts.isStringLiteral(noeud) || ts.isNoSubstitutionTemplateLiteral(noeud)) return noeud.text;
	if (ts.isNumericLiteral(noeud)) return Number(noeud.text);
	if (
		ts.isPrefixUnaryExpression(noeud) &&
		noeud.operator === ts.SyntaxKind.MinusToken &&
		ts.isNumericLiteral(noeud.operand)
	)
		return -Number(noeud.operand.text);
	if (noeud.kind === ts.SyntaxKind.TrueKeyword) return true;
	if (noeud.kind === ts.SyntaxKind.FalseKeyword) return false;
	if (noeud.kind === ts.SyntaxKind.NullKeyword) return null;
	if (ts.isIdentifier(noeud)) {
		if (noeud.text === 'undefined')
			throw new Refus(`${ou} : « undefined » n'est pas une valeur publiée`);
		return resoudre(noeud.text);
	}
	if (ts.isTemplateExpression(noeud))
		return (
			noeud.head.text +
			noeud.templateSpans
				.map((s) => morceau(lire(s.expression), ou, s.expression.getText()) + s.literal.text)
				.join('')
		);
	if (ts.isBinaryExpression(noeud) && noeud.operatorToken.kind === ts.SyntaxKind.PlusToken) {
		const g = lire(noeud.left);
		const d = lire(noeud.right);
		if (typeof g !== 'string' || typeof d !== 'string')
			throw new Refus(
				`${ou} : « ${noeud.getText().slice(0, 60)} » n'est pas une concaténation de chaînes`,
			);
		return g + d;
	}
	if (ts.isArrayLiteralExpression(noeud)) {
		const liste = [];
		for (const e of noeud.elements) {
			if (ts.isSpreadElement(e)) {
				const etalee = lire(e.expression);
				if (!Array.isArray(etalee))
					throw new Refus(`${ou} : « ${e.getText()} » n'étale pas une liste`);
				liste.push(...etalee);
			} else liste.push(lire(e, `${ici}[]`));
		}
		return liste;
	}
	if (ts.isObjectLiteralExpression(noeud)) {
		const objet = {};
		for (const p of noeud.properties) {
			if (ts.isSpreadAssignment(p)) {
				const etale = lire(p.expression);
				if (etale === null || typeof etale !== 'object' || Array.isArray(etale))
					throw new Refus(`${ou} : « ${p.getText()} » n'étale pas un objet`);
				Object.assign(objet, etale);
				continue;
			}
			const nom = nomDePropriete(p.name);
			if (nom !== null && exclus?.has(`${ici}.${nom}`)) {
				exclus.set(`${ici}.${nom}`, true);
				continue;
			}
			if (ts.isShorthandPropertyAssignment(p)) objet[nom] = resoudre(nom);
			else if (ts.isPropertyAssignment(p) && nom !== null)
				objet[nom] = lire(p.initializer, `${ici}.${nom}`);
			else throw new Refus(`${ou} : propriété non littérale (« ${p.getText().slice(0, 60)} »)`);
		}
		return objet;
	}
	throw new Refus(`${ou} : valeur non littérale (« ${noeud.getText().slice(0, 60)} »)`);
}

/** La valeur de la constante EXPORTÉE `nom` d'un texte seul (sans import). PURE. */
export function constanteExportee(texte, nom, ou) {
	return lecteur(() => texte)(ou, nom, true);
}
