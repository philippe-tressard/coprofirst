<!--
  Ce que l'envoi d'une affaire URGENTE déclenche — dit avant d'envoyer.

  Extrait de `FormulaireTicket.svelte` le 31/10/2026 (#2362), quand ce fichier a
  franchi les 500 lignes du rang 1 en prenant la constante des séparateurs
  (`standards/02` §6). Le bloc se détache seul : un texte, sans donnée ni
  comportement partagés avec le formulaire, qui décide seul QUAND il paraît.

  Le formulaire ne le rend qu'en CRÉATION d'une affaire suivie : c'est l'envoi qui
  notifie. Il suit la case « Urgent » (#820), qui pose `priorite = haute` — pour le
  résident aussi. Aucun mot du texte n'a changé en le déplaçant.
-->
<script lang="ts">
	import { GLYPHE_URGENCE } from '#lib/options-publication.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';
</script>

<div class="alert alert-error largeur-saisie">
	{GLYPHE_URGENCE} <strong>Urgent</strong>{SEPARATEUR.tiret}Le conseil syndical et le syndic seront
	notifiés immédiatement. En cas de danger immédiat, composez le
	<strong>15 (SAMU), 17 (Police) ou 18 (Pompiers)</strong>.
</div>
