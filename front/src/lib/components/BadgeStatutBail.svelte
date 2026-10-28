<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	/**
	 * Le badge « état d'un bail » — **une seule écriture**.
	 *
	 * ## Ce qu'il remplace
	 *
	 * Trois copies du même bloc, dans trois formes différentes (15/09/2026) :
	 * deux ternaires imbriqués dans `OngletGestionLocative`, et un troisième dans
	 * `mon-lot` — **le seul faux**. Il disait `actif ? vert : jaune`, si bien
	 * qu'un bail **terminé** s'affichait en jaune là et en gris ailleurs.
	 *
	 * 🔴 Une pastille jaune ressemble à une pastille : rien ne le signalait, et
	 * la divergence a survécu à toutes les relectures de l'écran.
	 *
	 * C'est le même geste que `BadgePerimetre`, qui a rassemblé neuf copies pour
	 * la même raison — et qui y a trouvé, lui aussi, un défaut que les neuf
	 * partageaient.
	 *
	 * ⚠️ Le vocabulaire (libellé, teinte) ne vit pas ici mais dans `#lib/bail` :
	 * ce composant décide du **rendu**, pas des mots. Un écran qui voudrait un
	 * autre rendu passe par une prop, jamais par une seconde table.
	 */
	import { BADGE_STATUT_BAIL, LIBELLE_STATUT_BAIL } from '#lib/bail.ts';

	/** L'état du bail — la valeur brute de l'API. */
	export let statut: string | null | undefined;
	/** Rendu compact pour une liste dense ; taille normale par défaut. */
	export let compact = false;
</script>

<!--  Repli gris + valeur brute : un état inconnu doit se VOIR, pas s'effacer.
      C'est la même règle que `libelleRole()` côté `#lib/roles`.  -->
<Badge {compact} teinte={BADGE_STATUT_BAIL[statut ?? ''] ?? 'badge-gray'}>
	{LIBELLE_STATUT_BAIL[statut ?? ''] ?? statut ?? '—'}
</Badge>
