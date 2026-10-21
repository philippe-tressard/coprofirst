#!/usr/bin/env node
/**
 * Garde-fou — **aucun sélecteur CSS ne survit au balisage qu'il stylait.**
 *
 * ## Pourquoi (#557, 20/08/2026)
 *
 * `svelte-check` sait déjà le dire : `Unused CSS selector`. Il le disait pour
 * **33 sélecteurs dans 9 fichiers**, à chaque exécution, depuis des semaines —
 * noyés parmi **95 avertissements**. Le job de CI ne regarde que les *erreurs*,
 * et à raison : rendre les avertissements bloquants d'un coup rendrait le job
 * rouge en permanence, donc désarmé dans la semaine.
 *
 * 🔴 Mais **un avertissement permanent ne se lit plus** (`standards/04` §18).
 * C'est le même mécanisme que les huit `SKIPPED` de #542 : ce qui se confond
 * avec le vert cesse d'être lu.
 *
 * Ce contrôle prend **une** famille d'avertissements, celle qui est maintenant à
 * zéro, et la rend bloquante. Les autres restent des avertissements tant qu'on
 * ne les a pas ramenées à zéro — c'est la seule façon d'en faire des contrôles
 * plutôt que du bruit.
 *
 * ## C'est #550 par l'autre bout
 *
 * #550 a retiré 74 symboles morts — imports et déclarations laissés par des
 * extractions. Ceci en est le pendant **côté styles** : le balisage part, la
 * règle reste. Les deux garde-fous prennent chacun un sens de la relation :
 *
 * | Contrôle | Question |
 * |---|---|
 * | `lint:classes-nues` | une classe **employée** est-elle **définie** ? |
 * | celui-ci | un sélecteur **défini** est-il **employé** ? |
 *
 * ⚠️ Une relation a deux sens de rupture, et un contrôle qui n'en garde qu'un
 * laisse passer l'autre (`standards/05` §9 bis).
 *
 * ## Ce que le relevé a trouvé au passage, et qui ne relevait PAS du nettoyage
 *
 * `.muted-sm` était définie dans **un seul** fichier et employée par **quatre
 * autres** — qui la rendaient donc **nue**. Elle n'a pas été supprimée : elle a
 * été **remontée** dans `app.css`. C'est la régression des pastilles de la
 * v2.67.11, trouvée par l'autre bout — par le sélecteur orphelin resté dans le
 * fichier d'origine, et non par l'écran nu.
 *
 * 🔴 Et `lint:classes-nues` ne pouvait pas la voir : il demande « cette classe
 * est-elle définie quelque part ? » — elle l'était. La question qu'il ne pose
 * pas est « une définition **s'applique-t-elle** à ce balisage ? ». Angle mort
 * relevé en #562.
 *
 * ⚠️ Remontée, elle est ensuite morte DANS la feuille globale — ses quatre
 * emplois partis un à un — sans que ce contrôle le voie : c'est l'une des 23
 * classes retirées le 02/10/2026 (#1537), quand il a appris à lire les feuilles.
 *
 * ## Deux portées, deux relevés (#1537, 02/10/2026)
 *
 * | Portée | Qui mesure |
 * |---|---|
 * | le `<style>` d'un composant | `svelte-check` (`Unused CSS selector`) |
 * | les feuilles globales (`app.css`, `src/styles/*.css`) | `lib-classes-globales.mjs` |
 *
 * 🔴 Jusqu'au 02/10/2026, seule la première existait, et le verdict disait
 * « CSS : aucun sélecteur orphelin » — 23 classes globales étaient mortes.
 *
 * Usage : `npm run lint:css-orphelin`
 *   exit 0 = aucun sélecteur orphelin hors exception, dans les deux portées
 *   exit 1 = sélecteur orphelin, ou exception devenue inutile
 *   exit 2 = INCONNU (svelte-check n'a pas pu être mesuré, ou le relevé des
 *            feuilles globales n'a rien lu)
 */
import { avertissements, lignesDuRapport } from './lib-svelte-check.mjs';
import { releveDuDepot } from './lib-classes-globales.mjs';

//  ══ 1. LES FEUILLES GLOBALES (#1537, 02/10/2026) ════════════════════════════
//
//  🔴 Ce contrôle a dit « aucun sélecteur orphelin » pendant que 23 classes de
//  `src/styles/*.css` n'étaient plus employées nulle part. Il ne lisait que ce
//  que `svelte-check` lit — les `<style>` des composants — et une feuille
//  globale n'est le `<style>` de personne : l'outil ne peut pas dire qui
//  l'emploie, donc il se tait, et le verdict héritait de ce silence en parlant
//  de « CSS » sans borne (`standards/04` §12, §26, §38).
//
//  Le relevé et ses limites — indulgent, jamais sévère — sont décrits et
//  éprouvés dans `lib-classes-globales.mjs` (`--selftest`).

/**
 * Classes globales que le relevé croit orphelines et qui ne le sont PAS, avec
 * leur raison — typiquement une classe construite par morceaux
 * (`class="badge-{x}"`), dont le nom complet n'est écrit nulle part.
 *
 * ⚠️ Une entrée qui ne sert plus — classe redevenue employée en toutes lettres,
 * ou retirée de la feuille — FAIT ÉCHOUER le contrôle. Vide au 02/10/2026 :
 * aucune des 23 orphelines du relevé n'était construite dynamiquement.
 */
const EXCEPTIONS_GLOBALES = {};

/**
 * Le TÉMOIN : une classe que l'on SAIT employée partout. Si le relevé ne la
 * voit pas employée, c'est la lecture qui est cassée — le contrôle rend
 * INCONNU au lieu de crier sur 250 classes, ou pire, de se taire.
 *
 * Un relevé dont le résultat normal est zéro ne distingue pas « rien trouvé »
 * de « rien lu » sans témoin extérieur (`standards/04` §27).
 */
const TEMOIN_GLOBAL = 'btn';

const RACINE_SRC = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const globales = releveDuDepot(RACINE_SRC, EXCEPTIONS_GLOBALES, TEMOIN_GLOBAL);
let globalesKo = false;
let globalesInconnu = false;

if (!globales.definies || !globales.lues || !globales.temoinVu) {
	//  Cas zéro (`standards/04` §2) : aucune feuille, aucune source, ou un témoin
	//  invisible — rien n'a été mesuré, et « 0 orpheline » serait un faux vert.
	console.error(
		`\n? INCONNU — feuilles globales : ${globales.feuilles} feuille(s), ` +
			`${globales.definies} classe(s) définie(s), ${globales.lues} source(s) lue(s), ` +
			`témoin \`.${TEMOIN_GLOBAL}\` ${globales.temoinVu ? 'vu' : 'NON vu employé'}.\n` +
			'  La lecture est cassée : ce relevé ne conclut pas.\n',
	);
	globalesInconnu = true;
} else if (globales.orphelines.length || globales.mortes.length) {
	console.error(
		`\n✗ ${globales.orphelines.length} classe(s) des feuilles globales employée(s) nulle part\n`,
	);
	for (const o of globales.orphelines)
		console.error(`   src/${o.fichier}:${o.ligne}  .${o.classe}`);
	for (const m of globales.mortes) {
		console.error(
			`   ✗ exception « ${m.classe} » devenue inutile (elle ${m.motif}) : ` +
				'la retirer de EXCEPTIONS_GLOBALES',
		);
	}
	console.error(
		'\n  Une classe globale que plus aucun balisage ne porte est le reste d’un écran\n' +
			'  parti. ⚠️ Avant de la supprimer, chercher une construction par morceaux\n' +
			'  (`class="kb-{x}"`, `` `kb-${x}` ``) : si elle en est une, la DÉCLARER dans\n' +
			'  EXCEPTIONS_GLOBALES avec sa raison, au lieu de la supprimer.\n',
	);
	globalesKo = true;
}

//  ══ 2. LES COMPOSANTS — ce que `svelte-check` sait dire ══════════════════════

/**
 * Sélecteurs orphelins TOLÉRÉS, avec leur raison.
 *
 * ⚠️ Une entrée qui ne sert plus FAIT ÉCHOUER le contrôle : une dérogation
 * oubliée est une porte qu'on croit fermée. La liste ne peut que décroître.
 *
 * Elle est vide, et c'est le but : le relevé a été ramené à zéro avant que ce
 * contrôle ne devienne bloquant. Un garde-fou posé sur une dette non soldée est
 * un job rouge en permanence, donc un job désarmé.
 */
const TOLERANCES = {};

//  ⚠️ Le TUYAU — lancer `svelte-check`, retirer les couleurs, reconnaître un
//  rapport valide, apparier chaque message à son emplacement — vivait ICI, et il
//  a été extrait dans `lib-svelte-check.mjs` quand un SECOND contrôle en a eu
//  besoin (`lint:libelles`, #561). Deux de ces quatre gestes ont déjà coûté un
//  défaut à ce dépôt : recopiés, ils divergent, et c'est du côté non testé qu'ils
//  sont faux. Le module porte leur `--selftest`.
const orphelins = avertissements(lignesDuRapport(), 'Unused CSS selector').map((a) => {
	const selecteur = /"([^"]+)"/.exec(a.message);
	return { fichier: a.fichier, ligne: a.ligne, selecteur: selecteur ? selecteur[1] : a.message };
});

const fautifs = orphelins.filter((o) => !(o.selecteur in TOLERANCES));
const inutiles = Object.keys(TOLERANCES).filter((s) => !orphelins.some((o) => o.selecteur === s));

if (fautifs.length || inutiles.length) {
	console.error(`\n✗ ${fautifs.length} sélecteur(s) CSS orphelin(s)\n`);
	for (const o of fautifs) console.error(`   ${o.fichier}:${o.ligne}  ${o.selecteur}`);
	for (const s of inutiles) {
		console.error(`   ✗ tolérance « ${s} » devenue inutile : la retirer de TOLERANCES`);
	}
	console.error(
		"\n  Un sélecteur qui ne style plus rien est le RESTE d'un balisage parti.\n" +
			"  ⚠️ Avant de le supprimer, vérifier qu'il n'est pas employé par un AUTRE\n" +
			'  fichier : Svelte scope au fichier, et une règle « orpheline » ici peut être\n' +
			"  la SEULE définition d'une classe qu'un autre écran rend alors NUE.\n" +
			'  Dans ce cas, elle se REMONTE dans `app.css` — elle ne se supprime pas.\n',
	);
	process.exit(1);
}

//  🔴 CE QUE CE CONTRÔLE NE PEUT PAS MESURER, ET QU'IL DOIT DIRE (#810, 06/09/2026)
//
//  Devant une classe INTERPOLÉE (`class="badge {expr}"`), le compilateur Svelte
//  ne sait pas résoudre ce qui sera rendu : il devient conservateur et cesse de
//  déclarer des sélecteurs inutilisés **pour tout le fichier**. Une seule
//  interpolation aveugle donc le contrôle sur l'écran entier.
//
//  Constaté le 06/09/2026 : en sortant un tableau de `mon-lot` vers son propre
//  composant, DIX sélecteurs morts depuis longtemps sont apparus d'un coup —
//  dont un recopié d'un composant qui le portait déjà. Ils n'avaient jamais été
//  signalés : le tableau contenait `class="badge {statutObjetBadge[…]}"`.
//
//  ⚠️ Le contrôle annonçait « 0 orphelin », pas « je n'ai pas pu regarder ». Un
//  vert qui ne distingue pas les deux est un faux vert (`standards/04` §1). Il
//  ne peut pas encore rendre INCONNU — cela le ferait échouer sur les fichiers
//  concernés, dette qui se solde écran par écran (#810) — mais il ANNONCE
//  désormais sa portée réelle, et c'est le minimum honnête.
import { readdirSync, readFileSync, statSync } from 'node:fs';

function fichiersSvelte(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = `${dir}/${e}`;
		if (statSync(p).isDirectory()) fichiersSvelte(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

const tous = fichiersSvelte('src');
/**
 *  Le fichier PRIVÉ de ses commentaires — sinon le contrôle se compte lui-même.
 *
 *  🔴 Trois fichiers convertis le 06/09/2026 sont restés comptés « non
 *  mesurés » : leurs commentaires expliquaient la conversion en CITANT le motif
 *  (`class="toast toast-{t.type}"`). Un garde-fou qui se déclenche sur le récit
 *  de sa propre application est un faux positif qu'on apprend à ignorer — et
 *  c'est la deuxième fois de la journée, après `@sans-appelant` cité dans
 *  `lint:client-appele`.
 */
function sansCommentaires(source) {
	//  Les blocs `/* … */` ENTIERS aussi (15/10/2026) : une ligne de suite qui ne
	//  commence pas par `*` passait pour du code — `mon-lot` restait compté aveugle
	//  pour un commentaire de sa `<style>` qui cite l'ancienne interpolation.
	return source
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/^\s*(\/\/|\*|\/\*).*$/gm, '');
}

/**
 *  Un fichier SANS `<style>` n'a aucun sélecteur à perdre de vue : une classe
 *  interpolée ne l'aveugle sur rien (10/10/2026). C'est le cas de `CarteListe`,
 *  qui fusionne la classe de son appelant (`class="carte-liste {classes}"`) et
 *  laisse tout son rendu à `normes.css` — le compter « non mesurable » aurait
 *  fait monter le plafond pour une mesure qui n'existe pas.
 */
const aveugles = tous.filter((f) => {
	const source = sansCommentaires(readFileSync(f, 'utf8'));
	return /<style[\s>]/.test(source) && /class="[^"]*\{/.test(source);
});

/**
 *  Le nombre de fichiers que ce contrôle ne peut PAS mesurer. Il ne peut que
 *  DÉCROÎTRE — comme le plafond de `lint:each-key`.
 *
 *  🔴 C'est ce qui transforme un constat en garde-fou. Sans plafond, le contrôle
 *  annonçait sa portée et personne n'était tenu par le chiffre : une classe
 *  interpolée ajoutée demain aurait fait un aveugle de plus, en silence.
 *
 *  Il valait 30 au relevé du 06/09/2026 (#810), puis 27 après conversion de cinq
 *  écrans et correction du contrôle lui-même, qui se comptait dans ses propres
 *  commentaires.
 *
 *  ⚠️ **Le baisser fait partie du geste.** Un plafond qui reste au-dessus du
 *  relevé est une tolérance qui ne sert plus, et ce contrôle échoue aussi dans
 *  ce sens-là.
 *
 *  🔴 **Remonté à 28 le 11/09/2026, et c'est la seule hausse admise** : une
 *  EXTRACTION. `FluxCorps` est né de `FluxCard` (plafond de modularité), et
 *  l'interpolation qui rendait la carte aveugle a suivi le balisage dans le
 *  fichier neuf — celle qui reste dans la carte en concerne une autre. La dette
 *  n'a pas augmenté : elle s'est répartie sur deux fichiers.
 *
 *  ⚠️ Une hausse pour toute autre raison est une régression, et doit être
 *  refusée. Écrire ici « + 1 parce que j'ai ajouté une classe interpolée »
 *  reviendrait à désarmer le contrôle en le documentant.
 */
//  🔴 29 depuis le 12/09/2026, et la raison compte : `OngletAcces` a été SCINDÉ
//  (#928) — `OngletAcces` en trois, `mon-lot` en deux — et les moitiés portent
//  la même classe interpolée qu'avant le découpage
//  (`class="badge {statutClass(…)}"`). Un fichier non mesurable est devenu deux.
//
//  ⚠️ Ce n'est PAS une dérogation de confort : le plafond monte d'exactement un,
//  pour un découpage qui n'ajoute aucune interpolation nouvelle. Le jour où il
//  monte parce qu'on a écrit une classe interpolée de plus, la bonne réponse est
//  de ne pas l'écrire.
//
//  ✅ 28 depuis le 29/09/2026 : l'annuaire a quitté `espace-cs` (#779), et la
//  page redevient mesurable — la classe interpolée qui l'aveuglait est partie
//  avec lui dans des composants qui n'en portent pas.
//
//  🔴 29 depuis le 30/09/2026 — même raison qu'au 11 et au 12/09 : l'onglet
//  Utilisateurs a été EXTRAIT de `admin/+page.svelte` (#779) avec ses deux classes
//  tirées d'une TABLE (`badge {badgeStatut(…)}`, `badge {d.cls}`), qui ne se
//  convertissent pas en `class:` sans recopier la table. La page reste aveugle
//  pour les siennes (onglet Comptes) : aucune interpolation nouvelle, une dette
//  répartie sur deux fichiers. La classe LOCALE `utag-{e}` du même bloc, elle, a
//  été convertie en `class:`.
//
//  24 le 08/10/2026 (#1571) : les cinq fichiers dont TOUTES les classes
//  interpolées étaient des ternaires locaux passent en `class:` — barre
//  d'import, confirmation, liste des sondages, réponses, renouvellements
//  d'audits. Aucun sélecteur orphelin ne s'y cachait. Les 24 restants tirent
//  leur classe d'une TABLE de teintes (`badge {STATUT[…]}`) : un composant de
//  pastille commun les rendrait mesurables, mais un `.badge` stylé dans une page
//  cesserait de s'y appliquer — chantier à regarder à l'écran, pas à l'aveugle.
//
//  25 le même jour, et pour la même raison qu'au 30/09 : les informations du
//  profil ont été EXTRAITES de `profil/+page.svelte` (`InformationsCompte`) avec
//  leurs badges de rôle tirés d'une table (`badge {b.cls}`). La page garde le
//  badge d'état d'une demande, tiré de sa propre table : aucune interpolation
//  nouvelle, une dette répartie sur deux fichiers.
//  ✅ 1 le 15/10/2026 (#1571) : les trente classes tirées d'une TABLE de teintes
//  passent par `Badge` (`$lib/components/Badge.svelte`), qui pose la teinte en
//  `class:` — le « composant de pastille commun » annoncé au 08/10. Aucun `.badge`
//  stylé dans une page ne s'y perdait (relevé avant conversion). Rendus
//  mesurables, les écrans ont livré cinq sélecteurs morts, retirés : `.pastille-xs`
//  et `.statut-compte` (la taille de base du badge), `.btn-sm` (Utilisateurs),
//  `.commande-row:last-child` (Accès), `.evol-form` (fiche d'affaire). `mon-lot`
//  n'était plus compté que pour un commentaire : le relevé saute désormais les
//  blocs `/* … */`.
//  ✅ 0 le 21/10/2026 (#1571) : `LiensGuide`, dernier fichier aveugle, recevait sa
//  classe de son APPELANT (`class="{classe} nav-guide"`) et comptait sur deux
//  règles `:global` de `Nav.svelte`. Il porte désormais son habillage : plus de
//  classe passée, rendu mesuré identique avant/après (`e2e/liens-guide`).
//  Le contrôle garde son rôle : il échoue dès qu'un fichier redevient aveugle.
//  Carte des plafonds décroissants : #1571.
const PLAFOND_NON_MESURES = 0;

const mesures = tous.length - aveugles.length;

if (aveugles.length !== PLAFOND_NON_MESURES) {
	const trop = aveugles.length > PLAFOND_NON_MESURES;
	console.error(
		`\n✗ ${aveugles.length} fichier(s) non mesurable(s) — le plafond est ${PLAFOND_NON_MESURES}.\n`,
	);
	if (trop) {
		for (const f of aveugles) console.error(`   ${f}`);
		console.error(
			[
				'',
				'  Une classe INTERPOLÉE fait cesser Svelte de déclarer les sélecteurs',
				'  inutilisés pour TOUT le fichier. Ce contrôle y devient aveugle, sans le dire.',
				'',
				'  Deux issues :',
				'    • la classe calculée est LOCALE et ses valeurs sont connues',
				'      -> `class:ma-classe={condition}`, que Svelte sait résoudre ;',
				"    • c'est la teinte d'un badge tirée d'une TABLE (`badge {STATUT[…]}`)",
				'      -> `<Badge teinte={STATUT[…]}>` (`$lib/components/Badge.svelte`) ;',
				"    • elle vient de l'APPELANT (une prop `classe`) : monter le plafond en le",
				'      justifiant ici — ce qui doit rester exceptionnel.',
				'',
			].join('\n'),
		);
	} else {
		console.error(
			[
				`  Abaisser \`PLAFOND_NON_MESURES\` à ${aveugles.length} dans ce fichier.`,
				'  Un plafond qui reste au-dessus du relevé est une tolérance qui ne sert plus.',
				'',
			].join('\n'),
		);
	}
	process.exit(1);
}

if (globalesKo) process.exit(1);
if (globalesInconnu) process.exit(2);

console.log(
	`✓ CSS des composants : aucun sélecteur orphelin (${orphelins.length} toléré(s) et déclaré(s))`,
);
console.log(
	`✓ CSS des feuilles globales : ${globales.definies} classes définies dans ` +
		`${globales.feuilles} feuilles, toutes employées par ${globales.lues} sources ` +
		`(${Object.keys(EXCEPTIONS_GLOBALES).length} exception(s) déclarée(s))`,
);
console.log(
	`  ⚠️ portée réelle des composants : ${mesures}/${tous.length} fichiers mesurés — ` +
		`${aveugles.length} portent une classe interpolée (plafond ${PLAFOND_NON_MESURES}, #1571).`,
);
