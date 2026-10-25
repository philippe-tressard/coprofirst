<!--
  Admin › Copropriété › Lots — **les clés de charges telles que le syndic les appelle** (#2252).

  L'acte dit le libellé, le dénominateur et les parts : ils ne se règlent pas ici, ils
  entrent par l'état descriptif. Le conseil ne règle que ce que l'acte ne dit pas :
  - « Appelée par le syndic » — décochée, la clé passe dans le bloc replié « Prévues au
    règlement, non appelées actuellement » de « Mes lots », avec sa part ;
  - « Sur l'appel de fonds » — le libellé de la même ligne chez le syndic, montré sous la clé.

  Chaque réglage s'enregistre à sa modification, comme un interrupteur d'Admin › Services.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { lotsAdmin, type CleDeChargesReglee } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { fmtNombre } from '$lib/utils';

	let cles: CleDeChargesReglee[] = [];
	let chargement = true;
	let erreur = '';
	let enCours: number | null = null;

	onMount(async () => {
		try {
			cles = await lotsAdmin.cles();
		} catch (e) {
			erreur = messageErreur(e, 'Impossible de lire les clés de charges');
		} finally {
			chargement = false;
		}
	});

	async function regler(cle: CleDeChargesReglee, champs: Partial<CleDeChargesReglee>) {
		enCours = cle.id;
		try {
			const reglee = await lotsAdmin.reglerCle(cle.id, champs);
			cles = cles.map((c) => (c.id === reglee.id ? reglee : c));
			toast('success', `« ${reglee.libelle} » enregistrée`);
		} catch (e) {
			toast('error', messageErreur(e));
			cles = [...cles];
		} finally {
			enCours = null;
		}
	}
</script>

<section class="card config-section">
	<h2 class="config-section-title"><Icon name="file-text" size={17} />Clés de charges</h2>
	<p class="config-section-intro muted">
		Ce que le règlement ne dit pas : si le syndic appelle la clé en ce moment, et son libellé sur
		l’appel de fonds. « Mes lots » s’aligne ainsi sur ce que le copropriétaire reçoit.
	</p>
	<EtatListe {chargement} {erreur} titreErreur="Impossible d’afficher les clés de charges">
		{#if cles.length === 0}
			<p class="muted">Aucune clé : elles entrent avec l’état descriptif (Admin › Imports).</p>
		{:else}
			<ul class="cles">
				{#each cles as c (c.id)}
					<li>
						<div class="cle">
							<strong>{c.libelle}</strong>
							<span class="muted">/{fmtNombre(c.denominateur)}</span>
							{#if c.description}<span class="description">{c.description}</span>{/if}
						</div>
						<label class="case">
							<input
								type="checkbox"
								checked={c.appelee}
								disabled={enCours === c.id}
								on:change={(e) => regler(c, { appelee: e.currentTarget.checked })}
							/>
							Appelée par le syndic
						</label>
						<div class="field">
							<label for="cle-syndic-{c.id}">Sur l’appel de fonds</label>
							<input
								id="cle-syndic-{c.id}"
								type="text"
								value={c.libelle_syndic ?? ''}
								placeholder="Libellé de la ligne chez le syndic"
								disabled={enCours === c.id}
								on:change={(e) => regler(c, { libelle_syndic: e.currentTarget.value })}
							/>
						</div>
					</li>
				{/each}
			</ul>
		{/if}
	</EtatListe>
</section>

<style>
	.cles {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.cles li {
		display: grid;
		grid-template-columns: minmax(0, 1.2fr) auto minmax(0, 1fr);
		gap: 0.5rem 1rem;
		align-items: center;
		padding: 0.6rem 0;
		border-bottom: 1px solid var(--color-border);
	}
	.description {
		display: block;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.cles .field {
		margin: 0;
	}
	@media (max-width: 767px) {
		.cles li {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
