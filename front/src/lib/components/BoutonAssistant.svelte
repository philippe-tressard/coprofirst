<!--
  BoutonAssistant.svelte — l'icône ✨ qui ouvre l'assistant, dans la barre de
  l'éditeur.

  ## Pourquoi il existe (22/09/2026, demandé à l'écran)

  > « l'icône IA et le prompt de modulation ne peut pas être dans la boîte
  >   description sur la ligne d'icône Gras Italique (cadré à droite) ? »

  Oui pour l'icône. **Non pour le prompt** : son champ fait 14 rem au minimum et
  ferait s'enrouler la barre sur deux lignes dès 375 px de large — l'inverse de
  l'effet recherché. Il descend donc dans le panneau, qui ne s'ouvre qu'au clic.

  Ce que ça retire : **deux lignes permanentes** sous l'éditeur, sur les six
  formulaires qui portent la section Description, pour un geste que l'on fait
  rarement.

  ## 🔴 Ce que l'icône NE dit pas, et que l'`aria-label` doit dire

  L'assistant retravaille **le titre ET la description** — `SectionDescription`
  lui prête le titre de l'objet par `bind:`. Une icône posée dans la barre de
  l'éditeur de description annoncerait un périmètre plus étroit que le sien :
  c'est le libellé qui rétablit la vérité, et c'est la seule raison pour
  laquelle il est aussi long.

  ⚠️ Il suit la taille des autres boutons de la barre, pas les 44 px de cible
  tactile. Ce n'est pas un oubli : toute la barre est à `min-width: 1.8rem`, et
  faire de celui-ci le seul bouton de 44 px au milieu de huit boutons de 29
  produirait un défaut visible pour corriger un défaut qui ne l'est pas. La
  barre entière se traite d'un coup, ou pas du tout (#1144).

  ⚠️ Pas de `.btn-icon` ici : ce bouton vit DANS `.editeur-barre`, dont les
  règles globales (fond, bordure, `.active`) l'habillent déjà comme ses voisins.
  Le dessin et l'attente — ✨, puis ⏳ qui clignote — sont ceux de TOUT geste
  qui lance l'assistant : `IconeIA` (17/10/2026). Ce bouton n'a plus de style
  à lui ; sa pulsation d'étincelle, la seule du produit, est partie.
-->
<script lang="ts">
	import IconeIA from '#lib/components/IconeIA.svelte';

	/** Le panneau est-il ouvert ? Porté par l'assistant, lu ici pour `aria-expanded`. */
	export let ouvert = false;
	/** L'`id` du panneau que ce bouton commande — la liaison ARIA l'exige. */
	export let commande: string;
	/** Vrai pendant l'appel : ✨ devient ⏳, pour que l'attente ne soit pas muette. */
	export let enCours = false;

	export let onBasculer: () => void;

	$: libelle = ouvert
		? 'Fermer l’assistant'
		: 'Retravailler le titre et la description avec l’assistant';
</script>

<button
	type="button"
	class:active={ouvert}
	aria-expanded={ouvert}
	aria-controls={commande}
	aria-label={libelle}
	aria-busy={enCours}
	title={libelle}
	on:click={onBasculer}
>
	<IconeIA {enCours} />
</button>
