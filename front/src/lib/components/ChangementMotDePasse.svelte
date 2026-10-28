<!--
  Changer son mot de passe — extrait de `routes/(app)/profil/+page.svelte` le
  14/08/2026, au fil de l'eau : la page dépassait 800 lignes et le contrôle de
  modularité refuse qu'un fichier déjà au-dessus de 500 grossisse (rang 1 §4).

  C'est le bloc le plus autonome de cette page : trois champs, un appel, aucun
  état partagé avec le reste du profil. Il ne reçoit aucune prop — il n'a besoin
  de rien de son parent, et c'est précisément ce qui le rendait extractible.

  Depuis le 15/08/2026 (issue #344), la saisie elle-même — libellé, œil,
  robustesse, Verr. Maj. — appartient à `ChampMotDePasse.svelte`, partagé avec
  les trois écrans d'authentification. Il ne reste ici que ce qui est propre au
  profil : l'enchaînement des trois champs, la validation croisée et l'appel.
-->
<script lang="ts">
	import ChampMotDePasse from './ChampMotDePasse.svelte';
	import { auth as authApi } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from './Toast.svelte';

	let pwdActuel = '';
	let pwdNouv = '';
	let pwdConf = '';
	let savingPwd = false;

	/* La divergence entre les deux saisies est connue dès la frappe. L'annoncer
	   au clic, par un message d'erreur, faisait payer un aller-retour complet
	   pour une information déjà disponible — on ne signale qu'une fois la
	   confirmation entamée, pour ne pas crier sur un champ encore vide. */
	$: confirmationDivergente = pwdConf.length > 0 && pwdNouv !== pwdConf;

	/* Ce qui reste à faire, dit dans l'ordre où l'utilisateur remplit — un
	   bouton désactivé sans explication laisse chercher (`standards/11` §3). */
	$: aideAction =
		pwdActuel.length === 0
			? 'Saisissez d’abord votre mot de passe actuel.'
			: pwdNouv.length < 8
				? 'Le nouveau mot de passe doit faire 8 caractères au minimum.'
				: pwdNouv !== pwdConf
					? 'Les deux saisies du nouveau mot de passe doivent être identiques.'
					: '';
	$: formulaireValide = aideAction === '';

	async function changePassword() {
		// Garde conservée : la soumission reste atteignable à la touche Entrée.
		if (pwdNouv !== pwdConf) {
			toast('error', 'Les mots de passe ne correspondent pas');
			return;
		}
		savingPwd = true;
		try {
			await authApi.changePassword({
				mot_de_passe_actuel: pwdActuel,
				nouveau_mot_de_passe: pwdNouv,
			});
			pwdActuel = '';
			pwdNouv = '';
			pwdConf = '';
			toast('success', 'Mot de passe modifié');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			savingPwd = false;
		}
	}
</script>

<section class="card carte-mot-de-passe">
	<h2 class="section-title">Modifier le mot de passe</h2>
	<p class="section-aide">
		Il vous faut votre mot de passe actuel, puis le nouveau saisi deux fois.
	</p>

	<form on:submit|preventDefault={changePassword}>
		<ChampMotDePasse
			id="pwd-actuel"
			libelle="Mot de passe actuel"
			bind:valeur={pwdActuel}
			autocomplete="current-password"
		/>

		<!-- Les deux saisies du nouveau mot de passe forment un bloc : le liseré
		     dit qu'elles se répondent, plutôt que trois champs de même poids. -->
		<div class="bloc-nouveau">
			<ChampMotDePasse
				id="pwd-nouv"
				libelle="Nouveau mot de passe"
				bind:valeur={pwdNouv}
				autocomplete="new-password"
				longueurMini={8}
				robustesse
			/>
			<ChampMotDePasse
				id="pwd-conf"
				libelle="Confirmation"
				bind:valeur={pwdConf}
				autocomplete="new-password"
				longueurMini={8}
				erreur={confirmationDivergente ? 'Cette saisie diffère du nouveau mot de passe.' : ''}
			/>
		</div>

		<div class="form-actions">
			{#if aideAction && !savingPwd}
				<p class="aide">{aideAction}</p>
			{/if}
			<button
				type="submit"
				class="btn btn-primary"
				disabled={savingPwd || !formulaireValide}
				aria-busy={savingPwd}
			>
				{#if savingPwd}<span class="spinner" aria-hidden="true"></span>{/if}
				{savingPwd ? 'Modification…' : 'Modifier le mot de passe'}
			</button>
		</div>
	</form>
</section>

<style>
	/*  `.section-title` : la charte porte tout (composants.css). Retiree le 28/08/2026 (#607). */
	.section-aide {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin-bottom: 1rem;
		line-height: 1.4;
	}

	.bloc-nouveau {
		border-left: 3px solid var(--color-border);
		padding-left: 0.85rem;
		margin-bottom: 1rem;
	}
	/* Le dernier champ du bloc ne pousse pas : la marge est portée par le bloc. */
	.bloc-nouveau > :global(.field:last-child) {
		margin-bottom: 0;
	}

	/*  La charte porte l'alignement, l'ecart et la marge ; seuls
    `align-items` et `flex-wrap` sont propres a cette rangee (#607, 28/08/2026). */
	.form-actions {
		align-items: center;
	}
	/*  Seul le placement reste ici : l'aide partage sa ligne avec le bouton et le
	    pousse à droite. La typographie vient de la charte depuis le 09/09/2026 —
	    elle y était recopiée avec .8rem au lieu de .78, valeur que personne
	    n'avait choisie. */
	.aide {
		margin-right: auto;
	}

	/* Sur un téléphone, l'aide et le bouton s'empilent : le bouton prend toute
	   la largeur plutôt que de se tasser dans un coin (`standards/11` §10). */
	@media (max-width: 480px) {
		.form-actions {
			gap: 0.6rem;
		}
		.aide {
			margin-right: 0;
			width: 100%;
		}
		.form-actions .btn {
			width: 100%;
			justify-content: center;
		}
	}
	.carte-mot-de-passe {
		margin-bottom: 1.5rem;
	}
</style>
