<!--
  CanauxNotification.svelte — « Qui est prévenu ? », écriture unique.

  Les trois canaux (groupe WhatsApp, syndic, conseil syndical) étaient écrits à
  la main dans SIX formulaires : actualités, évolutions (EvolForm), calendrier,
  sondages, devis, et création de ticket. Ils avaient divergé exactement comme le
  prévoit `standards/02-factorisation.md` §2 — deux tracés SVG WhatsApp, trois
  libellés (« Partager sur le groupe », « …sur le groupe WhatsApp », « Notifier
  WhatsApp »), deux icônes d'e-mail (✉️ et 📧), trois libellés de CS — et surtout
  un écran où le canal WhatsApp manquait purement et simplement : la création
  d'un ticket. C'est ce trou-là que l'utilisateur a signalé le 08/08/2026.

  La référence retenue est celle des actualités, qui est la plus complète et la
  seule à porter le libellé métier (« le groupe » = le groupe de la copropriété).

  Props :
    whatsapp / syndic / cs – à lier avec `bind:` ; les trois cases
    compact                – formulaire dense en ligne (évolution, devis) :
                             police réduite
    aideWhatsapp           – infobulle propre au contexte (ex. « la photo part avec »)

  MISE EN FORME : une rangée simple, icône + libellé, comme les actualités. Les
  précisions (« le syndic principal recevra un e-mail ») sont en **infobulle** et
  non en texte visible : essayées sous chaque case, elles élargissaient tellement
  les trois blocs qu'ils s'enroulaient sur deux lignes ragged — vérifié au rendu
  le 08/08/2026. Seule la création de ticket les affichait avant, c'est-à-dire un
  écran sur six : les garder visibles partout, c'était garder la divergence dans
  l'autre sens.

  Aucune de ces cases n'est un choix par défaut : elles partent toujours
  décochées côté appelant. Envoyer une notification est une action délibérée.
-->
<script lang="ts">
	import { nomAffiche } from '#lib/noms.ts';
	import { currentUser } from '#lib/stores/auth.ts';
	import Icon from '#lib/components/Icon.svelte';

	/** Partager sur le groupe WhatsApp de la copropriété */
	export let whatsapp = false;
	/** Envoyer un e-mail au syndic principal */
	export let syndic = false;
	/** Envoyer un e-mail aux membres du conseil syndical */
	export let cs = false;
	/** Formulaire dense en ligne : police réduite */
	export let compact = false;
	/** Infobulle propre au contexte, sinon la formulation générique */
	export let aideWhatsapp = '';
	/**  🔴 M'ENVOYER UNE COPIE — la quatrième case, arbitrée le 31/08/2026.
	 *
	 *   > « pour l'auteur dans la diffusion, que cette section fasse apparaître
	 *   > une coche supplémentaire EN CLAIR et pas un envoi implicite à l'auteur »
	 *
	 *   Un envoi implicite avait été livré quelques heures plus tôt : l'auteur
	 *   recevait une copie cachée dès qu'il n'était pas déjà destinataire. C'était
	 *   commode, et c’était une décision prise à sa place — le formulaire annonçait
	 *   trois destinataires et en servait quatre.
	 *
	 *   ⚠️ Elle vit ICI et non dans un écran : cette section sert huit formulaires,
	 *   et une case posée dans l'un des huit n'aurait été offerte que là. C'est la
	 *   règle rappelée le même jour — *« les comportements demandés doivent être au
	 *   niveau des objets pour être dans toutes les pages y faisant référence »*.
	 *
	 *   ⚠️ **Décochée par défaut.** Une case cochée d'avance n'est pas un choix :
	 *   ce serait l'envoi implicite sous un autre nom. */
	export let auteur = false;
	/**  Le NOM de l'auteur de l'objet — celui qui recevra la copie. Vide tant
	 *   que l'objet n'existe pas : l'écran passe alors le nom du rédacteur, qui
	 *   en sera l'auteur.
	 *
	 *   ⚠️ L'écran ne le passe QUE s'il tient un objet déjà créé. À la création,
	 *   l'auteur sera le rédacteur : le composant retombe donc tout seul sur le
	 *   compte connecté, plutôt que de faire écrire la même ligne dans chacun des
	 *   huit formulaires. C'est la règle du 31/08/2026 — *« les comportements
	 *   demandés doivent être au niveau des objets pour être dans toutes les
	 *   pages y faisant référence »*. */
	export let auteurNom = '';
	/**  🔴 LE MOTIF QUI INTERDIT LE GROUPE — vide quand rien ne l'interdit.
	 *
	 *   > « si "Visibilité du ticket au seul conseil syndical" est sélectionné,
	 *   > la diffusion WhatsApp est interdite » (05/09/2026)
	 *
	 *   Le groupe rassemble **tous les résidents** : un objet qu'on vient de
	 *   réserver au conseil syndical ne peut pas y être recopié. La règle vaut
	 *   pour toute entité qui porte cette option — actualité comme ticket —,
	 *   donc elle vit ICI, au niveau de l'objet, et pas dans les huit
	 *   formulaires qui affichent cette section : *« faire ces évolutions au
	 *   niveau de l'objet pour ne pas dupliquer le code »*.
	 *
	 *   ⚠️ Une chaîne, pas un booléen : la case grisée doit DIRE pourquoi elle
	 *   l'est. Une case qui refuse sans motif se lit comme une panne.
	 *
	 *   ⚠️ **Ceci n'est PAS le contrôle.** Le serveur refuse l'envoi de son
	 *   côté (`api/tests/test_canaux_notification.py`) : `partager_whatsapp` est
	 *   un champ du corps de la requête, qui se poste sans passer par l'écran. */
	export let whatsappInterdit = '';

	//  Le nom réellement affiché : celui de l'auteur de l'objet, sinon le nôtre.
	$: nomCopie = auteurNom || nomAffiche($currentUser);

	//  Cocher puis interdire laisserait une case cochée et grisée, c'est-à-dire
	//  la promesse d'un envoi qui n'aura pas lieu. On décoche.
	$: if (whatsappInterdit && whatsapp) whatsapp = false;
</script>

<div class="canaux" class:compact>
	<label
		class="checkbox-field"
		class:interdite={whatsappInterdit}
		title={whatsappInterdit ||
			aideWhatsapp ||
			'Le message est publié sur le groupe WhatsApp de la copropriété.'}
	>
		<input type="checkbox" bind:checked={whatsapp} disabled={!!whatsappInterdit} />
		<Icon name="whatsapp" size={compact ? 16 : 18} />
		<span>Partager sur le groupe</span>
	</label>
	<!--  Le motif est ÉCRIT, pas seulement en infobulle : au doigt il n'y a pas de
	      survol, et un lecteur d'écran ne lit pas un `title` sans l'y chercher.
	      C'est la leçon du 28/08/2026, déjà tirée pour `aideWhatsapp` juste à
	      côté — l'appliquer ici plutôt que la réapprendre. -->
	{#if whatsappInterdit}
		<p class="motif-interdit">{whatsappInterdit}</p>
	{/if}

	<label class="checkbox-field" title="Le syndic principal recevra un e-mail.">
		<input type="checkbox" bind:checked={syndic} />
		<span class="ico" aria-hidden="true">&#x2709;&#xFE0F;</span>
		<span>Envoyer au syndic</span>
	</label>

	<label class="checkbox-field" title="Les membres du conseil syndical recevront un e-mail.">
		<input type="checkbox" bind:checked={cs} />
		<span class="ico" aria-hidden="true">&#x2709;&#xFE0F;</span>
		<span>Envoyer au Conseil Syndical</span>
	</label>

	<!--  EN DERNIER : les trois premières disent qui d'AUTRE est prévenu, celle-ci
	      parle de soi. L'ordre suit le sens, pas l'ordre d'ajout. -->
	<!--  🔴 CETTE CASE NOMME SON DESTINATAIRE, et c'est le seul libellé qui lève
	      l'ambiguïté (arbitré à l'écran le 31/08/2026, en trois temps).

	      « M'envoyer une copie », puis « … de ce message » : jugés obscurs.
	      « Envoyer une copie à l'auteur » : pire encore — dès que le CS prend le
	      relais d'un ticket, « l'auteur » ne désigne plus rien de sûr, celui du
	      ticket ou celui du commentaire ?

	      La règle retenue : *« si le CS prend la main sur un ticket ouvert par un
	      résident pour notifier le CS ou le syndic, il décide alors de notifier
	      l'auteur »*. Donc l'auteur de l'OBJET, et son nom écrit en toutes
	      lettres — le seul libellé où l'on sait à qui l'on écrit.

	      ⚠️ Sans nom (objet pas encore créé, auteur supprimé), on retombe sur
	      « l'auteur » : jamais sur rien. Une case sans destinataire lisible
	      serait un envoi implicite sous un autre nom. -->
	<label class="checkbox-field">
		<input type="checkbox" bind:checked={auteur} />
		<span class="ico" aria-hidden="true">&#x2709;&#xFE0F;</span>
		<span>Envoyer une copie à {nomCopie || "l'auteur"}</span>
	</label>
</div>

<style>
	.canaux {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		margin-bottom: 1rem;
	}
	.canaux.compact {
		gap: 0.75rem;
		margin-bottom: 0.6rem;
		font-size: var(--fs-md);
	}
	/*  `:global` parce que `.checkbox-field` est une classe partagée du thème :
	    la styler localement seule laisserait Svelte la considérer inutilisée. */
	.canaux :global(.checkbox-field) {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		cursor: pointer;
		margin: 0;
		white-space: nowrap;
	}
	.canaux input[type='checkbox'] {
		width: auto;
		margin: 0;
		flex-shrink: 0;
	}
	.ico {
		font-size: 1.1em;
		line-height: 1;
	}
	/*  Grisée ET non cliquable : `disabled` seul laisse le libellé au contraste
	    normal, donc une case qui a l'air disponible. */
	.canaux :global(.checkbox-field.interdite) {
		opacity: 0.55;
		cursor: not-allowed;
	}
	.motif-interdit {
		flex-basis: 100%;
		margin: 0;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	/*  Sous 480 px, trois cases côte à côte deviennent illisibles : elles
	    passent en colonne pleine largeur. Et surtout la case gagne une hauteur
	    de 44 px : en rangée, la cible tactile ne faisait que 16 à 18 px de haut
	    — mesuré au rendu le 08/08/2026 (socle 11 §10). */
	@media (max-width: 480px) {
		.canaux {
			flex-direction: column;
			gap: 0.25rem;
		}
		.canaux :global(.checkbox-field) {
			min-height: 44px;
			white-space: normal;
		}
	}
</style>
