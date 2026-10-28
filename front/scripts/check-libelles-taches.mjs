/**
 * Garde-fou : le nom d'une tâche planifiée ne s'écrit qu'à un seul endroit.
 *
 * POURQUOI. Le nom d'une tâche apparaissait à trois endroits qui ne se voyaient
 * pas les uns les autres : la synthèse « Santé des tâches planifiées », la
 * colonne Tâche du journal des exécutions, et le titre de la carte qui détaillait
 * cette tâche — ces deux derniers dans des FICHIERS DIFFÉRENTS. Ils avaient
 * divergé : la synthèse annonçait « Sauvegarde quotidienne » quand la carte
 * s'appelait « Système — Sauvegardes ». On ne pouvait donc pas relier une ligne
 * de la synthèse au tableau censé la détailler — signalé par l'utilisateur le
 * 11/08/2026.
 *
 * Les cartes de détail ont disparu avec #299, et `titreDetail()` avec elles. Ce
 * contrôle reste utile : il reste deux emplacements dans deux fichiers, et rien
 * n'empêcherait le prochain écran de retaper un nom à la main.
 *
 * Regrouper les libellés dans `#lib/taches.ts` ne suffit pas : rien n'empêche
 * le prochain écran de retaper « Sauvegarde quotidienne » dans un titre. Ce
 * contrôle échoue en CI si c'est le cas.
 *
 * LA RÈGLE : un libellé de tâche en toutes lettres n'est permis que dans
 * `lib/taches.ts`. Ailleurs, passer par `LIBELLE_TACHE[...]`.
 *
 * Le contrôle s'auto-contrôle : s'il n'analyse aucun fichier, s'il ne trouve
 * plus la source unique, ou s'il n'en extrait aucun libellé, il ÉCHOUE au lieu
 * de conclure au vert (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { corpsDesTables, valeursDeclarees } from './lib-lecture-source.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SOURCE = join('lib', 'taches.ts');

/** Fichiers à analyser : tout le front sauf la source unique elle-même. */
function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

const tous = fichiers(RACINE);
if (tous.length === 0) {
	console.error('✗ check-libelles-taches : aucun fichier analysé — contrôle inopérant.');
	process.exit(1);
}

const cheminSource = join(RACINE, SOURCE);
let source;
try {
	source = readFileSync(cheminSource, 'utf8');
} catch {
	console.error(`✗ check-libelles-taches : ${SOURCE} introuvable — la source unique a disparu.`);
	process.exit(1);
}

//  Les libellés sont extraits de la source, jamais recopiés ici : une seconde
//  liste serait exactement la duplication que ce contrôle interdit.
//
//  Le motif ramasse TOUTES les tables de libellés de `taches.ts`, pas seulement
//  `LIBELLE_TACHE` — depuis le 11/08/2026 il y a aussi `LIBELLE_ACTION`, le nom
//  du BOUTON quand il diffère du nom de la tâche. C'est voulu : un libellé
//  d'action recopié dans un écran diverge exactement comme un nom de tâche.
//  ⚠️ Sans supposer la mise en page : le motif d'avant exigeait une
//  tabulation et une seule ligne, si bien qu'un fichier reformaté rendait un
//  relevé FAUX — des libellés « écrits en dur » qui ne l'étaient pas (#419).
//  🔴 DEUX tables, nommées — et non « toutes celles qui commencent par
//  LIBELLE_ ». `taches.ts` en porte cinq : `LIBELLE_STATUT`, `AIDE_STATUT` et
//  `CLASSE_STATUT` sont arrivées après, et décrivent l'état d'EXÉCUTION d'une
//  tâche planifiée — pas son nom.
//
//  ⚠️ Les inclure produit un faux positif sur un mot français courant : onze
//  écrans écrivent « En cours » pour un TICKET ou une ANNONCE, notion sans
//  rapport avec l'exécution d'un cron. Les leur faire remplacer par
//  `LIBELLE_STATUT.en_cours` coupleraient deux vocabulaires qui ne partagent
//  qu'un mot — et la première divergence légitime de l'un casserait l'autre.
//
//  ⚠️ Le motif d'origine (`^	[a-z_]+: '…'`) les ramassait toutes, mais ne
//  voyait que les guillemets simples : le dépôt en portait de doubles à ces
//  endroits-là, et le contrôle était vert par accident de citation. Prettier
//  normalise les guillemets, ce qui a révélé l'angle mort (#419).
const LIBELLES = corpsDesTables(source, /export const (LIBELLE_TACHE|LIBELLE_ACTION)\b/g).flatMap(
	(corps) => valeursDeclarees(corps, '[a-z_]+'),
);
if (LIBELLES.length < 5) {
	console.error(
		`✗ check-libelles-taches : ${LIBELLES.length} libellé(s) extrait(s) de ${SOURCE} — ` +
			'le format a changé et le contrôle ne mesure plus rien.',
	);
	process.exit(1);
}

const fautes = [];
for (const chemin of tous) {
	const rel = relative(RACINE, chemin);
	if (rel === SOURCE) continue;
	//  🔴 Les commentaires sont NEUTRALISÉS avant l'analyse, et non détectés
	//  ligne par ligne.
	//
	//  La forme d'avant regardait si la ligne COMMENCE par `//`, `*` ou `<!--`.
	//  Elle ne voyait donc qu'un commentaire dont chaque ligne s'ouvre ainsi —
	//  or un commentaire Svelte de plusieurs lignes ne réouvre rien, et sa
	//  deuxième ligne passait pour du code. C'est exactement ce qui a fait
	//  refuser un lot le 20/08/2026, sur une phrase qui nommait
	//  « Sauvegarde quotidienne » pour EXPLIQUER la règle.
	//
	//  Un contrôle qui interdit d'en parler oblige à taire la raison — et c'est
	//  la raison qui se perd en premier. La parade vit dans
	//  `lib-commentaires.mjs`, partagée par les cinq contrôles qui en ont besoin
	//  (elle en avait quatre copies, écrites le même jour).
	const lignes = neutraliserCommentaires(readFileSync(chemin, 'utf8')).split('\n');
	lignes.forEach((ligne, i) => {
		for (const libelle of LIBELLES) {
			if (ligne.includes(libelle)) {
				fautes.push(`${rel.split(sep).join('/')}:${i + 1}  « ${libelle} »`);
			}
		}
	});
}

if (fautes.length) {
	console.error('✗ Libellé de tâche écrit en dur hors de lib/taches.ts :\n');
	for (const f of fautes) console.error(`   ${f}`);
	console.error(
		`\n  ${fautes.length} occurrence(s). Utiliser LIBELLE_TACHE[...] :` +
			'\n  un nom recopié diverge, et la synthèse cesse de renvoyer à son détail.',
	);
	process.exit(1);
}

console.log(
	`✓ Libellés de tâches : ${LIBELLES.length} noms, source unique respectée ` +
		`(${tous.length} fichiers analysés).`,
);
