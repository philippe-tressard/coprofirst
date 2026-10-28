<!--
  L'étage de chacun de mes LOGEMENTS (#835).

  🔴 DEUX étages, deux natures, et c'est pour cela qu'ils vivent dans le MÊME
  composant : `Utilisateur.etage` est l'endroit où l'on VIT, `Lot.etage` un bien du
  patrimoine. Un bailleur a un lot au 4ᵉ et habite ailleurs. Les séparer dans deux
  fichiers inviterait à écrire l'un pour l'autre.

  ⚠️ Le champ personnel a été RETIRÉ le matin du 09/09/2026 — « deux champs Étage à
  trois lignes d'écart » — puis REDEMANDÉ le soir même, quand un compte de test sans
  lot s'est retrouvé sans aucun moyen de dire où il habite. Les deux arbitrages sont
  justes : c'est la RESSEMBLANCE des deux champs qui était le défaut, pas leur
  nombre. D'où, cette fois, deux libellés qui ne peuvent pas se confondre — « où
  j'habite » contre « mes logements » — et un seul des deux qui parle du bien.

  🔴 Quand un logement de référence existe, sa valeur est PROPOSÉE dans le champ
  personnel : personne ne devrait ressaisir ce que le site détient déjà. La
  désignation de ce logement vient de l'API (`est_logement_de_reference`), jamais
  d'un calcul refait ici — voir `etageDuLot` dans `#lib/utils`.

  ⚠️ PAS d'indication sous ce bloc. Elle disait « Facultatif. L'étage du bien
  lui-même — il apparaît sur les fiches et les affiches ». Retirée le 09/09/2026 :
  « facultatif » se voit à l'absence d'astérisque, et où la valeur ressort ne dit
  rien à qui la saisit. Une indication n'a de valeur que si elle apprend quelque
  chose — sinon elle allonge l'écran et s'apprend à ne plus être lue.

  🔴 SEULS LES LOGEMENTS sont listés — pas les caves ni les parkings. « Étage de
  chacun de mes logements » énumérait « N° 417 Cave » et « N° 450 Parking », qui
  n'en sont pas : un titre qui ment sur son contenu se corrige par le contenu,
  pas par le titre (arbitrage à l'écran, 09/09/2026). Leur étage se règle depuis
  l'administration du patrimoine, comme avant.
-->
<script lang="ts">
	import { auth as authApi, lots as lotsApi, type MonLot, type User } from '#lib/api/index.ts';
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	import { currentUser } from '#lib/stores/auth.ts';
	import { ETAGE_MAX, ETAGE_MIN, etageDuLot, etageLabel, lotTypeLabel } from '#lib/utils.ts';

	/**  L'étage de CHAQUE logement, par identifiant — donnée de patrimoine. */
	export let etagesLot: Record<number, number | null> = {};
	export let lots: MonLot[] = [];

	/**  L'étage où l'on VIT — `Utilisateur.etage`, saisi à l'inscription puis
	 *   modifiable ici. Sans validation du conseil syndical, délibérément : il ne
	 *   revendique rien, c'est un repère de voisinage comme le téléphone.
	 *
	 *   🔴 Lu DEPUIS LE STORE, et non reçu en propriété : l'écran du profil passe
	 *   déjà le plafond de modularité, et il n'a rien à faire de cette valeur
	 *   qu'il ne ferait que transporter. Le composant qui saisit une donnée est
	 *   celui qui sait la lire comme celui qui sait l'écrire.
	 *
	 *   ⚠️ `?? null` et jamais `|| null` : `0` est le rez-de-chaussée, et un test
	 *   de vérité le rendrait « non renseigné ». */
	let etage: number | null = $currentUser?.etage ?? null;

	/**  L'étage que le classeur de la copropriété connaît, ou `null`. */
	$: etageLot = etageDuLot(lots);

	/**  Proposé, jamais imposé : une valeur SAISIE ne se remplace pas par une
	 *   déduction, même juste — c'est l'utilisateur qui a raison sur où il vit.
	 *   ⚠️ `== null` et non un test de vérité : `0` est le rez-de-chaussée. */
	$: if (etage == null && etageLot != null) etage = etageLot;

	/**  Les deux se contredisent-ils ? L'écran le DIT, il ne tranche pas : c'est
	 *   l'administrateur du site qui vérifie, prévenu par courriel au moment de
	 *   l'enregistrement (`api/app/utils/alerte_etage.py`). */
	$: divergence = etage != null && etageLot != null && etage !== etageLot;

	/**  Les LOGEMENTS seuls : une cave et un parking ont un niveau, pas un étage
	 *   d'habitation, et les lister sous « mes logements » était faux. Le filtre
	 *   porte sur le type, jamais sur une liste de types à exclure — un type
	 *   ajouté demain serait alors inclus par défaut, ce qui est le mauvais sens. */
	$: logements = lots.filter((l) => l.type === 'appartement');

	/**  Enregistre les étages de lots MODIFIÉS, et rend la liste à jour.
	 *
	 *   L'écriture vit ici plutôt que dans la page : `Lot.etage` est une autre
	 *   table, une autre règle d'accès (le lot doit m'être rattaché) et une autre
	 *   route que `Utilisateur.etage`. Le composant qui saisit une donnée est
	 *   celui qui sait comment elle s'enregistre.
	 *
	 *   ⚠️ Seuls les lots CHANGÉS partent : réécrire les autres poserait un
	 *   `modifie_le` sur des lignes que personne n'a touchées. */
	export async function enregistrerEtagesDeLots(): Promise<MonLot[]> {
		const changes = logements.filter((l) => (l.etage ?? null) !== (etagesLot[l.id] ?? null));
		const majs = await Promise.all(
			changes.map((l) => lotsApi.majEtage(l.id, etagesLot[l.id] ?? null)),
		);
		const parId = new Map(majs.map((m) => [m.id, m]));
		lots = lots.map((l) => parId.get(l.id) ?? l);
		return lots;
	}

	/**  Enregistre l'étage PERSONNEL et rend le compte à jour.
	 *
	 *   Ici et non dans la page, pour la même raison que les étages de lots : le
	 *   composant qui saisit une donnée est celui qui sait comment elle
	 *   s'enregistre. La page appelle les deux, sans connaître ni les deux tables
	 *   ni les deux routes.
	 *
	 *   ⚠️ Envoyé même à `null` : effacer son étage est un geste, et `update_me`
	 *   n'écrit que ce qu'il reçoit — un champ omis ne s'efface jamais. */
	export async function enregistrerEtagePersonnel(): Promise<User> {
		return authApi.updateMe({ etage });
	}
</script>

<!--  🔴 L'étage où l'on VIT — rendu SEULEMENT quand aucun logement ne le dit
      déjà (10/09/2026, régression signalée à l'écran : « l'étage est en double,
      on avait dit de conserver uniquement ceux des lots »).

      La règle existait, écrite le 08/09 : *« afficher deux fois le même chiffre
      inviterait à les désaccorder »*. En remettant ce champ le 09/09 pour le cas
      d'un compte SANS lot, je ne l'ai pas rappliquée — le bloc « mes logements »
      apparaît depuis le 09/09 dès UN logement, et les deux champs se sont
      retrouvés côte à côte avec la même valeur.

      ⚠️ Ce n'est pas un troisième revirement : les deux demandes tiennent
      ensemble. *Un seul champ à l'écran*, et c'est le logement qui parle quand il
      existe — le champ personnel n'est là que pour ceux qu'aucun lot ne situe.

      ⚠️ Le bailleur qui habite ailleurs qu'à son lot ne peut donc plus le
      déclarer ici. C'est le coût, assumé une seconde fois : l'écran gagne en
      clarté ce que ce cas précis perd en précision. -->
{#if logements.length === 0}
	<div class="field">
		<label for="p-etage">Étage où j'habite</label>
		<input
			id="p-etage"
			type="number"
			bind:value={etage}
			min={ETAGE_MIN}
			max={ETAGE_MAX}
			placeholder="Ex. 3"
			aria-describedby={divergence ? 'p-etage-divergence' : undefined}
		/>
		<!--  L'indication dit la CONVENTION de saisie, pas l'évidence : « facultatif »
	      se voit à l'absence d'astérisque, et où la valeur ressort n'apprend rien à
	      qui la saisit. Que `0` vaille rez-de-chaussée, en revanche, ne se devine
	      pas — c'est la seule chose qu'un champ « Étage » ne dit pas tout seul. -->
		<!--  ⚠️ PAS de « -1 = sous-sol », bien que la borne basse l'autorise encore
	      (arbitrage de Philippe, 09/09/2026) : aucun LOGEMENT n'est en sous-sol
	      — il n'y a là que des caves et des parkings —, et proposer cette valeur
	      à quelqu'un qui déclare où il HABITE est dévalorisant pour rien.

	      L'exemple positif dit pourtant la même chose de la convention : ce qui
	      manquait, c'était de montrer la FORME attendue, pas d'énumérer les cas
	      limites. Un exemple en dit autant qu'une règle et ne heurte personne. -->
		<p class="aide">0 = rez-de-chaussée, 2 = 2ème étage.</p>
		{#if divergence}
			<EncartAvertissement compact id="p-etage-divergence" role="status">
				⚠️ Votre logement est enregistré au <strong
					>{etageLabel(etageLot, { suffixe: true })}</strong
				>. C'est cette valeur qui s'affiche dans l'annuaire. Votre saisie est conservée et le
				gestionnaire du site est prévenu pour vérifier.
			</EncartAvertissement>
		{/if}
	</div>
{/if}

{#if logements.length > 0}
	<div class="field">
		<!--  `.libelle-groupe` + `role="group"` : un `<label>` ne sait pas nommer un
		      groupe de contrôles — posé dessus, il n'associe rien, ET IL LE FAIT EN
		      SILENCE (`champs.css`, #561). -->
		<!--  Le titre S'ACCORDE : un logement dans la plupart des cas, plusieurs pour
		      un multipropriétaire. « Étage de chacun de mes logements » au-dessus
		      d'une seule ligne annonce un choix qui n'existe pas. -->
		<span class="libelle-groupe" id="p-etages-lots">
			{logements.length === 1 ? 'Étage de mon logement' : 'Étages de chacun de mes logements'}
		</span>
		<div class="etages-lots" role="group" aria-labelledby="p-etages-lots">
			{#each logements as lot (lot.id)}
				<div class="etage-lot">
					<label for={`p-etage-lot-${lot.id}`}>
						<!--  Les deux espaces autour du tiret sont INSÉCABLES : écrites en
						      blanc elles disparaissaient au reformatage, et `&#32;` était
						      recollée par le navigateur — le libellé rendait « Bât. 4 —N° 15 ».
						      Une espace insécable ne se réduit ni ne se replie. -->
						{#if lot.batiment_nom}{lot.batiment_nom}&nbsp;—&nbsp;{/if}N° {lot.numero}
						<span class="etage-lot-type">{lotTypeLabel(lot.type)}</span>
					</label>
					<input
						id={`p-etage-lot-${lot.id}`}
						type="number"
						bind:value={etagesLot[lot.id]}
						min={ETAGE_MIN}
						max={ETAGE_MAX}
						placeholder="Ex. 3"
					/>
				</div>
			{/each}
		</div>
	</div>
{/if}

<style>
	/*  Un logement par ligne : son identité à gauche, son étage à droite. La
	    grille tient sur un téléphone parce que la colonne du champ est FIXE et
	    celle du libellé élastique — l'inverse aurait écrasé le libellé sur les
	    numéros longs (« Bât. 3 — N° 412 · appartement »). */
	.etages-lots {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.etage-lot {
		display: grid;
		grid-template-columns: 1fr 6rem;
		align-items: center;
		gap: 0.5rem 0.75rem;
	}
	.etage-lot label {
		font-weight: 400;
		color: var(--color-text-muted);
	}
	.etage-lot-type {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	/*  44 px : une cible tactile est une taille PHYSIQUE, celle d'un pouce — elle
	    ne suit pas la typographie (#839, où `2.75rem` avait rendu 33 px, la racine
	    valant alors 12 px en émulation mobile, 14 depuis #2165). */
	.etage-lot input {
		min-height: 44px;
	}
	/*  Sous 480 px, la grille à deux colonnes serre le champ : on empile. */
	@media (max-width: 480px) {
		.etage-lot {
			grid-template-columns: 1fr;
		}
	}
</style>
