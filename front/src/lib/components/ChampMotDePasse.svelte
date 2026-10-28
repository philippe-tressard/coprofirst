<!--
  Champ de saisie d'un mot de passe : libellé, zone de saisie, bascule
  afficher/masquer intégrée à droite, jauge de robustesse et avertissement
  « Verr. Maj. » — l'exemplaire unique de ce geste.

  Pourquoi un composant. Le même balisage (`.input-eye` + `.eye-btn`) et les
  mêmes déclarations CSS étaient recopiés dans QUATRE fichiers : connexion,
  inscription, réinitialisation et profil. C'est la duplication que le rang 1
  interdit (`standards/02` §1-2), et c'est elle qui a produit la régression du
  14/08/2026 : en sortant le bloc du profil vers un composant, le balisage est
  parti et ses règles CSS sont restées derrière — l'œil est retombé sous le
  champ, sans qu'aucun test ni le type-check ne puissent le voir.

  Le remède structurel n'est pas de recopier les règles une cinquième fois,
  c'est de rendre la séparation impossible : ici, le balisage et ses styles
  vivent dans le même fichier et voyagent ensemble.
-->
<script lang="ts">
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	import Icon from './Icon.svelte';
	import PasswordStrength from './PasswordStrength.svelte';
	import { capsLockActif } from '#lib/utils.ts';

	/** Identifiant du champ — relie le libellé (`for`) et le message d'erreur. */
	export let id: string;
	/** Libellé affiché ; l'astérisque des champs requis est ajouté ici. */
	export let libelle: string;
	export let valeur = '';
	/**
	 * Jamais omis : c'est ce que lisent les gestionnaires de mots de passe pour
	 * proposer le bon enregistrement et pour offrir d'en générer un nouveau.
	 */
	export let autocomplete: 'current-password' | 'new-password' = 'current-password';
	export let requis = true;
	/** `null` = pas d'attribut `minlength` sur le champ. */
	export let longueurMini: number | null = null;
	/** Jauge de robustesse sous le champ — pour une saisie de NOUVEAU mot de passe. */
	export let robustesse = false;
	/** Avertissement « Verr. Maj. activée » sous le champ. */
	export let verrouMaj = true;
	/** Message de validation affiché sous le champ ; chaîne vide = pas d'erreur. */
	export let erreur = '';

	let visible = false;
	let verrouMajDetecte = false;

	function surFrappe(e: KeyboardEvent | FocusEvent) {
		// `null` au focus : l'état des touches n'y est pas connaissable.
		const etat = capsLockActif(e);
		if (etat !== null) verrouMajDetecte = etat;
	}

	// Inutile d'avertir quand le mot de passe est affiché : l'utilisateur le lit.
	$: alerteVerrouMaj = verrouMaj && verrouMajDetecte && !visible;
	$: libelleBascule = visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe';
</script>

<div class="field">
	<label for={id}
		>{libelle}{#if requis}<EtoileRequis vide={!valeur} />{/if}</label
	>
	<div class="saisie">
		<input
			{id}
			type={visible ? 'text' : 'password'}
			bind:value={valeur}
			required={requis}
			{autocomplete}
			minlength={longueurMini}
			aria-invalid={erreur ? 'true' : undefined}
			aria-describedby={erreur ? `${id}-erreur` : undefined}
			on:keydown={surFrappe}
			on:keyup={surFrappe}
			on:focus={surFrappe}
		/>
		<button
			type="button"
			class="oeil"
			on:click={() => (visible = !visible)}
			aria-label={libelleBascule}
			title={libelleBascule}
		>
			<Icon name={visible ? 'eye-off' : 'eye'} size={18} />
		</button>
	</div>

	{#if robustesse}
		<PasswordStrength password={valeur} />
	{/if}

	{#if erreur}
		<p class="message erreur" id="{id}-erreur" role="alert">{erreur}</p>
	{/if}

	{#if alerteVerrouMaj}
		<EncartAvertissement compact role="alert">
			⚠️ <strong>Verr. Maj. activée</strong> — votre mot de passe pourrait être incorrect.
		</EncartAvertissement>
	{/if}
</div>

<style>
	.saisie {
		position: relative;
		display: flex;
		align-items: center;
	}

	/* Dégage la place de l'œil : bouton de 44 px + une marge de confort. */
	.saisie input {
		flex: 1;
		padding-right: 3rem;
	}

	/* Cible tactile de 44 × 44 px (`standards/11` §10). Le bouton est plus haut
	   que le champ de quelques pixels : cela ne se voit pas — il n'a ni fond ni
	   bordure — mais cela se touche au pouce, ce qu'une icône de 18 px ne
	   permettait pas. */
	.oeil {
		position: absolute;
		right: 0;
		top: 50%;
		transform: translateY(-50%);
		width: 44px;
		height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: none;
		border: none;
		padding: 0;
		cursor: pointer;
		color: var(--color-text-muted);
		border-radius: var(--radius);
		transition: color var(--duree-geste);
	}
	@media (hover: hover) and (pointer: fine) {
		.oeil:hover {
			color: var(--color-text);
		}
	}
	/* Le survol ne suffit pas : au doigt comme au clavier, il n'existe pas. */
	.oeil:focus-visible {
		color: var(--color-text);
		outline: 2px solid var(--color-primary);
		outline-offset: -2px;
	}

	.message {
		margin-top: 0.4rem;
		font-size: var(--fs-sm);
		line-height: 1.4;
	}
	.erreur {
		color: var(--color-danger);
	}
</style>
