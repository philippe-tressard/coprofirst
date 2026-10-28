<!--
  Modale.svelte — le fond, le rôle, `Échap` et le verrou de défilement, UNE fois.

  ## Pourquoi (#561, 28/08/2026)

  Le fond de modale était écrit **vingt-deux fois** dans **treize** fichiers. Le
  relevé de #561 les classait « rien à faire », au motif que *« la fermeture
  clavier est `Échap`, et le rôle est déjà posé »*.

  🔴 **C'était vrai de quatre fichiers sur treize.** Vérifié en comptant, pas en
  lisant : `admin` (5 modales), `mon-lot` (6), `residence` (7), `espace-cs`,
  `prestataires`, `delegations` et `ModaleOrdreService` **n'avaient aucune
  fermeture clavier**. Dix-neuf modales sur vingt-deux ne se fermaient qu'à la
  souris — l'avertissement n'était donc pas un faux positif pour elles.

  C'est `standards/04` §3 : *vérifier le fait, pas le symptôme attendu*. Le ticket
  avait raison sur le principe et tort sur le compte, et suivre son classement
  aurait laissé dix-neuf défauts derrière une case cochée.

  ## Ce que ce composant porte, et que chaque copie devait retenir

  | | |
  |---|---|
  | `role="dialog"` + `aria-modal` + `aria-label` | 22 fois, dont plusieurs sans `aria-label` |
  | **`Échap` ferme** | 4 fois sur 13 |
  | fermeture au clic sur le FOND seul (`\|self`) | oui, mais désactivable — voir plus bas |
  | **verrou de défilement** | épars, et c'est le plus piégeux |

  ⚠️ **Le verrou de défilement est un état GLOBAL** (`standards/11` §12). Il se
  pose sur `<body>`, donc une modale qui oublie de le rendre fige la page entière
  jusqu'au rechargement — y compris si l'utilisateur navigue ailleurs sans fermer.
  C'est l'incident du 04/08/2026. Il est donc rendu depuis `onDestroy` **et** à
  chaque sortie, et la fonction est idempotente.

  ⚠️ **Un COMPTEUR, pas un booléen.** Deux modales peuvent se superposer (une
  confirmation par-dessus un formulaire) : la première qui se ferme rendrait le
  défilement alors que la seconde est encore là. Le compteur est le seul moyen de
  ne le rendre qu'à la dernière.

  ## `fermetureAuFond` — pourquoi c'est une option et pas un défaut

  `OngletPerimetres` la refuse explicitement : *« on saisit ici un libellé et une
  description, et un clic à côté effaçait tout sans prévenir »*. Un formulaire
  long ne se ferme pas au clic ; une confirmation, si. C'est une décision d'écran,
  pas une valeur par défaut à imposer.

  ## L'EN-TÊTE aussi — le titre s'écrivait DEUX fois (29/08/2026)

  Le composant recevait `titre` pour l'`aria-label`, et chaque écran réécrivait
  ensuite le titre visible dans son balisage. Deux écritures pour un seul objet,
  donc deux textes libres de diverger — et **onze des vingt-six** avaient
  divergé : ce qu'un lecteur d'écran annonçait n'était pas ce que l'écran
  affichait. « Règle » pour *Modifier la règle*, « Modifier locataire » pour
  *Modifier les informations*, « Valider le compte » pour *Valider le compte de
  Jean Dupont*. Aucune n'est une décision.

  C'est le défaut que `lint:titres` refuse déjà pour `SectionFormulaire` — *le
  nom écrit deux fois* — appliqué aux modales, où rien ne le regardait.

  Le titre affiché **est** la prop : il ne peut plus diverger de ce qui est
  annoncé. Un titre riche (une interpolation, un `<code>`) passe par le slot
  nommé `titre`, la prop restant le texte pour le lecteur d'écran.

  ## Ce que l'en-tête retire aux écrans

  | | Avant | Après |
  |---|---|---|
  | `.modal-header` + croix, recopiés | 15 fois | 0 |
  | `<h2 style="font-size:1rem;font-weight:700;…">` en ligne | 8 fois, 2 marges | 0 |
  | `.modal-header h3` redéfini localement | 3 fichiers, à l'identique | 0 |
  | niveaux de titre | `h2` **et** `h3` | `h2` |
  | modales sans bouton de fermeture | 11 sur 26 | 0 |

  ⚠️ **Les deux boîtes gardent leur mise en page**, et c'est structurel : `.modal`
  porte son padding dans l'en-tête et le corps, `.modal-box` le porte sur la
  boîte. L'en-tête s'y adapte par UNE règle CSS (`.modal-box > .modal-header`),
  pas par une seconde écriture dans les écrans.

  Usage :

      <Modale titre="Ajouter un plan" on:fermer={() => (showPlanForm = false)}>
        … contenu …
      </Modale>

      <Modale titre="Modifier le périmètre" classeBoite="modal-box">
        <span slot="titre">{edite.libelle}</span>
        … contenu …
      </Modale>
-->
<script lang="ts">
	import { afterUpdate, createEventDispatcher, onDestroy } from 'svelte';
	import { poserCouche } from '#lib/couche.ts';

	/**
	 * Le titre de la boîte — **affiché ET annoncé**. Obligatoire : sans lui, un
	 * lecteur d'écran ne dit que « dialogue ».
	 *
	 * ⚠️ Ne PAS réécrire ce titre dans le contenu : c'est ce qui produisait les
	 * onze divergences. Pour un rendu riche, utiliser le slot `titre` — la prop
	 * reste alors le texte annoncé.
	 */
	export let titre: string;
	/** Classes de la boîte — `modal`, `modal-box`, `modal-sm`… selon l'écran. */
	export let classeBoite = 'modal';
	/** Style de la boîte, pour une largeur propre à l'écran. */
	export let styleBoite = '';
	/**
	 * Fermer au clic sur le FOND. À mettre à `false` sur un formulaire long :
	 * un clic à côté effacerait une saisie sans prévenir.
	 */
	export let fermetureAuFond = true;

	/**
	 * Cette modale porte un formulaire d'**ÉDITION** — le geste que
	 * `ux-patterns` §14 bis autorise en modale depuis le 30/08/2026 :
	 *
	 * > créer → la boîte dans la page · éditer → la modale
	 *
	 * ⚠️ **Une déclaration, pas une commodité.** `lint:formulaires` refuse toute
	 * `<Modale>` contenant un `<form>` qui ne la porte pas — c'est-à-dire toute
	 * modale de CRÉATION, le paradigme que #367 a supprimé après trois
	 * signalements. Sans cette distinction, la règle redeviendrait « au cas par
	 * cas », et les trois paradigmes reviendraient avec elle.
	 *
	 * 🔴 Elle existe aussi parce que rien dans le balisage ne dit si l'on crée ou
	 * si l'on corrige. Le contrôle ne peut pas le deviner ; celui qui écrit
	 * l'écran, si. C'est R4 appliqué à un geste : *la divergence se déclare.*
	 *
	 * ⚠️ **Elle n'est PAS décorative** : elle implique `fermetureAuFond={false}`.
	 * Une modale d'édition contient une saisie, et un clic à côté ne doit pas
	 * l'effacer sans prévenir — c'est la décision qu'`OngletPerimetres` avait
	 * prise seul (*« on saisit ici un libellé et une description »*), et qui
	 * devient générale. Le geste la porte, l'écran n'a plus à y penser.
	 *
	 * `svelte-check` l'a exigé, et il avait raison : une prop qu'aucun rendu ne
	 * lit est une prop que rien ne relie au comportement — elle aurait pu être
	 * mal orthographiée dans un appel sans que rien ne le dise.
	 */
	export let edition = false;

	/**
	 * La boîte contient-elle un champ de saisie ? Mesuré sur le DOM rendu.
	 *
	 * 🔴 POURQUOI LE COMPOSANT LE DÉCIDE, ET NON L'ÉCRAN (30/08/2026, #640).
	 *
	 * `fermetureAuFond` et `edition` existaient tous deux pour protéger une
	 * saisie d'un clic à côté. Les deux sont des **déclarations** — il faut y
	 * penser. Relevé sur l'écran d'administration : **trois** modales portant
	 * respectivement 8, 3 et 2 champs de saisie, et **aucune des trois** ne
	 * l'avait posée. Un clic à côté effaçait la saisie, sans confirmation ni
	 * moyen de la retrouver.
	 *
	 * Trois sur trois, ce n'est pas de l'inattention : c'est qu'une protection
	 * qui dépend d'un geste qu'on peut oublier ne protège que ceux qui y ont
	 * pensé. La même leçon que la prop `marge` d'`EntetePage` — *tant que le
	 * mécanisme d'exception existe, l'exception se reproduit*.
	 *
	 * Or ce n'est pas une décision d'écran : **c'est une propriété du contenu.**
	 * Une boîte qui contient une saisie ne se ferme pas au clic sur le fond, et
	 * le composant est le seul à pouvoir le savoir pour tout le monde à la fois.
	 *
	 * ⚠️ Mesuré `afterUpdate` et non au seul montage : le contenu d'une modale
	 * est souvent conditionnel (un champ qui n'apparaît qu'une fois une option
	 * choisie). Une mesure unique au montage manquerait exactement ces cas-là,
	 * et se tromperait dans le sens dangereux.
	 *
	 * La garde `!==` est nécessaire, pas décorative : `afterUpdate` qui écrit un
	 * état déclenche un rendu, donc `afterUpdate` à nouveau. Sans elle, la
	 * boucle ne converge pas.
	 */
	let boite: HTMLElement | undefined;
	let contientSaisie = false;
	afterUpdate(() => {
		const trouve = !!boite?.querySelector('input, textarea, select');
		if (trouve !== contientSaisie) contientSaisie = trouve;
	});

	//  Le fond ne se clique ni sur une édition (déclarée), ni sur une saisie
	//  (constatée). `fermetureAuFond={false}` reste utile pour une modale sans
	//  champ qu'on veut néanmoins protéger d'un clic distrait.
	$: fondFermant = fermetureAuFond && !edition && !contientSaisie;

	const dispatch = createEventDispatcher<{ fermer: void }>();

	function fermer() {
		retirerCouche();
		dispatch('fermer');
	}

	//  Défilement du fond et Échap : `#lib/couche.ts`, partagé avec la
	//  visionneuse — deux modales ou une photo ouverte depuis une modale, et
	//  seule la couche du dessus se ferme (#1042). Posée au montage : le
	//  composant n'existe que lorsque l'écran l'ouvre (`{#if}`).
	const retirerCouche = poserCouche(fermer);
	//  ⚠️ Retirée AUSSI au démontage : l'utilisateur peut naviguer ailleurs sans
	//  jamais fermer, et la page d'arrivée resterait figée.
	onDestroy(retirerCouche);
</script>

<div class="modal-overlay" role="presentation" on:click|self={() => fondFermant && fermer()}>
	<div
		bind:this={boite}
		class={classeBoite}
		style={styleBoite}
		role="dialog"
		aria-modal="true"
		aria-label={titre}
		tabindex="-1"
	>
		<div class="modal-header">
			<h2 class="modal-titre">
				{#if $$slots.titre}<slot name="titre" />{:else}{titre}{/if}
			</h2>
			<!--  ⚠️ `aria-label` et non le seul glyphe : « ✕ » se lit « multiplication »
			      chez plusieurs lecteurs d'écran. Onze modales n'avaient AUCUN bouton
			      de fermeture — dont les deux d'`OngletPerimetres`, qui refusent aussi
			      la fermeture au fond : elles ne se fermaient qu'à `Échap`, geste qui
			      n'existe pas au doigt. -->
			<button type="button" class="modal-close" aria-label="Fermer" on:click={fermer}>✕</button>
		</div>
		<slot {fermer} />
	</div>
</div>
