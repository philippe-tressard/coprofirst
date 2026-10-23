"""Le manuel PDF s'affiche tout de suite — même après un déploiement (#1071).

## Ce que ce contrôle protège (25/09/2026, arbitré : « visualisation instantanée »)

Trois trous laissaient le premier lecteur attendre les 21 s d'un rendu :

1. **le cache ne survivait pas au redémarrage** — il vivait dans le process ;
2. **deux lecteurs simultanés lançaient deux rendus** complets, chacun dans son
   process, sur un Raspberry Pi ;
3. **le préchauffage abandonnait au premier échec** — or après un déploiement,
   `front` démarre APRÈS l'API, et le manuel n'était pas encore lisible.

⚠️ Aucun test ne rend de PDF : WeasyPrint n'est pas installé sur un poste. Le
moteur est remplacé par un compteur — ce qu'on vérifie, c'est QUAND il est
appelé, pas ce qu'il produit.
"""

from __future__ import annotations

import threading
import time
from datetime import date

import pytest

from app.utils import manuel_pdf as m
from app.utils import manuel_pdf_cache as cache

MANUEL = '<main><h2>Un écran</h2><div class="ecran-card">x</div></main>'
JOUR = date(2026, 9, 25)


@pytest.fixture
def moteur(monkeypatch):
    """Un moteur factice qui compte ses rendus, et une mémoire vide."""
    appels: list[str] = []
    m._cache().clear()
    monkeypatch.setattr(m, "html_to_pdf", lambda doc: appels.append(doc) or b"%PDF-x")
    yield appels
    m._cache().clear()


def _generer(dossier, *, jour=JOUR, manuel=MANUEL, logo_png=None, sous_titre=""):
    return m.generer_manuel_pdf(
        "5Hostachy",
        "https://exemple.fr",
        logo_png=logo_png,
        sous_titre=sous_titre,
        html_manuel=manuel,
        edite_le=jour,
        dossier=dossier,
    )


def test_le_PDF_SURVIT_au_redemarrage(moteur, tmp_path):
    """🔴 Le fait mesuré : mémoire vidée (= redémarrage), aucun rendu refait."""
    premier = _generer(tmp_path)
    m._cache().clear()
    assert _generer(tmp_path) == premier
    assert len(moteur) == 1, "le disque n'a pas servi : le premier lecteur repaie 21 s"


def test_un_manuel_MODIFIE_n_est_jamais_servi_depuis_le_disque(moteur, tmp_path):
    """Le nom du fichier EST l'empreinte : pas d'invalidation à écrire, donc à oublier."""
    _generer(tmp_path)
    m._cache().clear()
    _generer(tmp_path, manuel=MANUEL.replace("Un écran", "Un écran retouché"))
    assert len(moteur) == 2


def test_le_disque_est_BORNE(moteur, tmp_path):
    for i in range(m._CACHE_MAX + 3):
        _generer(tmp_path, jour=date(2026, 9, 1 + i))
    assert len(list(tmp_path.glob("*.pdf"))) == m._CACHE_MAX
    assert not list(tmp_path.glob("*.tmp")), "un fichier provisoire est resté"


def test_UN_SEUL_rendu_pour_deux_lecteurs_simultanes(monkeypatch, tmp_path):
    """🔴 Deux clics sur un cache vide : le second attend le premier, il ne recompose pas."""
    appels: list[str] = []

    def lent(doc):
        appels.append(doc)
        time.sleep(0.3)
        return b"%PDF-x"

    m._cache().clear()
    monkeypatch.setattr(m, "html_to_pdf", lent)
    depart = threading.Barrier(2)
    resultats: list[bytes] = []

    def lecteur():
        depart.wait()
        resultats.append(_generer(tmp_path))

    fils = [threading.Thread(target=lecteur) for _ in range(2)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    m._cache().clear()
    assert resultats == [b"%PDF-x", b"%PDF-x"]
    assert len(appels) == 1, f"{len(appels)} rendus pour un seul document"


def test_un_disque_INUTILISABLE_ne_coute_pas_le_document(moteur, tmp_path):
    """Un disque plein ou en lecture seule perd le cache de demain, pas le PDF d'aujourd'hui."""
    bloque = tmp_path / "fichier"
    bloque.write_text("pas un dossier")
    assert _generer(bloque / "cache") == b"%PDF-x"


def test_le_dossier_vit_dans_app_data_et_HORS_des_uploads(monkeypatch):
    """`uploads` est servi en statique : un PDF posé là serait public."""
    from app.config import Settings, get_settings

    defaut = Settings.model_fields["cache_manuel_dir"].default
    assert defaut == "/app/data/cache-manuel-pdf"
    assert not defaut.startswith(Settings.model_fields["uploads_dir"].default)

    reglages = get_settings()
    monkeypatch.setattr(reglages, "cache_manuel_dir", defaut)
    # `as_posix` : sur un poste Windows, `str` rend « \app\data\… » (rejeu local).
    assert cache.dossier_par_defaut().as_posix() == defaut

    monkeypatch.setattr(reglages, "cache_manuel_dir", "")
    assert cache.dossier_par_defaut() is None


def test_le_prechauffage_ATTEND_le_front(monkeypatch):
    """🔴 Après un déploiement, `front` démarre après l'API : le manuel est
    illisible les premières secondes. Abandonner là, c'était laisser le premier
    lecteur payer le rendu."""
    essais = []

    def front_lent(*_a, **_k):
        essais.append(1)
        if len(essais) < 3:
            raise m.ManuelIndisponible("front pas encore prêt")
        return b"%PDF-x"

    monkeypatch.setattr(m, "generer_manuel_pdf", front_lent)
    assert m.prechauffer("5Hostachy", "https://exemple.fr", logo_png=None, pause_s=0) is True
    assert len(essais) == 3


def test_le_prechauffage_finit_par_RENONCER(monkeypatch):
    essais = []

    def jamais(*_a, **_k):
        essais.append(1)
        raise m.ManuelIndisponible("front absent")

    monkeypatch.setattr(m, "generer_manuel_pdf", jamais)
    assert m.prechauffer("5Hostachy", "https://exemple.fr", logo_png=None, pause_s=0) is False
    assert len(essais) == m.TENTATIVES_PRECHAUFFAGE


def test_un_MOTEUR_en_panne_ne_se_reessaie_pas(monkeypatch):
    """Un rendu cassé le serait encore quinze secondes plus tard."""
    essais = []

    def casse(*_a, **_k):
        essais.append(1)
        raise RuntimeError("moteur indisponible")

    monkeypatch.setattr(m, "generer_manuel_pdf", casse)
    assert m.prechauffer("5Hostachy", "https://exemple.fr", logo_png=None, pause_s=0) is False
    assert len(essais) == 1


# ── Ce que la clé du cache contient (repris de `test_manuel_pdf.py`) ─────────


def test_le_cache_sert_le_MEME_pdf_et_ne_recompose_pas(tmp_path, moteur):
    """🔴 Signalé à l'écran : *« plus de 10 secondes avec une page vide »*.

    WeasyPrint recomposait tout le document à chaque clic. Le résultat ne dépend
    pourtant que du manuel, du site, du logo et de la date — aucun ne change
    entre deux clics.
    """
    assert _generer(tmp_path) == _generer(tmp_path)
    assert len(moteur) == 1, "le document a été recomposé alors qu'il n'a pas changé"


def test_un_manuel_MODIFIE_produit_un_pdf_neuf(tmp_path, moteur):
    """⚠️ La clé est l'EMPREINTE du manuel : toute retouche produit un PDF neuf.

    Le manuel ne porte plus de numéro de version (23/10/2026) ; une clé tenue à
    la main aurait servi un document périmé sans que rien ne le signale.
    """
    _generer(tmp_path)
    _generer(tmp_path, manuel=MANUEL + "<!-- retouche -->")
    assert len(moteur) == 2, "un manuel modifié a servi le PDF de l'ancien"


def test_un_LOGO_change_produit_un_pdf_neuf(tmp_path, moteur):
    """Le logo est DANS la page de garde (#1728) : le changer est un autre PDF.

    Sans lui dans la clé, la résidence qui téléverse son logo aurait reçu le
    manuel au logo neutre jusqu'au lendemain — le PDF du cache, servi de bonne foi.
    """
    _generer(tmp_path)
    _generer(tmp_path, logo_png=b"PNG-factice")
    assert len(moteur) == 2, "le logo a changé, et le PDF servi est l'ancien"
    assert "data:image/png;base64," in moteur[1], "la page de garde ne porte pas le logo"


def test_un_SOUS_TITRE_change_produit_un_pdf_neuf(tmp_path, moteur):
    """Le sous-titre se règle dans Admin › Site : le changer est un autre PDF."""
    _generer(tmp_path)
    _generer(tmp_path, sous_titre="Notre résidence")
    assert len(moteur) == 2, "le sous-titre a changé, et le PDF servi est l'ancien"
    assert "Notre résidence<br>" in moteur[1]


def test_le_cache_est_BORNE(tmp_path, moteur):
    """Une boucle anormale ne doit pas gonfler la mémoire d'un conteneur.

    La date change à minuit : deux entrées suffisent en régime normal. La borne
    existe pour l'anormal, pas pour le nominal.
    """
    for jour in range(1, 12):
        _generer(tmp_path, jour=date(2026, 9, jour))
    assert len(m._cache()) <= m._CACHE_MAX
