<!--
  PersonnesMasquees.svelte — dans le Profil, les résidents dont on a masqué ce
  qu'ils publient, et le geste pour revenir sur ce choix (#2861).

  Le masque se pose depuis une publication (`#lib/masquages`) ; il se défait ici, et
  seulement ici : c'est l'endroit qu'annonce la confirmation du geste. La règle — ce
  qui se masque, qui ne se masque pas — vit au serveur (`utils/masquage`).

  Une liste qui peut être vide, en erreur ou en cours : `EtatListe`, jamais un
  « aucun » qui prendrait un échec pour une absence.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { masquages as masquagesApi, type Masquage } from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { fmtDate } from '#lib/date.ts';

	let masques: Masquage[] = [];
	let chargement = true;
	let erreur = '';

	onMount(async () => {
		[masques, erreur] = await essayer(masquagesApi.liste(), []);
		chargement = false;
	});

	async function demasquer(m: Masquage) {
		await tenter(async () => {
			await masquagesApi.demasquer(m.auteur_id);
			masques = masques.filter((x) => x.auteur_id !== m.auteur_id);
		}, `Vous voyez de nouveau ce que publie ${m.auteur}`);
	}
</script>

<section class="card carte-masquees">
	<h2 class="section-title">Personnes masquées</h2>
	<p class="aide">
		Vous ne voyez plus les annonces, les réponses ni les messages dans les affaires de ces
		personnes. Elles n’en sont pas averties, et rien n’est supprimé.
	</p>
	<EtatListe
		{chargement}
		{erreur}
		vide={masques.length === 0}
		titreVide="Personne n’est masqué"
		messageVide="Le geste « Masquer ce que publie… » se trouve sur une annonce, une réponse ou un message."
		compact
	>
		<ul class="liste-masquees">
			{#each masques as m (m.auteur_id)}
				<li>
					<span class="nom">{m.auteur}</span>
					<small class="aide">depuis le {fmtDate(m.cree_le)}</small>
					<button
						type="button"
						class="btn btn-sm btn-outline"
						on:click={() => demasquer(m)}
						aria-label="Ne plus masquer {m.auteur}"
						><IconeAction icone="eye" /> Ne plus masquer</button
					>
				</li>
			{/each}
		</ul>
	</EtatListe>
</section>

<style>
	/*  `.section-title`, `.aide`, `.btn` : la charte porte tout (composants.css). */
	.carte-masquees {
		margin-bottom: 1.5rem;
	}
	.liste-masquees {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
	}
	.liste-masquees li {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem 0.75rem;
		padding: 0.5rem 0;
		border-top: 1px solid var(--color-border);
	}
	.liste-masquees .nom {
		font-weight: 600;
	}
	.liste-masquees .btn {
		margin-left: auto;
	}
</style>
