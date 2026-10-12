/**
 * Accusés du serveur WhatsApp — « le message envoyé est-il bien arrivé ? »
 *
 * 🔴 Né le 12/10/2026 : CHAQUE envoi au groupe de la résidence était classé
 * « accusé non observé » depuis au moins le 25/09 — six sur six —, alors que
 * tous étaient arrivés. L'administrateur recevait un courriel d'alerte à chaque
 * message, et le bridge se reconnectait de force après chacun.
 *
 * La cause : le bridge n'écoutait que `messages.update`, et Baileys (6.7) ne
 * l'émet JAMAIS pour un envoi à un groupe. Ce qu'il fait réellement :
 *   - l'accusé du SERVEUR (`<ack class="message">`) n'émet aucun événement de
 *     `sock.ev` — seul celui qui porte une erreur devient un `messages.update`
 *     (statut ERROR). Il ne se lit que sur `sock.ws`, `CB:ack,class:message` ;
 *   - les accusés des destinataires d'un GROUPE deviennent des
 *     `message-receipt.update` (un par participant), jamais `messages.update`,
 *     réservé aux conversations individuelles
 *     (`node_modules/baileys/lib/Socket/messages-recv.js`, `handleReceipt`).
 * Le banc de test simulait l'hypothèse au lieu de la bibliothèque — il émettait
 * un `messages.update` « comme en vrai » —, d'où un vert permanent sur un
 * comportement qui n'existait pas (`standards/04`, observer la chose).
 *
 * Les trois sources sont donc écoutées : la première qui parle tranche.
 */

/** Statut d'accusé à partir duquel le serveur a reçu le message (SERVER_ACK). */
const STATUT_SERVEUR = 2;
/** Statut ERROR de Baileys : le serveur a refusé le message. */
const STATUT_ERREUR = 0;

/** Le serveur WhatsApp a REFUSÉ le message : il a répondu, et c'est non. */
class AccuseRefuse extends Error {}

/**
 * Suivi des messages en attente d'accusé.
 *
 * `attendre(id)` rend une promesse : tenue au premier accusé, rejetée par
 * `AccuseRefuse` sur un refus du serveur, ou par une `Error` à l'échéance.
 */
function creerSuiviAccuses({ delaiMs }) {
  const enAttente = new Map(); // id → { tenir, rejeter, minuteur }

  function solder(id, geste, valeur) {
    const attente = enAttente.get(id);
    if (!attente) return false;
    clearTimeout(attente.minuteur);
    enAttente.delete(id);
    attente[geste](valeur);
    return true;
  }

  return {
    attendre(id) {
      return new Promise((tenir, rejeter) => {
        const minuteur = setTimeout(() => {
          solder(id, "rejeter", new Error(`ACK timeout after ${delaiMs}ms — ghost session suspected`));
        }, delaiMs);
        enAttente.set(id, { tenir, rejeter, minuteur });
      });
    },
    confirmer: (id, source) => solder(id, "tenir", source),
    refuser: (id, motif) => solder(id, "rejeter", new AccuseRefuse(`refusé par le serveur WhatsApp : ${motif}`)),
    toutRejeter(motif) {
      for (const id of [...enAttente.keys()]) solder(id, "rejeter", new Error(motif));
    },
    get nombre() {
      return enAttente.size;
    },
  };
}

/** Branche le suivi sur les trois sources d'accusé d'un socket Baileys. */
function brancherAccuses(sock, suivi) {
  // 1. L'accusé du serveur, pour tout envoi — groupe ou individuel.
  sock.ws?.on("CB:ack,class:message", (noeud) => {
    const { id, error } = noeud?.attrs ?? {};
    if (!id) return;
    if (error) suivi.refuser(id, `code ${error}`);
    else suivi.confirmer(id, "serveur");
  });

  // 2. Conversation individuelle : remis / lu, ou l'erreur que Baileys traduit.
  sock.ev.on("messages.update", (majs) => {
    for (const { key, update } of majs) {
      const statut = update?.status;
      if (statut === STATUT_ERREUR) suivi.refuser(key?.id, update?.messageStubParameters?.[0] ?? "erreur");
      else if ((statut ?? -1) >= STATUT_SERVEUR) suivi.confirmer(key?.id, "destinataire");
    }
  });

  // 3. Groupe : un participant l'a reçu — le serveur, a fortiori.
  sock.ev.on("message-receipt.update", (accuses) => {
    for (const { key } of accuses) suivi.confirmer(key?.id, "participant");
  });
}

module.exports = { AccuseRefuse, brancherAccuses, creerSuiviAccuses };
