<!--
  LibelleGroupe.svelte — nommer un GROUPE de contrôles, une fois pour toutes.

  ## Pourquoi (#561, 28/08/2026)

  Un `<label>` ne sait nommer QU'UN contrôle. Posé devant un groupe — des
  pastilles, des cases à cocher, deux champs sous un même intitulé — il n'associe
  rien, **et il le fait en silence** : un lecteur d'écran n'annonce rien en
  entrant dans le groupe. Quinze écrans étaient dans ce cas.

  Le remède tient en trois éléments qui doivent s'accorder — un titre, un `id`,
  et un `aria-labelledby` qui les relie. Recopiés sept fois, ils se seraient
  désaccordés au premier renommage : c'est le motif même de la duplication, où
  chaque copie est correcte et l'ensemble faux.

  ⚠️ **Ce composant ne sert PAS aux contrôles labelables.** Un `<input>`, un
  `<select>`, un `<textarea>` se nomment par `<label for>` — c'est plus simple et
  mieux supporté. Le forcer ici les priverait de l'association native.

  Pour un éditeur riche, employer sa prop `ariaLabelledby` avec un
  `<span class="libelle-groupe" id="…">` : `RichEditor` la porte déjà.

  Garde-fou : `npm run lint:libelles`.

  Usage :

      <LibelleGroupe titre="Périmètre" requis vide={!perimetre.length} id="crag-perimetre" classe="perimetre-pills">
        <Pastille active={…}>…</Pastille>
        <Pastille active={…}>…</Pastille>
      </LibelleGroupe>
-->
<script lang="ts">
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';

	/**  L'intitulé affiché — SANS astérisque : le requis passe par `requis`.
	 *
	 *   ⚠️ Cette ligne disait le contraire jusqu'au 27/09/2026 (« le `*` du requis
	 *   s'écrit dedans »), cinq jours après que l'étoile est devenue un ÉTAT —
	 *   collée et rouge tant que le groupe est vide (#1121). Les deux appelants qui
	 *   la suivaient affichaient une étoile noire, à jamais (#1329). */
	export let titre: string;
	/** Le groupe est obligatoire : l'étoile `EtoileRequis` suit le titre. */
	export let requis = false;
	/** …et rien n'y est encore choisi : l'étoile est rouge. */
	export let vide = false;
	/** Racine des identifiants — le titre porte `<id>-titre`. Doit être unique. */
	export let id: string;
	/**  Classes du conteneur, quand le groupe a une mise en page à lui.
	 *
	 *  🔴 **Le style de cette classe doit être écrit en `:global()` IMBRIQUÉ chez
	 *  l'appelant** — jamais à plat. Le `<div>` ci-dessous appartient à CE fichier :
	 *  il reçoit le scope de `LibelleGroupe`, pas celui de qui passe la classe. Une
	 *  règle `.ma-classe { … }` écrite chez l'appelant est compilée en
	 *  `.ma-classe.svelte-<hash-appelant>` et ne correspond à rien.
	 *
	 *  ⚠️ Ce n'est pas théorique : les **deux** appelants du site étaient dans ce
	 *  cas au 01/09/2026, et leur mise en page était morte depuis toujours — la
	 *  liste de lots d'un bail sans bordure ni colonne, les deux champs du
	 *  copropriétaire aidé empilés au lieu d'être côte à côte. Rien ne levait :
	 *  `svelte-check` ne signale « sélecteur inutilisé » que si le fichier n'a
	 *  aucun autre usage de la classe, et les deux en avaient un ailleurs.
	 *
	 *  La forme juste : envelopper, et borner le `:global()` par l'enveloppe —
	 *  `.mon-enveloppe :global(.ma-classe) { … }`. Un `:global()` nu fuirait vers
	 *  tout le site, une route à la fois (mémoire `project_css_route_fuite_globale`).
	 *
	 *  🔒 `npm run lint:classe-relayee` refuse la forme à plat.
	 */
	export let classe = '';
	/** Style du conteneur. ⚠️ Une mise en page ponctuelle, jamais une recomposition. */
	export let style = '';
</script>

<span class="libelle-groupe" id="{id}-titre"
	>{titre}{#if requis}<EtoileRequis {vide} />{/if}</span
>
<div class={classe} role="group" aria-labelledby="{id}-titre" {style}><slot /></div>
