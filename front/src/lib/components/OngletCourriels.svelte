<!--
  Espace CS › Courriels — ce que la relève a fait de chaque message reçu à
  l'adresse des affaires, et pourquoi (#1447, ouvert au conseil le 05/10/2026).

  🔴 Un transfert du conseil a été refusé parce que son objet portait `TK-E000066`
  pour `TK-E00066`. Le refus était juste, sa trace n'était lisible que de
  l'administrateur (Paramétrage › SMTP), et la notification — « Transfert non
  versé » — renvoyait vers la liste des affaires. Le journal est ici, à la
  portée de ceux qui transfèrent, avec une pliure par message.

  Jamais le texte du message : il est dans l'affaire ou dans la boîte de
  réception. L'adresse de l'expéditeur n'est lue en entier que par
  l'administrateur — le serveur ne l'envoie pas au conseil.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { courriels, type CourrielReleve } from '#lib/api/index.ts';
	import { fmtDatetimeShort } from '#lib/date.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import JournalVerdicts, {
		type EntreeJournal,
		type TonVerdict,
	} from '#lib/components/JournalVerdicts.svelte';
	import { lienTicket } from '#lib/tickets.ts';

	//  La gravité, pas le nom : un refus est orange — le conseil a été prévenu,
	//  rien n'est cassé —, un message ignoré est gris.
	const VERDICTS: Record<CourrielReleve['decision'], { libelle: string; ton: TonVerdict }> = {
		accepte: { libelle: 'Ajouté au fil', ton: 'succes' },
		relance: { libelle: 'Transmis au conseil', ton: 'info' },
		refuse: { libelle: 'Refusé', ton: 'attention' },
		ignore: { libelle: 'Ignoré', ton: 'neutre' },
	};

	let releves: CourrielReleve[] = [];
	let limite = 0;
	let chargement = true;
	let erreur = '';

	async function charger() {
		chargement = true;
		erreur = '';
		try {
			const journal = await courriels.journal();
			releves = journal.messages;
			limite = journal.limite;
		} catch (e) {
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			chargement = false;
		}
	}

	$: entrees = releves.map((r): EntreeJournal => ({
		cle: r.id,
		titre: r.objet || '(sans objet)',
		sousTitre: r.envoye_le
			? `${r.expediteur} · envoyé le ${fmtDatetimeShort(r.envoye_le)}`
			: r.expediteur,
		verdict: VERDICTS[r.decision]?.libelle ?? r.decision,
		ton: VERDICTS[r.decision]?.ton ?? 'neutre',
		date: r.releve_le,
		texte: r.motif,
		lien: r.ticket_id
			? { href: lienTicket(r.ticket_id), libelle: `Affaire #${r.affaire}` }
			: undefined,
	}));

	onMount(charger);
</script>

{#if chargement || erreur}
	<EtatListe {chargement} {erreur} compact />
{:else}
	<p class="aide largeur-saisie">
		Les {limite} derniers messages reçus à l'adresse des affaires, du plus récent au plus ancien. Un message
		refusé n'est pas perdu : corrigez ce que le motif indique (le plus souvent le numéro d'affaire dans
		l'objet), puis transférez-le de nouveau.
	</p>
	<JournalVerdicts
		{entrees}
		pliable
		recharger={charger}
		vide="Aucun message relevé pour l’instant."
		libelleRecharger="Rafraîchir la liste des courriels"
	/>
{/if}
