"""🔒 L'alerte d'une actualité ⚡ urgente — la seule notification qui sonne sur un téléphone (#2789).

Décision de Philippe du 18/11/2026 (`utils/alerte_actualite`) : une actualité qui
devient urgente par le geste d'un modérateur fait sonner la cloche de ses lecteurs,
et seules ces notifications-là partent vers un téléphone. Ce fichier tient :

1. **les trois chemins du geste ⚡** — publication, correction, Suite — par les
   vraies routes, avec la vraie authentification ;
2. **une fois par passage** : corriger une actualité déjà urgente ne resonne pas ;
3. **rien d'autre ne sonne** : ni l'actualité non urgente, ni celle réservée au
   conseil, ni l'affaire urgente d'un résident ; et l'auteur du geste ne s'avertit pas ;
4. **la porte du push ne pousse que l'alerte**, quoi que sonne la cloche ;
5. **chaque appelant d'`appliquer_options` appelle `sonner_l_alerte`** — un quatrième
   chemin du geste ⚡ qui l'oublierait est refusé (éprouvé sur son cas fautif).
"""

from __future__ import annotations

import ast

import pytest
from sqlmodel import Session, select

from app.models.core import ConfigSite, Notification, RoleUtilisateur
from app.utils import cloche
from app.utils.alerte_actualite import alerte_due
from app.utils.push import porte
from app.utils.push.porte import TYPE_POUSSE
from app.utils.services import SERVICE_PUSH, cle_actif
from tests.aides_base import compte
from tests.aides_http import base_http, client_http
from tests.aides_sources import modules_app

DESCRIPTION = "<p>Coupure d'eau générale ce matin, à partir de 9 h.</p>"


@pytest.fixture
def moteur():
    with base_http() as m:
        yield m


@pytest.fixture
def scene(moteur):
    """Un membre du conseil connecté, deux résidents et un compte désactivé."""
    http, cs_id = client_http(moteur, RoleUtilisateur.conseil_syndical)
    with Session(moteur) as s:
        lecteurs = [
            compte(s, prefixe="lecteur", roles_json="résident,propriétaire").id for _ in range(2)
        ]
        inactif = compte(s, prefixe="parti", roles_json="résident", actif=False).id
    return http, cs_id, lecteurs, inactif


def _alertes(moteur) -> list[Notification]:
    with Session(moteur) as s:
        return list(s.exec(select(Notification).where(Notification.type == TYPE_POUSSE)).all())


def _publier(http, **champs):
    corps = {"titre": "Coupure d'eau", "description": DESCRIPTION, "categorie": "actualite"}
    reponse = http.post("/tickets", json=corps | champs)
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["id"]


# ── 1 et 2. Les trois chemins, une fois par passage ──────────────────────────


def test_publier_une_actualite_urgente_sonne_chez_ses_lecteurs(moteur, scene):
    http, cs_id, lecteurs, inactif = scene
    _publier(http, urgente=True)
    alertes = _alertes(moteur)
    assert sorted(a.destinataire_id for a in alertes) == sorted(lecteurs)
    assert all(a.urgente and a.titre == "⚡ Coupure d'eau" for a in alertes)
    #  Ni l'auteur du geste, ni un compte désactivé.
    assert cs_id not in {a.destinataire_id for a in alertes}
    assert inactif not in {a.destinataire_id for a in alertes}


def test_la_marquer_urgente_ensuite_sonne_une_fois(moteur, scene):
    http, _, lecteurs, _ = scene
    ident = _publier(http)
    assert _alertes(moteur) == []
    assert http.patch(f"/tickets/{ident}", json={"urgente": True}).status_code == 200
    assert len(_alertes(moteur)) == len(lecteurs)
    #  Corrigée, toujours urgente : le geste n'a pas changé, rien ne resonne.
    reponse = http.patch(f"/tickets/{ident}", json={"urgente": True, "titre": "Coupure d'eau !"})
    assert reponse.status_code == 200
    assert len(_alertes(moteur)) == len(lecteurs)


def test_la_marquer_urgente_dans_une_suite_sonne(moteur, scene):
    http, _, lecteurs, _ = scene
    ident = _publier(http)
    reponse = http.post(
        f"/tickets/{ident}/evolutions",
        json={"type": "commentaire", "contenu": "<p>Elle dure.</p>", "urgente": True},
    )
    assert reponse.status_code == 201, reponse.text
    assert len(_alertes(moteur)) == len(lecteurs)


# ── 3. Rien d'autre ne sonne ─────────────────────────────────────────────────


def test_une_actualite_reservee_au_conseil_ne_sonne_pas(moteur, scene):
    http, *_ = scene
    _publier(http, urgente=True, public_cible=["conseil_syndical"])
    assert _alertes(moteur) == []


def test_l_affaire_urgente_d_un_resident_n_est_pas_une_alerte(moteur, scene):
    _, _, lecteurs, _ = scene
    http, _ = client_http(moteur, RoleUtilisateur.résident)
    reponse = http.post(
        "/tickets",
        json={"titre": "Fuite", "description": DESCRIPTION, "categorie": "panne", "urgente": True},
    )
    assert reponse.status_code == 201, reponse.text
    assert _alertes(moteur) == []


@pytest.mark.parametrize(
    "changees,categorie,priorite,moderateur,attendu",
    [
        (["urgente"], "actualite", "haute", True, True),
        ([], "actualite", "haute", True, False),  # déjà urgente : pas de passage
        (["urgente"], "actualite", "normale", True, False),  # ⚡ retiré
        (["urgente"], "panne", "haute", True, False),  # une affaire, pas une actualité
        (["urgente"], "actualite", "haute", False, False),  # le geste d'un non-modérateur
    ],
)
def test_alerte_due(changees, categorie, priorite, moderateur, attendu):
    from app.models.core import Ticket, Utilisateur

    ticket = Ticket(titre="t", categorie=categorie, priorite=priorite, statut="publie")
    auteur = Utilisateur(
        email="a@exemple.test",
        roles_json="conseil_syndical" if moderateur else "résident",
    )
    assert alerte_due(ticket, auteur, changees) is attendu


# ── 4. La porte ne pousse que l'alerte ───────────────────────────────────────


def test_la_porte_ne_retient_que_l_alerte(moteur):
    with Session(moteur) as s:
        s.add(ConfigSite(cle=cle_actif(SERVICE_PUSH), valeur="1"))
        s.commit()
        dest = compte(s, prefixe="pousse", roles_json="résident").id
        cloche.sonner_systeme(s, "compte", destinataire_id=dest, type="system", titre="t")
        assert s.info.get(porte._EN_ATTENTE) is None
        cloche.sonner(s, destinataire_id=dest, type=TYPE_POUSSE, titre="⚡ t", urgente=True)
        assert s.info[porte._EN_ATTENTE] == {dest: True}
        s.rollback()


# ── 5. Chaque chemin du geste ⚡ appelle l'alerte ─────────────────────────────


def _appelle(arbre: ast.AST, nom: str) -> bool:
    return any(
        isinstance(n, ast.Call)
        and (getattr(n.func, "id", None) == nom or getattr(n.func, "attr", None) == nom)
        for n in ast.walk(arbre)
    )


def _chemins_sans_alerte(modules) -> list[str]:
    return [
        m.rel
        for m in modules
        if _appelle(m.arbre, "appliquer_options") and not _appelle(m.arbre, "sonner_l_alerte")
    ]


def test_le_controle_voit_un_chemin_qui_oublie_l_alerte():
    class Faux:
        rel = "routers/tickets/quatrieme.py"
        arbre = ast.parse("def f(t, b):\n    appliquer_options(t, b, est_cs=True)\n")

    assert _chemins_sans_alerte([Faux]) == ["routers/tickets/quatrieme.py"]


def test_chaque_chemin_du_geste_urgent_appelle_l_alerte():
    modules = list(modules_app())
    #  Cas zéro : les trois chemins sont bien vus.
    chemins = [m.rel for m in modules if _appelle(m.arbre, "appliquer_options")]
    assert len(chemins) >= 3, chemins
    assert _chemins_sans_alerte(modules) == []
