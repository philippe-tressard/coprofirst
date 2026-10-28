<!--
  La DERNIÈRE LIGNE d'une carte d'affaire — la même partout (27/09/2026).

  Arbitré à l'écran : la ligne de la carte d'AFFAIRE fait la norme, et le fil
  d'activité comme la carte d'actualité la rendent à l'identique — même
  pastilles, même couleur, même nom, même place. Elles différaient sur neuf
  points (catégorie en texte ou en emoji, état absent du fil, périmètre en tête
  ou après l'état, « urgent » rouge contre « ⚡ Urgente » orange, numéro en
  badge ou en texte, auteur avec ou sans ✍️, lecteurs et ✨ absents du fil…).

  L'ORDRE, qui ne se discute plus :
    catégorie (emoji, libellé au survol) · état · 🔹 périmètre · qui la lit ·
    ⚡ urgence · marqueurs · #numéro · ✍️ auteur · ✨ IA

  Deux différences, et deux seulement, DÉCLARÉES :
    • une ACTUALITÉ n'a pas d'état — elle n'a pas de suivi (#1091) ;
    • dans le FIL (`dansLeFil`), pas de 📌 : le fil a son bandeau « Épinglé »
      (arbitré le 27/09/2026).

  🔴 PAS DE BADGE 📍 DU DEMANDEUR — arbitré à l'écran le 30/08/2026 (#653) :
  *« se restreindre uniquement au périmètre »*. Il disait où habite la personne,
  pas où est le problème ; le 🔹 répond à la seule question du lecteur de liste.
  Ce qui manque vraiment est le LOT, suivi dans #653 — ne pas remettre de badge
  de bâtiment en attendant.

  🔒 `npm run lint:pastilles` exige que les trois cartes passent par ici.

  Le squelette (catégorie, numéro, fin) est `PiedCarte`, commun à ce composant
  et au carnet d'entretien (24/10/2026) : l'ordre ci-dessus s'y lit, il ne s'y
  écrit plus qu'une fois.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import BadgeEtatAffaire from '#lib/components/BadgeEtatAffaire.svelte';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import PastilleLecture from '#lib/components/PastilleLecture.svelte';
	import AuteurCarte from '#lib/components/AuteurCarte.svelte';
	import MarqueIA from '#lib/components/MarqueIA.svelte';
	import PiedCarte from '#lib/components/PiedCarte.svelte';
	import { BADGE_PRIORITE, PRIORITE_BREVE, optionsEnBadge, ticketUrgent } from '#lib/tickets.ts';
	import type { Ticket } from '#lib/api/index.ts';
	import { etatAffiche } from '#lib/suivi-actualite.ts';

	/** L'affaire — une carte la passe entière, le fil ses seuls champs de ligne. */
	export let affaire: Ticket;
	/** Le PROPRIÉTAIRE à nommer (`nomProprietaire`, ou le nom que le fil reçoit). */
	export let auteur: string | null | undefined = null;
	/** Le fil a son bandeau « Épinglé » : pas de 📌 sur la ligne. */
	export let dansLeFil = false;

	$: marqueurs = optionsEnBadge(affaire).filter((o) => !(dansLeFil && o.cle === 'epingle'));
	//  L'état d'une affaire ; celui d'une actualité seulement si elle est suivie.
	$: etat = etatAffiche(affaire);
</script>

<!--  Le squelette — catégorie, numéro, créneau de fin — est `PiedCarte` (24/10/2026),
      que le carnet d'entretien rend aussi : ici, seulement ce que dit une affaire. -->
<PiedCarte categorie={affaire.categorie} numero={affaire.numero}>
	{#if etat}
		<BadgeEtatAffaire statut={etat} fusionnee={affaire.fusionnee} />
	{/if}
	<BadgePerimetre perimetre={affaire.perimetre_cible} />
	<PastilleLecture ticket={affaire} />
	{#if ticketUrgent(affaire)}
		<Badge teinte={BADGE_PRIORITE[affaire.priorite] ?? 'badge-gray'}
			>{PRIORITE_BREVE[affaire.priorite]}</Badge
		>
	{/if}
	{#each marqueurs as opt (opt.cle)}
		<span class="badge badge-gray" title={opt.aide}>{opt.glyphe} {opt.etat}</span>
	{/each}
	<!--  🧾 Une synthèse VALIDÉE l'accompagne (maquette A, 15/10/2026) : la carte
	      repliée le dit, comme un marqueur. Le serveur en décide (`synthese_validee`). -->
	{#if affaire.synthese_validee}
		<span class="badge badge-gray" title="Une synthèse validée accompagne cette affaire"
			>🧾 Synthèse</span
		>
	{/if}
	<svelte:fragment slot="fin">
		<AuteurCarte nom={auteur} />
		<MarqueIA assiste={affaire.assiste_ia} />
	</svelte:fragment>
</PiedCarte>
