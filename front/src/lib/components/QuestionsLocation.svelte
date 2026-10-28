<!--
  **Ce que loue le locataire** — trois questions, d'après le fichier des lots.

  ## Pourquoi (signalé à l'écran le 04/10/2026)

  Un locataire dont le propriétaire n'a pas de compte n'était rattaché à rien :
  l'écran lui disait d'attendre que son propriétaire le fasse. Le fichier des lots
  du syndic connaît pourtant les lots de ce propriétaire. Arbitré : le locataire
  répond — appartement, cave, parking —, et chaque « Oui » le rattache tout de
  suite, avec tous les badges du lot (Vigik de l'appartement, télécommandes du
  parking). Ce qui borne ce geste vit côté serveur
  (`api/app/utils/rattachement_locataire.py`) : l'écran ne propose que ce que
  le serveur propose, et le serveur refuse tout autre lot.

  Une question sans lot à proposer ne se pose pas ; sans aucune, le composant
  rend le message d'attente d'avant.
-->
<script lang="ts">
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { lots as lotsApi, type LotPropose, type PropositionsLocation } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { lotTypeLabel } from '#lib/utils.ts';
	import { onMount } from 'svelte';

	/** Appelé une fois le locataire rattaché : la page relit ses lots. */
	export let onRattache: () => void = () => {};

	type Nature = 'appartement' | 'cave' | 'parking';

	const OUI_NON = [
		{ val: 'oui', label: 'Oui' },
		{ val: 'non', label: 'Non' },
	];

	let propositions: PropositionsLocation | null = null;
	let chargement = true;
	let erreur = '';
	let enCours = false;

	/** La réponse à chaque question : `''` tant qu'il n'y en a pas. */
	let reponses: Record<Nature, string> = { appartement: '', cave: '', parking: '' };
	/** L'appartement retenu, quand il y en a plusieurs. */
	let appartementChoisi = '';
	/** Les caves et parkings retenus — tous par défaut, on décoche. */
	let coches: Record<number, boolean> = {};

	onMount(async () => {
		try {
			propositions = await lotsApi.propositionsLocation();
			for (const l of [...propositions.cave, ...propositions.parking]) coches[l.id] = true;
		} catch (e) {
			erreur = messageErreur(e, 'Impossible de lire les lots de votre propriétaire');
		} finally {
			chargement = false;
		}
	});

	$: proposes = (n: Nature): LotPropose[] => propositions?.[n] ?? [];
	$: questions = (['appartement', 'cave', 'parking'] as Nature[]).filter(
		(n) => proposes(n).length > 0,
	);
	$: appartements = proposes('appartement');

	/** « Parking 462 », « Appartement 13 (Bât. 4) » : la nature d'abord, un numéro seul ne dit rien. */
	function libelleLot(l: LotPropose): string {
		return `${lotTypeLabel(l.type)} ${numeroLot(l)}`;
	}
	const numeroLot = (l: LotPropose) => `${l.numero}${l.batiment_nom ? ` (${l.batiment_nom})` : ''}`;

	/** « 2 badges Vigik · 1 télécommande » — ce que le « Oui » remet. */
	function libelleAcces(l: LotPropose): string {
		const vigik = l.acces.vigik ?? 0;
		const tc = l.acces.telecommande ?? 0;
		return [
			vigik ? `${vigik} badge${vigik > 1 ? 's' : ''} Vigik` : '',
			tc ? `${tc} télécommande${tc > 1 ? 's' : ''}` : '',
		]
			.filter(Boolean)
			.join(' · ');
	}

	function question(n: Nature): string {
		if (n === 'appartement') {
			return appartements.length === 1
				? `Résidez-vous dans l’appartement ${numeroLot(appartements[0])} ?`
				: 'Résidez-vous dans l’un de ces appartements ?';
		}
		return n === 'cave'
			? 'Votre location comprend-elle une cave ?'
			: 'Votre location comprend-elle une place de parking ?';
	}

	/** Les lots que les réponses désignent. */
	$: retenus = [
		...(reponses.appartement === 'oui'
			? appartements.length === 1
				? appartements
				: appartements.filter((l) => String(l.id) === appartementChoisi)
			: []),
		...(reponses.cave === 'oui' ? proposes('cave').filter((l) => coches[l.id]) : []),
		...(reponses.parking === 'oui' ? proposes('parking').filter((l) => coches[l.id]) : []),
	];
	$: complet =
		questions.every((n) => reponses[n] !== '') &&
		!(reponses.appartement === 'oui' && appartements.length > 1 && !appartementChoisi);

	async function enregistrer() {
		enCours = true;
		try {
			await lotsApi.declarerLocation(retenus.map((l) => l.id));
			toast('success', 'Vos lots et leurs badges vous sont rattachés');
			onRattache();
		} catch (e) {
			toast('error', messageErreur(e, 'Impossible d’enregistrer vos réponses'));
		} finally {
			enCours = false;
		}
	}
</script>

<EtatListe compact {chargement} {erreur}>
	{#if questions.length === 0}
		<div class="empty-state">
			<h3>Aucun bail actif</h3>
			<p>
				Votre propriétaire doit vous rattacher depuis la section <strong>Gestion locative</strong> de
				son espace.
			</p>
		</div>
	{:else}
		<div class="lots-section-label">🏠 Votre location</div>
		<form class="card largeur-saisie questions" on:submit|preventDefault={enregistrer}>
			<p class="aide">
				D’après le fichier des lots du syndic, voici les lots de votre propriétaire{propositions?.proprietaire
					? ` (${propositions.proprietaire})`
					: ''}. Chaque « Oui » vous rattache au lot et vous remet ses badges.
			</p>
			{#each questions as n (n)}
				<ChoixPastilles
					options={OUI_NON}
					bind:valeur={reponses[n]}
					tous={false}
					radio={`location-${n}`}
					libelle={question(n)}
					libelleVisible
					requis
					defilante={false}
				/>
				{#if reponses[n] === 'oui'}
					{#if n === 'appartement' && appartements.length > 1}
						<ChoixPastilles
							options={appartements.map((l) => ({ val: String(l.id), label: libelleLot(l) }))}
							bind:valeur={appartementChoisi}
							tous={false}
							radio="location-appartement-choisi"
							libelle="Lequel ?"
							libelleVisible
							requis
							defilante={false}
						/>
					{:else if n !== 'appartement'}
						<div class="lots-coches">
							{#each proposes(n) as l (l.id)}
								<label class="checkbox-field">
									<input type="checkbox" bind:checked={coches[l.id]} />
									<span>{libelleLot(l)}</span>
									{#if libelleAcces(l)}<span class="acces">{libelleAcces(l)}</span>{/if}
								</label>
							{/each}
						</div>
					{/if}
					{#if n === 'appartement' && appartements.length === 1 && libelleAcces(appartements[0])}
						<p class="aide">Vous recevrez : {libelleAcces(appartements[0])}.</p>
					{/if}
				{/if}
			{/each}
			<div class="form-actions">
				<button
					type="submit"
					class="btn btn-primary"
					disabled={enCours || !complet || retenus.length === 0}
				>
					{enCours ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
			{#if complet && retenus.length === 0}
				<p class="aide">Aucun lot n’est retenu : rien ne sera rattaché.</p>
			{/if}
		</form>
	{/if}
</EtatListe>

<style>
	/*  Une question, sa phrase d'aide et ses cases forment un bloc : l'écart les
	    sépare du bloc suivant, sinon « Vous recevrez… » collait à la question d'après. */
	.questions {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.lots-coches {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		margin-bottom: 1rem;
	}
	.acces {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
</style>
