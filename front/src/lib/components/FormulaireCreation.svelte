<!--
  Le cadre d'un formulaire de création ou de modification : la boîte, sa largeur,
  son titre. UNE seule écriture pour tout le site (#367).

  Avant, le produit offrait **trois paradigmes** pour la même intention — créer un
  objet :

    • une boîte dans la page       (actualités, sondages)
    • une modale                    (calendrier, prestataires — et deux largeurs)
    • une page dédiée               (nouveau ticket)

  Le paradigme retenu est **la boîte dans la page**, sur désignation de
  l'utilisateur : les actualités sont le modèle de référence. C'est aussi le seul
  qui n'escamote pas l'écran pendant la saisie, et celui que suivaient déjà les
  rubriques les plus utilisées.

  ⚠️ CE QUE CE COMPOSANT NE PORTE PAS, ET CE QUE L'APPELANT DOIT PORTER.

  🔴 Ce paragraphe disait l'inverse jusqu'au 29/08/2026 : « la commande
  d'annulation reste dans l'en-tête de page ». C'était la règle de #367, et elle
  a été REMPLACÉE le 18/08/2026 — « Annuler » est **à côté** d'« Enregistrer »,
  norme posée sur Tickets, constatée à l'écran, puis étendue. La consigne d'ici
  n'a pas suivi, et pendant onze jours elle a légitimé la divergence : quatre
  formulaires suivaient la nouvelle règle, les autres l'ancienne, et la page
  Prestataires en portait TROIS variantes à elle seule. Une consigne périmée est
  pire qu'absente.

  **Ce que l'appelant doit écrire**, dans un `<div class="form-actions">` :
  « Annuler » en `btn-outline` PUIS la soumission en `btn-primary`. L'ordre
  compte : la commande destructrice ne se met pas là où le pouce se pose, et un
  ordre qui change d'un écran à l'autre fait cliquer de travers par mémoire du
  geste. 🔒 Vérifié par `npm run lint:soumission` (contrôle C).

  Le composant, lui, ne pose aucun bouton : il ne connaît ni l'enregistrement ni
  ce qu'annuler veut dire pour l'écran qui l'emploie.
-->
<script lang="ts">
	import EncartDemo from './EncartDemo.svelte';
	import { onMount } from 'svelte';
	import { amenerEnVue } from '#lib/accordeon.ts';

	export let titre: string;
	/**  Le cadre visible — une carte blanche avec sa bordure.
	 *
	 *   `false` quand le formulaire s'ouvre DÉJÀ dans une carte : celle d'un
	 *   ticket, d'une actualité, d'un événement. Une carte dans une carte, c'est
	 *   deux bordures imbriquées pour un seul objet — signalé à l'écran (#425).
	 *
	 *   ⚠️ **Le TITRE suit le cadre** (corrigé le 18/08/2026, le soir même où il
	 *   avait été rendu systématique). Un formulaire encadré EST une carte : son
	 *   titre en est l'en-tête. Un formulaire qui s'ouvre dans la carte d'un objet
	 *   n'a pas à en poser un second — signalé à l'écran : « ce pseudo état
	 *   éloigne du titre ».
	 *
	 *   Le mode se lit alors sur **l'icône qui a ouvert le formulaire**, qui
	 *   s'inverse (`aria-pressed`, style dans `app.css`). C'est le bon endroit :
	 *   elle est déjà là, déjà regardée, et son inversion se lit sans être lue.
	 *   `titre` reste requis — il sert d'`aria-label` au formulaire, donc le mode
	 *   reste annoncé à qui ne voit pas l'icône. */
	export let encadre = true;

	/**  Le formulaire s'amène LUI-MÊME à l'écran quand il s'ouvre hors du champ
	 *   de vision.
	 *
	 *   🔴 Signalé à l'écran le 29/08/2026 : « le bouton Modifier ne marche pas…
	 *   ah non, je ne l'avais pas vu car tout en haut ». Le formulaire s'ouvrait
	 *   bien — en haut de la page, alors que le geste avait été fait sur une carte
	 *   plus bas. Rien ne bougeait sous les yeux : la commande semblait morte.
	 *
	 *   ⚠️ Le correctif vit ICI et non dans la page qui l'a révélé, parce que la
	 *   cause n'a rien de propre aux contrats : DOUZE écrans ouvrent leur
	 *   formulaire par ce composant, et le geste vient d'une liste dans presque
	 *   tous. Corriger `prestataires/+page.svelte` aurait laissé onze écrans avec
	 *   le même défaut — et la treizième ouverture l'aurait réintroduit.
	 *
	 *   ⚠️ On ne défile QUE si le formulaire n'est pas déjà visible. Un
	 *   formulaire qui s'ouvre sous les yeux (`encadre={false}`, dans la carte
	 *   d'un ticket) n'a pas à faire sauter la page : un défilement non demandé
	 *   sur un écran qui montrait déjà la bonne chose est lui-même un défaut.
	 *
	 *   ⚠️ Et `behavior: 'smooth'` est écarté quand l'utilisateur a demandé moins
	 *   d'animation (`prefers-reduced-motion`) — la destination est la même, seul
	 *   le trajet disparaît. */
	/**  Optionnel : ce qui identifie l'objet en cours d'édition.
	 *
	 *   Le montage ne couvre qu'un cas — le formulaire était fermé. Cliquer
	 *   « Modifier » sur une SECONDE carte alors que le formulaire est déjà
	 *   ouvert plus haut ne remonte rien, et le geste redevient muet. Les écrans
	 *   qui offrent ce geste depuis une liste passent donc l'identifiant : il
	 *   change, le formulaire se ramène à nouveau.
	 *
	 *   Ne pas le passer est légitime pour un formulaire qui ne s'ouvre que
	 *   depuis l'en-tête de page, ou DANS la carte de l'objet qu'on corrige — il
	 *   n'y a alors rien à distinguer, et rien à ramener : ce qu'on regarde est
	 *   déjà là. **Sans `cle`, ce composant ne défile jamais** (10/09/2026).
	 *
	 *   🔴 **Elle est OBLIGATOIRE dès que le formulaire est rendu loin du geste
	 *   qui l'ouvre** (10/09/2026). Signalé à l'écran sur les contrats : « le
	 *   formulaire d'édition apparaît en bas de page, donc invisible sur une
	 *   longue liste ». Le formulaire y était rendu 674 lignes sous celui de
	 *   création — « la même boîte » au sens du composant, pas de l'endroit.
	 *
	 *   L'audit qui a suivi a trouvé le même défaut sur l'édition d'un bail
	 *   (`mon-lot`, 240 lignes d'écart), que personne n'avait signalé.
	 *   `lint:geste-edition` refuse désormais un second rendu éloigné sans `cle`. */
	export let cle: unknown = undefined;

	let cadre: HTMLElement;
	let monte = false;

	//  ⚠️ `monte` garde ce bloc muet AVANT le montage : sans lui, la réactivité
	//  s'exécuterait une première fois côté serveur, où `cadre` n'existe pas.
	$: if (monte && cle !== undefined) ramener(cle);

	//  La règle — le HAUT dans la fenêtre, sous l'en-tête fixe — vit dans
	//  `#lib/accordeon` depuis que l'accordéon en a eu besoin (30/09/2026).
	function ramener(_cle: unknown) {
		amenerEnVue(cadre);
	}

	onMount(() => {
		//  🔴 On ne défile PAS au montage, et c'est tout le sujet du 10/09/2026 :
		//  « le contrat édité remonte en haut ».
		//
		//  Ce bloc appelait `ramener(cle)` — donc `ramener(undefined)` pour les
		//  formulaires qui n'en passent pas, c'est-à-dire tous ceux qui s'ouvrent
		//  SOUS LES YEUX de celui qui a cliqué. Un formulaire ouvert dans la carte
		//  d'un objet, en bas de la fenêtre, dépassait la bande visible de quelques
		//  pixels et se faisait ramener en haut de l'écran, emportant sa carte.
		//
		//  ⚠️ L'intention était DÉJÀ écrite, quelques lignes plus haut : « un
		//  formulaire qui s'ouvre sous les yeux n'a pas à faire sauter la page ».
		//  Le code ne testait que la position, jamais la RAISON d'être là — et la
		//  position seule ne distingue pas « ouvert loin du geste » de « ouvert un
		//  peu bas ».
		//
		//  Poser `monte` suffit : la réactivité ci-dessus rappelle `ramener` dans
		//  la foulée pour les seuls formulaires qui portent une `cle`, c'est-à-dire
		//  ceux qui s'ouvrent AILLEURS que là où l'on a cliqué. `cle` n'est donc
		//  plus seulement ce qui distingue deux objets : c'est ce qui DEMANDE le
		//  défilement.
		monte = true;
	});
</script>

<!--  `aria-label` porte le titre dans TOUS les cas : ce qui disparaît est le
      titre VISIBLE, pas l'information. Un lecteur d'écran continue d'annoncer
      « Modifier le commentaire » en entrant dans le formulaire. -->
<div
	class="formulaire-creation largeur-saisie"
	class:card={encadre}
	bind:this={cadre}
	role="group"
	aria-label={titre}
>
	{#if encadre}<h2>{titre}</h2>{/if}
	<EncartDemo saisie />
	<slot />
</div>

<style>
	.formulaire-creation {
		margin-bottom: 1.5rem;
		scroll-margin-top: 5rem;
	}
	.formulaire-creation h2 {
		font-size: var(--fs-xl);
		font-weight: 600;
		margin: 0 0 1rem;
	}
</style>
