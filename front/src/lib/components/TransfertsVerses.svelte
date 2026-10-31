<!--
  TransfertsVerses.svelte — les transferts de courriel versés dans cette
  affaire, et les gestes qui les défont (#1482, 30/09/2026).

  Un fil transféré à l'adresse des affaires y entre en autant de Suites que de
  messages. Versé au mauvais endroit, il s'ANNULE, se DÉPLACE vers une autre
  affaire, ou devient une AFFAIRE NEUVE — en un geste. La règle est au serveur
  (`api/app/utils/versement_transfert.py`) ; cet écran ne rejoue rien :

  - la liste ne contient que les transferts que le lecteur peut défaire —
    celui qui a transféré, ou l'administrateur ; vide, le bloc ne se rend pas ;
  - `bloque` dit pourquoi un transfert ne se défait pas ENCORE — un transfert
    suivant, toujours défaisable, le retient —, et ses boutons disparaissent :
    on ne propose pas un geste refusé — au plus un transfert à la fois les
    porte. Celui que plus rien ne rouvrira (une suite écrite depuis, un
    suivant validé) n'est pas dans la liste (14/10/2026) : il y restait sous
    « Ne peut plus être défait », avec « Valider » pour seul bouton ;
  - `peut_deplacer` : déplacer exige de modérer ;
  - « Valider le transfert » (13/10/2026) — « si c'est ok et pour faire
    disparaître ces boutons » : le transfert reste versé, quitte la liste et ne
    se défait plus. Offert aussi sur un transfert retenu par un suivant.

  🔴 Rendu sur la fiche ET dans la carte dépliée de la liste (01/10/2026). Il
  n'était que sur la fiche, « là que mène la notification » — et la carte n'a
  aucun lien vers la fiche : son 🔗 COPIE l'adresse. Un transfert versé par
  erreur sur TK-109008 ne se défaisait donc que si l'on retrouvait la
  notification ou le journal des relèves. Le coût est une lecture par
  dépliage, comme le fil ; vide, le bloc ne rend rien.

  `encadre={false}` dans la carte : pas de carte dans la carte (#425), le titre
  descend d'un cran sous celui de la carte.
-->
<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { tickets as ticketsApi } from '#lib/api/index.ts';
	import type { AffaireLiee, AffaireVisee, TransfertVerse } from '#lib/api/types.ts';
	import ChoixAffaire from '#lib/components/ChoixAffaire.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { confirmer } from '#lib/confirmation.ts';
	import { fmtDatetime } from '#lib/date.ts';
	import { TICKET } from '#lib/entites/ticket.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let ticketId: number;
	/** `false` dans la carte d'une liste : pas de carte dans la carte (#425). */
	export let encadre = true;

	/** L'affaire a changé sous les yeux : la page recharge ce qu'elle montre. */
	const dispatch = createEventDispatcher<{ change: void }>();

	let transferts: TransfertVerse[] = [];
	/** Le transfert dont on choisit l'affaire de destination. */
	let deplace: number | null = null;
	let enCours = false;

	async function charger() {
		try {
			transferts = await ticketsApi.transferts(ticketId);
		} catch (e) {
			//  Dit, jamais avalé : sans la liste, on ne saurait pas qu'un geste existe.
			toast('error', messageErreur(e));
		}
	}

	onMount(charger);

	const suites = (t: TransfertVerse) => `${t.suites} suite${t.suites > 1 ? 's' : ''}`;

	/** Ce qui arrive à l'affaire ouverte, dit avant le geste. */
	function ceQuiReste(t: TransfertVerse): string {
		return t.affaire_creee
			? `Cette ${TICKET.libelle.toLowerCase()}, créée par le transfert, sera archivée.`
			: `Les ${suites(t)} versées par ce transfert quitteront cette ${TICKET.libelle.toLowerCase()}.`;
	}

	async function geste(appel: () => Promise<AffaireVisee>, fait: string) {
		enCours = true;
		try {
			const visee = await appel();
			toast('success', fait);
			deplace = null;
			if (visee.ticket_id !== ticketId) {
				//  Une navigation complète : la fiche charge au montage, et SvelteKit
				//  garderait ce composant pour un autre identifiant.
				window.location.href = `/tickets/${visee.ticket_id}`;
				return;
			}
			await charger();
			dispatch('change');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
		}
	}

	async function annuler(t: TransfertVerse) {
		const ok = await confirmer({
			titre: 'Annuler le transfert',
			message: `${ceQuiReste(t)} Le fil pourra être transféré de nouveau.`,
			libelleConfirmer: 'Annuler le transfert',
			libelleAnnuler: 'Garder',
			danger: true,
		});
		if (ok) await geste(() => ticketsApi.annulerTransfert(ticketId, t.id), 'Transfert annulé');
	}

	async function valider(t: TransfertVerse) {
		const ok = await confirmer({
			titre: 'Valider le transfert',
			message: `Le transfert reste dans cette ${TICKET.libelle.toLowerCase()} : il quitte cette liste et ne pourra plus être annulé ni déplacé.`,
			libelleConfirmer: 'Valider',
			libelleAnnuler: 'Revenir',
		});
		if (ok) await geste(() => ticketsApi.validerTransfert(ticketId, t.id), 'Transfert validé');
	}

	async function versAffaire(t: TransfertVerse, a: AffaireLiee) {
		const ok = await confirmer({
			titre: 'Déplacer le transfert',
			message: `${ceQuiReste(t)} Elles rejoindront ${a.numero} — ${a.titre}, sans doubler ce qui y est déjà.`,
			libelleConfirmer: 'Déplacer',
		});
		if (ok)
			await geste(
				() => ticketsApi.deplacerTransfert(ticketId, t.id, a.id),
				`Transfert déplacé vers ${a.numero}`,
			);
	}

	async function versNouvelle(t: TransfertVerse) {
		const ok = await confirmer({
			titre: TICKET.libelleNouveau,
			message: `${ceQuiReste(t)} Une ${TICKET.libelle.toLowerCase()} neuve les reçoit, décrite par le premier message, au nom de son auteur.`,
			libelleConfirmer: 'Créer',
		});
		if (ok)
			await geste(
				() => ticketsApi.deplacerTransfert(ticketId, t.id, null),
				`${TICKET.libelle} créée`,
			);
	}
</script>

{#if transferts.length > 0}
	<section
		class="transferts"
		class:card={encadre}
		class:colonne-lecture={encadre}
		class:dans-carte={!encadre}
		aria-labelledby="transferts-titre-{ticketId}"
	>
		<h2 id="transferts-titre-{ticketId}" class="transferts-titre">
			<Icon name="inbox" size={16} /> Transferts de courriel
		</h2>
		{#each transferts as t (t.id)}
			<div class="transfert">
				<p class="transfert-quoi">
					{fmtDatetime(t.cree_le)}{SEPARATEUR.tiret}transféré par {t.transfere_par_nom}{SEPARATEUR.point}{suites(
						t,
					)}{t.affaire_creee ? ` · ${TICKET.libelle.toLowerCase()} créée` : ''}
				</p>
				{#if t.bloque}
					<p class="aide">Ne se défait pas encore : {t.bloque}.</p>
				{/if}
				<div class="transfert-gestes">
					<button
						type="button"
						class="btn btn-primary btn-sm"
						disabled={enCours}
						on:click={() => valider(t)}>Valider le transfert</button
					>
					{#if !t.bloque}
						<button
							type="button"
							class="btn btn-outline btn-sm"
							disabled={enCours}
							on:click={() => annuler(t)}>Annuler le transfert</button
						>
						{#if t.peut_deplacer}
							<button
								type="button"
								class="btn btn-outline btn-sm"
								aria-expanded={deplace === t.id}
								disabled={enCours}
								on:click={() => (deplace = deplace === t.id ? null : t.id)}
								>Déplacer vers une autre {TICKET.libelle.toLowerCase()}</button
							>
							{#if !t.affaire_creee}
								<button
									type="button"
									class="btn btn-outline btn-sm"
									disabled={enCours}
									on:click={() => versNouvelle(t)}
									>En faire une nouvelle {TICKET.libelle.toLowerCase()}</button
								>
							{/if}
						{/if}
					{/if}
				</div>
				{#if !t.bloque}
					{#if deplace === t.id}
						<div class="transfert-cible">
							<ChoixAffaire
								id="transfert-{t.id}-cible"
								libelle="Vers l’{TICKET.libelle.toLowerCase()}"
								exclure={[ticketId]}
								sansCloses
								on:choisir={(e) => versAffaire(t, e.detail)}
							/>
						</div>
					{/if}
				{/if}
			</div>
		{/each}
	</section>
{/if}

<style>
	.transferts {
		margin-bottom: 1rem;
	}
	/*  Dans la carte : posé comme le fil qu'il précède (`.tk-fil`), un filet
	    au-dessus au lieu d'un cadre, et le titre au corps d'une section. */
	.dans-carte {
		margin: 0.9rem 0 0;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
	}
	.dans-carte .transferts-titre {
		font-size: var(--fs-md);
	}
	.transferts-titre {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: var(--fs-lg);
		font-weight: 600;
		margin: 0 0 0.5rem;
	}
	.transfert + .transfert {
		margin-top: 0.75rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
	}
	.transfert-quoi {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0 0 0.4rem;
	}
	.transfert-gestes {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.transfert-cible {
		margin-top: 0.6rem;
	}
</style>
