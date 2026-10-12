<!--
  La capsule du VERDICT d'une question au règlement — dans l'onglet
  (`CarteQuestionReglement`) et au fil d'activité (`FluxCard`), depuis le
  11/10/2026 : écrite dans la carte seule, le fil l'aurait recopiée ou rendue
  dans le bleu par défaut.

  La teinte s'écrit en `class:`, jamais en classe interpolée : une interpolation
  rendrait le fichier aveugle à `lint:css-orphelin`, dont le plafond ne monte
  pas pour cela. Le LIBELLÉ vient du serveur (`format.VERDICTS`).
-->
<script lang="ts">
	/** Le code du verdict : `oui`, `non`, `sous_conditions`, `non_prevu`, `incertain`. */
	export let verdict: string | undefined;
	export let libelle: string;
</script>

<span
	class="badge"
	class:badge-green={verdict === 'oui'}
	class:badge-red={verdict === 'non'}
	class:badge-orange={verdict === 'sous_conditions'}
	class:badge-gray={verdict === 'non_prevu'}
	class:badge-yellow={verdict !== 'oui' &&
		verdict !== 'non' &&
		verdict !== 'sous_conditions' &&
		verdict !== 'non_prevu'}>{libelle}</span
>
