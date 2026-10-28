<!--
  Ajouter un INVITÉ au Qui d'un point CS / Syndic (#2041, arbitré le 17/10/2026).

  Tous les champs sont facultatifs. L'invité figure au compte rendu, coordonnées
  comprises — pour le rappeler si un complément est nécessaire — et ne reçoit ni
  le CR ni la demande de validation : la phrase d'aide le dit, parce qu'une
  adresse saisie laisse croire qu'on écrira.

  Il s'ouvre sous la rangée du Qui, là où est le geste ; il vit DANS le
  formulaire du point, donc sans `<form>` à lui (`PiedFormulaire soumission={false}`).
-->
<script lang="ts">
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import type { PresentEntree } from '#lib/api/index.ts';

	export let idPrefixe: string;
	export let onAjoute: (invite: PresentEntree) => void;
	export let onAnnule: () => void;

	const CHAMPS = [
		{ cle: 'prenom', libelle: 'Prénom', type: 'text', exemple: 'Paul' },
		{ cle: 'nom', libelle: 'Nom', type: 'text', exemple: 'Leroy' },
		{ cle: 'fonction', libelle: 'Fonction', type: 'text', exemple: 'Chef de chantier' },
		{ cle: 'entreprise', libelle: 'Entreprise', type: 'text', exemple: 'Étanchéité Sud' },
		{ cle: 'telephone', libelle: 'Téléphone', type: 'tel', exemple: '06 12 34 56 78' },
		{ cle: 'email', libelle: 'Courriel', type: 'email', exemple: 'p.leroy@exemple.fr' },
	] as const;
	type Cle = (typeof CHAMPS)[number]['cle'];

	let valeurs: Record<Cle, string> = {
		prenom: '',
		nom: '',
		entreprise: '',
		fonction: '',
		telephone: '',
		email: '',
	};
	$: vide = Object.values(valeurs).every((v) => !v.trim());

	function ajouter() {
		if (vide) return;
		const invite: PresentEntree = { nature: 'invite' };
		for (const { cle } of CHAMPS) invite[cle] = valeurs[cle].trim() || null;
		onAjoute(invite);
	}
</script>

<div class="invite" role="group" aria-label="Ajouter un invité">
	<div class="grille">
		{#each CHAMPS as c (c.cle)}
			<div class="field champ-en-ligne">
				<label for="{idPrefixe}-invite-{c.cle}">{c.libelle}</label>
				<input
					id="{idPrefixe}-invite-{c.cle}"
					type={c.type}
					placeholder={c.exemple}
					autocomplete="off"
					maxlength={c.cle === 'telephone' ? 40 : 120}
					bind:value={valeurs[c.cle]}
				/>
			</div>
		{/each}
	</div>
	<p class="aide">
		Tout est facultatif. L’invité figure au compte rendu ; il ne reçoit ni le compte rendu ni la
		demande de validation.
	</p>
	<PiedFormulaire
		petit
		soumission={false}
		desactive={vide}
		on:annule={onAnnule}
		on:enregistre={ajouter}
	/>
</div>

<style>
	.invite {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		margin-top: 0.25rem;
		padding: 0.75rem;
		border: 1px solid var(--color-primary);
		border-radius: var(--radius);
		background: var(--color-primary-light);
	}
	/*  Trois colonnes, deux rangées : Prénom · Nom · Fonction, puis Entreprise ·
	    Téléphone · Courriel — le courriel n'est plus seul sur sa ligne. Au
	    téléphone, deux colonnes : trois rangées pleines. */
	.grille {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.6rem 0.75rem;
	}
	@media (max-width: 767px) {
		.grille {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
