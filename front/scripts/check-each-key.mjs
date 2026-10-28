/**
 * Garde-fou : le nombre de `{#each}` **sans clé** ne remonte pas.
 *
 * ## Pourquoi un plafond, et pas la règle ESLint
 *
 * `svelte/require-each-key` est coupée dans `eslint.config.js` (#549) : elle
 * comptait **142** signalements le 30/08/2026, et une règle qui échoue en
 * permanence finit désarmée. Ce contrôle-ci est ce qui manquait entre les deux —
 * il n'exige pas zéro, il **empêche d'en ajouter**, et il baisse à chaque lot.
 *
 * ⚠️ Ce n'est PAS un `--max-warnings <chiffre>`, que #549 interdit à raison : ce
 * dernier masque **toutes** les règles derrière un seul nombre. Celui-ci ne
 * concerne qu'un défaut nommé, et **nomme chaque occurrence** quand il dépasse.
 * C'est le motif de `lint:confirmation`, déjà en service.
 *
 * ## Ce que le défaut vaut réellement — mesuré, pas supposé
 *
 * Sans clé, Svelte réutilise les nœuds par POSITION : retirer un élément au
 * milieu d'une liste fait glisser l'état de son voisin.
 *
 * 🔴 Le relevé du 30/08 a montré que **le danger est aujourd'hui contenu**, et
 * pour une raison qui mérite d'être protégée : ce dépôt indexe son état par
 * IDENTITÉ, pas par position — `expandedEvId === ev.id`, `evolOuverte === ev.id`.
 * Les composants de liste (`CarteEvenement`, `FluxCard`) reçoivent leur état en
 * props plutôt que de le tenir en interne. Là où l'état est indexé par POSITION —
 * l'annuaire du CS et du syndic —, le décalage est compensé à la suppression.
 *
 * ⚠️ Depuis le 01/09/2026 cette compensation ne s'écrit plus dans l'écran mais
 * dans `#lib/listeDepliable`, éprouvée par `npm run lint:liste-depliable` : elle y
 * existait en DEUX exemplaires identiques, et c'est exactement le genre de code
 * qu'on recopie sans le relire. Les lignes de
 * formulaire de l'annuaire du syndic (`AnnuaireSyndic.svelte`, jadis dans
 * `espace-cs`) peuvent donc rester SANS clé, et c'est justifié : elles
 * n'ont aucun identifiant stable (`user_id` est nullable, un membre ajouté n'a
 * rien), et l'état y est indexé par position. Poser une clé devinée y serait le
 * remède pire que le mal que ce fichier décrit plus bas.
 *
 * Autrement dit : la convention du dépôt neutralise l'essentiel du risque. Ce
 * qui reste vrai, et ce que ce plafond protège :
 *
 *   1. le jour où un composant de liste tiendra un état INTERNE, le défaut
 *      deviendra réel — et rien ne le préviendrait ;
 *   2. sans clé, Svelte déplace des nœuds sans nécessité : coût de rendu, focus
 *      perdu, animations qui sautent ;
 *   3. la compensation manuelle des index est un travail que la clé supprime.
 *
 * ## Comment le faire baisser
 *
 * ⚠️ **Ne jamais deviner une clé.** Une clé DUPLIQUÉE fait planter Svelte à
 * l'exécution — « Cannot have duplicate keys » —, ce qui est pire que le défaut.
 * L'index n'en est pas une : il ne corrige rien.
 *
 * Les 37 corrigées le 30/08 l'ont été sur une PREUVE : `x.id` lu dans le corps
 * du bloc, donc un identifiant qui existe. Les 105 restantes itèrent sur des
 * primitives, des déstructurations ou des constantes sans identifiant — chacune
 * demande une décision, pas un motif.
 *
 * Usage : npm run lint:each-key
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**
 * Le compte réel. Il ne remonte pas.
 *
 * 30/08/2026 : 60 clés prouvées (37 par `id`, 15 par `val`/`code`, 8 par groupe) → 33.
 *
 * 02/09/2026 : **33 → 26**, sept de plus, et par deux voies seulement — parce que
 * ce sont les deux seules qui ne devinent rien :
 *
 * 1. **La valeur EST la clé**, sur une liste littérale et distincte par
 *    construction : les 24 heures d'une sauvegarde, les 4 barres d'une jauge de
 *    mot de passe, les 5 étoiles d'une notation, les 5 graduations d'un graphe
 *    (dont l'écart est démontré ≥ 1 dans le commentaire posé sur place).
 * 2. **Le doublon était lui-même un défaut d'affichage**, corrigé à la source :
 *    les variables d'un modèle d'e-mail (texte libre en base) et les pastilles de
 *    périmètre d'un événement (liste de codes écrite par plusieurs chemins)
 *    pouvaient afficher deux fois la même chose. Les dédoublonner rend la clé
 *    sûre EN MÊME TEMPS qu'elle corrige le rendu — au lieu de choisir entre les
 *    deux, ou de fabriquer une clé pour satisfaire ce contrôle.
 *
 * ## 26 → 5, le 03/09/2026
 *
 * Vingt et une ont reçu une clé, et la plupart par l'IDENTITÉ DE RÉFÉRENCE de
 * l'objet — `(occ)`, `(m)`, `(_contact)`. C'est la bonne clé d'une liste éditée
 * en place : elle survit à un retrait au milieu, là où l'index décale l'état de
 * tous les suivants. Trois de ces listes portaient des `bind:` sur chaque ligne
 * — le cas exact que la règle protège, pas une coquetterie de linter.
 *
 * Les cinq restantes itéraient sur des CHAÎNES potentiellement dupliquées — des
 * numéros découpés d'un champ libre. Leur poser une clé aurait été PIRE que le
 * défaut : deux numéros identiques font lever `each_key_duplicate`, et l'écran
 * entier tombe. Quatre ont été réglées **à la source** : `telephonesDe()`
 * (`#lib/utils`) découpe, nettoie et DÉDOUBLONNE — la clé devient sûre en même
 * temps que le rendu se corrige, au lieu de choisir entre les deux. Elle
 * remplace au passage `splitTels()` et une recopie littérale dans l'annuaire.
 *
 * ✅ LA DERNIÈRE EST SOLDÉE (21/10/2026, #1571) : l'unique `{#each}` sans clé
 * était dans `AnnuaireSyndic.svelte` (l'édition du syndic, jadis
 * dans `espace-cs`), qui édite les numéros d'un membre par
 * `bind:value={…telephones[ti]}` — la ligne se retrouve par ce `bind`, elle
 * n'est pas recopiée ici : le numéro écrit jadis (« ligne ~1248 ») avait dérivé.
 * La boucle a BESOIN de l'index pour écrire dans le tableau, et une clé portée par la valeur
 * changerait à chaque caractère tapé — Svelte recréerait le nœud, et le champ
 * perdrait le focus en cours de frappe. Aucune clé n'est meilleure que l'index :
 * elle s'y écrit donc en toutes lettres (`(ti)`), ce qui ne change pas le rendu
 * — Svelte réutilise déjà les nœuds par position — et dit que c'est un choix.
 */
//  Carte des plafonds décroissants : #1571.
const PLAFOND = 0;

/** En dessous, le repérage ne mord plus — le dépôt en porte ~200. */
const PLANCHER_EACH = 150;

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

const tous = fichiers(RACINE);
if (tous.length < 50) {
	console.error(`✗ Cas zéro : ${tous.length} composant(s) analysé(s) — le parcours a changé.`);
	process.exit(1);
}

/**
 * Les blocs `{#each …}` d'une source, chacun avec sa ligne.
 *
 * 🔴 La fin du bloc est l'accolade **équilibrée**, pas la première rencontrée.
 * Un motif naïf (`[^}]*?\}`) rate celui-ci :
 *
 *     {#each Array.from({ length: 24 }, (_, h) => h) as h}
 *
 * — il s'arrête au `}` de `{ length: 24 }`. C'est ce qui a fait annoncer **104**
 * là où ESLint en comptait 105, et un écart d'un seul est justement celui qu'on
 * impute à une divergence d'outil sans chercher plus loin. Un contrôle dont le
 * motif ne sait pas lire ce qu'il compte se trompe en silence.
 *
 * ⚠️ Même piège que la fin de balise `<Modale …>` dans `lint:formulaires`, trouvé
 * le même jour : un attribut peut contenir `=>` ou un objet.
 */
function blocsEach(source) {
	const sortie = [];
	for (const m of source.matchAll(/\{#each\b/g)) {
		let i = m.index;
		let prof = 0;
		for (; i < source.length; i++) {
			if (source[i] === '{') prof++;
			else if (source[i] === '}') {
				prof--;
				if (prof === 0) break;
			}
		}
		sortie.push({
			texte: source.slice(m.index, i + 1),
			ligne: source.slice(0, m.index).split('\n').length,
		});
	}
	return sortie;
}

/** Une clé est un `(…)` juste avant l'accolade fermante du bloc. */
const AVEC_CLE = /\)\s*\}$/;

const sansCle = [];
let eachLus = 0;

for (const chemin of tous) {
	const rel = relative(RACINE, chemin).split(sep).join('/');
	for (const bloc of blocsEach(sansCommentaires(readFileSync(chemin, 'utf8')))) {
		eachLus++;
		if (!AVEC_CLE.test(bloc.texte)) {
			sansCle.push(`${rel}:${bloc.ligne} — ${bloc.texte.replace(/\s+/g, ' ').slice(0, 66)}`);
		}
	}
}

//  Le relevé légitime de ce contrôle n'est pas vide, mais il pourrait le devenir
//  par accident de lecture plutôt que par mérite (`standards/04` §27).
if (eachLus < PLANCHER_EACH) {
	console.error(
		`✗ Cas zéro : ${eachLus} bloc(s) \`{#each}\` recensé(s), ${PLANCHER_EACH} attendus au ` +
			'minimum. Le motif ne mord plus — ne pas lire ceci comme un succès.',
	);
	process.exit(1);
}

if (sansCle.length > PLAFOND) {
	console.error(
		`\n✗ ${sansCle.length} \`{#each}\` sans clé — le plafond est ${PLAFOND}.\n\n` +
			sansCle
				.slice(0, 12)
				.map((l) => `   ${l}`)
				.join('\n') +
			(sansCle.length > 12 ? `\n   … et ${sansCle.length - 12} autre(s)` : '') +
			'\n\n  Sans clé, Svelte réutilise les nœuds par POSITION : retirer un élément au' +
			"\n  milieu d'une liste fait glisser l'état de son voisin." +
			'\n\n  ⚠️ Ne pas deviner la clé. Une clé DUPLIQUÉE fait planter Svelte à' +
			"\n  l'exécution, et l'index n'est pas une clé — il ne corrige rien." +
			'\n  La forme sûre : un identifiant que le corps du bloc lit déjà.\n',
	);
	process.exit(1);
}

if (sansCle.length < PLAFOND) {
	console.error(
		`\n✗ ${sansCle.length} \`{#each}\` sans clé, sous le plafond de ${PLAFOND}.\n\n` +
			`  Abaisser \`PLAFOND\` à ${sansCle.length} dans ce fichier. Un plafond qui reste` +
			"\n  au-dessus du réel laisse la place d'en réintroduire sans que rien ne le dise.\n",
	);
	process.exit(1);
}

console.log(
	`✓ Clés de liste : ${sansCle.length} \`{#each}\` sans clé sur ${eachLus} recensés ` +
		`(plafond ${PLAFOND}, ${tous.length} composants) — la conversion se poursuit par lots.`,
);
