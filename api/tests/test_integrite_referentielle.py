"""Intégrité référentielle — les clés étrangères, vérifiées par la base (#546).

Le serveur vérifie toutes les clés déclarées. Ce fichier tient trois choses :

1. **le moteur de l'application** ne suspend jamais les clés (dernier test) ;
2. **un moteur strict jetable** fait réellement mordre la contrainte ;
3. **la purge des fixtures** (`vider_patrimoine`, `delier_references`) respecte
   les clés — auto-référence, cycles, colonnes NOT NULL.
"""

import os
import tempfile

os.environ.setdefault("SECRET_KEY", "x" * 40)

os.environ.setdefault("ENABLE_API_DOCS", "false")
os.environ.setdefault("UPLOADS_DIR", os.path.join(tempfile.gettempdir(), "hostachy-tests-uploads"))

import pytest  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.models.core import Batiment, Copropriete, Utilisateur  # noqa: E402
from app.models.perimetre import Perimetre  # noqa: E402
from tests.aides_base import compte, moteur_de_test  # noqa: E402
from tests.conftest import delier_references, vider_patrimoine  # noqa: E402


@pytest.fixture()
def moteur_strict():
    """Un moteur JETABLE aux clés vérifiées, isolé de celui de la suite.

    `moteur_de_test(cles_etrangeres=True)` : ces tests créent et purgent un
    patrimoine sans rien laisser sur le moteur partagé.
    """
    moteur = moteur_de_test(cles_etrangeres=True)
    yield moteur
    moteur.dispose()


def test_le_moteur_strict_applique_vraiment_les_cles(moteur_strict):
    """Cas zéro — sans lui, tous les tests de ce fichier passeraient pour rien.

    Un test d'intégrité sur un moteur permissif ne vérifie rien et ne le dit pas :
    la contrainte doit MORDRE.
    """
    with Session(moteur_strict) as session:
        session.add(Batiment(copropriete_id=99999, numero="fantôme"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_la_purge_du_patrimoine_respecte_l_auto_reference(moteur_strict):
    """`Perimetre.parent_id` s'auto-référence : la purge doit aller des feuilles
    vers la racine.

    Avant #546, `vider_patrimoine` supprimait les périmètres dans un ordre
    arbitraire. La base l'acceptait — parce qu'elle ne vérifiait rien. Avec les
    clés actives, c'était **20 erreurs** dans quatre fichiers.
    """
    with Session(moteur_strict) as session:
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        racine = Perimetre(code="racine", libelle="Racine")
        session.add(racine)
        session.flush()
        enfant = Perimetre(code="enfant", libelle="Enfant", parent_id=racine.id)
        session.add(enfant)
        session.flush()
        session.add(Perimetre(code="petit", libelle="Petit-enfant", parent_id=enfant.id))
        session.commit()

        vider_patrimoine(session)
        assert session.exec(select(Perimetre)).all() == []
        assert session.exec(select(Copropriete)).all() == []


def test_la_purge_sait_defaire_un_cycle_de_parente(moteur_strict):
    """Un cycle `parent_id` ne doit ni bloquer la purge, ni la faire boucler.

    ⚠️ Ce n'est pas un cas théorique : `test_cycle_de_parente_ne_suspend_pas_et_refuse`
    en fabrique un **volontairement**, c'est son sujet. Une fixture de purge
    s'exécute précisément après les tests qui abîment les données exprès — elle
    n'a donc pas le droit de supposer un arbre sain.

    Sans ce cas, la première version de la purge par vagues tournait
    indéfiniment : plus aucune feuille à trouver, et une suite qui ne rend jamais
    la main ne dit pas qu'elle a échoué.
    """
    with Session(moteur_strict) as session:
        a = Perimetre(code="a", libelle="A")
        b = Perimetre(code="b", libelle="B")
        session.add(a)
        session.add(b)
        session.flush()
        a.parent_id = b.id
        b.parent_id = a.id
        session.add(a)
        session.add(b)
        session.commit()

        vider_patrimoine(session)
        assert session.exec(select(Perimetre)).all() == []


def test_un_noeud_qui_se_designe_lui_meme_ne_bloque_pas(moteur_strict):
    """Le cycle le plus court — et celui qui a fait échouer la première version.

    Un nœud dont le `parent_id` vaut son propre `id` n'est jamais une feuille : il
    est son propre parent. La purge doit le délier avant de l'effacer.
    """
    with Session(moteur_strict) as session:
        seul = Perimetre(code="seul", libelle="Seul")
        session.add(seul)
        session.flush()
        seul.parent_id = seul.id
        session.add(seul)
        session.commit()

        vider_patrimoine(session)
        assert session.exec(select(Perimetre)).all() == []


def test_la_purge_delie_les_references_au_batiment(moteur_strict):
    """Un bâtiment est référencé par ONZE colonnes, toutes nullables.

    La purge les effaçait sans s'en soucier : **132 violations**, la famille la
    plus nombreuse du relevé de #546. On délie, on ne supprime pas — un
    utilisateur ne cesse pas d'exister parce que le patrimoine de test est
    démonté, et une fixture qui l'effacerait retirerait des données que le test
    suivant attend peut-être.
    """
    with Session(moteur_strict) as session:
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        bat = Batiment(copropriete_id=copro.id, numero="1")
        session.add(bat)
        session.flush()
        compte(session, prefixe="resident", nom="Résident", prenom="Test", batiment_id=bat.id)

        vider_patrimoine(session)

        #  Le bâtiment est parti, l'utilisateur est resté — délié.
        assert session.exec(select(Batiment)).all() == []
        restant = session.exec(select(Utilisateur)).one()
        assert restant.batiment_id is None


def test_delier_ne_touche_PAS_les_colonnes_non_nullables(moteur_strict):
    """🔴 Le garde-fou du garde-fou.

    `delier_references` met à NULL ce qui est nullable. Une version qui
    tenterait aussi les colonnes NOT NULL échouerait — ou pire, les
    contournerait. `batiment.copropriete_id` est NOT NULL : délier les
    références à la copropriété doit le laisser intact.

    C'est ce qui distingue « délier » de « casser » : les porteurs NOT NULL
    doivent partir AVANT, et le contrôle doit le rendre visible plutôt que de le
    contourner en silence.
    """
    with Session(moteur_strict) as session:
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        session.add(Batiment(copropriete_id=copro.id, numero="1"))
        session.commit()

        delier_references(session, Copropriete)

        bat = session.exec(select(Batiment)).one()
        assert bat.copropriete_id == copro.id, (
            "une colonne NOT NULL a été déliée — la purge masquerait alors un "
            "ordre de suppression faux au lieu de le révéler"
        )


# ── Le garde-fou du garde-fou (#546, 29/08/2026) ─────────────────────────────


def test_la_suite_TOURNE_avec_les_cles_actives():
    """🔴 Le moteur de l'application ne suspend JAMAIS les clés.

    Les bases de test les suspendent pour leurs fixtures
    (`session_replication_role = replica`) ; une suspension qui fuirait jusqu'au
    moteur de l'application lui ferait accepter des lignes orphelines, et la
    suite resterait verte (`standards/04` §1).
    """
    from sqlmodel import Session, text

    from app.database import engine

    with Session(engine) as session:
        role = session.exec(text("SHOW session_replication_role")).one()[0]
    assert role == "origin", (
        "le moteur de l'application suspend ses clés étrangères : il accepterait "
        "des lignes orphelines, et rien d'autre ne le dirait."
    )
