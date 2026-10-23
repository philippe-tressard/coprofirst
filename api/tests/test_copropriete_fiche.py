"""La fiche copropriété : ce qu'elle enregistre, et d'où vient son assurance.

## Ce que ce fichier protégeait, et ce qu'il protège désormais

À l'origine (13/08/2026) : `PATCH /copropriete` recevait `assurance_echeance` en
**chaîne** et l'affectait à une colonne `date`. SQLAlchemy levait, et **toute la
fiche devenait inenregistrable** — y compris quand seul le nom du syndic avait
changé, puisque l'erreur tombe au `commit`. Un écran qui refuse d'enregistrer ne
dit pas *pourquoi* : le front affichait « Erreur lors de la sauvegarde ».

⚠️ **Ce champ n'existe plus dans le schéma d'entrée** (#490) : l'assurance est
devenue un `ContratEntretien` rattaché à un `Prestataire`, parce que trois
chaînes libres décrivaient un objet que le projet possédait déjà. Les tests qui
éprouvaient la conversion de cette chaîne n'ont donc plus d'objet.

🔴 **Ils ne sont pas supprimés pour autant : ils sont DÉPLACÉS sur l'invariant
qui reste.** Trois choses doivent rester vraies :

1. la fiche s'enregistre toujours, et un champ n'en écrase pas un autre — c'est
   le symptôme le plus déroutant du défaut d'origine, et il ne dépendait pas de
   l'assurance ;
2. les trois champs d'assurance ne s'écrivent **plus** par cette route — les
   accepter en silence rouvrirait le doublon que #490 vient de fermer ;
3. ce que la fiche AFFICHE vient du contrat, pas des colonnes conservées.

Supprimer un test parce que son champ a bougé, c'est perdre la raison pour
laquelle il existait. La classe d'erreur — une valeur mal typée qui emporte tout
l'enregistrement — n'a pas disparu avec le champ.
"""

from datetime import date

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    ContratEntretien,
    Copropriete,
    Prestataire,
    TypeEquipement,
)
from app.routers.copropriete import (
    CoproprieteUpdate,
    copropriete_lue,
    update_copropriete,
)


@pytest.fixture()
def copro() -> int:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for ligne in session.exec(select(Copropriete)).all():
            session.delete(ligne)
        session.commit()
        c = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(c)
        session.commit()
        session.refresh(c)
        identifiant = c.id
    yield identifiant
    with Session(engine) as session:
        #  ⚠️ Les CONTRATS d'abord. Sans cela, supprimer la copropriété fait
        #  tenter à SQLAlchemy un `UPDATE contrat_entretien SET copropriete_id
        #  = NULL`, refusé par la contrainte `NOT NULL` — et l'erreur tombe au
        #  DÉMONTAGE, donc elle se lit comme un échec du test suivant.
        for modele in (ContratEntretien, Prestataire, Copropriete):
            for ligne in session.exec(select(modele)).all():
                session.delete(ligne)
            session.commit()


def _patch(**champs):
    """Appelle le router directement : c'est la couche où le défaut vivait."""
    with Session(engine) as session:
        return update_copropriete(body=CoproprieteUpdate(**champs), session=session, _=None)


def test_modifier_un_champ_n_ecrase_pas_les_autres(copro):
    """Le symptôme le plus déroutant du défaut d'origine, conservé.

    L'erreur du 13/08 tombait au `commit` : elle emportait la requête entière
    quel que soit le champ réellement modifié. Ce test ne dépend pas de
    l'assurance — il éprouve que la fiche s'enregistre par morceaux sans se
    perdre, et c'est ce qui reste vrai après #490.
    """
    _patch(nb_lots_total=195)
    lu = _patch(nom="Résidence du Parc")
    assert lu.nom == "Résidence du Parc"
    assert lu.nb_lots_total == 195, "modifier le nom a écrasé un autre champ"


#: Ce qu'une fiche a le droit d'écrire sur une section adossée à un contrat :
#: la DÉSIGNATION du contrat, et rien d'autre.
#:
#: 🔴 La distinction est tout le sujet. Écrire `assurance_compagnie = "AXA"`
#: crée un second assureur qui ne renvoie à rien (#490). Écrire
#: `assurance_contrat_id = 12` dit lequel des contrats EXISTANTS fait foi : la
#: donnée reste unique, côté contrat.
DESIGNATIONS_AUTORISEES = {"assurance_contrat_id", "syndic_contrat_id"}


def test_les_VALEURS_d_assurance_ne_s_ecrivent_plus_par_cette_route():
    """🔴 Elles ont QUITTÉ le schéma d'entrée (#490), et cela se vérifie.

    Les accepter « au cas où » aurait été pire que de les retirer : l'écran
    aurait continué d'écrire du texte que plus personne ne lit, et la fiche
    aurait pu afficher un assureur pendant que le contrat en désignait un autre.

    ⚠️ Ce test lit le SCHÉMA, pas une réponse : un champ réaccepté ne casserait
    aucun appel — il recréerait silencieusement le doublon.

    ⚠️ **Précisé le 20/08/2026 (#553)**, et le garde-fou avait raison de crier :
    il refusait `assurance_contrat_id`, que ce lot venait d'ajouter. Le motif
    « tout ce qui commence par `assurance_` » confondait la VALEUR et la
    DÉSIGNATION. Élargir le test à la liste blanche, plutôt que d'y ajouter une
    exception, garde la règle lisible — et il couvre maintenant le syndic, qui
    n'existait pas quand il a été écrit.
    """
    fautifs = {
        c
        for c in CoproprieteUpdate.model_fields
        if c.startswith(("assurance_", "syndic_")) and c not in DESIGNATIONS_AUTORISEES
    }
    assert not fautifs, (
        f"{sorted(fautifs)} sont de nouveau acceptés en écriture : une section "
        "adossée à un contrat ne se SAISIT pas, elle se DÉSIGNE."
    )


def test_les_designations_sont_bien_acceptees():
    """⚠️ Le cas zéro du test ci-dessus, et il compte.

    Un `CoproprieteUpdate` amputé de ses deux désignations rendrait le test
    précédent vert — il ne trouverait plus rien de fautif — pendant que l'écran
    ne pourrait plus rien choisir. Un contrôle qui passe parce qu'il n'y a plus
    rien à contrôler n'est pas un contrôle (`standards/04` §2).
    """
    manquantes = DESIGNATIONS_AUTORISEES - set(CoproprieteUpdate.model_fields)
    assert not manquantes, (
        f"{sorted(manquantes)} ne sont plus acceptées : la fiche ne peut plus "
        "désigner son contrat, et le test ci-dessus ne mesure plus rien."
    )


def test_l_assurance_affichee_vient_du_CONTRAT_pas_des_colonnes(copro):
    """Ce que la fiche montre est celui du contrat.

    Les colonnes `assurance_*` ne sont plus déclarées par le modèle (#2059) : le test qui
    les renseignait « volontairement différentes » pour prouver laquelle est lue n'a plus
    de colonne à renseigner. Reste ce qui compte : la fiche rend la compagnie, le numéro
    et l'échéance du CONTRAT, et l'échéance se déduit (`prochaine_visite` n'est pas lue).
    """
    with Session(engine) as session:
        presta = Prestataire(nom="Nouvel Assureur", specialite="Assurance")
        session.add(presta)
        session.commit()
        session.refresh(presta)

        session.add(
            ContratEntretien(
                copropriete_id=copro,
                prestataire_id=presta.id,
                type_equipement=TypeEquipement.assurance,
                libelle="Assurance de la copropriété",
                numero_contrat="POL-2026",
                date_debut=date(2026, 1, 1),
                prochaine_visite=date(2027, 6, 30),
            )
        )
        session.commit()

        lu = copropriete_lue(session, session.get(Copropriete, copro))

    assert lu.assurance_compagnie == "Nouvel Assureur"
    assert lu.assurance_numero_police == "POL-2026"

    #  🔴 L'échéance se DÉDUIT (`utils/echeance_contrat.py`), elle ne recopie
    #  plus `prochaine_visite` — un champ qui s'appelle « Prochaine visite »
    #  dans le formulaire et qui n'a pas de sens pour une assurance.
    #
    #  Contrat commencé le 01/01/2026, sans durée saisie → annuel, donc terme au
    #  01/01/2027, reporté tant qu'il est passé. La valeur de `prochaine_visite`
    #  (30/06/2027) est posée DIFFÉRENTE exprès : c'est le seul moyen de prouver
    #  laquelle des deux est lue.
    assert lu.assurance_echeance != date(2027, 6, 30), "la fiche lit encore prochaine_visite"
    assert lu.assurance_echeance == date(2027, 1, 1)


def test_sans_contrat_la_fiche_n_invente_rien(copro):
    """Aucun contrat : la ligne se masque, comme le faisait un champ texte vide.

    Les colonnes héritées (`assurance_compagnie`…) ont quitté la base avec la 0308
    (#2124) : il n'y a plus d'ancienne saisie sur laquelle retomber.
    """
    with Session(engine) as session:
        lu = copropriete_lue(session, session.get(Copropriete, copro))
    assert lu.assurance_compagnie is None


def test_le_contrat_le_plus_recent_gagne(copro):
    """Une copropriété change d'assureur ; l'ancien contrat reste en base.

    C'est même tout l'intérêt d'en avoir fait un contrat. Rendre le premier
    trouvé afficherait l'assureur de l'an dernier sans que rien ne le dise.
    """
    with Session(engine) as session:
        for nom, debut, police in (
            ("Ancien", date(2024, 1, 1), "A-1"),
            ("Récent", date(2026, 1, 1), "R-1"),
        ):
            presta = Prestataire(nom=nom, specialite="Assurance")
            session.add(presta)
            session.commit()
            session.refresh(presta)
            session.add(
                ContratEntretien(
                    copropriete_id=copro,
                    prestataire_id=presta.id,
                    type_equipement=TypeEquipement.assurance,
                    libelle="Assurance de la copropriété",
                    numero_contrat=police,
                    date_debut=debut,
                )
            )
        session.commit()
        lu = copropriete_lue(session, session.get(Copropriete, copro))
    assert lu.assurance_compagnie == "Récent"


def test_les_deux_decomptes_de_lots_sont_independants(copro):
    """Les deux chiffres de la fiche ANAH ne se déduisent pas l'un de l'autre.

    La fiche du registre national en porte deux : le total (caves et parkings
    compris) et les seuls lots d'habitation, commerces et bureaux — relevé réel
    sur la résidence, 195 et 63. L'application n'avait qu'un champ, si bien que le
    chiffre saisi ne disait pas lequel il était et que le produit annonçait une
    taille fausse du simple au triple.

    Ce test verrouille l'indépendance : écrire l'un ne doit pas toucher l'autre.
    Le rapport entre les deux dépend du nombre de caves et de parkings, propre à
    chaque copropriété — le déduire serait inventer une mesure.
    """
    lu = _patch(nb_lots_total=195, nb_lots_principaux=63)
    assert (lu.nb_lots_total, lu.nb_lots_principaux) == (195, 63)

    lu = _patch(nb_lots_total=196)
    assert lu.nb_lots_principaux == 63, "modifier le total a écrasé les lots principaux"


def test_un_seul_decompte_renseigne_reste_valide(copro):
    """Une copropriété peut n'en connaître qu'un — on n'invente pas l'autre.

    Cas zéro du couple (`standards/04-fiabilite-des-controles.md` §2) : le champ
    absent reste vide, et l'écran n'affiche que celui qu'il a.
    """
    lu = _patch(nb_lots_principaux=63)
    assert lu.nb_lots_principaux == 63
    assert lu.nb_lots_total is None, "le total a été déduit alors que personne ne le sait"
