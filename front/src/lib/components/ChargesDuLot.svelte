<!--
  **Les charges d'un lot, clé par clé** (#2215) — ce que le règlement lui fait payer, dit en
  clair : la clé, ce qu'elle finance, la part en dix-millièmes et en pourcentage.

  Les parts viennent du serveur (`MonLot.quotes_parts`) : l'écran les MONTRE, il ne les
  calcule pas. Un lecteur qui n'a pas à les voir ne reçoit aucune ligne : rien ne s'affiche,
  jamais un tableau vide qui laisserait croire à des charges nulles.

  Le même composant rend les parts d'UN lot et le total de plusieurs (`totauxParCle`) :
  même forme, pour que « ma part » se lise pareil partout.
-->
<script lang="ts">
	import { fmtNombre, fmtPartEnPourcent } from '$lib/utils';

	interface Ligne {
		cle: string;
		libelle: string;
		perimetre: string | null;
		numerateur: number;
		denominateur: number;
		/** Ce qui précise la ligne : « 38 lots y contribuent », « 2 de mes lots ». */
		precision?: string;
	}

	export let lignes: Ligne[];
	/** Le titre accessible du tableau — il n'a pas de légende visible. */
	export let titre = 'Mes charges, clé par clé';
</script>

{#if lignes.length}
	<div class="table-wrap">
		<table class="table charges-lot" aria-label={titre}>
			<thead>
				<tr>
					<th scope="col">Charges</th>
					<th scope="col" class="nombre">Ma part</th>
					<th scope="col" class="nombre">En %</th>
				</tr>
			</thead>
			<tbody>
				{#each lignes as l (l.cle)}
					<tr>
						<th scope="row">
							{l.libelle}
							{#if l.perimetre || l.precision}
								<span class="precision">
									{[l.perimetre, l.precision].filter(Boolean).join(' · ')}
								</span>
							{/if}
						</th>
						<td class="nombre">{fmtNombre(l.numerateur)}/{fmtNombre(l.denominateur)}</td>
						<td class="nombre">{fmtPartEnPourcent(l.numerateur, l.denominateur)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<style>
	/*  La cellule d'en-tête de ligne reprend l'allure d'une cellule : le nom de la clé n'est
	    pas un titre de colonne, c'est une donnée — avec sa précision dessous. */
	.charges-lot tbody th {
		text-align: left;
		text-transform: none;
		background: transparent;
		color: var(--color-text);
		font-weight: 500;
		font-size: var(--fs-base);
	}
	.precision {
		display: block;
		font-weight: 400;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
</style>
