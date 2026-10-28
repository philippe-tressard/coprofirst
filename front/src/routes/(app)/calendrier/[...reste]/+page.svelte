<!--
  `/calendrier` — une ADRESSE, plus une page (#1092, lot 5, 23/09/2026).

  Les événements sont devenus des affaires : le Calendrier est le filtre
  « Calendrier » d'Affaires (une date est définie), son kanban un onglet. La
  route reste parce que des adresses ont été ENVOYÉES — courriels, WhatsApp,
  notifications, favoris. Le `#` n'arrive jamais au serveur : d'où une page.

  | Adresse | Destination |
  |---|---|
  | `/calendrier#ev-N`, `#ev_archive-N` | la fiche de l'affaire née de l'événement N (410 du serveur) |
  | `/calendrier/kanban` | l'onglet Kanban d'Affaires |
  | `/calendrier/archives` | l'onglet Archives d'Affaires |
  | `/calendrier` | Affaires, filtre « Calendrier » |

  ⚠️ Un `#ev-N` inconnu mène à la liste filtrée, jamais sur une autre affaire.
  Même contrat que `/actualites` (#1091).
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { cibleDuHash } from '#lib/deepLink.ts';
	import { suivreEvenementPromu } from '#lib/gestes-actualite.ts';
	import { routeOnglet } from '#lib/routes-onglets.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	onMount(async () => {
		//  `#ev_archive-N` : le lien d'un événement archivé (carnet d'entretien).
		const idEv = cibleDuHash('ev') ?? cibleDuHash('ev_archive');
		if (idEv !== null && (await suivreEvenementPromu(idEv))) return;
		const reste = page.params.reste;
		const cible =
			reste === 'kanban' || reste === 'archives'
				? routeOnglet('mes-demandes', reste)
				: '/tickets?nature=calendrier';
		goto(cible, { replaceState: true });
	});
</script>

<EtatListe chargement messageChargement="Redirection vers les affaires…" />
