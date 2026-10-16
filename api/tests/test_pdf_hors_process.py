"""Le rendu PDF sort-il vraiment du process de l'API ? — et y reste-t-il dehors ?

POURQUOI CE TEST (16/09/2026) :

Le rendu des documents imprimables a été isolé dans un process `spawn`, pour que
WeasyPrint ne puisse plus emporter l'API en plantant ou en épuisant la mémoire du
RPi, et pour supprimer la pointe de latence qu'il impose aux requêtes
concurrentes (mesurée : `/health` à 122 ms pendant un rendu, contre 3,3 ms après
— le détail est dans `app/utils/pdf_rendu.py`).

⚠️ Ce module ne corrige aucun « figeage » du site : la première version de ce
fichier l'affirmait, et la mesure l'a démenti. Ce qui est vérifié ici est plus
modeste et plus vrai : le rendu a lieu ailleurs, et il y reste.

Trois propriétés, dont aucune n'est visible à la lecture du code appelant et que
toutes trois peuvent être défaites par une modification d'apparence anodine :

1. **le rendu a lieu ailleurs** — sinon l'isolation n'existe plus, en silence ;
2. **l'enfant est `spawn` et pas `fork`** — un enfant forké hérite des
   connexions du pool de l'API, et peut fermer côté serveur une session qu'elle
   croit encore ouverte ;
3. **le journal de l'enfant remonte** — sans quoi `test_documents_pdf.py`
   ::`test_la_fiche_avec_ses_icones_se_rend_en_pdf` lirait un `caplog` vide et
   deviendrait vert pour toujours. Ce test-ci protège donc un autre test.

⚠️ **La porte, elle, est gardée ailleurs** — et il a fallu casser ce contrôle-là
pour s'en apercevoir : `test_weasyprint_appel_unique.py` vérifiait DÉJÀ que
WeasyPrint n'est appelé qu'à un seul endroit, et il a échoué au premier rejeu de
la CI parce que l'appel avait déménagé. La première version de ce fichier en
avait écrit un second, par ignorance du premier. Il n'en reste qu'un : celui qui
existait, mis à jour, et qui porte maintenant les deux raisons de tenir la porte
fermée (la dérogation de sécurité et l'isolation).
"""

import logging
import os

import pytest

from tests.aides_pdf import besoin_weasyprint

#: Un document minimal : ce qu'on mesure ici est l'isolation, pas la mise en page.
HTML_MINIMAL = "<html><body><h1>Essai</h1><p>Contenu.</p></body></html>"


@besoin_weasyprint
def test_le_rendu_se_fait_dans_un_autre_process():
    """La propriété sur laquelle tout le reste repose : ce n'est pas nous qui rendons.

    L'enfant rapporte son pid dans le message lui-même. Comparer les pid est
    direct et déterministe — là où un test de concurrence (« un thread
    avance-t-il pendant le rendu ? ») dépendrait de la charge de la machine et
    finirait désarmé pour cause d'instabilité. C'est d'ailleurs par une mesure de
    ce genre qu'on a découvert que le rendu en process ne bloquait pas le site :
    elle informe, elle ne verrouille pas.

    ⚠️ Le témoin passait d'abord par le journal, et ce test est né rouge en
    intégration continue pour cette raison — voir `pdf_rendu.dernier_temoin`.
    """
    from app.utils import pdf_rendu
    from app.utils.pdf_theme import html_to_pdf

    contenu = html_to_pdf(HTML_MINIMAL)
    assert contenu[:5] == b"%PDF-", "le rendu ne produit plus un PDF"

    temoin = pdf_rendu.dernier_temoin
    assert temoin, "l'enfant n'a rapporté aucun témoin — ce fichier ne mesure plus rien"
    assert temoin["pid"] != os.getpid(), (
        "le PDF a été rendu DANS le process de l'API : l'isolation a disparu, "
        "un plantage de WeasyPrint emporte de nouveau l'API"
    )


@besoin_weasyprint
def test_l_enfant_n_herite_pas_de_la_base_donc_ce_n_est_pas_un_fork():
    """`spawn` et non `fork` — vérifié par ce que l'enfant a en mémoire.

    On charge délibérément `app.database` **ici**, dans le parent, avant de
    rendre. Un enfant forké hériterait de tout `sys.modules`, donc de ce module
    et des connexions qu'il tient. Un enfant `spawn` démarre d'un interpréteur
    neuf et ne l'a pas.

    On n'affirme pas que le code demande `spawn`, on constate que l'enfant n'a
    pas la base.
    """
    import app.database  # noqa: F401 — l'import EST le dispositif du test

    from app.utils import pdf_rendu
    from app.utils.pdf_theme import html_to_pdf

    html_to_pdf(HTML_MINIMAL)

    temoin = pdf_rendu.dernier_temoin
    assert temoin, "témoin de rendu absent — voir le test précédent"
    assert temoin["base_chargee"] is False, (
        "le process de rendu a la base en mémoire : c'est un fork, et il tient "
        f"donc les connexions de l'API ({temoin!r})"
    )


@besoin_weasyprint
def test_le_journal_de_weasyprint_remonte_au_parent(caplog):
    """Sans ce transfert, un autre test deviendrait vert pour toujours.

    `test_la_fiche_avec_ses_icones_se_rend_en_pdf` conclut « WeasyPrint ne s'est
    pas plaint du document » en lisant `caplog`. Le rendu ayant lieu ailleurs,
    un `caplog` vide s'y lirait comme une absence de plainte — soit exactement
    le faux vert que ce dépôt passe son temps à débusquer.

    On provoque donc une plainte. 🔴 Et le choix de la plainte compte : jusqu'au
    18/09/2026 c'était `box-shadow`, « non supportée, WeasyPrint le dit à chaque
    rendu depuis toujours ». La version 70 la supporte — l'avertissement a
    disparu, et ce test est tombé le jour de la montée de version.

    L'ancre est désormais une propriété qui ne PEUT PAS devenir valide, parce
    qu'elle n'existe dans aucune spécification. Sans tiret initial, volontairement : un analyseur CSS écarte souvent une propriété préfixée EN SILENCE, et le test retomberait dans le même piège par une autre porte. C'est la leçon : un cas zéro
    appuyé sur une LIMITE du moteur se périme quand le moteur progresse ; un cas
    zéro appuyé sur une IMPOSSIBILITÉ, non.
    """
    from app.utils import pdf_rendu
    from app.utils.pdf_theme import html_to_pdf

    html = (
        "<html><head><style>p { propriete-inexistante-hostachy: 1; }</style></head>"
        "<body><p>Contenu.</p></body></html>"
    )
    with caplog.at_level(logging.WARNING, logger="weasyprint"):
        html_to_pdf(html)

    #  Deux mesures, parce qu'un seul vide ne dit pas OÙ il se produit : le
    #  journal brut dit ce que l'enfant a collecté, `caplog` ce qui a survécu au
    #  rejeu dans ce process.
    rapporte = [(n, m[:60]) for n, _niv, m in pdf_rendu.dernier_journal]
    assert any("propriete-inexistante" in m for _n, _niv, m in pdf_rendu.dernier_journal), (
        "l'ENFANT n'a pas collecté la plainte de WeasyPrint — le transfert n'est "
        f"pas en cause, la collecte l'est. Journal rapporté : {rapporte}"
    )

    plaintes = [r.getMessage() for r in caplog.records if r.name.startswith("weasyprint")]
    assert any("propriete-inexistante" in p for p in plaintes), (
        "la plainte de WeasyPrint n'est pas remontée du process de rendu : tout "
        "contrôle qui lit caplog est devenu aveugle — à commencer par "
        "`test_la_fiche_avec_ses_icones_se_rend_en_pdf`, qui conclut « aucune "
        "plainte » sur un caplog vide. L'enfant l'avait pourtant collectée : le "
        "rejeu est donc en cause dans CE process. "
        f"Plaintes weasyprint reçues : {plaintes}. "
        f"Tous les enregistrements : {[(r.name, r.getMessage()[:60]) for r in caplog.records]}"
    )


@besoin_weasyprint
def test_un_rendu_trop_long_est_abandonne_proprement():
    """Le chemin d'erreur, exercé — et non seulement écrit.

    Un délai d'une milliseconde ne peut pas être tenu : démarrer un interpréteur
    `spawn` en demande plusieurs centaines. On vérifie que l'attente s'arrête,
    qu'elle le dit franchement, et qu'elle ne rend surtout pas un document
    partiel.
    """
    from app.utils.pdf_rendu import RenduPdfImpossible, rendre_pdf

    with pytest.raises(RenduPdfImpossible) as echec:
        rendre_pdf(HTML_MINIMAL, delai_s=0.001)

    assert "abandonné" in str(echec.value)
