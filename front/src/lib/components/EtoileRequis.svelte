<!--
  L'astérisque des champs obligatoires — **un objet, pas un caractère**.

  ## La règle (22/09/2026, demandée à l'écran)

  > « Dans tous les champs obligatoires (y compris le panel de login) : ils sont
  >   post-fixés par une étoile (sans espace) : cette étoile est en rouge quand
  >   le champ est vide ; elle devient en couleur par défaut (noir) quand le
  >   champ est initialisé. »

  Trois choses, donc, et la deuxième est la seule qui compte vraiment :

  1. l'astérisque est **collée** au libellé — `TITRE*`, pas `Titre *` ;
  2. elle est **rouge tant que le champ est vide**, et reprend la couleur du
     libellé dès qu'il porte une valeur ;
  3. elle cesse ainsi d'être une décoration : c'est l'**état** du champ, lisible
     d'un coup d'œil sur un long formulaire.

  ## Pourquoi un composant pour un caractère (#1121)

  Parce qu'un caractère ne sait pas si le champ est vide. L'astérisque était
  écrite **trente-cinq fois** — vingt-cinq `<label>Titre *</label>` en clair et
  cinq composants qui calculaient `{requis ? ' *' : ''}` —, et aucun de ces
  points ne connaissait la valeur du champ. C'est ce qu'il fallait leur
  apporter, et un `*` de plus dans une chaîne ne l'aurait pas fait.

  🔒 `lint:champs` refuse désormais l'astérisque écrite à la main.

  ## Accessibilité

  La couleur ne se lit pas au lecteur d'écran, et le rouge seul ne suffit jamais
  (`standards/11` §2) : le mot « obligatoire » est rendu comme texte de
  rechange. Le `*` lui-même est décoratif à ce moment-là, d'où `aria-hidden`
  sur le caractère et le mot porté par le conteneur.

  UTILISATION :
    <label for="titre">Titre<EtoileRequis vide={!titre.trim()} /></label>
-->
<script lang="ts">
	/**  Le champ est-il VIDE ? C'est la seule question posée.
	 *
	 *   ⚠️ L'appelant décide ce que « vide » veut dire pour lui : une chaîne
	 *   blanche, une liste sans entrée, une date absente. Le composant ne le
	 *   devine pas — il le rendrait faux pour la moitié des champs. */
	export let vide = false;
</script>

<!--  🔴 TOUT SUR UNE LIGNE, et ce n'est pas du style : un saut de ligne entre
      deux éléments est un NŒUD DE TEXTE BLANC, que le navigateur rend comme un
      espace. L'astérisque s'affichait donc « PÉRIMÈTRE * » alors que le code
      l'écrivait collée — signalé à l'écran le 22/09/2026, capture à l'appui.

      ⚠️ Et surtout PAS `inline-flex` pour s'en protéger : un conteneur flex
      ignore bien les nœuds blancs, mais il met chaque enfant sur sa propre
      ligne — le texte de rechange « obligatoire » se retrouvait alors annoncé
      comme un bloc. Mesuré par le test de navigateur, pas deviné. -->
<span class="requis" class:requis--vide={vide}>
	<span aria-hidden="true">*</span><span class="sr-only">obligatoire</span>
</span>

<style>
	/*  Collée au libellé : aucune marge à gauche, c'est la règle. */
	.requis {
		font-weight: 700;
	}
	/*  Rouge tant que le champ est vide ; la couleur du libellé sinon — donc
	    rien à écrire dans ce second cas, elle s'hérite. */
	.requis--vide {
		color: var(--color-danger);
	}
</style>
