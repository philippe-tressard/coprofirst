"""Garde-fou de sécurité : le PÉRIMÈTRE d'un document à catégorie (#617).

Extrait de `test_documents_acces.py` le 29/08/2026 : ce fichier passait 501
lignes, et la coupe suit une frontière réelle plutôt qu'un compte.

## Deux régimes, deux fichiers

`document_visible` le dit lui-même : « un document tire sa protection soit de
l'objet qui le porte, soit de son profil d'accès de catégorie — **jamais des
deux, jamais d'aucun** ».

  • `test_documents_acces.py` couvre le premier — une pièce jointe suit son
    actualité, son ticket, son événement, et refuse quand le porteur a disparu ;
  • **ce fichier-ci** couvre le second — profil d'accès de catégorie, puis
    périmètre. C'est le régime des documents de la bibliothèque, dont les
    comptes-rendus d'AG.

Les deux ne partagent aucun montage : le premier a besoin d'un porteur, le
second d'un profil. Les garder ensemble obligeait chaque lecteur à trier.
"""

from app.models.core import StatutUtilisateur
from app.utils.visibility import document_visible

# ═══════════════════════════════════════════════════════════════════════════════
#  #617 — le ciblage d'un PV d'AG est DESCRIPTIF, jamais restrictif
# ═══════════════════════════════════════════════════════════════════════════════
#
#  POURQUOI (29/08/2026, trouvé en instruisant #470). L'écran des comptes-rendus
#  d'AG écrit DEUX formes de ciblage selon le nombre de bâtiments cochés :
#
#      un bâtiment    → perimetre='bâtiment' + batiment_id=N
#      deux ou plus   → perimetre='résidence' + batiments_ids_json='[1,2]'
#
#  `document_visible` ne lisait que la première. Cocher un bâtiment de plus
#  repassait donc par « résidence », le contrôle de périmètre ne s'appliquait
#  plus, et le seul champ portant encore le ciblage n'était jamais lu. Mesuré :
#
#       refusé   CR d'AG du seul bâtiment 1
#      VISIBLE   CR d'AG des bâtiments 1 ET 2      ← le défaut
#
#  🔴 Rien ne pouvait le signaler : chaque forme était cohérente prise seule, et
#  l'écran affichait « Bâtiment(s) spécifique(s) » dans les deux cas. C'est la
#  signature du ciblage à deux formes — celle qu'on relit le moins devient fausse.
#
#  Ces tests fixent la règle dans les DEUX sens : ce qui doit passer autant que ce
#  qui doit être refusé. Un test qui ne vérifierait que le refus laisserait
#  fermer un accès légitime sans que rien ne le dise.


class _ProfilOuvertATous:
    """Profil d'accès de catégorie qui n'exclut personne par son RÔLE.

    C'est le point : le profil filtre par rôle, jamais par bâtiment. Le filtrage
    géographique est le travail de la dernière étape de `document_visible` —
    celle que #617 corrige.
    """

    roles_autorises = '["resident", "locataire"]'
    profil_acces_id = 1


class _SessionProfil:
    """`session.get()` rend toujours le profil : seule branche exercée ici."""

    def get(self, _modele, _id):
        return _ProfilOuvertATous()


def _cr_ag(perimetre="résidence", batiment_id=None, batiments_ids_json=None):
    """Un CR d'AG : rattaché à une CATÉGORIE, donc protégé par son profil d'accès.

    ⚠️ Objet minimal, pour la même raison que `_ResidentDuBatiment` : `categorie`
    est une RELATION SQLModel, et lui affecter un objet hors ORM déclenche
    l'événement de backref. On expose exactement les champs que
    `document_visible` consulte — la surface de la règle se lit ainsi d'un coup.
    """
    return type(
        "CrAg",
        (),
        {
            "id": 99,
            "contrat_id": None,
            "ticket_id": None,
            "evenement_id": None,
            #  Les annexes de fiche (migration 0276) : un CR d'AG n'en est pas une.
            "document_parent_id": None,
            "diagnostic_rapport_id": None,
            "regle_residence_id": None,
            "categorie_id": 1,
            "profil_acces_override_id": None,
            "perimetre": perimetre,
            "batiment_id": batiment_id,
            "lot_id": None,
            "batiments_ids_json": batiments_ids_json,
            "categorie": _ProfilOuvertATous(),
        },
    )()


class _ResidentDuBatiment:
    """Un résident dont le seul lot est dans le bâtiment `numero`.

    ⚠️ Objet minimal et non le modèle `Utilisateur` : `user_lots` est une
    RELATION SQLModel, et lui affecter des objets hors ORM déclenche l'événement
    de backref (`'_UserLot' object has no attribute '_sa_instance_state'`).
    Monter de vraies lignes exigerait une base — pour éprouver une fonction qui
    n'en ouvre aucune.

    Il expose exactement ce que `document_visible` consulte, et rien de plus :
    c'est aussi ce qui rend visible, à la lecture, la surface dont dépend la
    règle. Même parti pris que `_SessionSansBase` plus haut.
    """

    def __init__(self, numero: int, *, actif: bool = True):
        lot = type("Lot", (), {"batiment_id": numero, "id": 500 + numero})()
        self.user_lots = [
            type("UserLot", (), {"actif": actif, "lot": lot, "lot_id": 500 + numero})()
        ]
        self.statut = StatutUtilisateur.locataire
        self.roles = ["resident"]

    def has_role(self, *_roles):
        #  Ni admin ni conseil syndical : ce sont eux qui court-circuitent tout
        #  en tête de `document_visible`, et ce n'est pas ce qu'on éprouve ici.
        return False


def _resident_du_batiment(numero: int) -> _ResidentDuBatiment:
    return _ResidentDuBatiment(numero)


# ── Ce qui doit être REFUSÉ ──────────────────────────────────────────────────


def test_document_de_batiment_refuse_a_un_resident_d_ailleurs():
    """`perimetre='bâtiment'` RESTREINT — c'est son rôle, et il le garde.

    Diagnostics, contrats, attestations : ces documents-là ne concernent que les
    détenteurs d'un lot dans le bâtiment visé. Ce test protège ce mécanisme d'un
    assouplissement collatéral au moment où l'on retire les PV d'AG de son champ.
    """
    doc = _cr_ag(perimetre="bâtiment", batiment_id=1)
    assert document_visible(_resident_du_batiment(3), doc, _SessionProfil()) is False


# ── Ce qui doit RESTER lisible ───────────────────────────────────────────────


def test_pv_ag_multi_batiments_lisible_par_tout_copropriétaire():
    """🔴 LA règle : « une AG doit être visible par tous les copropriétaires ».

    Un premier correctif avait rendu ce ciblage RESTRICTIF, pour aligner les deux
    formes que l'écran écrivait. L'incohérence était réelle, mais refermée du
    mauvais côté : c'est `perimetre='bâtiment'` qui n'avait rien à faire sur un
    PV d'AG. Ce test fixe le sens définitif.
    """
    doc = _cr_ag(batiments_ids_json="[1,2]")
    assert document_visible(_resident_du_batiment(3), doc, _SessionProfil()) is True


def test_pv_ag_multi_batiments_lisible_par_un_copropriétaire_cible():
    doc = _cr_ag(batiments_ids_json="[1,2]")
    assert document_visible(_resident_du_batiment(2), doc, _SessionProfil()) is True


def test_pv_ag_de_toute_la_copropriete_reste_lisible():
    assert document_visible(_resident_du_batiment(3), _cr_ag(), _SessionProfil()) is True


def test_pv_ag_ciblage_illisible_ne_ferme_rien():
    """Un JSON abîmé ne doit ni ouvrir ni FERMER : ce champ ne décide de rien.

    ⚠️ Le raisonnement « en cas de doute on refuse » ne s'applique pas ici, et
    c'est le piège : il vaut pour un champ qui PORTE un droit. Celui-ci n'en
    porte aucun — le refus sur donnée abîmée rendrait des AG invisibles sans que
    personne comprenne pourquoi.
    """
    doc = _cr_ag(batiments_ids_json="[1,2")  # tronqué
    assert document_visible(_resident_du_batiment(9), doc, _SessionProfil()) is True


def test_document_de_batiment_lisible_par_son_batiment():
    doc = _cr_ag(perimetre="bâtiment", batiment_id=1)
    assert document_visible(_resident_du_batiment(1), doc, _SessionProfil()) is True


# ═══════════════════════════════════════════════════════════════════════════════
#  #1551 — « rattaché » se demande à `est_rattache_au_lot`, jamais relu ici
# ═══════════════════════════════════════════════════════════════════════════════
#
#  `document_visible` jugeait `ul.actif` lui-même, deux fois (bâtiment, lot). Ces
#  tests fixent les cas limites où une copie divergerait de la source : le lien
#  DÉSACTIVÉ (l'ancien occupant), et le bâtiment de RATTACHEMENT sans lot — où la
#  règle est plus étroite que `utils/mes_batiments`, et c'est voulu.


def _doc_du_lot(lot_id: int):
    doc = _cr_ag()
    doc.perimetre, doc.lot_id = "lot", lot_id
    return doc


def test_document_de_batiment_refuse_a_l_ancien_occupant():
    """Un lien désactivé est l'historique d'un rattachement, pas un rattachement."""
    doc = _cr_ag(perimetre="bâtiment", batiment_id=1)
    ancien = _ResidentDuBatiment(1, actif=False)
    assert document_visible(ancien, doc, _SessionProfil()) is False


def test_document_de_lot_lisible_par_son_detenteur_et_pas_par_l_ancien():
    assert document_visible(_resident_du_batiment(1), _doc_du_lot(501), _SessionProfil()) is True
    ancien = _ResidentDuBatiment(1, actif=False)
    assert document_visible(ancien, _doc_du_lot(501), _SessionProfil()) is False


def test_document_de_batiment_refuse_au_domicilie_sans_lot():
    """⚠️ Plus étroit que « mes bâtiments » (rattachement + lots), et VOULU.

    Un diagnostic ou une attestation de bâtiment concernent qui y détient un lot.
    Un compte domicilié dans le bâtiment 1 (`batiment_id`) mais dont le seul lot
    est au 3 ne le lit pas : appeler `batiments_de_l_utilisateur` ici aurait
    élargi la règle sans que rien ne le dise.
    """
    domicilie = _resident_du_batiment(3)
    domicilie.batiment_id = 1
    doc = _cr_ag(perimetre="bâtiment", batiment_id=1)
    assert document_visible(domicilie, doc, _SessionProfil()) is False


# ═══════════════════════════════════════════════════════════════════════════════
#  Le SYNDIC voit les PV d'AG — il ne les voyait pas du tout (29/08/2026)
# ═══════════════════════════════════════════════════════════════════════════════
#
#  La catégorie `pv_ag` pointe sur le profil `résidence_tous`, dont les rôles
#  autorisés étaient `["propriétaire", "résident"]`. Le syndic n'a ni l'un ni
#  l'autre : son STATUT vaut `syndic`, et `document_visible` compare
#  `roles ∪ {statut}` à cette liste. Il tombait au premier filtre — sur les
#  quatre catégories de ce profil : règlement, PV d'AG, fiche synthétique, plan.
#
#  🔴 **Le syndic RÉDIGE le PV d'AG.** C'est l'argument qui a tranché la question,
#  posée puis reposée le 29/08/2026 : un rédacteur qui ne peut pas relire son
#  propre document est un défaut, pas une règle. Migration 0159.


def _syndic():
    """Le syndic : un STATUT, aucun rôle de copropriétaire, et AUCUN LOT.

    L'absence de lot est le point : elle rend `user_batiments` vide, donc tout
    document restreint par bâtiment lui serait refusé même s'il passait le filtre
    de rôle. C'est pourquoi retirer `perimetre='bâtiment'` des PV d'AG et ouvrir
    le profil sont **deux** correctifs, pas un.
    """
    return type(
        "Syndic",
        (),
        {
            "user_lots": [],
            "statut": StatutUtilisateur.syndic,
            "roles": [],
            "has_role": lambda *_: False,
        },
    )()


class _ProfilAvecSyndic:
    """`résidence_tous` après la migration 0159."""

    roles_autorises = '["propriétaire", "résident", "syndic"]'
    profil_acces_id = 1


class _SessionProfilAvecSyndic:
    def get(self, _modele, _id):
        return _ProfilAvecSyndic()


def test_le_syndic_voit_le_pv_d_ag_de_la_copropriete():
    assert document_visible(_syndic(), _cr_ag(), _SessionProfilAvecSyndic()) is True


def test_le_syndic_voit_un_pv_d_ag_cible_sur_des_batiments():
    """Le ciblage étant descriptif, son absence de lot ne lui ferme plus rien."""
    doc = _cr_ag(batiments_ids_json="[1,2]")
    assert document_visible(_syndic(), doc, _SessionProfilAvecSyndic()) is True


def test_sans_la_migration_le_syndic_ne_voyait_rien():
    """Le cas AVANT, gardé pour que la raison du correctif reste lisible.

    Un test qui ne montre que l'état corrigé laisse croire qu'il n'y avait rien à
    corriger — et le prochain qui touchera au profil ne saura pas ce qu'il défait.
    """
    assert document_visible(_syndic(), _cr_ag(), _SessionProfil()) is False
