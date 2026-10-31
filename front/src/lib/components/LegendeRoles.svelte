<!--
  Ce que veulent dire Admin et Opérateur, au-dessus de la liste des comptes : l'un
  gère la copropriété, l'autre supervise l'instance. La règle et les trois niveaux :
  `#lib/portee`.
-->
<script lang="ts">
	import { configStore, siteNomStore } from '#lib/stores/pageConfig.ts';
	import { CLE_OPERATEUR_PAR_EXPLOITANT } from '#lib/portee.ts';
	import { libelleRole } from '#lib/roles.ts';

	$: parExploitant = $configStore[CLE_OPERATEUR_PAR_EXPLOITANT] === '1';
</script>

<dl class="legende-roles aide">
	<div>
		<dt>{libelleRole('admin')}</dt>
		<dd>gère {$siteNomStore} : ses comptes, ses réglages, ses données.</dd>
	</div>
	<div>
		<dt>{libelleRole('operateur')}</dt>
		<dd>
			supervise l’instance — santé, tâches planifiées, base, inscription — sans lire les données des
			résidents.{parExploitant
				? ' Sur cette instance commune, l’exploitant du serveur le désigne.'
				: ''}
		</dd>
	</div>
</dl>

<style>
	.legende-roles {
		display: grid;
		gap: 0.2rem;
		margin: 0 0 0.75rem;
	}
	.legende-roles div {
		display: flex;
		gap: 0.35rem;
	}
	.legende-roles dt {
		font-weight: 600;
	}
	.legende-roles dd {
		margin: 0;
	}
</style>
