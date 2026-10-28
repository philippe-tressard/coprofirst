<!--
  L'onglet **Copropriété › Fonctionnement** de l'administration : les délais, le
  gestionnaire du site et les alertes qu'il reçoit.

  ## Pourquoi il existe (#513, puis #2062)

  Né « Paramétrage site » (#513), extrait d'`admin/+page.svelte` que le garde-fou
  de modularité refusait de faire grossir. Le rangement par niveau (21/10/2026)
  l'a scindé : ce qui règle la VIE de la copropriété reste ici ; ce qui règle la
  PRÉSENTATION — sous-titre de connexion, pied de page — est parti dans
  `OngletConnexion`, et le logo comme l'adresse publique dans l'Identité
  (`OngletCopropriete`). `?onglet=site` mène ici (`#lib/admin-adresses`).

  ## Ce qui reste chez le parent

  `siteConfig` est LIÉ et `saveSiteConfig` arrive en callback : c'est la page qui
  parle à l'API et qui met à jour le `configStore`. Dupliquer l'appel ici
  donnerait deux vérités sur la configuration du site.
-->
<script lang="ts">
	import type { UtilisateurAdmin } from '#lib/api/index.ts';
	import { GLYPHE_URGENCE } from '#lib/options-publication.ts';
	import { nomAffiche } from '#lib/noms.ts';
	import Icon from '#lib/components/Icon.svelte';
	import type { ConfigSite, SectionSite } from '#lib/configSite.ts';

	/** Lié : la page porte l'état et l'enregistre. */
	export let siteConfig: ConfigSite;
	export let siteSaving = false;
	export let siteManagerUsers: UtilisateurAdmin[] = [];
	/** Enregistre UNE section — ses clés seules (#2057). */
	export let saveSiteConfig: (section: SectionSite) => void;
</script>

<section class="card config-section">
	<h2 class="config-section-title"><Icon name="settings" size={17} />Fonctionnement</h2>
	<div class="form-grid largeur-saisie">
		<label class="field champ-double">
			Gestionnaire du site (administrateur)
			<select bind:value={siteConfig.site_manager_user_id}>
				<option value="">Aucun (utiliser l'e-mail administrateur)</option>
				{#each siteManagerUsers as u (u.id)}
					<option value={String(u.id)}>{nomAffiche(u)} — {u.email}</option>
				{/each}
			</select>
			<span class="aide"
				>Choisi parmi les administrateurs : il reçoit ce qui demande un geste dans l'administration
				— comptes à valider, alertes système, bogues signalés si l'option est activée.</span
			>
		</label>
		<label class="field champ-double">
			E-mail administrateur
			<input type="email" bind:value={siteConfig.email_admin} placeholder="admin@example.com" />
			<span class="aide"
				>Adresse de secours utilisée si aucun utilisateur gestionnaire du site n'est sélectionné.</span
			>
		</label>
		<!--  🔴 UN SEUL délai, pour tout le site (#515). Il y en avait TROIS : deux
          affichés ici — dont un qui ne concernait plus qu'un statut devenu
          inatteignable — et un troisième CODÉ EN DUR dans `annonces.py`, que
          l'écran n'a jamais montré. C'est le mélange qui a fait dire « je
          croyais qu'il était de 30 » (#513).

          ⚠️ Ce champ gouverne SEPT objets, pas seulement les actualités : le
          texte d'aide doit le dire, sinon on croira régler une seule page. -->
		<label class="field champ-court champ-double">
			Délai d'archivage automatique (jours)
			<input
				type="number"
				bind:value={siteConfig.archivage_delai_jours}
				min="1"
				max="365"
				placeholder="30"
			/>
			<span class="aide"
				>Un contenu terminé quitte les listes actives et bascule dans les <strong>Archives</strong>
				après ce délai (défaut : 30 jours). Il s'applique à <strong>tout le site</strong> :
				actualités, affaires résolues, petites annonces vendues ou données, idées décidées, sondages
				clôturés, événements passés et affiches de hall envoyées. Un contenu <strong>annulé</strong> est
				archivé immédiatement, sans attendre — et le bouton 📦 archive à la main, quel que soit ce réglage.</span
			>
		</label>
		<label class="field champ-court champ-double">
			Délai de relance syndic (jours)
			<input
				type="number"
				bind:value={siteConfig.relance_syndic_delai_jours}
				min="1"
				max="365"
				placeholder="30"
			/>
			<span class="aide"
				>Nombre de jours sans mise à jour d'une affaire destinataire-syndic avant qu'elle apparaisse
				dans la liste de relance de l'Espace CS (défaut : 30 jours).</span
			>
		</label>
		<label class="field champ-double">
			<span class="case">
				<input type="checkbox" bind:checked={siteConfig.notify_ticket_bug_email} />
				Notifier si un bug (Affaires)
			</span>
			<span class="aide"
				>Envoie un e-mail au gestionnaire du site sélectionné (ou à l'adresse administrateur de
				secours) uniquement pour les affaires de catégorie « Bug ». Une affaire marquée {GLYPHE_URGENCE}
				Urgent ne déclenche pas cette notification — l'urgence est une case, pas une catégorie.</span
			>
		</label>
		<label class="field champ-double">
			<span class="case">
				<input type="checkbox" bind:checked={siteConfig.notify_new_user_created_email} />
				Notifier si un nouvel utilisateur est créé
			</span>
			<span class="aide"
				>Envoie un e-mail au gestionnaire du site sélectionné (ou à l'adresse administrateur de
				secours) lorsqu'un nouveau compte est créé et mis en attente de validation.</span
			>
		</label>
	</div>
	<div class="form-actions largeur-saisie">
		<button
			class="btn btn-primary"
			on:click={() => saveSiteConfig('fonctionnement')}
			disabled={siteSaving}
		>
			{siteSaving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</section>

<style>
</style>
