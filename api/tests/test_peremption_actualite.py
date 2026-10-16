"""Une information datée sort du fil toute seule (#1093).

## Le besoin

« Coupure d'eau jeudi 9h-12h » n'a plus aucun intérêt vendredi ; « Nouveau
règlement de stationnement » n'en perd jamais. Rien ne les distinguait, et le
fil accumulait.

## 🔴 Dérivée à la lecture, JAMAIS recopiée à l'écriture

    perime_le =  fin de l'événement      si date d'événement
          sinon  jamais

⚠️ Il y avait un troisième champ en tête, `visible_jusqu_au`, saisi par
l'auteur pour une « durée de vie choisie ». Livré le matin du 22/09/2026,
retiré l'après-midi, arbitré à l'écran : *« cette date est à enlever, elle
est calculée par l'appli »*. Ce qui n'a pas de date d'événement ne périme
pas — l'archivage à trente jours couvre ce cas depuis le 19/08/2026, et le
champ faisait donc saisir ce que le produit savait déjà décider.

Calculer la péremption à la création laisserait un report d'événement
(jeudi → mardi) derrière lui : la date stockée dirait encore jeudi. C'est le
motif « deux copies qui divergent sur le cas limite », déjà vu trois fois dans
ce dépôt. Une source, une fonction.

## Périmée ≠ supprimée

Elle quitte le fil et le calendrier, elle **entre aux archives**, et son URL
directe continue d'ouvrir quelque chose — un lien envoyé il y a trois semaines
ne doit pas mener nulle part. C'est exactement ce que fait l'archivage : il
n'efface rien.

## ⚠️ La péremption DÉPINGLE

L'ordre des règles n'est pas cosmétique. L'épinglage interdit l'archivage
automatique — « garder en vue » — mais une information périmée n'a plus rien à
garder en vue. La péremption passe donc **avant** l'épinglage, et c'est la
seule règle qui le fasse après la décision humaine d'archiver.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.utils.archivage import REGLES, est_archivable, perime_le


class _Pub:
    """Le strict nécessaire : l'archivage est PUR, il ne lit qu'un objet.

    Une affaire de catégorie « Actualité » depuis le 23/09/2026 (#1091) : la
    règle se choisit sur la catégorie (`archivage._regle_de`), jamais par
    l'appelant — d'où le type « ticket » passé partout ci-dessous.
    """

    def __init__(self, **champs):
        self.categorie = "actualite"
        self.statut = champs.get("statut", "publie")
        self.mis_a_jour_le = champs.get("mis_a_jour_le")
        self.cree_le = champs.get("cree_le", datetime(2026, 9, 1))
        self.archive_manuel = champs.get("archive_manuel", False)
        self.epingle = champs.get("epingle", False)
        self.debut = champs.get("debut")
        self.fin = champs.get("fin")


AUJOURDHUI = datetime(2026, 9, 22, 10, 0)
HIER = AUJOURDHUI - timedelta(days=1)
DEMAIN = AUJOURDHUI + timedelta(days=1)


# ══════════════════════════════════════════════════════════════════════════════
#  La dérivation — trois familles, une seule saisie
# ══════════════════════════════════════════════════════════════════════════════


def test_une_actualite_permanente_ne_perime_jamais():
    """Le cas par défaut, et le plus fréquent : on ne saisit rien."""
    assert perime_le(_Pub()) is None


def test_une_actualite_datee_perime_a_la_fin_de_l_evenement():
    """« Coupure d'eau jeudi 9h-12h » : rien de plus à saisir."""
    pub = _Pub(debut=datetime(2026, 9, 24, 9), fin=datetime(2026, 9, 24, 12))
    assert perime_le(pub) == date(2026, 9, 24)


def test_la_peremption_NE_SE_SAISIT_PAS():
    """🔴 Le garde-fou de l'arbitrage du 22/09/2026, pas de son effet.

    Le champ a existé une demi-journée. Sans ce test, il suffirait qu'on le
    juge « pratique » un jour pour qu'il revienne — et il reviendrait avec sa
    promesse : faire saisir une date que le produit sait déjà calculer.

    Il regarde les DEUX portes : la colonne, et ce que le serveur accepte en
    entrée. Verrouiller la première seule laisserait passer un schéma qui
    accepte le champ et le jette en silence.
    """
    from app.models.core import Ticket
    from app.schemas import TicketCreate, TicketUpdate

    assert "visible_jusqu_au" not in Ticket.model_fields, (
        "La colonne est revenue : la péremption se déduit, elle ne se saisit pas (#1093)."
    )
    for schema in (TicketCreate, TicketUpdate):
        assert "visible_jusqu_au" not in schema.model_fields, (
            f"{schema.__name__} accepte de nouveau une date de validité en entrée."
        )


def test_un_debut_sans_fin_perime_au_debut():
    """Un événement ponctuel n'a qu'une date, et elle suffit à le dater."""
    assert perime_le(_Pub(debut=datetime(2026, 9, 24, 18))) == date(2026, 9, 24)


# ══════════════════════════════════════════════════════════════════════════════
#  L'effet : elle quitte les listes actives
# ══════════════════════════════════════════════════════════════════════════════


def test_le_jour_meme_elle_est_encore_la():
    """🔴 La péremption est au SOIR du jour dit, pas à son matin.

    Une coupure d'eau qui finit aujourd'hui à midi reste lisible ce soir : la
    date dit la fin de l'événement, pas l'heure à laquelle on l'efface.
    """
    pub = _Pub(fin=AUJOURDHUI)
    assert est_archivable("ticket", pub, maintenant=AUJOURDHUI) is False


def test_le_lendemain_elle_sort():
    pub = _Pub(fin=HIER)
    assert est_archivable("ticket", pub, maintenant=AUJOURDHUI) is True


def test_a_00h30_a_paris_la_veille_est_passee():
    """🔴 Le « jour dit » est celui de Paris, pas celui de l'UTC (#1565).

    `maintenant` est l'instant de la base, en UTC naïf. 22:30 UTC le 1er octobre,
    c'est 00:30 le 2 à Paris : une coupure d'eau finie le 1er est passée. Lire le
    jour en UTC la laissait au fil jusqu'à deux heures du matin.
    """
    #  Créée la semaine même : seule la péremption peut la sortir, pas l'âge.
    pub = _Pub(fin=datetime(2026, 10, 1, 18, 0), cree_le=datetime(2026, 9, 28))
    assert est_archivable("ticket", pub, maintenant=datetime(2026, 10, 1, 22, 30)) is True
    assert est_archivable("ticket", pub, maintenant=datetime(2026, 9, 30, 22, 30)) is False


def test_une_date_a_venir_ne_change_rien():
    pub = _Pub(fin=DEMAIN)
    assert est_archivable("ticket", pub, maintenant=AUJOURDHUI) is False


def test_la_peremption_DEPINGLE():
    """⚠️ L'épinglage interdit l'archivage automatique — mais pas celui-ci.

    « Garder en vue » n'a plus de sens pour une information qui n'est plus
    valable. Sans cette règle, une coupure d'eau épinglée resterait en tête du
    fil indéfiniment, et c'est le seul cas où l'épinglage nuit.
    """
    pub = _Pub(fin=HIER, epingle=True)
    assert est_archivable("ticket", pub, maintenant=AUJOURDHUI) is True


def test_l_archivage_manuel_prime_toujours():
    """Une décision humaine ne se discute pas, périmée ou non."""
    pub = _Pub(archive_manuel=True)
    assert est_archivable("ticket", pub, maintenant=AUJOURDHUI) is True


#: Tous les types déclarés, sauf celui qui périme. Lu dans `REGLES` et non
#: recopié : la liste écrite à la main nommait `evenement`, parti le 23/09/2026
#: (#1092), et ce cas-là sautait à chaque exécution sans que rien le dise.
#: Une actualité suivie (10/10/2026) reste une actualité : elle périme aussi.
_REGLES_D_ACTUALITE = ("actualite", "actualite_suivie")
_TYPES_QUI_NE_PERIMENT_PAS = sorted(t for t in REGLES if t not in _REGLES_D_ACTUALITE)


def test_la_liste_des_autres_types_n_est_pas_vide():
    """Cas zéro : un paramétrage vide rendrait le test ci-dessous vert sans rien lire."""
    assert "actualite" in REGLES, "la règle « actualite » a disparu de REGLES"
    assert "ticket" in _TYPES_QUI_NE_PERIMENT_PAS
    assert len(_TYPES_QUI_NE_PERIMENT_PAS) >= 5, _TYPES_QUI_NE_PERIMENT_PAS


@pytest.mark.parametrize("type_objet", _TYPES_QUI_NE_PERIMENT_PAS)
def test_les_autres_objets_ne_periment_pas(type_objet):
    """🔴 Une AFFAIRE ne périme jamais — elle se clôt.

    Une fuite d'eau ne cesse pas d'exister parce que personne n'a écrit depuis
    trois mois. L'équivalent est un signalement au conseil (« 4 affaires sans
    suite depuis 60 jours ») : c'est un manque de suivi, et le remède est qu'on
    s'en occupe, pas qu'elle disparaisse.

    Ce test vérifie que la règle de péremption ne s'est pas répandue aux autres
    types par un `getattr` trop large.
    """
    assert REGLES[type_objet].champs_peremption == (), (
        f"{type_objet} périmerait tout seul : seule une ACTUALITÉ le fait."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Le chemin réel vers l'écran : modèle → schéma
# ══════════════════════════════════════════════════════════════════════════════


def _lu(**champs):
    """L'affaire telle que l'écran la reçoit : `ticket_read`, sur une base jetable."""
    from sqlmodel import Session

    from app.models.core import Ticket
    from app.routers.tickets.commun import ticket_read
    from tests.aides_base import compte, moteur_de_test

    with Session(moteur_de_test()) as s:
        compte(s, prefixe="a", id=1, prenom="A", nom="B")
        t = Ticket(
            id=1,
            numero="TK-A1",
            titre="Assemblée générale",
            description="…",
            auteur_id=1,
            statut="publie",
            **champs,
        )
        s.add(t)
        s.commit()
        return ticket_read(s.get(Ticket, 1), s)


def test_la_derivation_traverse_le_schema_de_lecture():
    """🔴 Une règle juste que personne ne lit ne change rien à l'écran.

    `perime_le` se pose dans `ticket_read`. Sans ce test, la fonction pourrait
    être parfaite et la date ne jamais arriver au navigateur — c'est exactement
    ce qui est arrivé à `debut`/`fin`, saisissables depuis #1092 et **jamais
    rendus**.
    """
    lu = _lu(categorie="actualite", debut=datetime(2026, 9, 30, 18), fin=datetime(2026, 9, 30, 21))
    assert lu.fin == datetime(2026, 9, 30, 21)
    assert lu.perime_le == date(2026, 9, 30)


def test_une_affaire_suivie_datee_ne_perime_pas():
    """Une affaire se clôt, elle ne périme pas — même datée."""
    lu = _lu(categorie="panne", debut=datetime(2026, 9, 24, 9))
    assert lu.perime_le is None


def test_la_peremption_ne_se_STOCKE_nulle_part():
    """⚠️ Le garde-fou de la décision, pas de son effet.

    Une colonne `perime_le` survivrait à un report d'événement : jeudi devient
    mardi, la colonne dit encore jeudi, et l'actualité quitte le fil le jour où
    elle redevient utile. Ce test refuse qu'on l'ajoute un jour « pour
    accélérer une requête ».
    """
    from app.models.core import Ticket

    assert "perime_le" not in Ticket.model_fields, (
        "`perime_le` est devenue une COLONNE : elle se dérive à la lecture, "
        "sinon elle diverge au premier report de date (#1093)."
    )


def test_le_report_d_un_evenement_deplace_la_peremption():
    """La conséquence concrète de la dérivation : rien à resynchroniser."""
    pub = _Pub(fin=datetime(2026, 9, 24, 12))
    assert perime_le(pub) == date(2026, 9, 24)
    pub.fin = datetime(2026, 9, 29, 12)  # reportée
    assert perime_le(pub) == date(2026, 9, 29)
