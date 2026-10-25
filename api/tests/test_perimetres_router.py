"""`GET /perimetres` — le router, qui n'était couvert par aucun test.

Livré sans test dans la v2.55.0, il a répondu **500 en production** dès le premier
appel : `_codes_cites` dépaquetait `(valeur,)` alors que
`session.exec(select(<colonne>))` rend des scalaires. `ValueError: too many values
to unpack` tombait sur toute chaîne de plus d'un caractère — donc sur toutes.

Le lot portait 23 tests sur les RÈGLES (voir `test_perimetres_arbre.py`) et aucun
sur le chemin qui les sert. Fichier séparé pour que cette distinction reste
visible : les règles d'un côté, le point d'entrée de l'autre.

La vérification en navigateur, elle, avait bien exercé l'écran — mais sur une base
fraîchement semée où aucun contenu ne citait de périmètre, si bien que la boucle
fautive n'était jamais atteinte. Ces tests écrivent donc du contenu AVANT de lire.
"""

from datetime import datetime

from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    Evenement,
    Ticket,
    TypeEvenement,
    Utilisateur,
)
from app.models.perimetre import Perimetre
from app.routers.patrimoine import _codes_cites, _en_lecture
from app.seed.patrimoine import poser_arborescence
from tests.conftest import vider_patrimoine
from tests.aides_purge import purger_ligne


#  Le montage (quatre bâtiments + arbre semé) vit dans `conftest.py` depuis le
#  14/08/2026 : il était écrit à l'identique ici et dans `test_perimetres_arbre.py`.
#  La fixture `batiments` est donc injectée sans être déclarée dans ce fichier.
def _vider(session: Session) -> None:
    """Purge locale : le patrimoine **et** les contenus que ce fichier écrit."""
    vider_patrimoine(session, (Ticket, Evenement))


def _auteur(session: Session) -> int:
    """`Ticket.auteur_id` et `Evenement.auteur_id` sont NOT NULL."""
    existant = session.exec(
        select(Utilisateur).where(Utilisateur.email == "auteur@test.fr")
    ).first()
    if existant:
        return existant.id
    u = Utilisateur(nom="A", prenom="B", email="auteur@test.fr", actif=True)
    session.add(u)
    session.commit()
    return u.id


def _actualite(auteur: int, perimetre_cible: str) -> Ticket:
    """Une actualité — une affaire de catégorie « Actualité » depuis le 23/09/2026 (#1091)."""
    import uuid

    return Ticket(
        numero=f"TK-A{uuid.uuid4().hex[:6]}",
        titre="T",
        description="C",
        categorie="actualite",
        statut="publie",
        auteur_id=auteur,
        perimetre_cible=perimetre_cible,
    )


def test_lecture_de_l_arborescence_par_le_router(batiments):
    """`GET /perimetres` rend l'arbre — le contrôle qui manquait.

    Livré sans test, ce router a répondu **500 en production** dès le premier
    appel : `_codes_cites` dépaquetait `(valeur,)` alors que
    `session.exec(select(<colonne>))` rend des scalaires, et `ValueError: too many
    values to unpack` tombait sur toute chaîne de plus d'un caractère — donc sur
    toutes. L'écran d'administration restait vide et les libellés retombaient sur
    leur calcul de repli.

    Les tests portaient sur les règles, jamais sur le chemin qui les sert : un
    module entier était hors de portée, et rien ne le signalait.
    """

    with Session(engine) as session:
        auteur = _auteur(session)
        #  Un contenu qui cite deux périmètres, pour que `utilise` ait à les trouver
        #  dans les deux formats stockés (JSON et CSV).
        actualite = _actualite(auteur, '["aful", "bat:%d"]' % batiments[0])
        session.add(actualite)
        session.commit()

        cites = _codes_cites(session)
        assert "aful" in cites
        assert f"bat:{batiments[0]}" in cites

        lus = _en_lecture(list(session.exec(select(Perimetre)).all()), cites)
        purger_ligne(session, Ticket, actualite.id)

    assert len(lus) == 63, f"63 nœuds semés, {len(lus)} rendus"

    par_code = {n.code: n for n in lus}
    #  L'ordre est un parcours en profondeur : un enfant suit son parent.
    assert lus[0].code == "résidence"
    assert par_code["bat:%d/hall" % batiments[0]].profondeur == 2
    assert par_code["bat:%d/hall" % batiments[0]].parent == f"bat:{batiments[0]}"
    #  Héritage de la portée : le portail du parking concerne tout le monde.
    assert par_code["parking/portail"].concerne_tous is True
    assert par_code["parking/portail"].portee_globale is False
    #  Un espace de bâtiment ne concerne pas tout le monde.
    assert par_code["bat:%d/hall" % batiments[0]].concerne_tous is False
    #  `utilise` distingue ce qui est cité de ce qui ne l'est pas.
    assert par_code["aful"].utilise is True
    assert par_code["cheminements"].utilise is False


def test_codes_cites_lit_les_trois_formats_de_stockage(batiments):
    """JSON, CSV et champ vide : les cinq entités n'écrivent pas pareil."""

    with Session(engine) as session:
        auteur = _auteur(session)
        actualite = _actualite(auteur, '["parking"]')
        evenement = Evenement(
            titre="E",
            type=TypeEvenement.travaux,
            auteur_id=auteur,
            debut=datetime(2026, 8, 12, 9, 0),
            perimetre="espaces-verts,cheminements",
        )
        session.add_all([actualite, evenement])
        session.commit()
        cites = _codes_cites(session)
        #  Ce qu'il cite part avec lui : laissé dans la base du processus,
        #  « cheminements » paraissait utilisé au test de lecture joué après (#2223).
        purger_ligne(session, Evenement, evenement.id)
        purger_ligne(session, Ticket, actualite.id)

    assert {"parking", "espaces-verts", "cheminements"} <= cites


# ── Le seed ne doit plus jamais annuler une suppression ───────────────────────


def test_le_seed_ne_repose_pas_ce_qui_a_ete_supprime(batiments):
    """Une suppression doit survivre au déploiement suivant.

    `seed()` tourne au démarrage de l'API, donc à CHAQUE déploiement. La première
    écriture reposait « ce qui manque » : un périmètre supprimé depuis
    l'administration ressuscitait à la mise à jour suivante — « à chaque mise à
    jour mes périmètres ajoutés, supprimés sont perdus » (13/08/2026).

    La règle du paquet `seed` protège les MODIFICATIONS, pas les SUPPRESSIONS :
    un seed ne distingue pas un nœud supprimé d'un nœud jamais posé. D'où le
    marqueur `ConfigSite["perimetres_semes"]`.
    """
    from app.models.core import ConfigSite
    from app.seed.patrimoine import CLE_SEMEE

    with Session(engine) as session:
        assert session.get(ConfigSite, CLE_SEMEE) is not None, (
            "le premier semis doit poser son marqueur"
        )

        #  L'administrateur supprime un périmètre, et en ajoute un à lui.
        #
        #  🔴 La suppression passe par le code de PRODUCTION. Le test descendait
        #  d'UN niveau — les enfants directs, puis le nœud — et laissait les
        #  petits-enfants derrière : avec les clés vérifiées la base refuse, et
        #  elle a raison (#546). `purger_ligne` lit les métadonnées et descend
        #  l'arbre entier, quelle que soit sa profondeur, qui est une donnée
        #  administrée et non une constante du test.
        cible = session.exec(select(Perimetre).where(Perimetre.code == "cheminements")).one()
        purger_ligne(session, Perimetre, cible.id)
        session.add(Perimetre(code="piscine", libelle="Piscine", portee_globale=True))
        session.commit()

        #  Un déploiement plus tard : le seed repasse.
        assert poser_arborescence(session) == 0, "le seed ne doit plus rien poser"
        session.commit()

        codes = {n.code for n in session.exec(select(Perimetre)).all()}
        assert "cheminements" not in codes, "la suppression a été annulée par le seed"
        assert "piscine" in codes, "l'ajout de l'administrateur a disparu"
        assert "résidence" in codes, "le reste de l'arborescence doit être intact"


def test_le_seed_pose_bien_l_arbre_sur_une_base_vierge():
    """Le marqueur ne doit pas empêcher le premier semis.

    C'est le cas zéro : une installation neuve doit obtenir son arborescence.
    """
    from app.models.core import ConfigSite
    from app.seed.patrimoine import CLE_SEMEE

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _vider(session)
        marqueur = session.get(ConfigSite, CLE_SEMEE)
        if marqueur:
            session.delete(marqueur)
        session.commit()

        poses = poser_arborescence(session)
        session.commit()
        assert poses > 0, "une base vierge doit recevoir l'arborescence"
        assert session.get(ConfigSite, CLE_SEMEE) is not None

        #  Et une seconde exécution ne pose plus rien.
        assert poser_arborescence(session) == 0


# ── Icônes : initialisation, jamais écrasement ────────────────────────────────


def test_le_seed_pose_les_icones_initiales(batiments):
    """Chaque périmètre semé porte une icône que `Icon.svelte` sait rendre."""
    from app.seed.patrimoine import icone_pour

    with Session(engine) as session:
        noeuds = session.exec(select(Perimetre)).all()
        sans = [n.code for n in noeuds if not n.icone and icone_pour(n.code)]
        assert not sans, f"périmètre(s) sans icône alors qu'une était prévue : {sans}"

        par_code = {n.code: n.icone for n in noeuds}
        assert par_code["parking"] == "car"
        assert par_code["aful"] == "square-parking"
        assert par_code[f"bat:{batiments[0]}/ascenseur"] == "arrow-up-down"
        assert par_code[f"bat:{batiments[0]}"] == "building-2"


#  Le contrôle « une icône citée par le seed existe bien » a déménagé dans
#  `test_icones_svg.py` (14/08/2026), en même temps que les tracés eux-mêmes :
#  ils ne vivent plus dans `Icon.svelte` mais dans le catalogue partagé
#  `front/src/lib/icones-svg.json`, que le composant ET les documents imprimables
#  du serveur consomment. Le laisser ici l'aurait fait lire un fichier qui ne
#  porte plus la réponse — et le réécrire à côté de son jumeau aurait dupliqué un
#  contrôle, ce qui est aussi de la duplication.
