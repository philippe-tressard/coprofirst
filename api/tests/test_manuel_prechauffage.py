"""Le manuel en PDF est préchauffé — personne n'attend 21 secondes.

## Ce que ce contrôle protège (18/09/2026)

Le cache du manuel vivait dans le process : il repartait vide à chaque
déploiement. Depuis #1071 il est doublé sur disque, mais un manuel MODIFIÉ change
sa clé. Le prix en était payé par le premier lecteur d'après, et il a été MESURÉ
en production : **21,1 secondes**, contre 0,15 s ensuite.

Deux rendez-vous le remplissent d'avance — vingt secondes après le démarrage, et
chaque nuit à 00:05. Le second n'est pas un luxe : la clé du cache porte la DATE
d'édition, donc sans lui le premier lecteur de chaque jour repaierait l'attente.

⚠️ Ce test ne rend AUCUN PDF : WeasyPrint n'est pas installé sur un poste, et
exiger un rendu ici rendrait le contrôle INCONNU plutôt que vert. Il vérifie ce
qui peut l'être partout : que le préchauffage existe et qu'il est bien PLANIFIÉ
— écrire une fonction et la brancher sont deux gestes. Qu'il ne lève jamais (un
manuel indisponible n'empêche pas l'application de démarrer) est vérifié par
`test_manuel_pdf_cache.py::test_un_MOTEUR_en_panne_ne_se_reessaie_pas`.
"""

from __future__ import annotations

import inspect


def test_le_prechauffage_garnit_le_cache(monkeypatch):
    """Le fait, pas l'intention : après l'appel, le rendu a bien eu lieu."""
    from app.utils import manuel_pdf

    appels = []

    def _compte(nom, url, **_k):
        appels.append((nom, url))
        return b"%PDF-1.7 factice"

    monkeypatch.setattr(manuel_pdf, "generer_manuel_pdf", _compte)
    assert manuel_pdf.prechauffer("5Hostachy", "https://exemple.test", logo_png=None) is True

    assert appels == [("5Hostachy", "https://exemple.test")]


def test_les_deux_rendez_vous_sont_PLANIFIES():
    """Écrire une fonction et la brancher sont deux gestes (`standards/05`).

    Le second rendez-vous — celui de minuit — est vérifié nommément : c'est
    celui qu'on retire par mégarde en croyant qu'il fait double emploi avec le
    premier, alors qu'il couvre le changement de DATE dans la clé du cache.
    """
    from app import main

    source = inspect.getsource(main.lifespan)
    assert "manuel_pdf_prechauffage" in source, (
        "le préchauffage au démarrage n'est plus planifié : le premier lecteur "
        "après un déploiement attendra de nouveau le rendu complet."
    )
    assert "manuel_pdf_quotidien" in source, (
        "le rendez-vous de minuit a disparu : la clé du cache porte la date, "
        "donc le premier lecteur de chaque jour repaiera l'attente."
    )
    assert "prechauffer" in source
