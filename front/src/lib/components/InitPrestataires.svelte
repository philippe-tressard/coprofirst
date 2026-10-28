<!--
  « ⚙️ Init. prestataires » — les visites de l'exercice posées en une fois (#1193).

  Le bouton vivait dans le kanban du Calendrier, parti au lot 5b2 de #1092. Il
  revient dans l'onglet Kanban d'Affaires, réservé au conseil : il pose des
  affaires Entretien « Chez le prestataire », sans aucune diffusion.

  La DÉCISION vit dans `#lib/init-prestataires` (pure, autotestée) ; ce
  composant ne fait que lire, demander, écrire — et résoudre ce que lui seul
  sait : le nom d'un prestataire et le périmètre d'un bâtiment.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { prestataires as prestApi, tickets as ticketsApi, type Ticket } from '#lib/api/index.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { perimetreDuBatiment } from '#lib/perimetres/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		clesDesAffaires,
		planifier,
		resumePlan,
		sourcesDesAffaires,
		sourcesDesContrats,
		versAffaire,
	} from '#lib/init-prestataires.ts';

	/** Les affaires chargées par la page — archivées comprises, pour la clé anti-doublon. */
	export let tickets: Ticket[] = [];

	const dispatch = createEventDispatcher<{ cree: void }>();
	const annee = new Date().getFullYear();
	//  L'exercice en cours et le suivant : on l'initialise en début d'année, ou
	//  en décembre pour l'année qui vient.
	const EXERCICES = [annee, annee + 1];
	let exercice = annee;
	let enCours = false;

	async function initialiser() {
		enCours = true;
		try {
			const [contrats, prests] = await Promise.all([prestApi.contrats(), prestApi.list()]);
			const noms = new Map(prests.map((p) => [p.id, p.nom]));
			const ctx = {
				nomPrestataire: (id: number | null | undefined) => noms.get(id as number) ?? 'Prestataire',
				perimetreDuBatiment,
			};
			const { sources: desContrats, echus } = sourcesDesContrats(contrats, ctx);
			const titres = new Set(desContrats.map((s) => s.titre));
			const sources = [...desContrats, ...sourcesDesAffaires(tickets, titres)];
			const plan = planifier(sources, clesDesAffaires(tickets, exercice), exercice, echus);
			const message = resumePlan(plan, exercice);
			if (plan.aCreer.length === 0) {
				toast('info', message);
				return;
			}
			if (!(await confirmer({ titre: 'Initialiser les prestataires', message }))) return;
			await ticketsApi.creerLot(plan.aCreer.map(versAffaire));
			toast('success', `${plan.aCreer.length} visite(s) posée(s) pour ${exercice}`);
			dispatch('cree');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
		}
	}
</script>

<div class="init-prestataires">
	<label class="field champ-en-ligne">
		<span class="sr-only">Exercice</span>
		<select bind:value={exercice}>
			{#each EXERCICES as a (a)}<option value={a}>{a}</option>{/each}
		</select>
	</label>
	<button class="btn btn-sm btn-outline" on:click={initialiser} disabled={enCours}>
		{enCours ? '⏳ Création…' : '⚙️ Init. prestataires'}
	</button>
</div>

<style>
	.init-prestataires {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		justify-content: flex-end;
		margin-bottom: 0.5rem;
	}
</style>
