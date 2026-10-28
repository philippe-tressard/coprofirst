<!--
  `/actualites` — une ADRESSE, plus une page (#1091, lot 4 ; #1092).

  Arbitré le 23/09/2026 : *« la notion d'actualité n'existe plus ; c'est une
  affaire (tout est centralisé dans cette vue) »*. Les actualités se lisent sous
  le filtre « Actualité » de la vue Affaires.

  🔴 La route reste, parce que des adresses ont été ENVOYÉES : chaque courriel et
  chaque message WhatsApp d'une actualité portait `/actualites#pub-N`. Le `#`
  n'arrive jamais au serveur — seul le navigateur le lit —, d'où une page et non
  une redirection côté serveur :

  | Adresse | Destination |
  |---|---|
  | `/actualites#pub-N` | la fiche de l'affaire née de la publication N (410 du serveur) |
  | `/actualites` | la vue Affaires, filtre « Actualité » |

  ⚠️ Un `#pub-N` inconnu (404) mène à la liste filtrée, jamais sur une autre
  affaire : se tromper enverrait le lecteur chez quelqu'un d'autre.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { cibleDuHash } from '#lib/deepLink.ts';
	import { suivrePublicationPromue } from '#lib/gestes-actualite.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	onMount(async () => {
		const idPub = cibleDuHash('pub');
		if (idPub !== null && (await suivrePublicationPromue(idPub))) return;
		goto('/tickets?nature=actualite', { replaceState: true });
	});
</script>

<EtatListe chargement messageChargement="Redirection vers les actualités…" />
