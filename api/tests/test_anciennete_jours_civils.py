"""Une ancienneté en jours se pose en jours civils de Paris, pas en 24 h UTC (#2257).

L'application compte `aujourd_hui() - jour_civil(cree_le)`. Un test qui pose
`maintenant() - timedelta(days=N)` pose N × 24 h : passé un changement d'heure, et entre
22 h et 23 h UTC, l'instant tombe le lendemain à Paris — N − 1 jours. Quatre tests
d'ancienneté ont ainsi échoué chaque soir entre 23 h et minuit, y compris sur `main`
seul, sans qu'aucun code ne change (25/10/2026).

La pose se fait par `tests.aides_horloge.il_y_a_jours(N)` (midi de Paris, N jours civils
avant aujourd'hui), et le fichier se rejoue à l'heure hostile (`heure_hostile`).

Ce test refuse une pose en 24 h de plus. Les poses ci-dessous restent parce que
l'application y compare des INSTANTS (échéance, fenêtre glissante, seuil de plusieurs
jours avec une marge) : ±1 jour n'y change rien. Le compte ne fait que baisser — un
fichier converti sort de la liste, le test échoue tant qu'il y figure.
"""

import re
from pathlib import Path

#: fichier de tests → nombre de poses en 24 h tolérées (instants, pas jours civils).
INSTANTS = {
    "test_adoption.py": 3,
    "test_annonce_workflow.py": 2,
    "test_categorie_actualite.py": 3,
    "test_compteurs_tableau_de_bord.py": 1,
    "test_flux_epingle.py": 1,
    "test_points_conseil_validation.py": 2,
    "test_recidive_equipement.py": 1,
    "test_registre_alertes.py": 1,
    "test_registre_installations_admin.py": 1,
    "test_relance_syndic_affaires_suivies.py": 2,
    "test_sauvegarde_hors_site.py": 3,
    "test_sondage_cloture_unique.py": 2,
    "test_sources_affiche.py": 2,
}

#: Les fichiers qui NOMMENT la forme pour l'expliquer (docstring) ne la posent pas.
EXPLICATIONS = {"aides_horloge.py", "test_anciennete_jours_civils.py"}

POSE_EN_24H = re.compile(r"maintenant\(\)\s*-\s*timedelta\(\s*days")
TESTS = Path(__file__).parent


def poses_en_24h() -> dict[str, int]:
    comptes = {}
    for fichier in sorted(TESTS.glob("*.py")):
        if fichier.name in EXPLICATIONS:
            continue
        n = len(POSE_EN_24H.findall(fichier.read_text(encoding="utf-8")))
        if n:
            comptes[fichier.name] = n
    return comptes


def test_aucune_pose_en_24h_de_plus():
    fautes = []
    for nom, n in poses_en_24h().items():
        admis = INSTANTS.get(nom, 0)
        if n > admis:
            fautes.append(
                f"{nom} : {n} pose(s) en 24 h (admis : {admis}) — une ancienneté que l'application "
                "compte en jours se pose par `tests.aides_horloge.il_y_a_jours(N)`"
            )
    assert not fautes, "\n".join(fautes)


def test_la_liste_des_instants_ne_fait_que_baisser():
    """Un fichier converti, ou une pose retirée, sort de la liste : sinon elle couvre la suivante."""
    reel = poses_en_24h()
    obsoletes = [
        f"{nom} : {INSTANTS[nom]} admise(s), {reel.get(nom, 0)} trouvée(s) — ramener le compte"
        for nom in INSTANTS
        if reel.get(nom, 0) < INSTANTS[nom]
    ]
    assert not obsoletes, "\n".join(obsoletes)


def test_le_temoin_la_forme_fautive_est_reconnue():
    """Le cas zéro : le motif voit bien l'écriture qu'il doit refuser."""
    assert POSE_EN_24H.search("cree_le=horloge.maintenant() - timedelta(days=40),")
    assert POSE_EN_24H.search("maintenant() -\n    timedelta(days=3)"), "une ligne coupée reste vue"
    assert not POSE_EN_24H.search("cree_le=il_y_a_jours(40),")
    assert poses_en_24h(), "le balayage ne lit plus rien : le motif ou le dossier est cassé"


def test_les_fichiers_convertis_sont_rejoues_a_l_heure_hostile():
    """Un fichier qui pose par `il_y_a_jours` déclare `heure_hostile` — sinon la conversion ne se prouve pas."""
    manque = []
    for fichier in sorted(TESTS.glob("test_*.py")):
        texte = fichier.read_text(encoding="utf-8")
        if "il_y_a_jours(" in texte and "heure_hostile" not in texte and fichier.name not in EXPLICATIONS:
            manque.append(fichier.name)
    assert not manque, f"pose par il_y_a_jours sans pytestmark heure_hostile : {manque}"
