<!--
  CaseReservePerimetre.svelte — 🔒 « visible du seul périmètre sélectionné ».

  ## Pourquoi un composant (23/09/2026, #1096)

  Arbitré à l'écran : *« 🔒 Rendre confidentielle — visible du seul périmètre
  sélectionné » ne peut-il pas être déplacée dans Périmètre ? (c'est plus
  cohérent) »* — oui, **sous les pastilles** du périmètre, grisée avec son motif
  quand le périmètre concerne déjà tout le monde.

  La case vivait dans `OptionsPublication`, avec ses deux règles et son
  avertissement de diffusion. Elle en sort ENTIÈRE, pour être rendue à deux
  endroits sans être recopiée :

  | Où | Pour qui | État |
  |---|---|---|
  | section Périmètre (`SectionPerimetre`) | une actualité, une affaire suivie | cochable |
  | section Mise en avant (`OptionsPublication`) | — | verrouillée si un appelant passe `acquis` |

  🔴 Une affaire suivie la montrait cochée et verrouillée (25/09/2026) alors
  qu'elle partait `false` : le serveur ne restreignait rien, et un code
  d'ascenseur a été lu de toute la résidence et envoyé au groupe WhatsApp
  (22/10/2026). Elle est cochable pour les deux natures depuis.

  ## Les deux règles qu'elle fait respecter à l'écran

  1. **Elle exige un périmètre restreint.** Sur un périmètre qui concerne déjà
     tous les résidents, il n'y a rien à restreindre : la case est désactivée, et
     le texte dit pourquoi — une case inerte sans explication se lit comme un
     bug (`standards/11`).
  2. **Elle dit ce qui sortira**, canal par canal (#623), dès qu'elle est cochée.

  ⚠️ Ce n'est qu'un confort d'écran : le serveur retire le drapeau sur un
  périmètre global et refuse l'affiche (`tickets/actualite.appliquer_acces`,
  `visibility.hors_du_hall`). C'est lui qui décide.

  ## 🔴 EN TÊTE de la section, et plus sous les pastilles (25/09/2026)

  Lot 1 de la pastille de lecture, arbitré à l'écran — *« Comme la capture
  c'est parfait »* : les deux cases qui RESTREIGNENT la lecture ont une seule
  forme (case, icône du catalogue, libellé) et ouvrent leur section —
  « Réservé au périmètre sélectionné » le Périmètre, « Confidentielle » les
  Destinataires (`CaseConfidentielle`). Cela renverse le « sous les pastilles »
  de #1096 ; le reste de l'UX du périmètre ne bouge pas. Elle a quitté la Mise
  en avant : une affaire la montre ici, cochée d'office (`acquis`).
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import EncartAvertissement from '$lib/components/EncartAvertissement.svelte';
	import { concerneTous } from '$lib/utils';
	import { optionPublication } from '$lib/options-publication';

	/** La case — `reserve_perimetre`, actualité comme affaire. */
	export let coche = false;
	/** Le périmètre sélectionné, qui décide si la case a un sens. */
	export let perimetreCible: string[] = [];
	/**  🔒 DÉJÀ ACQUIS — le motif pour lequel l'objet est TOUJOURS restreint à
	 *   son périmètre (une affaire suivie). Vide quand le choix se pose vraiment :
	 *   la case est alors montrée cochée et verrouillée, avec son motif écrit. */
	export let acquis = '';
	/** Le nom de l'objet, pour les libellés qui le nomment. */
	export let objet = 'actualité';
	/**  SANS OBJET — le motif quand « Confidentielle » est cochée : elle passe
	 *   outre le périmètre. La valeur n'est pas effacée, elle revient au décoché. */
	export let sansObjet = '';

	//  Identifiant unique : deux formulaires peuvent coexister à l'écran.
	const idAide = `aide-reserve-${Math.random().toString(36).slice(2, 8)}`;
	const option = optionPublication('confidentiel');

	//  « Rien à restreindre » : miroir de `a_portee_globale` côté serveur. La
	//  question n'est pas « est-ce la copropriété entière ? » mais « cocher
	//  changerait-il quelque chose ? ».
	$: rienARestreindre = concerneTous(perimetreCible);
	//  Le périmètre peut changer APRÈS que la case a été cochée : une valeur
	//  devenue impossible ne part pas dans la requête.
	$: if (rienARestreindre && coche && !acquis) coche = false;
</script>

<label
	class="checkbox-field case-reserve"
	class:desactivee={rienARestreindre || acquis || sansObjet}
	title={sansObjet ||
		acquis ||
		(rienARestreindre
			? 'Le périmètre sélectionné concerne déjà tout le monde : il n’y a rien à restreindre.'
			: option?.aide)}
>
	<input
		type="checkbox"
		checked={sansObjet ? false : acquis ? !rienARestreindre : coche}
		on:change={(e) => (coche = e.currentTarget.checked)}
		disabled={!!acquis || !!sansObjet || rienARestreindre}
		aria-describedby={rienARestreindre || acquis || sansObjet ? idAide : undefined}
	/>
	<Icon name="lock" size={15} />
	Réservé au périmètre sélectionné
</label>

{#if sansObjet}
	<p class="aide" id={idAide}>{sansObjet}</p>
{:else if acquis}
	<!--  Le motif est ÉCRIT, pas seulement en infobulle : au doigt il n'y a pas
	      de survol, et un lecteur d'écran ne lit pas un `title` sans l'y
	      chercher (leçon du 28/08/2026). -->
	<p class="aide" id={idAide}>{acquis}</p>
{:else if rienARestreindre}
	<p class="aide" id={idAide}>
		Le périmètre concerne déjà tout le monde : rien à restreindre. Choisissez un bâtiment, par
		exemple, pour que seuls ceux qui y sont la lisent.
	</p>
{:else if coche}
	<p class="aide">
		Seuls ceux du périmètre sélectionné verront cette {objet} — ni dans le fil, ni par un lien direct
		pour les autres. Le réglage reste modifiable après publication.
	</p>
	<!--  🔴 CE QUI SORT, canal par canal (#623, 29/08/2026). Il n'est PAS le même
	      partout : le titre part sur WhatsApp, tout part par e-mail. Il s'affiche
	      dès la case cochée : c'est en écrivant le TITRE qu'il faut le savoir. -->
	<div class="avert-diffusion">
		<EncartAvertissement role="note">
			<p class="avert-titre">&#x26A0;&#xFE0F; Ce qui sortira de l'application</p>
			<ul class="avert-liste">
				<li>
					<strong>Groupe WhatsApp</strong> — le <strong>titre</strong> et le périmètre partent, avec
					un lien vers l'application. Le contenu, lui, ne sort pas.
					<span class="avert-consigne"
						>Le groupe est commun à toute la copropriété : n'écrivez rien de confidentiel dans le
						titre.</span
					>
				</li>
				<li>
					<strong>Syndic et conseil syndical</strong> — l'e-mail part
					<strong>en entier</strong>, titre et contenu, sans restriction.
				</li>
				<li><strong>Affiche de hall</strong> — aucune : un hall se lit sans connexion.</li>
			</ul>
		</EncartAvertissement>
	</div>
{/if}

<style>
	/*  En tête de section : elle précède les pastilles, l'air est dessous. */
	.case-reserve {
		margin-bottom: 0.5rem;
	}
	/*  Une case grisée doit se VOIR grisée, pas seulement refuser le clic. */
	.desactivee {
		opacity: 0.5;
		cursor: not-allowed;
	}
	/*  L'avertissement de diffusion : un ENCART, pas un simple paragraphe d'aide.
	    Il annonce une conséquence IRRÉVERSIBLE — un message parti ne se retire
	    pas d'un groupe — là où `.aide` explique un réglage. Seule sa place vit
	    ici ; son allure est celle d'`EncartAvertissement` (#1455). */
	.avert-diffusion {
		margin: 0.25rem 0 1rem;
	}
	.avert-titre {
		margin: 0 0 0.35rem;
		font-size: var(--fs-sm);
		font-weight: 600;
	}
	.avert-liste {
		margin: 0;
		padding-left: 1.1rem;
		font-size: var(--fs-sm);
		line-height: 1.5;
		color: var(--color-text);
	}
	.avert-liste li + li {
		margin-top: 0.3rem;
	}
	/*  La consigne d'écriture sur sa propre ligne : c'est la SEULE phrase qui
	    demande une action de l'auteur, les autres décrivent. */
	.avert-consigne {
		display: block;
		margin-top: 0.15rem;
		font-style: italic;
	}
	@media (max-width: 480px) {
		.case-reserve {
			min-height: 44px;
		}
	}
</style>
