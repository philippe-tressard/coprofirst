<script lang="ts">
	import { nomAffiche } from '$lib/noms';
	/**
	 * Pastille ronde d'identité : la photo de profil si elle existe, sinon les
	 * initiales, sinon une silhouette générique.
	 *
	 * Source unique — le même rendu servait déjà trois fois dans l'annuaire
	 * (membres du CS groupés par bâtiment, membres du CS à plat, contacts du
	 * syndic) avant d'être réclamé par l'en-tête du tableau de bord.
	 *
	 * Habillage : le composant ne décide que de la forme. La taille et le fond de
	 * repli se pilotent depuis le parent par variables CSS, qui
	 * cascadent jusqu'ici — `--avatar-size`, `--avatar-bg`, `--avatar-color`.
	 */
	import Icon from '$lib/components/Icon.svelte';

	export let photoUrl: string | null | undefined = null;
	export let prenom: string | null | undefined = '';
	export let nom: string | null | undefined = '';

	$: nomComplet = nomAffiche(prenom, nom);
	$: initiales = ((prenom?.[0] ?? '') + (nom?.[0] ?? '')).toUpperCase();
</script>

{#if photoUrl}
	<img class="avatar" src={photoUrl} alt={nomComplet} />
{:else if initiales}
	<div class="avatar" role="img" aria-label={nomComplet}>{initiales}</div>
{:else}
	<div class="avatar avatar-generique" role="img" aria-label="Utilisateur sans photo">
		<Icon name="user" size={20} />
	</div>
{/if}

<style>
	.avatar {
		width: var(--avatar-size, 2.5rem);
		height: var(--avatar-size, 2.5rem);
		border-radius: 50%;
		background: var(--avatar-bg, var(--color-primary));
		color: var(--avatar-color, var(--color-surface));
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 700;
		font-size: calc(var(--avatar-size, 2.5rem) * 0.38);
		line-height: 1;
		flex-shrink: 0;
		overflow: hidden;
	}
	img.avatar {
		object-fit: cover;
		background: none;
	}
	.avatar-generique :global(svg) {
		width: 55%;
		height: 55%;
	}
</style>
