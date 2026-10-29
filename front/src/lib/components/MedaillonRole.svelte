<!--
  **Le médaillon d'un rôle** — la pastille ronde posée au coin d'une carte de
  contact : gestionnaire du site, président du conseil syndical, gestionnaire
  principal d'un prestataire.

  ## 🔴 Pourquoi (14/09/2026, #779)

  Dans `annuaire/+page.svelte`, la même géométrie était écrite **deux fois** —
  une fois pour `.site-manager-icon, .president-icon`, une fois à l'identique pour
  `.star-principal-badge` — et le balisage des deux premières, **deux fois** lui
  aussi (une rangée groupée par bâtiment, une rangée à plat). Onze propriétés
  recopiées, dont seule la couleur de fond changeait.

  Trouvé par un relevé mécanique des blocs répétés : les copies étaient
  cohérentes entre elles, et rien ne les faisait relire ensemble.

  ## Ce que la factorisation a CORRIGÉ au passage

  ⚠️ Le ★ « Gestionnaire principal » portait un `title` et **aucun
  `aria-label`** : un lecteur d'écran annonçait une étoile sans dire ce qu'elle
  signifie. Les deux autres médaillons en avaient un. Un rendu écrit trois fois
  finit par diverger sur ce qui se voit le moins — et l'accessibilité est ce qui
  se voit le moins.

  Ici, le nom accessible **n'est pas facultatif** : c'est le même `titre` qui
  sert aux deux, donc il ne peut plus manquer à l'un sans manquer à l'autre.

  ## La couleur dit le rôle, elle ne se choisit pas au coup par coup

  Trois tons, nommés par ce qu'ils désignent et non par leur teinte — un
  `ton="bleu"` inviterait le quatrième bleu. Ajouter un rôle, c'est ajouter une
  entrée ici, une fois, pour tous les écrans qui l'afficheront.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';

	/**  Le rôle désigné. Le nom porte le SENS, pas la couleur : c'est ce qui
	 *   empêche deux rôles d'atterrir sur la même teinte par hasard. */
	export let role: 'gestionnaire-site' | 'president-cs' | 'gestionnaire-principal';
	/**  Le texte de l'infobulle ET du nom accessible — un seul, donc jamais l'un
	 *   sans l'autre. */
	export let titre: string;
	/**  L'icône du catalogue `#lib/icones-svg.json`. Sans elle, le contenu du
	 *   slot est rendu — c'est ce qui laisse passer le ★ du gestionnaire
	 *   principal sans lui inventer une icône qui n'existe pas.
	 *
	 *   ⚠️ Vérifier qu'un nom donné existe dans le catalogue : `Icon` retombe
	 *   SILENCIEUSEMENT sur `help-circle` (cf. `ux-patterns` §13). */
	export let icone: string;
</script>

<!--  ⚠️ `class:` et non une classe INTERPOLÉE (`medaillon-{role}`) : une seule
      interpolation rend Svelte incapable de signaler les sélecteurs inutilisés
      pour TOUT le fichier, et `lint:css-orphelin` y devient aveugle sans le
      dire. Les trois rôles sont connus, ils s'écrivent donc. -->
<span
	class="medaillon"
	class:medaillon-gestionnaire-site={role === 'gestionnaire-site'}
	class:medaillon-president-cs={role === 'president-cs'}
	class:medaillon-gestionnaire-principal={role === 'gestionnaire-principal'}
	title={titre}
	aria-label={titre}
>
	<Icon name={icone} size={12} />
</span>

<style>
	/*  La géométrie, écrite UNE fois. Elle vivait deux fois dans le `<style>` de
	    l'annuaire, à onze propriétés près identiques. Elle part avec le balisage :
	    Svelte scope le style au composant qui REND, la laisser derrière l'aurait
	    rendue inerte. */
	.medaillon {
		position: absolute;
		top: -10px;
		right: 10px;
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 999px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		color: var(--color-sur-plein);
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.18);
		z-index: 1;
	}
	.medaillon-gestionnaire-site {
		background: var(--color-sarcelle-plein);
	}
	.medaillon-president-cs {
		background: var(--color-info-plein);
	}
	.medaillon-gestionnaire-principal {
		background: var(--color-accent-plein);
		color: var(--color-sur-accent);
	}
</style>
