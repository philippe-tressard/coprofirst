<!--
  La capsule du VERDICT d'une question au règlement — dans l'onglet
  (`CarteQuestionReglement`) et au fil d'activité (`FluxCard`), depuis le
  11/10/2026 : écrite dans la carte seule, le fil l'aurait recopiée ou rendue
  dans le bleu par défaut.

  Le LIBELLÉ et le TON viennent du serveur (`format.VERDICTS`, `format.TONS_VERDICT`,
  #2505) : l'app iOS lit le même ton. Ce composant ne fait que le peindre à la
  charte du site — il ne décide plus quel verdict est un succès.

  La teinte s'écrit en `class:`, jamais en classe interpolée : une interpolation
  rendrait le fichier aveugle à `lint:css-orphelin`, dont le plafond ne monte
  pas pour cela.
-->
<script lang="ts">
	import type { TonVerdict } from '#lib/api/reglement.ts';

	/** Ce que le verdict signale — servi avec lui ; absent ou inconnu (le fil le
	 *  lit dans `meta`), il se lit incertain. */
	export let ton: TonVerdict | string | undefined;
	export let libelle: string;
</script>

<span
	class="badge"
	class:badge-green={ton === 'succes'}
	class:badge-red={ton === 'danger'}
	class:badge-orange={ton === 'alerte'}
	class:badge-gray={ton === 'neutre'}
	class:badge-yellow={ton !== 'succes' && ton !== 'danger' && ton !== 'alerte' && ton !== 'neutre'}
	>{libelle}</span
>
