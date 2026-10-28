/**
 *  Le BLOC DÉPLIABLE du contenu riche — `<details>` et son `<summary>`.
 *
 *  ## Pourquoi il existe (#992, 17/09/2026)
 *
 *  La synthèse d'un contrat joint en fin de texte les extraits des articles
 *  qu'elle cite. Onze extraits de trente lignes, dépliés, noient la synthèse
 *  qu'ils éclairent — demandé à l'écran : *« les articles de la section 8 ne
 *  sont pas pliés (par défaut) et dépliables »*.
 *
 *  🔴 **Un prompt n'y suffisait pas.** Le texte proposé traverse l'éditeur — le
 *  geste ✨ ouvre le formulaire de correction — et ProseMirror ne garde que ce
 *  que son schéma connaît : un `<details>` non déclaré serait aplati avant même
 *  d'être enregistré. Ces deux nœuds sont ce qui lui donne le droit d'exister.
 *
 *  ## Replié par défaut, et ce n'est pas un choix de style
 *
 *  Un `<details>` s'ouvre quand il porte l'attribut `open`. Cet attribut n'est
 *  PAS dans la liste blanche de `#lib/sanitize` : l'assainisseur le retire, quoi
 *  que le modèle écrive. Le repli n'est donc pas une consigne qu'on espère
 *  respectée, c'est une propriété du rendu.
 *
 *  ## Ce que ces nœuds ne font pas
 *
 *  Aucun bouton de barre d'outils : on ne CRÉE pas un bloc dépliable à la main
 *  dans l'éditeur. Ils servent à **conserver** ce que le modèle produit, et à le
 *  laisser corriger comme le reste du texte. Le jour où quelqu'un veut en poser
 *  un lui-même, c'est un autre lot — et une commande à écrire ici.
 */
import { Node } from '@tiptap/core';

/**
 *  Le titre du bloc, celui qui reste visible replié.
 *
 *  `content: 'inline*'` et non `'block+'` : un résumé est une ligne de texte,
 *  et l'y autoriser un paragraphe ferait un bloc dépliable dont l'en-tête se
 *  déplie lui-même.
 */
export const ResumeDepliable = Node.create({
	name: 'summary',
	content: 'inline*',
	//  `defining` : en corrigeant le texte, une sélection qui englobe le résumé
	//  ne le dissout pas dans le paragraphe voisin.
	defining: true,
	parseHTML: () => [{ tag: 'summary' }],
	renderHTML: ({ HTMLAttributes }) => ['summary', HTMLAttributes, 0],
});

/**
 *  Le bloc lui-même : un résumé, puis au moins un bloc de contenu.
 *
 *  ⚠️ L'ordre est imposé par le schéma (`summary block+`) : c'est ce qui garantit
 *  qu'un bloc sans titre ne peut pas exister — replié, il n'afficherait rien.
 */
export const BlocDepliable = Node.create({
	name: 'details',
	group: 'block',
	content: 'summary block+',
	parseHTML: () => [{ tag: 'details' }],
	renderHTML: ({ HTMLAttributes }) => ['details', HTMLAttributes, 0],
});
