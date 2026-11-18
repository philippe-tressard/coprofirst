"""Les options de publication d'un ticket : UNE écriture, TROIS chemins.

## Le besoin (05/09/2026, demandé à l'écran)

> « tous les autres options de publication doivent être aussi conservé dans
>   l'objet pour les tickets en édition et commentaire »
> « pas que Visibilité du ticket »

Le ticket ne portait qu'une option (🛡️ « au seul conseil syndical »), et
seulement à la création et à la correction. L'actualité en montre quatre, dans
les quatre états, et ce qu'on y enregistre devient l'état.

## 🔴 Ce que ces tests protègent

La création, le `PATCH` et le commentaire écrivent les mêmes options. Écrite
trois fois, la règle diverge au premier ajout — c'est ce qui était arrivé aux
destinataires, en quatre exemplaires (`commun.py`, en-tête). Ces tests vérifient
donc **le fait par les trois portes**, et refusent qu'une quatrième option
apparaisse dans la table sans que quelqu'un décide ce qu'elle écrit.
"""

from __future__ import annotations

import ast
import pathlib

from app.routers.tickets.commun import (
    OPTIONS_TICKET,
    appliquer_options,
    options_du_ticket,
)


class _Corps:
    """Un corps de requête minimal — seuls comptent les attributs présents."""

    def __init__(self, **champs):
        for cle in OPTIONS_TICKET:
            setattr(self, cle, champs.get(cle))


class _Ticket:
    """Un ticket en mémoire : ces règles ne touchent pas la base."""

    def __init__(self, **champs):
        self.epingle = champs.get("epingle", False)
        self.confidentiel = champs.get("confidentiel", False)
        self.priorite = champs.get("priorite", "normale")
        self.suivi_kanban = champs.get("suivi_kanban", False)
        self.suivi_actualite = champs.get("suivi_actualite")
        self.ferme_le = None


def test_TOUTES_les_options_s_appliquent():
    """⚠️ Le nom disait « les trois » — elles sont quatre depuis #833.

    Un test dont le nom compte les cas doit être renommé quand le compte change,
    sinon il devient un contresens qu'on lit sans le voir. C'est pourquoi
    l'assertion, elle, ne compte pas : elle compare à `OPTIONS_TICKET`.
    """
    t = _Ticket()
    changees = appliquer_options(
        t,
        _Corps(
            epingle=True, urgente=True, confidentiel=True, suivi_kanban=True, suivre_actualite=True
        ),
        est_cs=True,
    )
    assert t.epingle is True
    assert t.confidentiel is True
    assert t.priorite == "haute", "🚨 pilote la priorité, il n'y a pas de colonne `urgente`"
    assert t.suivi_kanban is True
    assert t.suivi_actualite == "ouvert", "la case pose l'ÉTAT du suivi (10/10/2026)"
    assert set(changees) == set(OPTIONS_TICKET)
    #  Le faux `_Ticket` ne prouve rien du VRAI modèle : chaque option écrite
    #  telle quelle doit en être une colonne (`urgente` passe par `priorite`,
    #  `suivre_actualite` par `suivi_actualite`).
    from app.models.core import Ticket

    indirectes = {"urgente": "priorite", "suivre_actualite": "suivi_actualite"}
    for colonne in [indirectes.get(o, o) for o in OPTIONS_TICKET]:
        assert colonne in Ticket.model_fields, f"`Ticket.{colonne}` n'existe plus"


def test_None_ne_touche_a_RIEN():
    """🔴 La convention qui rend le même code utilisable par un commentaire.

    Un commentaire qui ne parle que d'une case ne doit pas remettre les autres à
    leur défaut. C'est la même règle que `perimetre_cible` (#497) : `None` veut
    dire « cette entrée ne dit rien de cette option ».
    """
    t = _Ticket(epingle=True, confidentiel=True, priorite="haute")
    changees = appliquer_options(t, _Corps(), est_cs=True)
    assert changees == []
    assert (t.epingle, t.confidentiel, t.priorite) == (True, True, "haute")


def test_un_non_CS_ne_peut_ni_EPINGLER_ni_RESTREINDRE():
    """Ces deux options ordonnent la liste du conseil et décident qui lit : elles
    lui appartiennent (#710). Le contrôle est dans la règle, pas chez l'appelant.

    🔴 `urgente` EN EST SORTIE le 07/09/2026, et ce test l'a refusé avant que la
    CI ne le fasse — c'est exactement son rôle, et il tenait.

    Le retrait de la catégorie « Urgence » (migration 0177) a fait de cette option
    le SEUL moyen de dire qu'un ticket presse. Or la catégorie était ouverte à
    tout le monde et l'option était réservée au conseil : un résident face à une
    inondation n'avait plus aucun moyen de le signaler. Une description de sa
    propre situation appartient à l'auteur ; l'ordre de la liste et l'audience,
    non.

    C'est aussi le cas zéro de ce retour : ouvrir `urgente` ne doit pas ouvrir
    les deux autres — sans lui, tout ouvrir passerait au vert.

    Le récit de la régression et le cas nominal, sur un vrai `Ticket`, vivent
    dans `test_urgence_par_le_resident.py`.
    """
    t = _Ticket()
    changees = appliquer_options(t, _Corps(epingle=True, confidentiel=True), est_cs=False)
    assert changees == []
    assert (t.epingle, t.confidentiel) == (False, False)


def test_un_non_CS_peut_dire_que_ca_PRESSE():
    """Le pendant du précédent : ce qui a été rendu, et à qui."""
    t = _Ticket()
    changees = appliquer_options(t, _Corps(urgente=True), est_cs=False)
    assert changees == ["urgente"]
    assert t.priorite == "haute"


def test_decocher_marche_aussi():
    """Une option se retire comme elle se pose — sinon elle serait à sens unique."""
    t = _Ticket(epingle=True, confidentiel=True, priorite="haute")
    appliquer_options(t, _Corps(epingle=False, urgente=False, confidentiel=False), est_cs=True)
    assert (t.epingle, t.confidentiel, t.priorite) == (False, False, "normale")


def test_la_lecture_et_l_ecriture_couvrent_les_MEMES_options():
    """Les deux sens de la même table.

    Si `options_du_ticket` oubliait une option qu'`appliquer_options` écrit,
    l'écran rouvrirait le formulaire avec une case décochée sur un ticket qui la
    porte — et l'enregistrement suivant la retirerait sans que personne l'ait
    demandé.
    """
    t = _Ticket(epingle=True, confidentiel=True, priorite="haute", suivi_kanban=True)
    assert set(options_du_ticket(t)) == set(OPTIONS_TICKET)
    assert options_du_ticket(t) == {
        "epingle": True,
        "urgente": True,
        "confidentiel": True,
        #  Ajoutée le 08/09/2026 (#833) — et ce test l'a exigée le jour même :
        #  la table d'écriture l'avait, celle de lecture non.
        "suivi_kanban": True,
        #  10/10/2026 : la case de l'actualité, lue sur son ÉTAT de suivi.
        "suivre_actualite": False,
    }


def test_les_TROIS_chemins_appellent_la_regle_commune():
    """🔴 Le contrôle qui empêche la quatrième copie.

    Création, `PATCH` et commentaire doivent passer par `appliquer_options`. Une
    règle d'autorisation recopiée ne se durcit pas : on en corrige deux sur
    trois (`standards/03-securite.md` §1).
    """
    racine = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "tickets"
    #  ⚠️ `mise_a_jour.py` est né le 08/09/2026 (#833) : la CORRECTION pesait 238
    #  lignes dans `crud.py`, et sa moitié basse vivait déjà dans `correction.py`.
    #  Le chemin n'a pas disparu, il a déménagé — et ce test, qui compte par
    #  MODULE, l'a dit tout de suite. C'est ce qu'on attend de lui.
    #  Le chemin de la Suite a déménagé de même (01/10/2026) : `suite_sections.py`
    #  sert l'ajout ET la correction d'une Suite, qui rouvre ses sections.
    for module, attendus in (("crud.py", 1), ("mise_a_jour.py", 1), ("suite_sections.py", 1)):
        source = (racine / module).read_text(encoding="utf-8")
        arbre = ast.parse(source)
        appels = [
            n
            for n in ast.walk(arbre)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "appliquer_options"
        ]
        assert len(appels) == attendus, (
            f"{module} : {len(appels)} appel(s) à `appliquer_options`, {attendus} attendu(s). "
            "Soit un chemin ne pose plus les options, soit un quatrième est apparu "
            "sans passer par la règle commune."
        )


def test_aucune_option_muette_dans_la_table():
    """Une option déclarée doit écrire quelque chose.

    `OPTIONS_TICKET` est la table ; si on y ajoute une clé sans lui donner de
    colonne, `appliquer_options` la traverserait en silence et l'écran
    proposerait une case sans effet — la « promesse vide » que 🔒 aurait été.
    """
    for option in OPTIONS_TICKET:
        t = _Ticket()
        changees = appliquer_options(t, _Corps(**{option: True}), est_cs=True)
        assert changees == [option], (
            f"L'option « {option} » est déclarée mais n'écrit rien : une case "
            "sans effet derrière elle."
        )


def test_les_TROIS_corps_transportent_chaque_option():
    """🔴 #1171 (23/09/2026) — le chemin appelait la règle, et ne lui passait rien.

    `appliquer_options` lit `getattr(body, option, None)`. Or `TicketCreate` ne
    déclarait ni `urgente` ni `confidentiel` : Pydantic ignore un champ inconnu,
    le formulaire les envoyait, le serveur lisait `None`. Une affaire créée
    « 🛡️ réservée au conseil » partait lisible de tout son périmètre, et
    « 🚨 Urgent » coché à la création ne comptait pas.

    Le test précédent vérifie que les trois chemins APPELLENT la règle ; celui-ci,
    que leur corps TRANSPORTE chaque option. Dérivé d'`OPTIONS_TICKET` : une
    option ajoutée demain et oubliée dans un schéma échoue ici.
    """
    from app.schemas import TicketCreate, TicketUpdate
    from app.schemas_tickets import TicketEvolutionCreate

    #  Une option qui ne se pose que par un chemin se déclare ici, avec sa raison.
    #  `suivi_kanban` : un geste de CONDUITE du suivi, pas une parole — il ne passe
    #  pas par une Suite (#833).
    #  `suivre_actualite` : de même — la case s'active au formulaire, l'ÉTAT se
    #  change par une Suite (arbitré le 10/10/2026).
    hors_suite = {"suivi_kanban", "suivre_actualite"}
    manques = [
        f"{schema.__name__}.{option}"
        for schema in (TicketCreate, TicketUpdate, TicketEvolutionCreate)
        for option in OPTIONS_TICKET
        if option not in schema.model_fields
        and not (schema is TicketEvolutionCreate and option in hors_suite)
    ]
    assert not manques, f"Options perdues en silence par le corps de requête : {manques}"
    for option in hors_suite:
        assert option in OPTIONS_TICKET, (
            f"`{option}` déclarée hors Suite, mais n'est plus une option."
        )


def test_l_urgence_relue_de_la_base_se_compare_par_sa_valeur():
    """Relue de la base, la priorité est une ÉNUMÉRATION : `str` rendait
    « PrioriteTicket.haute », et le geste ⚡ passait pour changé à chaque
    enregistrement — l'alerte d'une actualité aurait resonné (#2789)."""
    from app.models.core import Ticket
    from app.models.tickets import PrioriteTicket

    t = Ticket(titre="t", priorite=PrioriteTicket.haute)
    assert options_du_ticket(t)["urgente"] is True
    assert appliquer_options(t, _Corps(urgente=True), est_cs=True) == []
    assert appliquer_options(t, _Corps(urgente=False), est_cs=True) == ["urgente"]
