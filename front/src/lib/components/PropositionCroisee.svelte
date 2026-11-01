<!--
  La PROPOSITION CROISÉE — équipement ⇄ périmètre : choisir l'un PROPOSE l'autre (#2442, arbitré le
  01/11/2026). Un composant sans rendu : il ne porte que la règle, branchée
  sur les deux valeurs liées du formulaire qui l'héberge.

  Les règles sont pures, à côté de `intervenantPropose` (`#lib/formulaire-affaire`) :
  un seul lieu pour l'équipement, un seul équipement pour le lieu — sinon rien ;
  et jamais par-dessus un choix déjà fait. Il ne réagit qu'à un CHANGEMENT : ouvrir
  une affaire existante ne modifie rien.

  `FormulaireTicket` était à 495 lignes : la règle y aurait franchi le plafond de
  modularité, et c'est d'ailleurs une notion à part — elle servira la Suite.
-->
<script lang="ts">
	import { equipementPropose, perimetrePropose } from '#lib/formulaire-affaire.ts';
	import { estPerimetreParDefaut } from '#lib/perimetres/index.ts';
	import { equipementsStore } from '#lib/stores/equipements.ts';

	/** Le code de l'équipement, lié. */
	export let equipement: string;
	/** Les codes du périmètre, liés. */
	export let perimetreCible: string[];
	/** Faux quand la section Équipement est éteinte (hors bâti, résident) : rien n'est proposé. */
	export let actif = true;

	let equipementVu = equipement;
	let perimetreVu = perimetreCible.join();

	//  Une fonction, et non deux blocs `$:` : chacun écrit ce que l'autre lit, et
	//  Svelte refuserait le cycle. Ce qu'elle assigne ne déclenche qu'un nouveau
	//  passage, où les deux valeurs « vues » sont déjà à jour.
	$: proposer(equipement, perimetreCible);

	function proposer(eq: string, lieu: string[]) {
		if (!actif) return;
		if (eq !== equipementVu) {
			equipementVu = eq;
			const propose = perimetrePropose(eq, lieu, estPerimetreParDefaut, $equipementsStore);
			if (propose) [perimetreCible, perimetreVu] = [propose, propose.join()];
		} else if (lieu.join() !== perimetreVu) {
			perimetreVu = lieu.join();
			const propose = equipementPropose(lieu, eq, $equipementsStore);
			if (propose) [equipement, equipementVu] = [propose, propose];
		}
	}
</script>
