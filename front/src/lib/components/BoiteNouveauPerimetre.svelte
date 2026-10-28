<!--
  **La boîte de création d'un périmètre** — champs et pied, écrits une fois.

  ## 🔴 Pourquoi (14/09/2026, #779)

  `OngletPerimetres` la rendait **deux fois** : une fois en tête de liste pour un
  périmètre de premier niveau, une fois dans un nœud pour un sous-périmètre. Les
  deux cadres diffèrent légitimement — titre, et `encadre={false}` pour ne pas
  poser une carte dans une carte — mais **leur contenu était identique**, y
  compris la condition qui active le bouton :

  ```
  desactive={!nouveau.libelle.trim() || !(nouveau.code || codePropose)}
  ```

  ⚠️ **C'est cette ligne-là qui rendait la copie dangereuse**, pas les six
  autres. Une règle de validation écrite deux fois diverge au premier
  assouplissement — et la moitié qu'on oublie est celle qui laisse passer un
  périmètre sans code. Les champs, eux, étaient déjà factorisés
  (`ChampsNouveauPerimetre`) : c'est ce qui rendait la duplication restante
  invisible à la lecture.

  ## Ce que les deux cadres gardent de différent

  Le **titre** et l'encadrement, parce qu'ils disent *où* le geste a lieu —
  « la boîte s'ouvre là où est le geste » (`ux-patterns` §14 ter). Ce n'est pas
  une variante de commodité : le `＋` d'un nœud ouvre DANS ce nœud, et une carte
  dans une carte serait le défaut de #425.
-->
<script lang="ts">
	import { createEventDispatcher, type ComponentProps } from 'svelte';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import ChampsNouveauPerimetre from '#lib/components/ChampsNouveauPerimetre.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';

	const dispatch = createEventDispatcher<{ annule: void; enregistre: void }>();

	/** Le titre de la boîte — il dit ce qu'on crée, et sous quoi. */
	export let titre: string;
	/** `false` dans un nœud : pas de carte imbriquée (#425). */
	export let encadre = true;
	/**  L'objet en cours de saisie, lié en deux sens : l'écran porte son cycle.
	 *
	 *   ⚠️ Le type vient de `ChampsNouveauPerimetre`, il n'est pas redéclaré ici :
	 *   une seconde écriture aurait divergé au premier champ ajouté — et c'est
	 *   exactement ce que `svelte-check` a refusé quand je l'ai tenté. */
	export let nouveau: ComponentProps<ChampsNouveauPerimetre>['nouveau'];
	/** Le code proposé d'après le libellé, quand l'utilisateur n'en saisit pas. */
	export let codePropose = '';
	export let enregistrement = false;
	/**  Un champ propre à l'appelant (le bâtiment d'une copie) reste à remplir :
	 *   il s'ajoute à la règle d'activation, il ne la remplace pas. */
	export let incomplet = false;
</script>

<FormulaireCreation {titre} {encadre}>
	<ChampsNouveauPerimetre bind:nouveau {codePropose} />
	<slot />
	<!--  🔴 La condition d'activation vit ICI, et nulle part ailleurs : un
	      périmètre a besoin d'un libellé ET d'un code, celui-ci pouvant être
	      proposé. Écrite deux fois, elle aurait fini par n'en exiger qu'un
	      des deux d'un côté. -->
	<PiedFormulaire
		enCours={enregistrement}
		desactive={incomplet || !nouveau.libelle.trim() || !(nouveau.code || codePropose)}
		soumission={false}
		on:annule={() => dispatch('annule')}
		on:enregistre={() => dispatch('enregistre')}
	/>
</FormulaireCreation>
