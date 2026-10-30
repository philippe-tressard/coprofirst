/**
 * La RÈGLE de `check-styles-nus.mjs` : ce qui est refusé, et les écarts déjà connus.
 *
 * Séparé du script pour que la DÉTECTION (lui) et ce qu’elle cherche (ici) ne
 * grossissent pas dans le même fichier — cette table-ci bouge à chaque écran repris.
 */
/**
 * Volet A — les éléments dont une règle CSS nue casse silencieusement un autre
 * usage : elle atteint TOUS les éléments de ce type, cases à cocher comprises.
 */
export const ELEMENTS = ['input', 'textarea', 'select', 'button', 'label'];

/** Les éléments qui portent la peau définie par `.field input, .field select, …`. */
export const CONTROLES = ['input', 'select', 'textarea'];

/**
 * Volet B — ce qu'une signature refuse, et par quelle classe on la remplace.
 * `regle` : le sélecteur d'`app.css` dont les valeurs sont LUES (jamais recopiées),
 * dont `proprietes` doit être déclaré — vérifié au cas zéro. `mode: valeurs` exige
 * TOUTES les propriétés AVEC la valeur d'app.css, ce qui rend la signature étroite
 * et sûre ; `mode: proprietes` se contente d'UNE propriété, mais seulement sur les
 * `elements` visés.
 */
export const SIGNATURES = [
	{
		nom: 'libelle-champ',
		//  `:not(.pastille)` depuis le 23/09/2026 : une pastille radio est un
		//  `<label>`, et la règle la passait en capitales.
		regle: '.field label:not(.pastille)',
		proprietes: ['font-size', 'font-weight'],
		mode: 'valeurs',
		quoi: 'la typographie du libellé de champ',
		remede:
			'écrire un vrai `<label for="…">` dans un `.field` — `.field label` (app.css) porte ' +
			'déjà cette taille et cette graisse ; quand la section ne contient qu’un champ, ' +
			'c’est le titre de `SectionFormulaire` qui EST le libellé (ux-patterns §9 septies)',
	},
	{
		nom: 'form-actions',
		regle: '.form-actions',
		proprietes: ['display', 'justify-content'],
		mode: 'valeurs',
		quoi: 'l’alignement à droite d’une rangée d’actions',
		remede:
			'utiliser `class="form-actions"` (app.css), qui porte display, alignement, gap et ' +
			'marge — ou `class="modal-footer"` quand la rangée est le pied d’une modale',
	},
	{
		nom: 'controle-saisie',
		regle: '.field input',
		proprietes: ['border', 'border-radius', 'padding', 'background'],
		mode: 'proprietes',
		elements: CONTROLES,
		quoi: 'la peau d’un contrôle de saisie (bordure, rayon, remplissage, fond)',
		remede:
			'placer le contrôle dans un `<div class="field">` — `.field input, .field select, ' +
			'.field textarea` (app.css) porte déjà bordure, rayon, remplissage, fond ET le style ' +
			'de focus, que le style en ligne fait perdre en silence',
	},
	{
		nom: 'largeur-saisie',
		regle: '.largeur-saisie',
		proprietes: ['max-width'],
		mode: 'valeurs',
		quoi: 'la largeur normée d’un bloc de saisie',
		remede: 'utiliser `class="largeur-saisie"` (app.css) — la norme UX §9, écrite une fois',
	},
];

/**
 * Volet B bis — les classes de STRUCTURE dont une redéclaration en ligne est
 * toujours une redite. Limité à celles-ci exprès : `font-size` sur un `.badge` ou
 * `padding` sur une `.card` sont des variations légitimes, et les refuser noierait
 * le vrai signal (53 `.badge` et 14 `.card` dans l'arborescence).
 */
/*  `filters` a rejoint la liste le 19/08/2026 (#446). Elle en relevait déjà :
    quatre usages sur six posaient la MÊME marge basse — deux par une règle
    locale, deux par un style en ligne — et une cinquième définition allait
    naître au découpage suivant. La norme et sa variante `--defilante` vivent
    maintenant dans `app.css` ; ce qui reste à empêcher, c'est la sixième. */
export const CLASSES_STRUCTURE = ['field', 'form-actions', 'largeur-saisie', 'filters', 'case'];

/**
 * Tolérances, chacune avec sa raison.
 *
 * Clé : `chemin/relatif.svelte::signature`, où la signature est le `nom` d'une
 * entrée de `SIGNATURES` (ou `redite-classe`). Une clé qui nomme une signature
 * inexistante fait ÉCHOUER le contrôle : une tolérance qui ne protège rien, en
 * silence, est pire qu'absente.
 *
 * ⚠️ Le volet C — une recomposition écrite dans un `<style>` sous sélecteur
 * qualifié — se tolère sous `chemin.svelte::style:signature`. Deux espaces de clés
 * distincts EXPRÈS : tolérer un `style="…"` en ligne dans un fichier ne doit pas
 * couvrir en silence une seconde recomposition, écrite ailleurs et sous une autre
 * forme. La contrepartie assumée (une tolérance vaut pour tout le fichier) est
 * déjà large ; l'étendre à deux volets à la fois la rendrait aveugle.
 * Il n'y en a AUCUNE aujourd'hui : le relevé de #593 est tombé à zéro le jour où
 * le volet est né. Son témoin est donc un PLANCHER de règles lues, pas cette liste.
 *
 * Trois règles, et elles ne se négocient pas :
 *
 *   1. **Une raison, toujours.** Une liste sans raison devient un dépotoir.
 *   2. **Une tolérance qui ne sert plus fait échouer le contrôle**, ce qui force à
 *      retirer la ligne plutôt qu'à la reconduire « au cas où ».
 *   3. **Jamais de seuil.** On ne tolère pas « quelques » recompositions : on
 *      nomme celles qu'on n'a pas encore corrigées, et elles se comptent.
 *
 * Ces tolérances jouent aussi le rôle de TÉMOIN : chacune décrit une prise que la
 * détection doit continuer de faire. Si elles se périment TOUTES d'un coup, c'est
 * le motif de lecture qui est cassé, pas le dépôt qui est devenu conforme.
 *
 * ⚠️ La clé est le FICHIER, pas la ligne : une ligne bouge à chaque édition, et une
 * exception qui pointe à côté ne protège plus rien. La contrepartie est assumée —
 * une seconde violation de la même signature dans un fichier déjà toléré ne sera
 * pas vue. C'est le même arbitrage que `check-libelles-soumission.mjs`.
 * Les numéros de ligne cités dans les raisons sont donc indicatifs (`l. ~N`).
 *
 * ── RESTE À TRAITER — révélé par l'élargissement au balisage (#425) ────────────
 *
 * Ces écarts sont réels et connus. Ils ne sont PAS corrigés dans #425, dont le
 * périmètre est le formulaire d'édition de ticket : les corriger au passage aurait
 * mélangé une dizaine d'écrans dans le même diff. Chaque ligne dit ce qu'on lit
 * dans le fichier ; l'entrée disparaît d'elle-même quand l'écran est repris.
 */
export const TOLERANCES = {
	//  ── Volet A : sélecteurs d'élément nus dans un `<style>` ────────────────
	//  (aucune — clé de la forme `chemin.svelte:input`)

	//  ── libelle-champ : la typographie de `.field label` réécrite à la main ──
	//  ⚠️ `FormulaireTicket` a quitté cette liste le 18/08/2026 : le `<legend>` qui
	//  recopiait la typographie a disparu avec le `<fieldset>` de la catégorie,
	//  devenue une section à part entière dont le TITRE est le libellé (§9 septies).
	//  La question « quelle classe pour un `<legend>` ? » ne se pose plus — il n'y
	//  en a plus. Le contrôle l'a signalé de lui-même, comme il doit.

	//  ── form-actions : la rangée d'actions alignée à droite, à la main ───────
	//  ✅ `annuaire` et `espace-cs` sont parties le 01/10/2026 (#779) : leur
	//  rangée portait le lien des consignes, devenu `LienConsignes`, qui la range
	//  par `.form-actions`. Avant elles, celle de la relance syndic (#453).
	//  `mon-lot::form-actions` est partie le 12/09/2026 (#928) : la rangée a
	//  quitté l'écran avec l'onglet Gestion locative, et le composant qui la
	//  reçoit n'aligne plus rien à la main.

	//  ── controle-saisie : la peau de `.field input` repeinte à la main ───────
	//  ✅ Tolérée pour `/admin` jusqu'au 07/09/2026, et TOMBÉE — pas par un lot de
	//  style : le champ repeint était le motif de refus d'une demande de profil, la
	//  troisième écriture d'un geste qui en avait deux autres. Il est parti avec
	//  elles dans `AccepterRefuser.svelte`, où il porte `.input-sm`. La dette n'a
	//  pas été rabotée, elle a été emportée par la factorisation — comme les deux
	//  `<textarea>` de #561, et pour la même raison : c'est un AUTRE contrôle qui
	//  a forcé la main.
	//  ✅ Le champ « Motif » du marquage non-relançable (`VueRelanceSyndic`) est
	//  TOMBÉ le 10/10/2026 avec le geste lui-même : toute affaire suivie se
	//  relance désormais, sans exception (demande de l'utilisateur).
	//  ⚠️ Pas une dette : une exception VOULUE (24/09/2026). Le `<select>` de
	//  `PastilleDeroulante` n'est pas un champ de formulaire mais le cœur d'une
	//  PASTILLE — transparent, sans bordure, arrondi par la pastille qui
	//  l'enveloppe. Le placer dans un `.field` lui rendrait la peau carrée que ce
	//  composant existe pour retirer (« son UX dénote à côté du filtre »).
	'lib/components/PastilleDeroulante.svelte::style:controle-saisie':
		'<select> habillé en pastille, jamais un champ de formulaire (l. ~87)',
	//  ⚠️ Pas une dette : une exception VOULUE (29/10/2026, #2308, maquette B).
	//  Le champ de RECHERCHE porte sa loupe et sa croix DANS le contour : c'est le
	//  cadre `.recherche-cadre` qui prend la peau de `.field input` (bordure,
	//  rayon, fond blanc, anneau de focus par `:focus-within`), et la saisie qu'il
	//  enveloppe est transparente et sans bordure — sinon deux contours.
	'lib/components/ChampRecherche.svelte::style:controle-saisie':
		'<input type="search"> transparent dans le cadre qui porte la peau (l. ~128)',
	//  ✅ Tolérance TOMBÉE le 11/09/2026 — troisième fois qu'une dette de peinture
	//  part sans qu'un lot de style s'en occupe. Le `<select>` et l'`<input>` de
	//  l'onglet Consommations ont suivi le balisage dans `OngletConsommations`,
	//  extrait pour la modularité, et ils y portent `.input-sm` : la classe
	//  existait déjà depuis le 07/09 pour exactement ce cas — une saisie dans une
	//  rangée, à côté de boutons `.btn-sm`, et non dans un `.field`.
	//  Reconduire la tolérance dans le fichier neuf aurait fait voyager la dette
	//  au lieu de la solder.
	//  ✅ Tolérance TOMBÉE le 28/08/2026 (#561). Les deux `<textarea>` sont dans un
	//  `.field` et ne repeignent plus rien — non par un lot de style, mais parce
	//  qu'associer leur libellé les a fait entrer dans le champ de `lint:champs`,
	//  qui a exigé le `.field`, lequel a rendu la peinture inutile.
	//  Trois contrôles se sont relayés sans se connaître : c'est ce que produit
	//  une charte tenue par des garde-fous plutôt que par la mémoire.
	//  ⚠️ Les deux tolérances de `tickets/[id]` sont tombées le 17/08/2026 (#431) :
	//  le champ e-mail re-peint à la main est parti avec le formulaire de réponse
	//  écrit à la main (remplacé par `EvolForm`), et les 720 px de quatre blocs
	//  sont devenus une seule règle `.ticket-header, .messages, …`. Le contrôle
	//  les a REFUSÉES dès qu'elles sont devenues inutiles.

	//  ── largeur-saisie ───────────────────────────────────────────────────────
	//  ✅ Plus aucune tolérance : les deux `<section>` de l'Espace CS qui
	//  écrivaient 720 px en dur portent la classe depuis le 18/08/2026. Vérifié
	//  en OUVRANT le fichier, et pas en lisant le verdict — c'est la règle que
	//  ce contrôle a lui-même enseignée la veille (`standards/04` §21).

	//  ── redite-classe : la classe est là, et le style en ligne la redit ──────
	//  ✅ Plus aucune tolérance (08/10/2026, #1571) : le `.field` de la correction
	//  d'une ligne d'import est parti dans `CorrectionImportLot`, sa marge en classe.
	//  ⚠️ Ce n'était pas une redite : `.field` porte `margin-bottom: 1rem`, et
	//  l'attribut écrivait .75rem. La description disait « exactement la valeur que
	//  la classe porte » — une tolérance se relit contre la feuille, pas de mémoire.
};
