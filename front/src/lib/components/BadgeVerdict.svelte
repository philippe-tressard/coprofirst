<!--
  La capsule du VERDICT d'une question au règlement — dans l'onglet
  (`CarteQuestionReglement`) et au fil d'activité (`FluxCard`), depuis le
  11/10/2026 : écrite dans la carte seule, le fil l'aurait recopiée ou rendue
  dans le bleu par défaut.

  Le LIBELLÉ et le TON viennent du serveur (`format.VERDICTS`, `format.TONS_VERDICT`,
  #2505) : l'app iOS lit le même ton. Ce composant ne fait que le peindre à la
  charte du site — il ne décide plus quel verdict est un succès.

  La teinte se lit dans `BADGES_DU_VERDICT` (`#lib/reglement.ts`, publiée aux apps,
  #2773) et se pose par `Badge`, en `class:` — jamais en classe interpolée.
-->
<script lang="ts">
	import type { TonVerdict } from '#lib/api/reglement.ts';
	import Badge from '#lib/components/Badge.svelte';
	import { teinteDuVerdict } from '#lib/reglement.ts';

	/** Ce que le verdict signale — servi avec lui ; absent ou inconnu (le fil le
	 *  lit dans `meta`), il se lit incertain. */
	export let ton: TonVerdict | string | undefined;
	export let libelle: string;
</script>

<Badge teinte={teinteDuVerdict(ton)}>{libelle}</Badge>
