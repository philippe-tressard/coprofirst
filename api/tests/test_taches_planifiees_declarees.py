"""Une tâche planifiée qui disparaît doit prévenir quelqu'un.

## Le constat (#1047, audit du 19/09/2026)

Sept tâches tournent en permanence, enregistrées à trois endroits — et **aucun
test ne citait un seul identifiant**. Trois fichiers de test les concernaient
(`test_taches_planifiees.py`, `test_sante_taches_forme.py`, `test_taches_sante.py`) :
ils vérifiaient des formes, jamais la liste.

Un `add_job` supprimé par mégarde laisse donc l'application démarrer normalement.
La sauvegarde ne se fait plus, et on l'apprend le jour d'une restauration.
« Une tâche planifiée qui disparaît ne prévient personne » (`standards/07` §5).

## Ce que ce test vérifie, et ce qu'il ne peut pas voir

Il confronte `utils/taches.TACHES_PERMANENTES` aux `scheduler.add_job(...)` du
code, **dans les deux sens** : une tâche déclarée sans enregistrement, et un
enregistrement sans déclaration.

⚠️ Il lit le **code**, pas l'exécution : un `add_job` qu'une condition saute au
démarrage lui paraît présent. C'est pourquoi la table sert **aussi** au
démarrage — `verifier_taches_enregistrees` compare ce qui tourne vraiment, dans
le process, et journalise l'écart. Aucun des deux contrôles ne suffit seul
(`standards/04` §12 — un contrôle borné dit ce qu'il ne couvre pas).
"""

import ast
import logging
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1] / "app"

from app import contexte  # noqa: E402
from app.utils.taches import TACHES_DE_LA_PLATEFORME, TACHES_PERMANENTES  # noqa: E402
from tests.aides_sources import modules_app  # noqa: E402


def _ids_enregistres() -> set[str]:
    """Les identifiants littéraux passés à un `scheduler.add_job(...)`."""
    ids = set()
    for m in modules_app():
        for noeud in ast.walk(m.arbre):
            if not (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)):
                continue
            if noeud.func.attr != "add_job":
                continue
            for mot in noeud.keywords:
                if mot.arg == "id" and isinstance(mot.value, ast.Constant):
                    ids.add(mot.value.value)
    return ids


def test_chaque_tache_declaree_est_enregistree():
    """Une tâche qui quitte le code sans quitter la table serait invisible."""
    manquantes = sorted(set(TACHES_PERMANENTES) - _ids_enregistres())
    assert not manquantes, (
        "Tâche(s) déclarée(s) qu'aucun `add_job` n'enregistre :\n"
        + "\n".join(f"  • {m} — on perd : {TACHES_PERMANENTES[m]}" for m in manquantes)
        + "\n\nSoit l'enregistrement a disparu (et il faut le remettre), soit la tâche "
        "n'existe plus (et il faut retirer sa ligne de `utils/taches.py`)."
    )


def test_aucune_tache_permanente_non_declaree():
    """L'autre sens : ce qui tourne sans être déclaré n'a pas de coût écrit.

    Le jour où elle tombe, personne ne sait ce qu'on vient de perdre — c'est
    précisément ce qui rendait la disparition indolore.
    """
    #  Les rattrapages ne sont pas des tâches permanentes : exclus par leur
    #  identifiant exact, la même source que le contrôle au démarrage (#1589).
    from app.utils.rattrapage import identifiants_rattrapage

    non_declarees = sorted(_ids_enregistres() - set(TACHES_PERMANENTES) - identifiants_rattrapage())
    assert not non_declarees, (
        f"Tâche(s) enregistrée(s) sans déclaration : {non_declarees}\n"
        f"Les inscrire dans `utils/taches.TACHES_PERMANENTES` **avec ce qu'on perd** "
        f"si elles cessent de tourner — c'est cette phrase qui permet de trancher, "
        f"en cas d'écart, s'il faut intervenir tout de suite."
    )


def test_la_table_n_est_pas_vide():
    """Cas zéro : une table vide rend les deux tests ci-dessus verts.

    Ils ne comparent que des ensembles ; vider la table les satisfait tous les
    deux en ayant supprimé la seule liste qui dise ce qui doit tourner.
    """
    assert len(TACHES_PERMANENTES) >= 5, (
        f"`TACHES_PERMANENTES` n'en porte plus que {len(TACHES_PERMANENTES)} : "
        f"le dépôt en enregistre {len(_ids_enregistres())}. Une table vide rendrait "
        f"ce contrôle vert sans rien mesurer."
    )


def test_le_controle_au_demarrage_existe_et_est_appele():
    """Le test statique ne voit pas un `add_job` qu'une condition saute.

    C'est la raison d'être du contrôle au démarrage : sans lui, ce fichier
    donnerait l'illusion d'une couverture qu'il n'a pas.
    """
    taches = (RACINE / "utils" / "taches.py").read_text(encoding="utf-8")
    assert "def verifier_taches_enregistrees" in taches, (
        "`verifier_taches_enregistrees` a disparu : il ne reste plus que l'analyse "
        "statique, aveugle à ce qui est sauté à l'exécution."
    )
    main = (RACINE / "main.py").read_text(encoding="utf-8")
    assert "verifier_taches_enregistrees(" in main, (
        "`main.py` n'appelle plus `verifier_taches_enregistrees` : le contrôle "
        "existe et ne s'exécute pas, ce qui ne sert à rien."
    )


# ── Le contrôle au démarrage, sur un vrai planificateur (#1589) ─────────────
#
#  Les tests ci-dessus lisent le CODE. Celui du démarrage lit le scheduler — et
#  il n'était exécuté nulle part en CI : son exclusion des rattrapages
#  (`startswith("rattrapage")`) ne correspondait à aucun identifiant réel
#  (`telemetry_rattrapage`, `backup_rattrapage`). Résultat : deux WARNING
#  « NON DECLAREE » à chaque démarrage depuis #1047, dans les journaux de
#  production — un avertissement permanent, qu'on cesse de lire, et au milieu
#  duquel un vrai écart passerait inaperçu (`standards/04` §7).


def _planificateur_comme_au_demarrage(*supplementaires: str):
    """Un planificateur monté comme dans `main.py` — jamais démarré.

    Les tâches permanentes y sont posées sous leur identifiant, et les
    rattrapages par la VRAIE `planifier_rattrapages` : c'est elle qui fixe leur
    identifiant, et c'est lui que l'exclusion doit reconnaître.
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    from app.utils.rattrapage import planifier_rattrapages

    planificateur = BackgroundScheduler(timezone="Europe/Paris")
    for identifiant in (*TACHES_PERMANENTES, *supplementaires):
        planificateur.add_job(
            contexte.pour_chaque_copropriete(print, identifiant),
            "interval",
            hours=24,
            id=identifiant,
        )
    poses = planifier_rattrapages(planificateur)
    assert poses, "cas zéro : aucun rattrapage posé, le test ne mesurerait rien"
    return planificateur


def _avertissements(planificateur, caplog) -> list[str]:
    """Les WARNING que le contrôle au démarrage journalise sur ce planificateur."""
    from app.utils.taches import verifier_taches_enregistrees

    with caplog.at_level(logging.WARNING, logger="taches"):
        verifier_taches_enregistrees(planificateur, logging.getLogger("taches"))
    return [r.getMessage() for r in caplog.records if r.name == "taches"]


def test_un_demarrage_sain_ne_produit_AUCUN_avertissement(caplog):
    """Toutes les tâches permanentes et les rattrapages réels : zéro WARNING."""
    avertissements = _avertissements(_planificateur_comme_au_demarrage(), caplog)
    assert not avertissements, (
        "Un démarrage sain journalise des écarts — l'avertissement serait permanent, "
        "donc ignoré :\n  " + "\n  ".join(avertissements)
    )


@pytest.mark.parametrize(
    "intruse",
    [
        "tache_fantome",
        #  Les deux formes qu'une exclusion par MOTIF avalerait : seul un
        #  identifiant réellement posé par `planifier_rattrapages` est attendu.
        "rattrapage_fantome",
        "fantome_rattrapage",
    ],
)
def test_une_tache_reellement_non_declaree_AVERTIT_toujours(caplog, intruse):
    """Témoin : faire taire le bruit ne doit pas rendre le contrôle muet."""
    avertissements = _avertissements(_planificateur_comme_au_demarrage(intruse), caplog)
    assert avertissements == [f"tache planifiee NON DECLAREE : {intruse}"]


# ── Chaque tâche travaille pour UNE copropriété (#1745, spec §4.6) ──────────
#
#  Une tâche enregistrée nue tournerait hors de tout contexte : elle lirait la
#  base que le repli désigne, pour toutes les copropriétés à la fois ou pour
#  aucune. Elle passe par `contexte.pour_chaque_copropriete`, ou se déclare
#  dans `TACHES_DE_LA_PLATEFORME` avec sa raison.


def _enveloppe(appel: ast.Call) -> bool:
    """Le premier argument d'un `add_job` est-il `pour_chaque_copropriete(…)` ?"""
    if not appel.args or not isinstance(appel.args[0], ast.Call):
        return False
    fonction = appel.args[0].func
    nom = fonction.attr if isinstance(fonction, ast.Attribute) else getattr(fonction, "id", "")
    return nom == "pour_chaque_copropriete"


def enregistrements_nus(arbre: ast.AST) -> list[tuple[int, str]]:
    """Les `add_job` d'un arbre qui ne passent pas par l'enveloppe : `(ligne, id)`."""
    nus = []
    for noeud in ast.walk(arbre):
        if not (
            isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Attribute)
            and noeud.func.attr == "add_job"
        ):
            continue
        ident = next((m.value for m in noeud.keywords if m.arg == "id"), None)
        lisible = ident.value if isinstance(ident, ast.Constant) else ast.unparse(ident or noeud)
        if lisible not in TACHES_DE_LA_PLATEFORME and not _enveloppe(noeud):
            nus.append((noeud.lineno, lisible))
    return nus


def test_chaque_tache_est_enregistree_par_copropriete():
    nus = {m.rel: n for m in modules_app() if (n := enregistrements_nus(m.arbre))}
    assert not nus, (
        "Tâche(s) enregistrée(s) hors de toute copropriété (#1745) — l'envelopper par "
        "`contexte.pour_chaque_copropriete(tache, id)`, ou la déclarer dans "
        "`taches.TACHES_DE_LA_PLATEFORME` avec sa raison :\n"
        + "\n".join(f"  app/{rel}:{ligne} — {i}" for rel, n in nus.items() for ligne, i in n)
    )


def test_le_releve_des_enregistrements_voit_chaque_forme():
    """Témoin : nu, enveloppé par attribut ou par nom, identifiant calculé."""
    source = (
        "s.add_job(f, 'cron', id='nue')\n"
        "s.add_job(contexte.pour_chaque_copropriete(f, 'a'), 'cron', id='a')\n"
        "s.add_job(pour_chaque_copropriete(f, 'b'), 'cron', id='b')\n"
        "s.add_job(partial(f, 1), 'date', id=t.job_id)\n"
    )
    assert enregistrements_nus(ast.parse(source)) == [(1, "nue"), (4, "t.job_id")]


def test_une_tache_de_la_plateforme_est_une_tache_declaree():
    """Une exception qui ne désigne plus rien est un oubli qui ressemble à une décision."""
    perimees = set(TACHES_DE_LA_PLATEFORME) - set(TACHES_PERMANENTES)
    assert not perimees, f"déclarées « de la plateforme » sans exister : {sorted(perimees)}"
    assert all(raison.strip() for raison in TACHES_DE_LA_PLATEFORME.values())


def test_une_tache_nue_AVERTIT_au_demarrage(caplog):
    """Le contrôle au démarrage voit aussi ce qu'une condition aurait posé sans enveloppe."""
    planificateur = _planificateur_comme_au_demarrage()
    planificateur.add_job(print, "interval", hours=24, id="backup", replace_existing=True)
    avertissements = _avertissements(planificateur, caplog)
    assert avertissements == ["tache planifiee HORS COPROPRIETE : backup"]


def _deux_coproprietes(monkeypatch):
    from dataclasses import replace

    une = contexte.courante()
    deux = (replace(une, identifiant="a"), replace(une, identifiant="b"))
    monkeypatch.setattr(contexte, "coproprietes", lambda: deux)
    return deux


def test_l_enveloppe_joue_la_tache_dans_chaque_copropriete(monkeypatch, caplog):
    _deux_coproprietes(monkeypatch)
    vues = []
    tache = contexte.pour_chaque_copropriete(
        lambda: vues.append(contexte.courante().identifiant), "essai"
    )
    with caplog.at_level(logging.INFO, logger="hostachy.taches"):
        tache()
    assert vues == ["a", "b"]
    lignes = [r.getMessage() for r in caplog.records if r.name == "hostachy.taches"]
    assert [ligne.split(" : ")[0] for ligne in lignes] == [
        "tache essai — copropriete a",
        "tache essai — copropriete b",
    ]
    #  Hors de l'enveloppe, le contexte est rendu : rien ne fuit vers la suite.
    assert contexte.courante().identifiant == contexte.IDENTIFIANT_UNIQUE


def test_l_echec_d_une_copropriete_ne_bloque_pas_les_autres(monkeypatch, caplog):
    _deux_coproprietes(monkeypatch)
    vues = []

    def tache():
        if contexte.courante().identifiant == "a":
            raise RuntimeError("base injoignable")
        vues.append(contexte.courante().identifiant)

    with caplog.at_level(logging.INFO, logger="hostachy.taches"):
        contexte.pour_chaque_copropriete(tache, "essai")()
    assert vues == ["b"]
    echecs = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert [r.getMessage() for r in echecs] == ["tache essai — copropriete a : ECHEC"]
