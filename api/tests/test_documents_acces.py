"""Garde-fou de sécurité : une pièce jointe ne fuit jamais au-delà de son actualité.

POURQUOI (28/07/2026) — `_user_can_read` traitait les pièces jointes d'actualité
comme un cas trivialement ouvert :

    if doc.publication_id and not doc.categorie_id:
        return True

Un document n'a pas de ciblage propre : ni `public_cible`, ni `perimetre_cible`. Sa
seule protection est celle de l'actualité qui le porte — et cette branche ne la
regardait pas. Concrètement, le PDF joint à une actualité réservée au conseil
syndical, ou ciblée sur un seul bâtiment, était :

  - listé par `GET /documents?publication_id=…`,
  - **téléchargeable** par `GET /documents/{id}/télécharger` pour tout compte
    authentifié, y compris un locataire,
  - et annoncé, titre compris, dans le fil d'activité du tableau de bord, qui
    s'appuie sur cette même fonction (`flux.py` → `_document_visible`).

Rien ne le signalait : les trois chemins partagent la fonction fautive, donc ils
étaient d'accord entre eux. Ce test fixe la règle dans les deux sens — ce qui doit
passer autant que ce qui doit être refusé — pour qu'un futur assouplissement de
`_user_can_read` échoue ici plutôt qu'en production.
"""

from app.models.core import (
    Document,
    RoleUtilisateur,
    StatutUtilisateur,
    Ticket,
    Utilisateur,
)
from app.utils.visibility import document_visible


class _SessionSansBase:
    """`session.get(<modèle>, id)` — seuls appels faits par les branches testées.

    ⚠️ Elle rend le porteur qu'on lui a donné, quel que soit le modèle demandé :
    chaque test n'exerce qu'UNE branche à la fois, et le modèle y est déterminé
    par le champ `*_id` du document. Rendre `None` permet d'éprouver le cas
    « porteur introuvable », qui doit refuser (#390).
    """

    def __init__(self, porteur=None):
        self._porteur = porteur

    def get(self, _modele, _id):
        return self._porteur


def _utilisateur(role: str, statut: StatutUtilisateur, batiment_id=None) -> Utilisateur:
    return Utilisateur(
        email="x@example.test",
        prenom="X",
        nom="Y",
        role=role,
        roles_json=role,
        statut=statut,
        batiment_id=batiment_id,
    )


def _piece_jointe() -> Document:
    """Pièce jointe d'actualité : rattachée à son affaire, sans catégorie.

    Une actualité est une affaire de catégorie « Actualité » depuis le
    23/09/2026 (#1091) : ses pièces jointes portent `ticket_id`, et la 0210 y a
    rattaché les anciennes.
    """
    return Document(
        id=42,
        titre="Compte rendu interne",
        fichier_nom="cr.pdf",
        ticket_id=7,
        categorie_id=None,
    )


def _publication(**champs) -> Ticket:
    base = dict(
        id=7,
        numero="TK-A7",
        titre="Réunion",
        description="",
        categorie="actualite",
        statut="publie",
        auteur_id=1,
        public_cible=None,
        perimetre_cible=None,
    )
    base.update(champs)
    return Ticket(**base)


# ── Ce qui doit être REFUSÉ ──────────────────────────────────────────────────


def test_piece_jointe_d_actualite_reservee_au_cs_refusee_a_un_locataire():
    """Le cas d'origine : `public_cible=["conseil_syndical"]` ne protégeait que le texte."""
    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)
    session = _SessionSansBase(_publication(public_cible='["conseil_syndical"]'))

    assert document_visible(locataire, _piece_jointe(), session) is False


def test_piece_jointe_d_actualite_ciblee_ailleurs_suit_l_actualite():
    """Le fichier suit l'actualité qui le porte — c'est le principe, et il tient.

    Ce test exigeait auparavant un refus. Il ne l'exige plus **parce que
    l'actualité elle-même a changé de verdict** (#339, 14/08/2026) : une actualité
    ciblée sur un autre bâtiment est désormais lisible, sauf si le lecteur a coché
    « n'afficher que mes bâtiments » dans son profil.

    Le principe que ce test protège n'a donc pas bougé d'un pouce — il est même
    vérifié dans les deux sens ici. Ce qui a bougé, c'est la visibilité de
    l'actualité, et le fichier la suit, comme il l'a toujours fait. La protection
    par le **public** (`public_cible`), elle, est inchangée : c'est le test
    juste au-dessus, et c'est lui qui empêche une agence ou un bailleur de gagner
    quoi que ce soit.
    """
    publication_ailleurs = _publication(perimetre_cible='["bat:1"]')

    ouvert = _utilisateur("locataire", StatutUtilisateur.locataire, batiment_id=2)
    assert document_visible(ouvert, _piece_jointe(), _SessionSansBase(publication_ailleurs)) is True

    restreint = _utilisateur("locataire", StatutUtilisateur.locataire, batiment_id=2)
    restreint.restreindre_a_mes_batiments = True
    assert (
        document_visible(restreint, _piece_jointe(), _SessionSansBase(publication_ailleurs))
        is False
    )


def test_piece_jointe_d_actualite_reservee_au_perimetre_suit_l_actualite():
    """🔒 L'Accès « visible du seul périmètre » referme le fichier avec l'actualité."""
    ailleurs = _utilisateur("locataire", StatutUtilisateur.locataire, batiment_id=2)
    session = _SessionSansBase(_publication(perimetre_cible='["bat:1"]', reserve_perimetre=True))

    assert document_visible(ailleurs, _piece_jointe(), session) is False


def test_piece_jointe_orpheline_refusee():
    """Publication introuvable : aucune règle de visibilité à appliquer → on refuse."""
    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)

    assert document_visible(locataire, _piece_jointe(), _SessionSansBase(None)) is False


# ── Ce qui doit rester AUTORISÉ ──────────────────────────────────────────────


def test_piece_jointe_d_actualite_tout_public_reste_lisible():
    """Le correctif ne doit pas fermer le cas courant : une actualité pour tous."""
    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)
    session = _SessionSansBase(_publication(public_cible='["résidents"]'))

    assert document_visible(locataire, _piece_jointe(), session) is True


def test_piece_jointe_d_actualite_sans_ciblage_reste_lisible():
    """Absence de ciblage = tout le monde, comportement historique conservé."""
    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)
    session = _SessionSansBase(_publication())

    assert document_visible(locataire, _piece_jointe(), session) is True


def test_le_conseil_syndical_garde_acces_a_tout():
    """CS et admin sortent avant toute autre règle — y compris sur un brouillon."""
    cs = _utilisateur(
        RoleUtilisateur.conseil_syndical.value, StatutUtilisateur.copropriétaire_bailleur
    )
    session = _SessionSansBase(_publication(brouillon=True, public_cible='["locataires"]'))

    assert document_visible(cs, _piece_jointe(), session) is True


# ── La règle elle-même, pour qu'on ne puisse pas la rouvrir par inadvertance ──


def test_la_branche_piece_jointe_consulte_bien_la_publication():
    """Si un jour la branche redevient un `return True` sec, ce test le dit.

    Il ne relit pas le code : il vérifie l'effet observable, à savoir que la
    fonction interroge la publication porteuse avant de se prononcer.
    """
    consultations = []

    class _SessionEspionne(_SessionSansBase):
        def get(self, modele, identifiant):
            consultations.append((modele, identifiant))
            return super().get(modele, identifiant)

    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)
    document_visible(locataire, _piece_jointe(), _SessionEspionne(_publication()))

    assert consultations == [(Ticket, 7)], (
        "la pièce jointe a été autorisée (ou refusée) sans regarder son actualité"
    )


#  ── Un document SANS source de protection ────────────────────────────────────
#
#  Trouvé le 20/08/2026 en instruisant #390, dont l'étape 1 prévoit de créer une
#  ligne `Document` « sans publication_id, rattachée ensuite ».


def _document_orphelin() -> Document:
    """Ni catégorie, ni contrat, ni publication — donc aucune règle applicable."""
    return Document(
        id=99,
        titre="photo de ticket",
        fichier_nom="degat.jpg",
        publication_id=None,
        categorie_id=None,
        contrat_id=None,
    )


def test_un_document_sans_source_de_protection_est_refuse():
    """🔴 Le repli est le REFUS, jamais l'autorisation.

    Une pièce jointe dont on ne sait pas de qui elle tire sa protection n'en a
    aucune. Autoriser « par défaut » un document que le modèle ne sait pas
    rattacher, c'est publier ce qu'on n'a pas su classer.
    """
    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)
    assert document_visible(locataire, _document_orphelin(), _SessionSansBase(None)) is False


def test_un_document_sans_source_de_protection_ne_LÈVE_pas():
    """⚠️ Et c'est le vrai défaut : ce n'était pas un refus, c'était un 500.

    `doc.profil_acces_override_id or doc.categorie.profil_acces_id` déréférençait
    `doc.categorie` sans le tester. Sur un document orphelin, `None.profil_acces_id`
    lève un `AttributeError` — et `GET /documents` le rend en **500** pour tout
    utilisateur non CS/admin, puisque le filtrage appelle cette fonction sur
    CHAQUE document de la liste. Un seul orphelin suffisait à rendre l'écran
    inaccessible à tous les résidents.

    Le cas était inatteignable par l'API — `POST /documents` exige l'un des trois
    rattachements — mais l'invariant était tenu à UN endroit et supposé à un
    autre, sans rien qui relie les deux. #390 allait justement écrire l'appelant
    qui le brise.
    """
    locataire = _utilisateur("locataire", StatutUtilisateur.locataire)
    try:
        document_visible(locataire, _document_orphelin(), _SessionSansBase(None))
    except AttributeError as exc:  # pragma: no cover — c'est ce qu'on refuse
        raise AssertionError(
            f"document_visible lève au lieu de refuser : {exc}. "
            "Une fonction de visibilité qui plante rend un écran inaccessible, "
            "elle ne protège rien."
        ) from exc


def test_le_cs_voit_quand_meme_un_document_orphelin():
    """Le refus ne doit pas déborder sur qui a le droit de tout voir.

    Sans ce cas, on pourrait « corriger » le défaut par un refus placé trop haut,
    et rendre invisible à l'administration un document qu'elle doit pouvoir
    reclasser — le seul rôle capable de réparer l'orphelin.
    """
    cs = _utilisateur("conseil_syndical", StatutUtilisateur.copropriétaire_résident)
    assert document_visible(cs, _document_orphelin(), _SessionSansBase(None)) is True


# ── Pièces jointes de TICKET et d'ÉVÉNEMENT (#390, 27/08/2026) ───────────────
#
# Décision du 27/08/2026 : « qui voit le porteur », et rien de plus. Le régime
# actuel de ces fichiers est celui de l'objet qui les porte ; leur donner au
# passage le contrôle à trois couches des documents casserait des accès qui
# marchent aujourd'hui, sans que personne soit prévenu.
#
# ⚠️ Ce que ces règles ne ferment PAS : le fichier lui-même. Une pièce jointe
# écrite dans `uploads/fichiers/` reste servie par Caddy sous `forward_auth`,
# donc lisible de toute session qui connaît l'URL. C'est le régime de RÉPERTOIRE
# qui protège, pas le modèle — et c'est le lot suivant de #390.

#  `Evenement` n'était importé que pour la forme : le test du porteur supprimé
#  passe une session qui rend `None`, et ne construit aucun événement. Import mort
#  retiré le 29/08/2026 — Ruff en CI ne couvre que `api/app/`, jamais `api/tests/`,
#  donc rien ne le signalait (il y en a 20 autres du même genre).


def _piece_jointe_ticket() -> Document:
    return Document(
        id=51,
        titre="Photo de la fuite",
        fichier_nom="fuite.jpg",
        ticket_id=11,
        categorie_id=None,
    )


def _piece_jointe_evenement() -> Document:
    return Document(
        id=52,
        titre="Plan d'accès",
        fichier_nom="plan.pdf",
        evenement_id=22,
        categorie_id=None,
    )


def test_piece_jointe_de_ticket_suit_son_ticket():
    """Le fichier hérite du verdict du ticket, jamais d'un droit propre."""
    resident = _utilisateur("résident", StatutUtilisateur.locataire, batiment_id=1)
    ticket = Ticket(id=11, titre="Fuite", description="", auteur_id=1, batiment_id=1)
    session = _SessionSansBase(ticket)

    from app.utils.visibility import ticket_visible

    assert document_visible(resident, _piece_jointe_ticket(), session) is ticket_visible(
        ticket, resident
    )


def test_piece_jointe_de_ticket_supprime_est_refusee():
    """🔴 Porteur introuvable → REFUS. « Aucune règle » n'est pas une autorisation.

    C'est le cas zéro de cette branche : un ticket supprimé laisse une pièce
    jointe sans source de protection, et le repli permissif serait invisible —
    le fichier resterait lisible pour toujours.
    """
    resident = _utilisateur("résident", StatutUtilisateur.locataire, batiment_id=1)

    assert document_visible(resident, _piece_jointe_ticket(), _SessionSansBase(None)) is False


def test_piece_jointe_d_evenement_supprime_est_refusee():
    resident = _utilisateur("résident", StatutUtilisateur.locataire, batiment_id=1)

    assert document_visible(resident, _piece_jointe_evenement(), _SessionSansBase(None)) is False


def test_le_cs_garde_acces_aux_pieces_jointes_de_ticket():
    """Le CS sort avant toute branche : il ne dépend d'aucun porteur."""
    cs = _utilisateur("conseil_syndical", StatutUtilisateur.copropriétaire_résident)

    assert document_visible(cs, _piece_jointe_ticket(), _SessionSansBase(None)) is True


def test_une_piece_jointe_de_ticket_avec_categorie_ne_passe_pas_par_cette_branche():
    """⚠️ La borne des branches : `not doc.categorie_id`.

    Un document CATÉGORISÉ tire sa protection de son profil d'accès, même s'il
    porte aussi un `ticket_id`. Sans cette borne, ranger une pièce jointe dans
    une catégorie changerait silencieusement son régime d'accès.
    """
    resident = _utilisateur("résident", StatutUtilisateur.locataire, batiment_id=1)
    doc = _piece_jointe_ticket()
    doc.categorie_id = 3

    #  La branche ticket est court-circuitée : on tombe dans l'algorithme du
    #  profil d'accès, qui refuse faute de profil chargeable ici.
    assert document_visible(resident, doc, _SessionSansBase(None)) is False
