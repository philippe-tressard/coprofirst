<!--
  Une liste de constats de `check-reliability.sh` — « [FAIL] … » ou « [WARN] … » —,
  chacun avec son badge de niveau.

  Rendue sous chaque nœud ET sous « Les deux nœuds » (#1396) : c'est le même objet,
  il s'écrit une fois.
-->
<script lang="ts">
	export let constats: string[] = [];

	//  « [WARN] Disque rpi1 à 81 % » → le niveau et le texte. Le préfixe est celui
	//  que `check-reliability.sh` écrit (`warn()`, `fail()`) ; un constat sans
	//  préfixe reste lisible, en vigilance.
	function lire(constat: string): { niveau: 'fail' | 'warn'; texte: string } {
		const m = /^\[(FAIL|WARN)\]\s*/.exec(constat);
		return {
			niveau: m?.[1] === 'FAIL' ? 'fail' : 'warn',
			texte: m ? constat.slice(m[0].length) : constat,
		};
	}

	$: lus = constats.map(lire);
</script>

{#if lus.length}
	<ul class="constats">
		{#each lus as c, i (i)}
			<li>
				<span
					class="badge"
					class:badge-red={c.niveau === 'fail'}
					class:badge-orange={c.niveau === 'warn'}
				>
					{c.niveau === 'fail' ? 'Échec' : 'Vigilance'}
				</span>
				<span>{c.texte}</span>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.constats {
		margin: 0.6rem 0 0;
		padding: 0;
		list-style: none;
		font-size: var(--fs-md);
	}
	/*  Le badge ne rétrécit pas : c'est le texte, souvent long, qui passe à la ligne. */
	.constats li {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		margin-bottom: 0.45rem;
		overflow-wrap: anywhere;
	}
	.constats .badge {
		flex-shrink: 0;
	}
</style>
