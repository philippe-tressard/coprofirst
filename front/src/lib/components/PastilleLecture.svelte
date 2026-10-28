<!--
  La PASTILLE DE LECTURE d'une carte — qui d'autre lit cette affaire
  (lot 1, arbitré le 25/09/2026, maquette « Anneau de lecture »).

  - **Une seule couleur**, celle des badges bleus du site ; les icônes sont
    celles des pastilles de Destinataires.
  - **Court sur la carte** (« Copropriétaires », « CS »), la phrase entière
    dans une bulle qui s'ouvre AU TOUCHER : au doigt il n'y a pas de survol, et
    l'infobulle native ne s'y montre pas (leçon du 07/09/2026). À la souris,
    la même phrase est AUSSI dans le `title` (#1311) : elle ne remplace pas
    la bulle, elle évite le clic. La bulle est `Infobulle` (15/10/2026), que
    la posture du registre emploie aussi.
  - **Rien** quand personne n'est exclu — comme le 🔹 du périmètre par défaut.
  - Elle remplace les badges 🔒 « Confidentielle » et 🛡️ « Conseil syndical » :
    le cadenas s'ajoute à droite quand le périmètre est réservé, et « CS » dit
    le reste. Le 🔹 reste à côté : c'est LUI qui dit lequel.

  Deux sortes d'objets (#1373, 27/09/2026) : une AFFAIRE (`ticket`), et un
  objet CIBLÉ — petite annonce, idée, sondage (`cible`) —, qui a sa propre
  règle au serveur. La pastille est la même : elle a remplacé sur leurs cartes
  le badge orange des destinataires, arbitré par l'utilisateur.

  Le calcul vit dans `#lib/lecture` — tenu contre la règle du serveur par
  `lint:lecture` et `test_lecture_pastille.py`. Ici, seulement le rendu.
-->
<script lang="ts">
	import ContenuBadge from '#lib/components/ContenuBadge.svelte';
	import Infobulle from '#lib/components/Infobulle.svelte';
	import {
		lectureDuCiblage,
		lectureDuTicket,
		type ChampsLecture,
		type ObjetCible,
	} from '#lib/lecture-ticket.ts';
	import { titreLecture } from '#lib/lecture.ts';
	import { perimetresStore } from '#lib/stores/perimetres.ts';
	import { relire } from '#lib/utils.ts';

	/** Une affaire — entière, ou telle que le Suivi des affaires la sert (#2089)… */
	export let ticket: ChampsLecture | null = null;
	/** … ou un objet ciblé : annonce, idée, sondage. */
	export let cible: ObjetCible | null = null;
	/** Un sondage : « Qui le lit », « Lu par… ». */
	export let masculin = false;

	//  `$perimetresStore` : l'arbre dit si le périmètre est restreint, et il
	//  arrive après la carte (#947, voir `BadgePerimetre`).
	$: lecture = relire($perimetresStore, () =>
		ticket ? lectureDuTicket(ticket) : lectureDuCiblage(cible ?? {}, masculin),
	);
	$: titre = titreLecture(lecture);
</script>

{#if !lecture.parDefaut}
	<span class="pastille-lecture">
		<Infobulle
			libelle="Qui {masculin ? 'le' : 'la'} lit : {titre}. {lecture.phrase}"
			titre="{titre} — {lecture.phrase} {lecture.exclus}"
		>
			<span class="badge badge-blue pastille-lecture-badge">
				<ContenuBadge
					icones={lecture.icones}
					texte={lecture.court}
					icone={lecture.perimetreReserve ? 'lock' : ''}
				/>
			</span>
			<svelte:fragment slot="bulle">
				<strong>{titre}</strong>
				{lecture.phrase}
				{lecture.exclus}
			</svelte:fragment>
		</Infobulle>
	</span>
{/if}

<style>
	.pastille-lecture {
		display: inline-flex;
		min-width: 0;
	}
	.pastille-lecture-badge {
		min-width: 0;
		max-width: 100%;
	}
</style>
