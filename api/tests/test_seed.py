"""Garde-fou : le seed pose tout ce qu'il déclare, et se rejoue sans doublon.

Le seed n'était couvert par **aucun** test avant son découpage en modules
(05/08/2026). Les tests d'e-mail lisaient bien `EMAIL_TEMPLATES`, mais personne
ne montait la base : un seed qui n'insère plus rien serait passé au vert.

Ce n'est pas une pièce anodine — `main.py` l'appelle à **chaque démarrage**. Une
donnée de démarrage qui manque ne se voit pas tout de suite : la FAQ est vide, un
modèle d'e-mail est absent et `send_email` se tait, un profil d'accès manque et
la bibliothèque documentaire refuse tout. Aucun de ces symptômes ne pointe vers
le seed.

Les deux propriétés vérifiées ici sont celles dont tout le reste dépend :

1. **tout ce qui est déclaré est réellement posé** — le compte en base doit
   égaler le compte de la liste source, sinon une entrée s'est perdue ;
2. **le rejeu ne crée pas de doublon** — c'est ce qui rend sûr un appel à chaque
   démarrage, et c'est exactement ce que `_poser_les_absents` garantit.
"""

import pytest
from sqlmodel import Session, func, select

from app.models.core import (
    CategorieDocument,
    ConfigSauvegarde,
    ConfigSite,
    Copropriete,
    DiagnosticType,
    FaqItem,
    ModeleEmail,
    ProfilAccesDocument,
    Utilisateur,
)
from app.seed import (
    CATEGORIES,
    DIAGNOSTICS,
    EMAIL_TEMPLATES,
    FAQ_COMPLEMENTAIRE,
    FAQ_INITIALE,
    PROFILS,
)
from tests.aides_base import moteur_de_test


@pytest.fixture
def base():
    """Base jetable : le seed ouvre sa propre session."""
    moteur = moteur_de_test()
    yield moteur
    moteur.dispose()


def _semer(moteur) -> None:
    """Rejoue la logique du seed sur `moteur`, sans toucher à la base réelle."""
    import app.seed as module_seed

    with Session(moteur) as session:
        module_seed._copropriete_par_defaut(session)
        module_seed._admin_initial(session)
        module_seed._profils_et_categories(session)
        module_seed._configuration_par_defaut(session)
        module_seed._modeles_email(session)
        session.commit()
        module_seed._questions_frequentes(session)
        session.commit()
        module_seed._types_de_diagnostics(session)
        session.commit()


def _compter(moteur) -> dict[str, int]:
    with Session(moteur) as session:
        return {
            nom: session.exec(select(func.count()).select_from(modele)).one()
            for nom, modele in (
                ("coproprietes", Copropriete),
                ("utilisateurs", Utilisateur),
                ("profils", ProfilAccesDocument),
                ("categories", CategorieDocument),
                ("config_site", ConfigSite),
                ("config_sauvegarde", ConfigSauvegarde),
                ("modeles_email", ModeleEmail),
                ("faq", FaqItem),
                ("diagnostics", DiagnosticType),
            )
        }


def test_tout_ce_qui_est_declare_est_pose(base):
    """Une entrée perdue au découpage se verrait ici, et nulle part ailleurs."""
    _semer(base)
    compte = _compter(base)

    assert compte["profils"] == len(PROFILS)
    assert compte["categories"] == len(CATEGORIES)
    assert compte["modeles_email"] == len(EMAIL_TEMPLATES)
    assert compte["faq"] == len(FAQ_INITIALE) + len(FAQ_COMPLEMENTAIRE)
    assert compte["diagnostics"] == len(DIAGNOSTICS)

    vides = [nom for nom, n in compte.items() if n == 0]
    assert not vides, f"Tables restées vides après le seed : {vides}"


def test_le_rejeu_ne_cree_aucun_doublon(base):
    """`main.py` appelle le seed à chaque démarrage : il doit être rejouable."""
    _semer(base)
    premier = _compter(base)
    _semer(base)
    second = _compter(base)

    ecarts = {nom: (premier[nom], second[nom]) for nom in premier if premier[nom] != second[nom]}
    assert not ecarts, (
        f"Le second passage du seed a créé des lignes : {ecarts}. Chaque "
        "redémarrage du conteneur dupliquerait ces données."
    )


def test_les_modeles_email_sont_poses_avec_leur_intention(base):
    """Une intention perdue ne casse rien — elle retire juste le bandeau, en silence."""
    _semer(base)
    with Session(base) as session:
        modeles = session.exec(select(ModeleEmail)).all()

    sans = sorted(m.code for m in modeles if not m.intention)
    assert not sans, f"Modèles posés sans intention : {sans}"


def test_le_seed_ne_reecrit_pas_ce_qui_a_ete_personnalise(base):
    """La règle qui gouverne le module : insérer, jamais mettre à jour.

    Une installation en service retouche ses modèles depuis Admin → Emails. Si le
    seed les réécrivait, chaque redémarrage effacerait ces choix — et personne ne
    ferait le lien entre un redémarrage et un texte revenu à son état d'origine.
    """
    _semer(base)
    with Session(base) as session:
        modele = session.exec(select(ModeleEmail)).first()
        modele.sujet = "Sujet réécrit par le conseil syndical"
        code = modele.code
        session.add(modele)
        session.commit()

    _semer(base)

    with Session(base) as session:
        apres = session.exec(select(ModeleEmail).where(ModeleEmail.code == code)).one()
    assert apres.sujet == "Sujet réécrit par le conseil syndical", (
        "Le seed a écrasé un modèle personnalisé : toute modification faite "
        "depuis l'administration serait perdue au prochain démarrage."
    )


def test_l_administrateur_initial_se_connecte(caplog):
    """Une installation NEUVE a un administrateur qui entre (DI-4, 10/10/2026).

    Le compte initial naissait avec `email_verifie=False` : la connexion le
    refusait (« vérifiez votre adresse »), et `admin@localhost` ne reçoit rien.
    La référence n'en souffrait pas — son administrateur date d'avant la règle —,
    c'est l'essai de bout en bout de la mise à jour d'une réplique qui l'a vu.
    Ce test passe par la VRAIE route de connexion : une condition ajoutée demain
    à la connexion, que le compte initial ne remplirait pas, échouerait ici.
    """
    import logging
    import re

    import app.seed as module_seed
    from tests.aides_http import base_http, client_http

    with base_http() as moteur:
        with caplog.at_level(logging.WARNING, logger="app.seed"), Session(moteur) as session:
            module_seed._admin_initial(session)
            session.commit()
        trouve = re.search(r"Mot de passe temporaire : (\S+)", caplog.text)
        assert trouve, "le mot de passe initial n'est plus journalisé"
        http, _ = client_http(moteur, None)
        r = http.post("/auth/login", json={"email": "admin@localhost", "password": trouve.group(1)})
        assert r.status_code == 200, r.text


def test_l_operateur_initial_est_un_compte_a_part(caplog):
    """Deux comptes techniques depuis #1985 : l'administrateur se confie (la démo
    peut le publier) sans livrer l'opérateur, qui tient le registre, la santé et la
    base. L'opérateur est AUSSI administrateur : ses écrans vivent sous `/admin`
    (#1750). Ce test passe par la vraie route de connexion, comme le précédent.
    """
    import logging
    import re

    import app.seed as module_seed
    from tests.aides_http import base_http, client_http

    with base_http() as moteur:
        with caplog.at_level(logging.WARNING, logger="app.seed"), Session(moteur) as session:
            module_seed._admin_initial(session)
            session.commit()
            techniques = session.exec(select(Utilisateur)).all()
        assert sorted(u.email for u in techniques) == ["admin@localhost", "operateur@localhost"]
        assert {u.email: u.has_role("operateur") for u in techniques} == {
            "admin@localhost": False,
            "operateur@localhost": True,
        }
        assert all(u.has_role("admin") for u in techniques)
        trouve = re.search(r"Mot de passe de l'opérateur : (\S+)", caplog.text)
        assert trouve, "le mot de passe de l'opérateur n'est pas journalisé"
        http, _ = client_http(moteur, None)
        r = http.post(
            "/auth/login", json={"email": "operateur@localhost", "password": trouve.group(1)}
        )
        assert r.status_code == 200, r.text
