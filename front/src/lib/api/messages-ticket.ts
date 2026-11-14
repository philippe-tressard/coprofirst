/**
 * Corriger ou retirer SON message d'une affaire (#2722) : son auteur, tant que
 * l'affaire n'est pas close. Les routes — `messages._message_de_l_auteur` — refusent
 * le reste ; l'écran ne montre les gestes qu'à qui peut les faire.
 *
 * Étalé dans `tickets` (`index.ts`) : les deux gestes s'appellent `ticketsApi.…`
 * comme l'envoi, et vivent ici parce que `index.ts` est au plafond de modularité.
 */
import { api } from './client';
import type { TicketMessage } from './types';

export const messagesTicket = {
	/** Corriger son message : le texte, et son entrée d'Historique le suit. */
	modifierMessage: (id: number, msgId: number, data: { contenu: string }) =>
		api.patch<TicketMessage>(`/tickets/${id}/messages/${msgId}`, data),
	/** Retirer son message — et son entrée d'Historique. */
	supprimerMessage: (id: number, msgId: number) => api.delete(`/tickets/${id}/messages/${msgId}`),
};
