<!--
  Les trois champs d'un périmètre à CRÉER — libellé, code, description.

  Extraits le 10/09/2026 parce que la boîte de création s'ouvre désormais à DEUX
  endroits : sous la barre pour un périmètre de premier niveau, et DANS le nœud
  pour un sous-périmètre. Deux copies des mêmes champs auraient divergé au
  premier ajustement — et c'est le champ `code`, immuable après création, qui
  aurait divergé le plus mal.

  ⚠️ La CORRECTION, elle, passe par `ChampsPerimetre` : ses champs ne sont pas
  les mêmes (portée, icône, ordre, sélectionnable…) et le `code` n'y est plus
  modifiable. Deux jeux de champs pour deux gestes, c'est le cas prévu par le
  cadre (`ux-patterns` §0) — ce n'est pas une divergence à réduire.
-->
<script lang="ts">
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	export let nouveau: { code: string; libelle: string; description: string };
	export let codePropose = '';
</script>

<label class="field"
	><span>Libellé<EtoileRequis vide={!nouveau.libelle.trim()} /></span>
	<input bind:value={nouveau.libelle} required />
</label>
<label class="field"
	><span>Code<EtoileRequis vide={!nouveau.code.trim() && !codePropose} /></span>
	<input bind:value={nouveau.code} placeholder={codePropose} />
	<span class="aide">
		Laissé vide, il vaudra <code>{codePropose || '…'}</code>. Il ne pourra plus être modifié : c’est
		lui qui sera enregistré dans les contenus.
	</span>
</label>
<label class="field"
	>Description
	<textarea bind:value={nouveau.description} rows="3"></textarea>
</label>
