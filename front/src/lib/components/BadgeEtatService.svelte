<!--
  L'état d'un service de la copropriété, en pastille : Activé · Coupé · Activé,
  incomplet. Une seule écriture, pour l'onglet Services et pour la ligne d'état
  de chaque onglet de réglages (`EtatService`).

  La couleur se pose par `class:` — une classe interpolée rendrait le fichier non
  mesurable par `lint:css-orphelin`.
-->
<script lang="ts">
	import type { ServiceCopropriete } from '#lib/api/index.ts';

	export let etat: ServiceCopropriete['etat'];

	const LIBELLE_ETAT: Record<ServiceCopropriete['etat'], string> = {
		actif: 'Activé',
		coupe: 'Coupé',
		incomplet: 'Activé, incomplet',
	};
</script>

<span
	class="badge"
	class:badge-green={etat === 'actif'}
	class:badge-gray={etat === 'coupe'}
	class:badge-orange={etat === 'incomplet'}>{LIBELLE_ETAT[etat]}</span
>
