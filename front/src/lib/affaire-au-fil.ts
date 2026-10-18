/**
 * Le corps d'une affaire dépliée au fil (`FluxAffaireEtapes`) est celui de la
 * liste Affaires : `CorpsCarteTicket`, chargé au geste. Un seul chargeur NOMMÉ,
 * pour que `FluxCard` le précharge à l'approche de la main (`onApprocher`) et que
 * le dépliage reprenne la même promesse — `import()` ne télécharge qu'une fois
 * (#1860).
 */
export const chargerCorpsAffaire = () => import('$lib/components/CorpsCarteTicket.svelte');
