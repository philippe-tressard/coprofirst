"""Communauté, FAQ, notifications : les règles d'affichage SERVIES par l'API (#2506).

## Pourquoi ce fichier (04/11/2026)

L'app iOS ne parle qu'au contrat de l'API et ne recopie aucune règle du front.
Le badge NEW, les catégories de FAQ qu'un statut lit et leur libellé, le crayon
et la corbeille d'une idée, d'une annonce ou d'une réponse, « Gratuit », le
« Prénom NOM » d'un auteur : tout cela se calculait dans le front seulement —
l'app ne montrait rien, ou montrait tout (`standards/09` §8, règle 1, #2501).

Chaque règle est servie par une fonction du serveur et lue par les deux
clients. Chaque test pose d'abord le CAS FAUTIF — ce que l'app montrait, ou ce
qu'une copie divergente montrerait.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session

from app.models.communaute import CommentaireSondage, Idee, PetiteAnnonce
from app.models.core import FaqItem, ReponseCommunaute, RoleUtilisateur, StatutUtilisateur
from app.routers import annonces, idees
from app.routers.auth_schemas import BatimentPublic
from app.routers.faq import FaqItemRead, list_faq
from app.routers.sondages.commun import SondageDetail
from app.utils import horloge
from app.utils.faq_categories import categorie_lue_par, libelle_categorie_faq
from app.utils.nouveaute import est_nouveau
from app.utils.reponses import enrich_reponse
from tests.aides_base import compte

PROPRIETAIRE = RoleUtilisateur.propriétaire.value


def _resident(session: Session, prefixe: str, **champs):
    return compte(session, prefixe=prefixe, roles_json=PROPRIETAIRE, **champs)


# ── 1. Le badge NEW ──────────────────────────────────────────────────────────


def test_un_element_de_trois_jours_n_est_plus_nouveau():
    maintenant = horloge.maintenant()
    assert not est_nouveau(maintenant - timedelta(hours=72), maintenant)
    assert not est_nouveau(maintenant - timedelta(hours=48), maintenant)
    assert est_nouveau(maintenant - timedelta(hours=47), maintenant)
    assert not est_nouveau(None, maintenant)


def test_idee_et_annonce_portent_leur_nouveaute(session: Session):
    auteur = _resident(session, "auteur")
    vieille = Idee(
        titre="Composteur",
        description="…",
        auteur_id=auteur.id,
        cree_le=horloge.maintenant() - timedelta(hours=120),
    )
    neuve = Idee(titre="Bancs", description="…", auteur_id=auteur.id)
    annonce = PetiteAnnonce(titre="Vélo", description="…", auteur_id=auteur.id)
    session.add_all([vieille, neuve, annonce])
    session.commit()
    lues = {i["titre"]: i for i in idees._enrich([vieille, neuve], auteur, session)}
    assert lues["Composteur"]["nouveau"] is False
    assert lues["Bancs"]["nouveau"] is True
    assert annonces._enrich(annonce, auteur, session)["nouveau"] is True


# ── 2. La FAQ : le libellé d'une catégorie, et qui la lit ────────────────────


def test_la_categorie_copropriete_mandataire_se_lit_bailleur():
    assert libelle_categorie_faq("Copropriétaire ou MANDATAIRE") == "📋 Copropriétaire bailleur"
    assert libelle_categorie_faq("🗑️ Tri des déchets") == "🗑️ Tri des déchets"
    assert libelle_categorie_faq(None) == "Général"
    item = FaqItem(categorie="Copropriétaire / mandataire", question="?", reponse="!", id=1)
    item.cree_le = item.mis_a_jour_le = horloge.maintenant()
    assert FaqItemRead.model_validate(item).categorie_libelle == "📋 Copropriétaire bailleur"


def test_un_locataire_ne_lit_pas_les_categories_des_coproprietaires():
    locataire = StatutUtilisateur.locataire
    assert not categorie_lue_par("Copropriétaire résident", locataire)
    assert not categorie_lue_par("Copropriétaire / mandataire", locataire)
    assert categorie_lue_par("Locataires", locataire)
    resident = StatutUtilisateur.copropriétaire_résident
    assert not categorie_lue_par("Locataires", resident)
    assert not categorie_lue_par("Copropriétaire bailleur", resident)
    assert categorie_lue_par("Copropriétaire résident", resident)
    bailleur = StatutUtilisateur.copropriétaire_bailleur
    assert not categorie_lue_par("Copropriétaire résident", bailleur)
    assert categorie_lue_par("Copropriétaire / mandataire", bailleur)
    #  Sans statut résidentiel connu (syndic, mandataire), tout reste lisible —
    #  comme l'écran le faisait.
    assert categorie_lue_par("Locataires", StatutUtilisateur.syndic)
    assert categorie_lue_par("Locataires", None)


def test_get_faq_filtre_pour_le_lecteur_et_rend_tout_au_conseil(session: Session):
    for cat in ("Locataires", "Copropriétaire résident", "Général"):
        session.add(FaqItem(categorie=cat, question=f"Q {cat}", reponse="R"))
    session.commit()
    locataire = _resident(session, "loc", statut=StatutUtilisateur.locataire)
    cs = compte(
        session,
        prefixe="cs",
        roles_json=RoleUtilisateur.conseil_syndical.value,
        statut=StatutUtilisateur.locataire,
    )
    lues = {i.categorie for i in list_faq(session=session, user=locataire)}
    assert lues == {"Locataires", "Général"}
    assert {i.categorie for i in list_faq(session=session, user=cs)} == {
        "Locataires",
        "Copropriétaire résident",
        "Général",
    }


# ── 3. Les droits affichés : crayon et corbeille ─────────────────────────────


def test_le_conseil_n_a_pas_le_crayon_d_une_idee_l_auteur_si(session: Session):
    auteur = _resident(session, "auteur")
    cs = compte(session, prefixe="cs", roles_json=RoleUtilisateur.conseil_syndical.value)
    admin = compte(session, prefixe="admin", roles_json=RoleUtilisateur.admin.value)
    idee = Idee(titre="Bancs", description="…", auteur_id=auteur.id)
    session.add(idee)
    session.commit()

    def lue(par):
        return idees._enrich([idee], par, session)[0]

    assert lue(cs)["peut_modifier"] is False
    assert lue(cs)["peut_supprimer"] is False
    assert lue(auteur)["peut_modifier"] is True
    assert lue(auteur)["peut_supprimer"] is False
    assert lue(admin)["peut_modifier"] is True
    assert lue(admin)["peut_supprimer"] is True


def test_annonce_le_crayon_a_l_auteur_la_corbeille_au_conseil(session: Session):
    auteur = _resident(session, "auteur")
    voisin = _resident(session, "voisin")
    cs = compte(session, prefixe="cs", roles_json=RoleUtilisateur.conseil_syndical.value)
    annonce = PetiteAnnonce(titre="Vélo", description="…", auteur_id=auteur.id)
    session.add(annonce)
    session.commit()

    def lue(par):
        return annonces._enrich(annonce, par, session)

    assert lue(voisin)["peut_modifier"] is False
    assert lue(voisin)["peut_supprimer"] is False
    assert lue(cs)["peut_modifier"] is False
    assert lue(cs)["peut_supprimer"] is True
    assert lue(auteur)["peut_modifier"] is True
    assert lue(auteur)["peut_supprimer"] is True


def test_une_reponse_se_supprime_par_son_auteur_ou_le_conseil(session: Session):
    auteur = _resident(session, "auteur")
    voisin = _resident(session, "voisin")
    cs = compte(session, prefixe="cs", roles_json=RoleUtilisateur.conseil_syndical.value)
    rep = ReponseCommunaute(rubrique="idee", cible_id=1, auteur_id=auteur.id, contenu="Oui")
    commentaire = CommentaireSondage(sondage_id=1, auteur_id=auteur.id, contenu="Non")
    for r in (rep, commentaire):
        assert enrich_reponse(r, session, lecteur=voisin)["peut_supprimer"] is False
        assert enrich_reponse(r, session, lecteur=auteur)["peut_supprimer"] is True
        assert enrich_reponse(r, session, lecteur=cs)["peut_supprimer"] is True


# ── 4. L'annonce : « Gratuit », « Prénom NOM » ───────────────────────────────


def test_un_don_sans_prix_est_gratuit_une_vente_sans_prix_non(session: Session):
    auteur = _resident(session, "auteur", prenom="Odile", nom="Sorel")
    vente = PetiteAnnonce(titre="Table", description="…", type_annonce="vente", auteur_id=auteur.id)
    don = PetiteAnnonce(titre="Vélo", description="…", type_annonce="don", auteur_id=auteur.id)
    don_prix = PetiteAnnonce(
        titre="Lampe", description="…", type_annonce="don", prix=5, auteur_id=auteur.id
    )
    session.add_all([vente, don, don_prix])
    session.commit()
    assert annonces._enrich(vente, auteur, session)["gratuit"] is False
    assert annonces._enrich(don_prix, auteur, session)["gratuit"] is False
    lue = annonces._enrich(don, auteur, session)
    assert lue["gratuit"] is True
    assert lue["auteur_affiche"] == "Odile SOREL"
    #  Rien de plus que ce que la carte montrait déjà : le nom composé des deux
    #  champs servis, et le schéma typé le rend tel quel.
    assert annonces.AnnonceRead.model_validate(lue).auteur_affiche == "Odile SOREL"


# ── 5. Ce que les réponses déclarent ─────────────────────────────────────────


def test_la_liste_publique_des_batiments_ne_rend_que_le_numero():
    """La route sans session rendait la ligne entière (étages, caves, spécificités)."""
    assert set(BatimentPublic.model_fields) == {"id", "numero"}


def test_la_fiche_d_un_sondage_tait_les_votes_quand_ils_sont_masques():
    """« 0 vote » se lirait « personne n'a voté » : les clés restent ABSENTES."""
    fiche = SondageDetail.model_validate(
        {
            "id": 1,
            "question": "?",
            "resultats_publics": False,
            "cree_le": horloge.maintenant(),
            "options": [{"id": 1, "libelle": "Oui", "ordre": 0, "champ_libre": False}],
        }
    )
    option = fiche.model_dump(exclude_unset=True)["options"][0]
    assert "nb_votes" not in option and "reponses_libres" not in option
