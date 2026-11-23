"""Les appelants d'un geste d'envoi WhatsApp qui n'ont aucun objet derrière (#2143, #2977).

Une liste, lue par les deux contrôles du transport — `test_groupe_portes` (les
APPELS, la référence) et `test_diffusion_canal` (les IMPORTS). Elle vivait dans le
premier seulement, et le second, qui n'en savait rien, ne regardait pas le geste
qu'ils appellent (`envoyer_whatsapp_raw`).
"""

from __future__ import annotations

#: Appelant → pourquoi il nomme le transport : un message saisi par l'administrateur,
#: sans affaire ni publication dont il faudrait lire la réserve.
SANS_OBJET = {
    "utils/whatsapp_scheduler.py": "les messages programmés, saisis par l'administrateur",
    "routers/config.py": "le message de test, saisi par l'administrateur",
}
