<!--
  ChoixDecorFete.svelte — garder ou éteindre, pour soi, le DÉCOR DES JOURS DE
  FÊTE (#2312, 30/10/2026). Il vit dans la carte « Apparence » du Profil, sous le
  thème.

  Deux interrupteurs se suivent : l'administration allume le décor pour la
  copropriété (Admin › Services) ; chacun le garde ou l'éteint ici. Le réglage
  ne s'offre donc que si le service est allumé — une case qui n'aurait aucun
  effet se lirait comme une panne. Le choix vit sur le COMPTE (`decor_fetes`),
  pour tous les appareils : aucun cookie de plus.

  Il s'applique sur-le-champ, comme le thème au-dessus : le compte en mémoire
  change d'abord — le décor du coin arrive ou part sous les yeux —, puis la
  requête part ; un refus remet la case et le décor où ils étaient. La phrase
  d'aide dit ce que la case change AUJOURD'HUI : la fête en cours et jusqu'à
  quand, sinon la prochaine — hors des fêtes, cocher ne montrerait rien.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { auth as authApi } from '#lib/api/index.ts';
	import { currentUser, setUser } from '#lib/stores/auth.ts';
	import { configStore } from '#lib/stores/pageConfig.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { fmtDayMonth, jourIso } from '#lib/date.ts';
	import { feteEnCoursOuProchaine, LIBELLES_FETES, type PeriodeFete } from '#lib/fetes.ts';

	let periode: PeriodeFete | null = null;
	onMount(() => {
		periode = feteEnCoursOuProchaine(jourIso());
	});

	$: actif = $currentUser?.decor_fetes !== false;
	$: offert = $configStore['decor_fetes'] === '1' && $currentUser !== null;

	let enCours = false;

	async function basculer(e: Event) {
		const voulu = (e.currentTarget as HTMLInputElement).checked;
		const avant = $currentUser;
		if (!avant) return;
		enCours = true;
		setUser({ ...avant, decor_fetes: voulu });
		const ok = await tenter(
			async () => setUser(await authApi.updateMe({ decor_fetes: voulu })),
			undefined,
			"Le réglage du décor n'a pas pu être enregistré",
		);
		if (!ok) setUser(avant);
		enCours = false;
	}

	function phrase(p: PeriodeFete | null, affiche: boolean): string {
		if (!affiche) return 'Masqué pour vous, sur tous vos appareils.';
		if (!p) return 'Un ornement discret dans le coin des pages, les jours de fête.';
		const nom = LIBELLES_FETES[p.code];
		if (p.enCours)
			return p.debut === p.fin
				? `${nom} aujourd’hui : regardez en haut à droite de la page.`
				: `${nom} jusqu’au ${fmtDayMonth(p.fin)} : regardez en haut à droite de la page.`;
		const date = fmtDayMonth(p.debut);
		//  « 1er avril, le 1 avril » : un nom qui EST sa date ne la redit pas.
		if (nom.endsWith(date.split(' ')[1])) return `Prochain : ${nom}.`;
		return `Prochain : ${nom}, ${p.debut === p.fin ? 'le' : 'à partir du'} ${date}.`;
	}
</script>

{#if offert}
	<div class="choix-decor">
		<label class="checkbox-field">
			<input type="checkbox" checked={actif} disabled={enCours} on:change={basculer} />
			<span>Décor des jours de fête</span>
		</label>
		<p class="aide sous-case" aria-live="polite">{phrase(periode, actif)}</p>
	</div>
{/if}

<style>
	/*  `.checkbox-field`, `.aide`, `.sous-case` : la charte porte tout. */
	.choix-decor {
		margin-top: 1.25rem;
	}
	.checkbox-field input {
		margin: 0;
		flex-shrink: 0;
	}
</style>
