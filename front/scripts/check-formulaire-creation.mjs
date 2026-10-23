/**
 * Garde-fou : un formulaire de création s'écrit d'UNE seule façon.
 *
 * ## Pourquoi (#367, 15/08/2026)
 *
 * Le produit offrait **trois paradigmes** pour la même intention — créer un objet :
 * une boîte dans la page (actualités, sondages), une modale (calendrier,
 * prestataires — avec deux largeurs différentes), une page dédiée (nouveau
 * ticket). Un résident qui publie une actualité, ouvre un ticket et propose un
 * événement faisait trois gestes différents.
 *
 * Signalé **trois fois** par l'utilisateur avant d'être traité. Les deux premiers
 * lots (#361 largeur de saisie, #363 en-tête de page) avaient corrigé des
 * symptômes périphériques sans jamais ouvrir le formulaire lui-même.
 *
 * Le paradigme retenu est la **boîte dans la page**, sur désignation de
 * l'utilisateur : les actualités sont le modèle.
 *
 * ## Ce qui est interdit dans `routes/`
 *
 *   1. `class="card largeur-saisie"` écrit à la main — passer par
 *      `<FormulaireCreation titre="…">` ;
 *   2. une `<Modale>` portant un `<form>` **sans se déclarer `edition`**.
 *
 * ## 🔴 Le point 2 a changé de forme le 30/08/2026 — et il était MORT
 *
 * Il cherchait `class="modal-overlay"` suivi d'un `<form>`. Or #561 (28/08) a
 * fait absorber ce fond par `Modale.svelte`, qui vit dans `lib/` — hors du
 * périmètre `routes/` de ce contrôle. **Le motif ne pouvait donc plus rien
 * trouver, jamais**, et le contrôle restait vert : c'est `standards/04` §27, un
 * contrôle dont le résultat normal est zéro ne peut pas se relire lui-même.
 *
 * Il lit maintenant les `<Modale>` elles-mêmes, et il porte un **plancher
 * d'éléments lus** — sans quoi il pourrait redevenir muet de la même façon.
 *
 * ## Et la règle qu'il applique a changé le même jour (`ux-patterns` §14 bis)
 *
 * Arbitré à l'écran : *« en édition, le format modal est plus net que le
 * dépliement sur une même fenêtre »*. Un geste, un format :
 *
 *   - **créer** → la boîte dans la page (ce que #367 a établi, et qui tient) ;
 *   - **éditer** → la modale, qui se déclare par `<Modale edition>`.
 *
 * ⚠️ La modale de CRÉATION reste refusée. Sans cette moitié-là, la règle
 * redeviendrait « au cas par cas », c'est-à-dire les trois paradigmes que #367 a
 * supprimés après trois signalements.
 *
 * Le contrôle s'auto-contrôle : composant absent, prop disparue ou plus aucune
 * page utilisatrice → il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';
import { modales } from './lib-cadres.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const ROUTES = join(RACINE, 'routes');
const COMPOSANTS = join(RACINE, 'lib', 'components');
const COMPOSANT = join(COMPOSANTS, 'FormulaireCreation.svelte');
const CADRE = join(COMPOSANTS, 'CadreFormulaire.svelte');
const CADRE_REL = 'lib/components/CadreFormulaire.svelte';

/**
 * Les composants de `lib/components/` qui rendent eux-mêmes un `<form>`.
 *
 * 🔴 SANS CELA, LE CONTRÔLE EST AVEUGLE À TOUT FORMULAIRE FACTORISÉ — et donc à
 * ceux qu'on vient d'extraire, c'est-à-dire au bon code. Il cherchait `<form>`
 * dans le balisage de la page ; une modale montant `<FormulaireContrat />`
 * n'en contient aucun, et passait sans sa déclaration `edition`.
 *
 * Constaté le 30/08/2026 en éprouvant le contrôle **par son échec** : la
 * première modale d'édition du site a été écrite, sa déclaration retirée
 * exprès — et le contrôle est resté vert. Même famille que la première version
 * du self-test de `lib-volumes.sh`, qui avait échoué le jour où le code s'est
 * amélioré : *un contrôle qui ne voit pas la factorisation mesure la forme, pas
 * le fait.*
 *
 * La liste est **calculée**, jamais tenue à la main : une liste recopiée
 * diverge au premier composant ajouté, et c'est justement le composant ajouté
 * qui échappe au contrôle.
 *
 * 🔴 SOUS-DOSSIERS COMPRIS depuis le 23/10/2026 (#2173) : la lecture s'arrêtait
 * au premier niveau, et `reporting/FusionAffaires` — un `<form>` — monté dans
 * une `<Modale>` passait sans un mot. C'est la fenêtre de ce lot qui l'a montré,
 * en restant verte alors qu'elle devait se déclarer.
 */
function composantsPorteursDeFormulaire() {
	const noms = new Set();
	for (const chemin of fichiers(COMPOSANTS)) {
		if (/<form\b/.test(sansCommentaires(readFileSync(chemin, 'utf8')))) {
			noms.add(
				chemin
					.split(sep)
					.pop()
					.replace(/\.svelte$/, ''),
			);
		}
	}
	return noms;
}

/**
 * Emplois légitimes hors du composant, avec leur raison.
 *
 * Une tolérance sans raison devient un dépotoir : chacune est nommée, et le
 * contrôle échoue si l'une cesse de servir.
 */
const EXCEPTIONS = {
	//  ✅ VIDE, et c'est l'aboutissement de #672 — clos le 01/09/2026.
	//
	//  Le 31/08, l'élargissement de ce contrôle aux champs nus (`.field`, pas
	//  `<form>`) avait trouvé QUATRE écrans portant sept modales de création : le
	//  paradigme que #367 a supprimé après trois signalements de l'utilisateur.
	//  Ils y avaient échappé parce que le contrôle ne cherchait qu'un `<form>`,
	//  qu'aucun de ces formulaires ne porte.
	//
	//  `delegations`, `residence` et `OngletPerimetres` sont sortis le jour même.
	//  `mon-lot` a demandé un lot à lui : « Nouveau bail » vivait dans un fichier
	//  de 2 229 lignes, et le contrôle de modularité refusait d'y ajouter une
	//  ligne. Le corps est dans `FormulaireBail.svelte`, et la page est passée
	//  sous les 1 700.
	//
	//  ⚠️ Ne rien remettre ici sans un ticket et une date. Une exception sans
	//  échéance fait croire que la règle a des trous qu'elle n'a pas — et ce
	//  contrôle échoue si l'une d'elles cesse de servir, précisément pour que
	//  personne n'ait à y penser.
	//
	//  ── 12/09/2026, TRANCHÉE le 14/09 — ce n'est plus une attente (#931) ────
	//  🔴 `Saisie.svelte` n'est NI une création NI une édition : c'est une
	//  question posée avant un geste, la jumelle de `Confirmation.svelte` — qui
	//  passe ce contrôle pour la seule raison qu'elle n'a pas de champ.
	//
	//  Le ticket cherchait une TROISIÈME forme à arbitrer. Il n'y en a pas :
	//  `ux-patterns` §14 bis énonce depuis le 06/09 que la fenêtre reste légitime
	//  pour « ce qui n'est pas un formulaire d'entité », et sa liste nomme
	//  désormais la saisie qui accompagne un geste. Les deux règles qui
	//  interdisent la fenêtre parlent l'une et l'autre d'un OBJET — créé (#367)
	//  ou corrigé (§14 ter) ; aucune ne recouvre ce cas.
	//
	//  ⚠️ L'entrée RESTE, et ce n'est pas un oubli : ce contrôle lit une FORME
	//  (un champ dans une modale), pas une intention. Il ne peut pas distinguer
	//  « question posée avant un geste » d'un « formulaire d'entité », et lui
	//  apprendre à le faire reviendrait à lui confier l'arbitrage. La déclaration
	//  est donc l'endroit juste — elle nomme la décision au lieu de la cacher.
	'lib/components/Saisie.svelte':
		'saisie qui accompagne un geste, comme Confirmation — forme déclarée par ux-patterns §14 bis (#931, tranché le 14/09/2026)',
	//  ── 23/10/2026 (#2173) ───────────────────────────────────────────────────
	//  Fusionner les affaires liées DEPUIS la correction d'une affaire : la boîte
	//  du Suivi (`FusionAffaires`, un `<form>`) ne peut pas s'ouvrir dans la
	//  section, qui vit dans le `<form>` de la correction — deux formulaires
	//  imbriqués sont invalides. Ni création ni correction d'un objet : un geste
	//  (fusionner) et sa saisie, comme `Saisie`.
	'lib/components/ModaleFusionAffaires.svelte':
		'fusion depuis la correction : la boîte du Suivi, hors du <form> de la correction qui la contiendrait — saisie qui accompagne un geste, ux-patterns §14 bis (#2173)',
};

/** Retire commentaires et balisage commenté : expliquer la règle ne doit pas l'enfreindre. */

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

//  ── Auto-contrôle (cas zéro) ────────────────────────────────────────────────
if (!existsSync(COMPOSANT)) {
	console.error(`✗ Cas zéro : ${COMPOSANT} est introuvable — contrôle inopérant.`);
	process.exit(1);
}
if (!/export let titre\b/.test(readFileSync(COMPOSANT, 'utf8'))) {
	console.error(
		"✗ Cas zéro : FormulaireCreation n'expose plus `titre`. Le contrat a changé — " +
			'mettre ce contrôle à jour, sinon il laisse passer les formulaires écrits à la main.',
	);
	process.exit(1);
}

//  🔴 LE PÉRIMÈTRE INCLUT `lib/components/` DEPUIS LE 30/08/2026, ET C'EST LE
//  POINT 1 DE #640.
//
//  Il ne lisait que `routes/`. Or la conversion des écrans en modale d'édition
//  déplace le cadre là où vit le geste — et pour six formulaires sur sept, c'est
//  le composant qui le porte, pas la page (`FormulaireActualite` écrit son
//  propre `<FormulaireCreation>` depuis toujours). Chaque conversion faisait donc
//  SORTIR la modale du champ du contrôle : convertir revenait à se désarmer.
//
//  C'est la même cécité que celle décrite trois fois plus haut dans ce fichier —
//  `modal-overlay` mort depuis #561, le formulaire factorisé invisible — et
//  toujours pour la même raison : *le contrôle ne voyait pas la factorisation,
//  donc il mesurait la forme et non le fait.* La corriger AVANT de convertir est
//  ce que #640 demande en premier, faute de quoi chaque écran converti devrait
//  contourner le contrôle pour passer.
const tous = [...fichiers(ROUTES), ...fichiers(COMPOSANTS)];
if (tous.length === 0) {
	console.error("✗ Cas zéro : aucun fichier analysé — l'arborescence a changé.");
	process.exit(1);
}

//  Cas zéro du repérage par composant : s'il ne trouve plus aucun porteur, la
//  moitié « formulaire factorisé » du contrôle ne mesure plus rien — et elle
//  échouerait en silence, exactement comme le motif `modal-overlay` mort de #561.
const PORTEURS = composantsPorteursDeFormulaire();
if (PORTEURS.size === 0) {
	console.error(
		'✗ Cas zéro : aucun composant de lib/components/ ne rend de <form>. Le repérage ' +
			'des formulaires factorisés ne mord plus — ne pas lire ceci comme un succès.',
	);
	process.exit(1);
}

//  ── Recherche ───────────────────────────────────────────────────────────────
const MOTIFS = [
	{
		//  Le cadre N'EST fautif que s'il enveloppe un `<form>` : `card largeur-saisie`
		//  sert aussi, légitimement, à des cartes de LECTURE (les lots de `mon-lot`,
		//  par exemple, qui n'ont rien d'un formulaire). Sans cette condition, le
		//  contrôle criait sur elles — et un contrôle qui crie sur du légitime finit
		//  désarmé.
		regex: /class="[^"]*\bcard\b[^"]*\blargeur-saisie\b[^"]*"[\s\S]{0,400}?<form/g,
		quoi: 'un cadre de formulaire est rendu à la main',
		remede: '<FormulaireCreation titre="…"> … </FormulaireCreation>',
	},
	//  🔴 Le motif qui cherchait `class="modal-overlay"` est RETIRÉ : il était mort
	//  depuis #561 (28/08/2026). Le fond de modale ne s'écrit plus à la main —
	//  `Modale.svelte` l'a absorbé, et il vit dans `lib/`, hors du périmètre
	//  `routes/` de ce contrôle. Le motif ne pouvait donc plus rien trouver,
	//  jamais, et le contrôle restait vert : `standards/04` §27, un contrôle dont
	//  le résultat normal est zéro ne peut pas se relire lui-même.
	//
	//  Il est remplacé plus bas par une lecture de `<Modale>` — voir `modaleSansEdition`.
	//  Pas de motif sur `<h2 style="font-size…">`. Il avait été écrit, et il criait
	//  sur neuf pages dont sept portaient un titre de SECTION parfaitement légitime
	//  (admin, espace-cs, faq, profil, fiches de ticket et de sondage). Rien dans le
	//  balisage ne distingue un titre de formulaire d'un titre de section — et un
	//  contrôle qui crie sur du légitime finit désarmé, c'est la leçon de C16.
	//  L'uniformisation des titres de section est un autre sujet, qui aura son
	//  propre invariant le jour où il sera tranché.
	{
		//  🔴 LE CHOIX DU CADRE NE SE RECOPIE PAS (02/09/2026).
		//
		//  `<svelte:component this={… ? Modale : FormulaireCreation}>` s'écrivait
		//  dans CINQ formulaires, et `FormulaireAnnonce` allait être le sixième.
		//  Les copies avaient déjà divergé — deux passaient `fermetureAuFond={false}`
		//  avec un commentaire d'incident, alors que `Modale` l'impose depuis
		//  toujours dès que `edition` est posé. Une redondance qui faisait croire à
		//  un défaut chez les trois autres.
		//
		//  Le choix vit désormais dans `CadreFormulaire.svelte`, seul autorisé à
		//  nommer ce ternaire (il est écarté du relevé plus bas). Ailleurs, c'est
		//  une sixième copie.
		regex: /(?:Modale\s*:\s*FormulaireCreation|FormulaireCreation\s*:\s*Modale)/g,
		quoi: 'le CHOIX du cadre (boîte ou fenêtre) est recopié',
		remede: '<CadreFormulaire {edition} titre="…"> … </CadreFormulaire>',
	},
];

/**
 * Les `<Modale>` d'un fichier : la balise ouvrante et **son contenu réel**.
 *
 * La fin de la balise est le premier `>` HORS accolade — un attribut peut
 * contenir `=>` ou un objet, que suivre naïvement couperait trop tôt.
 *
 * 🔴 LE CONTENU EST BORNÉ PAR `</Modale>`, ET NON PAR UNE FENÊTRE DE N
 * CARACTÈRES (30/08/2026). Il l'était : « les 1200 caractères qui suivent ».
 * C'est une approximation, et elle se trompe **dans les deux sens** :
 *
 *   - trop court, elle rate un formulaire situé plus bas dans une longue modale ;
 *   - trop long, elle déborde sur la modale SUIVANTE — et c'est ce qui est
 *     arrivé le jour où un composant de formulaire a été monté dans la seconde
 *     de deux modales voisines : le contrôle a accusé la première, une simple
 *     confirmation sans le moindre champ.
 *
 * ⚠️ Un contrôle qui crie sur du légitime finit désarmé (leçon de C16). Ici il
 * aurait fallu déclarer `edition` sur une boîte de confirmation — c'est-à-dire
 * mentir sur le geste pour faire taire le contrôle.
 *
 * La borne équilibrée coûte deux lignes et supprime la classe entière.
 */

/**
 * Une modale qui porte un `<form>` **sans se déclarer `edition`** — donc une
 * modale de CRÉATION, le paradigme que #367 a supprimé.
 *
 * ⚠️ Rien dans le balisage ne dit si l'on crée ou si l'on corrige : le contrôle
 * ne peut pas le deviner, celui qui écrit l'écran si. D'où la prop, et non une
 * heuristique — une heuristique se trompe en silence dans les deux sens.
 */
function modaleSansEdition(contenu, porteurs) {
	//  Un formulaire, dans une modale, s'écrit de TROIS façons : en clair
	//  (`<form>`), monté par un composant qui en porte un, ou — et c'est la plus
	//  fréquente ici — écrit en champs nus, sans jamais la balise.
	//
	//  🔴 LA TROISIÈME A ÉTÉ AJOUTÉE LE 31/08/2026, ET ELLE A TROUVÉ 12 MODALES
	//  dans 8 fichiers : sept créations en modale, et neuf éditions qui n'avaient
	//  jamais déclaré leur geste. Aucune n'avait été vue par ce contrôle.
	//
	//  La FAQ ouvrait une modale pour la CRÉATION d'une question depuis toujours,
	//  soit le paradigme que #367 a supprimé après trois signalements de
	//  l'utilisateur. Elle est passée dessous parce que sa modale ne contient
	//  aucune balise `<form>` : seulement des `<label class="field">` et un
	//  éditeur riche. **Un formulaire n'a pas besoin d'en porter un.**
	//
	//  ⚠️ Le signal est `class="field"`, et NON `<input>` : le projet impose que
	//  tout champ libellé vive dans un `.field` (`lint:champs`, six nomenclatures
	//  locales avant #413). Un `<input>` nu sert aussi à filtrer une liste ou à
	//  chercher — le compter ferait crier sur des modales de lecture, et un
	//  contrôle qui crie sur du légitime finit désarmé (leçon de C16).
	const monteUnFormulaire = (suite) =>
		/<form\b/.test(suite) ||
		/class="[^"]*\bfield\b/.test(suite) ||
		[...porteurs].some((n) => new RegExp(`<${n}\\b`).test(suite));
	return modales(contenu)
		.filter((m) => monteUnFormulaire(m.suite) && !/\bedition\b/.test(m.balise))
		.map((m) => m.balise.slice(0, 80).replace(/\s+/g, ' '));
}

const fautifs = [];
const exceptionsUtiles = new Set();
let pagesAvecFormulaire = 0;
let modalesLues = 0;
let cadresLus = 0;

for (const f of tous) {
	//  Le chemin est rendu depuis `src/`, les deux racines étant mêlées : « lib/… »
	//  ou « routes/… » se lit sans ambiguïté, là où un relatif à ROUTES écrirait
	//  « ../lib/components/… » pour la moitié du relevé.
	const rel = relative(RACINE, f).split(sep).join('/');
	const brut = readFileSync(f, 'utf8');
	if (brut.includes('<FormulaireCreation')) pagesAvecFormulaire++;
	const contenu = sansCommentaires(brut);
	modalesLues += modales(contenu).length;
	if (rel !== CADRE_REL) cadresLus += (contenu.match(/<CadreFormulaire(?=[\s>])/g) ?? []).length;
	const trouves = [];
	for (const motif of MOTIFS) {
		const m = contenu.match(motif.regex);
		if (m) trouves.push({ ...motif, exemples: [...new Set(m.map((s) => s.trim()))].slice(0, 2) });
	}
	const creationEnModale = modaleSansEdition(contenu, PORTEURS);
	if (creationEnModale.length > 0) {
		trouves.push({
			quoi: 'un formulaire est rendu dans une MODALE sans se déclarer `edition`',
			remede:
				'créer → <FormulaireCreation titre="…"> (la boîte dans la page) · ' +
				'corriger un objet existant → <Modale edition …> (`ux-patterns` §14 bis)',
			exemples: creationEnModale.slice(0, 2),
		});
	}
	//  `CadreFormulaire` porte le ternaire par construction : le lui reprocher
	//  reviendrait à interdire la factorisation qu'on vient de faire. Le cas zéro
	//  ci-dessous vérifie qu'il le porte TOUJOURS — donc la tolérance ne peut pas
	//  devenir un trou.
	if (rel === CADRE_REL) continue;
	if (trouves.length === 0) continue;
	if (rel in EXCEPTIONS) {
		exceptionsUtiles.add(rel);
		continue;
	}
	fautifs.push({ fichier: rel, trouves });
}

//  🔴 Le relevé légitime de ce contrôle est VIDE : il ne peut donc pas distinguer
//  « rien trouvé » de « rien lu » (`standards/04` §27). C'est exactement ainsi que
//  son motif précédent est resté vert en étant mort. Le témoin est un plancher
//  d'éléments LUS : sous ce seuil, le repérage des `<Modale>` ne mord plus.
//  ⬇️ 10 → 9 le 12/09/2026 : les deux fenêtres de validation de compte sont parties dans `ValidationCompte` (12/09/2026, #889). Le plancher SUIT le relevé, il ne
//  le précède pas — le laisser au-dessus rendrait le cas zéro permanent.
//  ⬇️ « terminer un bail » s'ouvre dans la carte (12/09/2026, #889). Le plancher SUIT le relevé.
//  ⬇️ « noter un prestataire » s'ouvre dans la carte (12/09/2026, #889).
//  ⬇️ 7 → 6 le 01/10/2026 : la suppression d'un bail passe par `confirmer(SUPPRESSION(…))` (#779).
const PLANCHER_MODALES = 6;
if (modalesLues < PLANCHER_MODALES) {
	console.error(
		`✗ Cas zéro : ${modalesLues} <Modale> recensée(s) dans routes/ et lib/components/, ${PLANCHER_MODALES} ` +
			'attendues au minimum. Le repérage ne mord plus — ne pas lire ceci comme un succès.',
	);
	process.exit(1);
}

//  🔴 CAS ZÉRO DU CADRE FACTORISÉ (02/09/2026).
//
//  La factorisation a fait TOMBER le décompte de modales de 21 à 17 : cinq
//  formulaires ne nomment plus `Modale` dans leur balisage, et le contrôle est
//  passé au vert en mesurant MOINS. C'est le faux vert que ce fichier a déjà
//  produit trois fois — motif mort, formulaire factorisé invisible, périmètre
//  borné à `routes/`.
//
//  Le contrôle suit donc l'indirection : il exige que `CadreFormulaire` existe,
//  qu'il rende bien la boîte, et qu'il soit réellement employé. Sans quoi la
//  règle ne serait plus tenue par personne, et rien ne le dirait.
//
//  🔴 IL NOMMAIT « LES DEUX cadres », ET IL N'Y EN A PLUS QU'UN (06/09/2026).
//
//  L'utilisateur a écarté la fenêtre flottante pour l'édition : « comme le reste
//  du site, avec un UX standard, pas de spécifique ». `CadreFormulaire` ne rend
//  donc plus qu'une chose, et ce cas zéro — qui exigeait de trouver `Modale` dans
//  son `this={…}` — a **refusé le lot qui appliquait la décision**.
//
//  ⚠️ C'est le bon comportement d'un cas zéro, et il faut le dire : il a vu que la
//  règle qu'il gardait avait changé, au lieu de passer au vert en mesurant moins.
//  Ce qu'il vérifie désormais est ce qui reste vrai — le cadre existe, il rend la
//  boîte, il est employé.
if (!existsSync(CADRE)) {
	console.error(
		`✗ Cas zéro : ${CADRE_REL} est introuvable. Le choix du cadre n'a plus de ` +
			'source unique — ce contrôle ne mesure plus la règle qu’il énonce.',
	);
	process.exit(1);
}
const cadreSource = sansCommentaires(readFileSync(CADRE, 'utf8'));
if (!/<FormulaireCreation/.test(cadreSource)) {
	console.error(
		`✗ Cas zéro : ${CADRE_REL} ne rend plus <FormulaireCreation>. Créer et ` +
			'corriger doivent employer la MÊME boîte dans la page (06/09/2026).',
	);
	process.exit(1);
}
//  🔒 Et la fenêtre flottante ne doit pas revenir par la porte de derrière : un
//  `Modale` réintroduit ici rétablirait deux cadres sans que personne l'ait
//  décidé — exactement ce que la décision du 06/09 écarte.
if (/\bModale\b/.test(cadreSource)) {
	console.error(
		`✗ ${CADRE_REL} nomme à nouveau \`Modale\`. L'édition se fait dans la page ` +
			'depuis le 06/09/2026 ; une fenêtre flottante y serait un second cadre.',
	);
	process.exit(1);
}
//  Employé par les formulaires, pas seulement présent. Le plancher est bas
//  exprès : ce qui compte est qu'il ne tombe pas à zéro sans qu'on le voie.
const PLANCHER_CADRE = 5;
if (cadresLus < PLANCHER_CADRE) {
	console.error(
		`✗ Cas zéro : ${cadresLus} emploi(s) de <CadreFormulaire>, ${PLANCHER_CADRE} attendus ` +
			'au minimum. Les formulaires sont-ils repartis chacun avec son cadre ?',
	);
	process.exit(1);
}

//  Le composant peut exister, être conforme, et n'être employé nulle part.
if (pagesAvecFormulaire === 0) {
	console.error(
		"✗ Cas zéro : aucune page n'utilise <FormulaireCreation>. Le composant existe mais " +
			'ne sert plus — ce contrôle ne mesure alors plus rien.',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error('✗ Formulaire(s) de création écrit(s) hors du composant :');
	for (const { fichier, trouves } of fautifs) {
		for (const t of trouves) {
			console.error(`    ${fichier} — ${t.exemples.join(' · ')}`);
			console.error(`        ${t.quoi}`);
			console.error(`        → ${t.remede}`);
		}
	}
	console.error(
		'\n  Trois paradigmes de création coexistaient pour la même intention, et il a fallu\n' +
			"  que l'utilisateur le signale trois fois. Un seul est retenu : la boîte dans la\n" +
			'  page, dont les actualités sont le modèle (#367).',
	);
	process.exit(1);
}

const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsUtiles.has(f));
if (inutiles.length > 0) {
	console.error('✗ Exception(s) devenue(s) inutile(s) :');
	for (const f of inutiles) console.error(`    ${f} — retirer l'entrée de EXCEPTIONS`);
	process.exit(1);
}

console.log(
	`✓ Formulaires : ${pagesAvecFormulaire} page(s) passent par FormulaireCreation, ` +
		`${tous.length} page(s), ${modalesLues} modale(s) et ${cadresLus} cadre(s) vérifié(s), ` +
		`${Object.keys(EXCEPTIONS).length} exception(s) justifiée(s).`,
);
