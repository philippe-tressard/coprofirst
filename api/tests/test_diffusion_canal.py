"""Garde-fou : on DIFFUSE sur le canal de la résidence, on n'« envoie pas un WhatsApp » (#1060).

## Le défaut (28/09/2026)

Cinq appelants écrivaient le même geste à la main : lire la configuration
WhatsApp, vérifier qu'elle est active, puis programmer `envoyer_whatsapp_avec_log`
en tâche de fond avec neuf arguments positionnels. Le transport était donc nommé
partout où l'on voulait seulement « prévenir le groupe » — et changer de canal
(Telegram, Signal, Matrix : une décision de copropriété, pas d'implémentation)
aurait demandé de rouvrir chacun d'eux.

`app/utils/diffusion.py` porte désormais le registre des canaux et les deux gestes
— `config_diffusion` et `diffuser`. Le bridge WhatsApp reste ce qu'il est :
l'ADAPTATEUR du seul canal déclaré.

## Ce que ce test vérifie

Qu'aucun module hors de l'adaptateur et du registre n'importe un geste du
transport : la lecture de sa configuration (`config_whatsapp`) et chacun de ses
gestes d'envoi, dont la liste est tenue par l'adaptateur (`GESTES_D_ENVOI`). Les
exceptions sont NOMMÉES avec leur raison, et le test échoue si l'une cesse de servir.

🔴 Jusqu'au 23/11/2026 (#2977), sa liste en recopiait deux sur trois : un module
qui importait `envoyer_whatsapp_raw` passait. Les deux appelants qui le font, sans
objet derrière, sont déclarés une fois (`aides_transport.SANS_OBJET`) pour les deux
contrôles — `test_groupe_portes`, qui lit les APPELS, fait référence.
"""

from __future__ import annotations

import ast

from app.utils.whatsapp import GESTES_D_ENVOI
from tests.aides_sources import modules_app
from tests.aides_transport import SANS_OBJET

GESTES_DU_TRANSPORT = GESTES_D_ENVOI | {"config_whatsapp"}

EXCEPTIONS = {
    #  Les appelants sans objet derrière — déclarés une fois pour les deux contrôles.
    **SANS_OBJET,
    #  L'adaptateur lui-même, et le registre qui le déclare.
    "utils/whatsapp.py": "l'adaptateur du canal WhatsApp",
    "utils/diffusion.py": "le registre des canaux",
    #  La santé du BRIDGE : c'est l'adaptateur qu'on surveille, pas un envoi.
    "utils/health_monitor.py": "surveille le bridge WhatsApp lui-même",
}


def _importeurs() -> dict[str, set[str]]:
    """{module relatif: gestes du transport qu'il importe} — lu dans l'arbre."""
    trouves: dict[str, set[str]] = {}
    for module in modules_app():
        for noeud in ast.walk(module.arbre):
            if isinstance(noeud, ast.ImportFrom) and noeud.module == "app.utils.whatsapp":
                noms = {a.name for a in noeud.names} & GESTES_DU_TRANSPORT
                if noms:
                    rel = module.rel
                    trouves.setdefault(rel, set()).update(noms)
    return trouves


def test_aucun_appelant_ne_nomme_le_transport():
    fautifs = {f: sorted(n) for f, n in _importeurs().items() if f not in EXCEPTIONS}
    assert not fautifs, (
        "Ces modules importent un geste du transport WhatsApp : passer par "
        "`app.utils.diffusion` (`config_diffusion`, `diffuser`) — #1060.\n"
        + "\n".join(f"  {f} : {', '.join(n)}" for f, n in sorted(fautifs.items()))
    )


def test_les_exceptions_servent():
    importeurs = _importeurs()
    sans_objet = [f for f in EXCEPTIONS if f not in importeurs and f != "utils/whatsapp.py"]
    assert not sans_objet, f"exceptions sans objet, à retirer : {sans_objet}"


def test_le_contrôle_lit_quelque_chose():
    """Cas zéro : un relevé vide dirait « conforme » sans avoir rien lu."""
    assert _importeurs(), "aucun import du transport trouvé : le contrôle ne mesure rien"
