/**
 * Les écarts DÉCLARÉS de `check-charte-recomposee.mjs`.
 *
 * Clé : `chemin/relatif.svelte::classe`. Trois règles, et elles ne se négocient
 * pas — ce sont celles de `check-styles-nus.regles.mjs`, pour les mêmes raisons :
 *
 *   1. **Une raison, toujours.** Une liste sans raison devient un dépotoir.
 *   2. **Une tolérance qui ne sert plus fait ÉCHOUER le contrôle**, ce qui force à
 *      retirer la ligne plutôt qu'à la reconduire « au cas où ».
 *   3. **Jamais de seuil.** On ne tolère pas « quelques » redéfinitions : on nomme
 *      celles qu'on n'a pas encore tranchées, et elles se comptent.
 *
 * Elles jouent aussi le rôle de TÉMOIN : chacune décrit une prise que la détection
 * doit continuer de faire. Si elles se périmaient TOUTES d'un coup, ce serait le
 * motif de lecture qui est cassé, pas le dépôt qui est devenu conforme.
 *
 * ── D'où vient cette liste ────────────────────────────────────────────────────
 *
 * Le relevé de #607 comptait **54** règles. Trente-cinq ont été supprimées ou
 * réduites à leur seule différence le 28/08/2026 ; les dix-neuf ci-dessous sont
 * des variations RÉELLES, dont chacune dit pourquoi elle existe.
 *
 * ⚠️ La plupart ne sont pas des dettes : `composants.css` autorise explicitement
 * qu'un écran réparte sa grille autrement, à condition de ne garder QUE ce qui
 * diffère. C'est le cas de tous les `.form-grid` ci-dessous. Les inscrire ici
 * n'est donc pas un aveu — c'est la seule façon qu'a le contrôle de distinguer
 * une variation VOULUE d'une copie oubliée, puisque le CSS ne le dit pas.
 */
export const TOLERANCES = {
	//  ── `.checkbox-field` : l'alignement quand le libellé fait plusieurs lignes ─
	//  La charte centre la case sur son libellé, ce qui est juste tant qu'il tient
	//  sur une ligne. Les conditions d'utilisation en font trois : la case doit
	//  alors s'aligner sur la PREMIÈRE, sinon elle flotte au milieu du paragraphe.
	//  C'est la SEULE des quatre propriétés qui reste locale — les trois autres
	//  (gap, font-size, display) étaient trois valeurs différentes pour la même
	//  case, et sont remontées dans la charte le 02/09/2026.
	//  ── `.aide` : plus AUCUNE tolérance, et c'est le but de #870 ─────────────
	//  Il y en avait deux ici, sur `ConfigSauvegarde` et `PreferencesAffichageNotifs`,
	//  parce que la charte imposait une marge NÉGATIVE en haut — pensée pour l'aide
	//  qui suit un groupe de cases, fausse partout ailleurs.
	//
	//  🔴 Deux écrans sur quatre la refusaient : ce n'étaient pas eux les cas
	//  particuliers, c'était la valeur de la charte qui était fausse. Une marge
	//  négative dans une classe de TEXTE compense l'espacement de quelqu'un d'autre
	//  — c'est un symptôme, jamais une intention.
	//
	//  Depuis le 10/09/2026, `.aide` est l'écriture unique des NEUF classes d'aide
	//  du dépôt (le ticket n'en avait relevé que quatre : quatre autres vivaient en
	//  local, invisibles d'un audit de la charte). Sa géométrie est celle de
	//  `.field-hint`, la plus déployée des neuf — 49 occurrences sur 79 —, et c'est
	//  aussi celle vers laquelle les deux écrans ci-dessus convergeaient d'eux-mêmes.
	//  Le seul écart qui reste est `.aide.sous-case`, et il porte sa raison.
	//  ── `.auth-header h1` : plus d'écart ─────────────────────────────────────
	//  L'inscription réduisait son titre à 1,4 rem (page longue, comme son logo,
	//  #607). Retiré le 30/10/2026 (#2313) : tout h1 de page prend
	//  `--fs-titre-page` — cinq h1 avaient quatre tailles. Le logo reste réduit.
	'routes/auth/inscription/+page.svelte::checkbox-field':
		'align-items: flex-start — le libellé des conditions tient sur plusieurs lignes',
	//  ── `.form-grid` : la répartition en colonnes ────────────────────────────
	//  `composants.css` le prévoit en toutes lettres : « les écrans qui
	//  répartissent autrement ne gardent QUE ce qui diffère — une colonne, un
	//  espacement — jamais la règle entière ». C'est exactement ce qu'ils font.
	'lib/components/ChampsPrestataire.svelte::form-grid':
		'colonnes de 180 px et gap resserré, même raison',
	//  `OngletCopropriete` en portait une (`auto-fill`), retirée le 01/10/2026
	//  (#779) : ses six champs remplissent leurs rangées, la différence ne se
	//  voyait jamais — et ils sont désormais ceux de `ChampsIdentiteCopropriete`.
	'lib/components/AnnuaireConseil.svelte::form-grid':
		'colonnes de 150 px et gap resserré — la fiche d’un membre du CS tient des champs très courts',
	//  ✅ La « pile » de `FormulaireFaq` (la dette nommée ici depuis le 31/08) est
	//  RÉSORBÉE le 26/09/2026 (#1329) : le formulaire passe par les sections du
	//  cadre, et la grille locale est partie avec la grille de champs à plat.

	//  ── Écrans d'authentification ────────────────────────────────────────────
	'routes/auth/inscription/+page.svelte::auth-page':
		'formulaire LONG : aligné en haut au lieu d’être centré, et plus aéré',
	'routes/auth/inscription/+page.svelte::auth-card':
		'480 px au lieu de 400 — l’inscription porte deux fois plus de champs',
	'routes/auth/inscription/+page.svelte::auth-logo': 'logo réduit sur une page déjà longue',

	//  ── Descendants par balise (lus depuis le 30/08/2026) ───────────────────
	//  🔴 Cette forme de sélecteur — `.classe element` — échappait au contrôle, qui
	//  ne lisait que `.classe` seule. C'est elle qu'emploie tout composant qui
	//  habille ses enfants : onglets, tableaux, listes. Son ajout a trouvé une
	//  redéfinition COMPLÈTE de `.tabs button` qui faisait disparaître le liseré de
	//  l'onglet actif en production, et deux règles de tableau dont cinq
	//  propriétés sur sept étaient identiques à la charte.
	//
	//  ⚠️ L'exception de `/prestataires` a disparu le 05/09/2026, et pas parce qu'on
	//  l'a rabotée : la rangée d'onglets est devenue UN composant (`BarreOnglets`),
	//  qui porte le défilement horizontal pour toutes les pages. L'écart n'avait plus
	//  d'objet — c'est la bonne façon de retirer une dérogation.
	'lib/components/AccesConnexes.svelte::table th':
		'tableaux DENSES (imports d’accès, listes de badges) : en-tête resserré',
	'lib/components/AccesConnexes.svelte::table td':
		'même raison — la cellule suit l’en-tête, sinon la colonne se décale',

	//  ── Boutons ──────────────────────────────────────────────────────────────
	//  `OngletUtilisateurs::btn-sm` retirée le 15/10/2026 (#1571) : la règle ne
	//  visait plus aucun bouton de l'écran — morte, invisible tant qu'un badge
	//  interpolé aveuglait le fichier.
	//  ⚠️ La clé a suivi le BALISAGE le 07/09/2026 : la barre d'actions d'un membre
	//  est devenue `ActionsMembre.svelte` (le trio « enregistrer · modifier ·
	//  supprimer » était écrit deux fois dans la page, et le crayon du bandeau une
	//  troisième). L'écart, lui, n'a pas bougé — c'est le même écart, au nouvel
	//  endroit. Le laisser sur l'ancien chemin l'aurait fait disparaître du relevé
	//  sans que rien ne soit corrigé, comme pour `FormulaireFaq` ci-dessus.
	'lib/components/ActionsMembre.svelte::btn-icon':
		'boutons-icônes CERCLÉS et carrés (2 rem) formant une barre d’actions, là où la ' +
		'charte habille une icône nue',
	'lib/components/ActionsMembre.svelte::btn-icon-edit':
		'le crayon est en couleur primaire — il est l’action principale de la rangée',

	//  ── Divers, chacun avec sa raison ────────────────────────────────────────
	'lib/components/ImageUpload.svelte::spinner':
		'attente posée SUR l’image : taille fixe et trait blanc, pour rester lisible sur ' +
		'une photo quelconque',
	'lib/components/TachesPlanifiees.svelte::chevron':
		'chevron plus petit et en couleur primaire : il annonce une action, pas un dépliage neutre',
	'lib/components/AccesConnexes.svelte::table':
		'tableau plus lisible : ses cellules portent des codes et des dates',
	'routes/(app)/notifications/+page.svelte::section-title':
		'espacement resserré — les sections de cette page sont courtes et nombreuses',
	'routes/(app)/notifications/+page.svelte::back-link':
		'retour discret et proche du contenu, là où la charte en fait un lien primaire',
};
