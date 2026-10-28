<!--
  Valider un compte en attente — la case « Nouvel Arrivant », ses deux champs, et
  le pied du formulaire.

  ## Pourquoi ce composant (12/09/2026, #889)

  Le bloc était écrit **DEUX FOIS**, dans `admin` et dans `espace-cs`, et les deux
  copies avaient divergé :

  * l'admin écrivait « demande d'ajout sur l'interphone **auprès du Conseil
    Syndical** », l'espace CS s'arrêtait à « l'interphone » ;
  * l'admin rangeait les deux champs dans un `.form-grid`, l'espace CS dans une
    grille à deux colonnes écrite en ligne — donc sans le passage à une colonne
    sur téléphone que la charte donne ;
  * l'admin soulignait la case cochée (`nouvel-arrivant-checked`), pas l'espace CS.

  Aucune de ces trois différences n'était voulue. C'est la forme canonique de la
  duplication : deux copies naissent identiques et dérivent là où personne ne les
  compare (`standards/02` §1 bis — la divergence est sur le CAS LIMITE).

  🔴 **La boîte s'ouvre DANS la carte**, à la place de son corps — l'arbitrage
  rendu le 11/09/2026 sur #889 : *« les gestes courts dans la carte »*. Valider un
  compte est un geste sur un objet de liste, au même titre que corriger.

  ⚠️ Ce composant ne fait AUCUN appel réseau. Le geste vit dans `#lib/comptes.ts`
  — un seul endroit qui sait quoi appeler, dans quel ordre, et quoi annoncer.
  L'écran garde ce qui lui est propre : d'où vient l'utilisateur, et ce qu'il
  advient de sa liste après.
-->
<script lang="ts">
	import type { User } from '#lib/api/index.ts';
	import PiedFormulaire from './PiedFormulaire.svelte';

	/** L'utilisateur dont on valide le compte. */
	export let utilisateur: User;
	/** Ce que l'écran sait de plus — « 3 lot(s) détecté(s) dans l'import ». */
	export let precision = '';
	export let enCours = false;

	export let nouvelArrivant = false;
	export let batiment = '';
	export let ancienResident = '';

	export let onAnnuler: () => void = () => {};
	export let onValider: () => void = () => {};

	$: void utilisateur;
</script>

{#if precision}
	<p class="vc-precision">{precision}</p>
{/if}

<!--  La case porte sa propre bordure : elle n'est pas un champ de plus, c'est un
      choix qui ouvre deux champs. Cochée, elle s'éclaire — sinon rien ne dit que
      la suite du formulaire vient d'elle. -->
<label class="vc-choix" class:vc-choix-actif={nouvelArrivant}>
	<input type="checkbox" bind:checked={nouvelArrivant} />
	<div>
		<strong>&#x1F3E0; Nouvel Arrivant</strong>
		<p>
			À cocher uniquement pour un <strong>nouveau résident</strong> qui emménage dans la
			copropriété. Déclenche automatiquement : message de bienvenue, envoi des consignes de
			copropriété, demande d'étiquette de boîte aux lettres auprès du syndic, et demande d'ajout sur
			l'interphone auprès du Conseil Syndical.
			<em>Ne pas cocher pour un résident existant qui crée simplement son compte.</em>
		</p>
	</div>
</label>

{#if nouvelArrivant}
	<div class="form-grid">
		<label class="field">
			Bâtiment / logement
			<input bind:value={batiment} placeholder="Ex: Bât. A, Apt. 12…" />
		</label>
		<label class="field">
			Ancien résident
			<input bind:value={ancienResident} placeholder="Nom de l'ancien occupant…" />
		</label>
	</div>
{/if}

<!--  ⚠️ Aucun `libelle` : le verbe de soumission est GÉNÉRIQUE partout (#396).
      Les deux fenêtres disaient « ✓ Valider le compte » ; le titre de la carte
      dit déjà de quel compte il s'agit, et `lint:pied-formulaire` refuse — à
      raison : sept formulaires portaient six libellés différents, aucun faux,
      l'ensemble sans logique.

      `PiedFormulaire` émet `enregistre`, pas `soumettre` — le nom vient du
      composant, pas d'ici : l'inventer aurait donné un bouton inerte, sans
      erreur ni avertissement. -->
<!--  🔴 `soumission={false}` — SANS quoi le bouton est INERTE (#1132).
      `PiedFormulaire` rend un `<button type="submit">` par défaut : il ne
      déclenche rien par lui-même, il compte sur le `on:submit` d'un
      `<form>` parent. Il n'y en a pas ici, et le clic ne faisait donc RIEN —
      ni erreur, ni message. Signalé à l'écran, bloquant : plus aucun compte
      ne pouvait être validé, ni depuis l'Espace CS, ni depuis l'admin. -->
<PiedFormulaire {enCours} soumission={false} on:annule={onAnnuler} on:enregistre={onValider} />

<style>
	.vc-precision {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0 0 1rem;
	}
	/*  ⚠️ Ces règles vivaient en LIGNE dans les deux pages (`style="display:flex;
	    align-items:flex-start;…"`), ce qui est précisément ce qui a permis à
	    l'une de gagner l'état « coché » sans l'autre. Elles voyagent désormais
	    avec le balisage. */
	.vc-choix {
		display: flex;
		align-items: flex-start;
		gap: 0.6rem;
		cursor: pointer;
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.75rem;
		margin-bottom: 0.75rem;
	}
	.vc-choix-actif {
		border-color: var(--color-primary);
		background: var(--color-primary-light);
	}
	.vc-choix input {
		margin-top: 0.2rem;
		flex-shrink: 0;
	}
	.vc-choix strong {
		font-size: var(--fs-base);
	}
	.vc-choix p {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0.25rem 0 0;
	}
	.form-grid {
		margin-bottom: 0.75rem;
	}
</style>
