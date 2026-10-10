<!--
  **La carte d'une personne de l'annuaire** — conseil syndical et syndic.

  ## Pourquoi ce composant (16/09/2026)

  `annuaire/+page.svelte` rendait TROIS fois la même carte : le membre du CS
  groupé par bâtiment, le membre du CS sans groupe, et le contact du syndic.
  Trente lignes recopiées à chaque fois — médaillons, avatar, nom — pour ne
  varier que sur le bloc de détail.

  🔴 **Et les copies avaient déjà divergé** : la version groupée n'affichait que
  l'étage, la version plate le bâtiment ET l'étage. Ce n'était pas un défaut —
  répéter le bâtiment sous un en-tête « Bâtiment 2 » n'aurait aucun sens — mais
  rien ne le disait, et la différence se perdait au milieu du copier-coller.
  Elle est maintenant **explicite** : deux appels, deux contenus de `<slot>`.

  ## Ce que le composant porte, et ce qu'il laisse

  | Porté ici | Laissé à l'appelant |
  |---|---|
  | la carte (`.contact-card`), sa mise en page, la variante principale | les lignes de détail, par le `<slot>` |
  | les médaillons de rôle, dans leur ordre | quels médaillons, par `medaillons` |
  | l'avatar et le nom affiché | — |

  C'est la même répartition que `CarteTicket`, `CarteContrat` et les quatre
  autres `Carte*` du dossier : la structure appartient au composant, le contenu
  variable arrive par les props et le slot.

  ⚠️ `nomAffiche` n'est PAS recopié ici : il vient de `$lib/noms`, comme partout
  ailleurs. Une carte qui composerait elle-même « Prénom NOM » divergerait du
  reste du site au premier changement de convention — et `npm run lint:noms` le
  refuse.
-->
<script context="module" lang="ts">
	/**
	 *  Un médaillon à poser sur la carte.
	 *
	 *  🔴 Exporté depuis le module — même raison qu'`ActionsMembre` : l'appelant
	 *  qui construit la liste s'en sert pour se typer. Recopier la forme chez lui
	 *  donnerait deux définitions d'une même chose, qui divergent au premier
	 *  champ ajouté.
	 */
	export type Medaillon = {
		role: 'gestionnaire-site' | 'president-cs' | 'gestionnaire-principal';
		titre: string;
		icone: string;
	};
</script>

<script lang="ts">
	import Avatar from '$lib/components/Avatar.svelte';
	import MedaillonRole from '$lib/components/MedaillonRole.svelte';
	import { nomAffiche } from '$lib/noms';

	/** La personne : ce qu'il faut pour l'avatar et le nom. */
	export let personne: {
		photo_url?: string | null;
		prenom?: string | null;
		nom?: string | null;
		genre?: string | null;
	};

	/** Les médaillons à afficher, dans l'ordre voulu. */
	export let medaillons: Medaillon[] = [];

	/** Variante « principale » — un liseré et un avatar accentués. */
	export let principal = false;
</script>

<div class="contact-card card" class:card-principal={principal}>
	{#each medaillons as m, i (`${i}|${m.role}`)}
		<MedaillonRole role={m.role} titre={m.titre} icone={m.icone} />
	{/each}
	<Avatar photoUrl={personne.photo_url} prenom={personne.prenom} nom={personne.nom} />
	<div>
		<strong class="contact-nom">{personne.genre ?? ''} {nomAffiche(personne)}</strong>
		<slot />
	</div>
</div>

<style>
	.contact-card {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		padding: 1.4rem 1rem 0.9rem;
		position: relative;
		/*  Base de 15 rem dans la rangée `flex` de l'annuaire, et jamais moins que
		    son contenu : c'est ce qui élargit la carte quand le nom l'exige. */
		flex: 1 1 15rem;
		max-width: 100%;
	}
	/*  « Mr Prénom NOM » sur UNE ligne (demandé à l'écran le 10/10/2026) : coupé,
	    le NOM tombait seul sous la civilité et le prénom. C'est la carte qui
	    s'élargit, pas le nom qui se plie. */
	.contact-nom {
		white-space: nowrap;
	}
	/*  Au téléphone la carte a déjà toute la largeur : un nom plus long qu'elle
	    se replie plutôt que de faire défiler la page en largeur. */
	@media (max-width: 480px) {
		.contact-nom {
			white-space: normal;
		}
	}
	.card-principal {
		border-left: 3px solid var(--color-accent);
		--avatar-bg: var(--color-accent);
	}
</style>
