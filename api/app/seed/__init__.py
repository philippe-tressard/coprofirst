"""Données de démarrage : pose ce qui manque, ne touche jamais à ce qui existe.

Lancer avec : `python -m app.seed`. Appelé aussi à chaque démarrage par `main.py`,
ce qui n'est sûr que grâce à la règle ci-dessous.

## La règle qui gouverne tout ce module

**Le seed n'INSÈRE que ce qui est absent. Il ne met jamais à jour.** Une
installation en service a pu retoucher ses modèles d'e-mail, sa FAQ ou ses textes
légaux depuis l'administration : réécrire écraserait ces choix. C'est pourquoi
toute modification d'une donnée déjà livrée passe par une **migration Alembic**
ciblée, et non par ce fichier — modifier une constante ici n'a aucun effet sur une
base existante.

Cette règle était répétée en sept variantes de `if not session.exec(...).first()`.
Elle est désormais portée par `_poser_les_absents`, en un seul endroit : c'est là
qu'il faut regarder pour comprendre ce que le seed garantit.

## Organisation

Les données vivent dans des modules dédiés, par domaine et non par type — chacun
a sa propre raison de changer :

- `emails/` — les modèles d'e-mail, par famille (comptes, tickets, vie
  collective, exploitation) ;
- `profils_documents` — qui voit quoi dans la bibliothèque documentaire ;
- `contenus_legaux` — mentions et politique de confidentialité par défaut ;
- `faq` — questions fréquentes ;
- `diagnostics` — diagnostics réglementaires et leur fondement légal.

`EMAIL_TEMPLATES`, `INTENTIONS_PAR_MODELE` et `DEFAULT_LEGAL` restent importables
depuis `app.seed` : quatre migrations **figées** en dépendent (0104, 0108, 0129,
0130, 0132), ainsi que l'administration et les tests. Cette surface ne bouge pas.
"""

from sqlmodel import Session, select

from app.auth.jwt import hash_password
from app.database import create_db_and_tables
from app import contexte
from app.models.core import (
    Batiment,
    CategorieDocument,
    ConfigSauvegarde,
    ConfigSite,
    Copropriete,
    DiagnosticType,
    FaqItem,
    ModeleEmail,
    ProfilAccesDocument,
    RoleUtilisateur,
    StatutUtilisateur,
    Utilisateur,
)
from app.models.equipements import Equipement
from app.models.roles import ROLE_OPERATEUR
from app.seed.contenus_legaux import DEFAULT_LEGAL
from app.seed.diagnostics import DIAGNOSTICS
from app.seed.equipements import EQUIPEMENTS
from app.seed.emails import EMAIL_TEMPLATES, INTENTIONS_PAR_MODELE
from app.seed.faq import FAQ_COMPLEMENTAIRE, FAQ_INITIALE
from app.seed.patrimoine import poser_arborescence
from app.utils.liens import NOM_SITE_PAR_DEFAUT
from app.utils.textes_legaux.identite import COPROPRIETE_EXEMPLE
from app.utils.whatsapp_message import PIED_WHATSAPP_PAR_DEFAUT
from app.seed.profils_documents import CATEGORIES, PROFILS

__all__ = [
    "seed",
    "EMAIL_TEMPLATES",
    "INTENTIONS_PAR_MODELE",
    "DEFAULT_LEGAL",
    "PROFILS",
    "CATEGORIES",
    "DIAGNOSTICS",
    "EQUIPEMENTS",
    "equipements_par_defaut",
    "FAQ_INITIALE",
    "FAQ_COMPLEMENTAIRE",
]

#: 🔴 Le seed porte le PRODUIT, la base porte l'INSTANCE (#1725) : aucune valeur
#: ici ne nomme une résidence. `email_footer` valait « ©2026-5Hostachy - Envoyé
#: depuis 5hostachy.fr » — une autre copropriété l'aurait signé. Vide, le pied
#: ne s'affiche pas (`email/gabarit.py`) ; le nom et l'adresse du site, eux,
#: figurent déjà dans l'en-tête de chaque courriel.
CONFIG_SITE_PAR_DEFAUT: dict[str, str] = {
    "site_nom": NOM_SITE_PAR_DEFAUT,
    "site_email": "admin@example.com",
    "site_manager_user_id": "",
    "login_sous_titre": "Votre espace numérique de résidence",
    "notify_ticket_bug_email": "0",
    "notify_new_user_created_email": "0",
    "whatsapp_footer": PIED_WHATSAPP_PAR_DEFAUT,
    "email_footer": "",
    "reference_copro": "",
    **DEFAULT_LEGAL,
}


def _poser_les_absents(session: Session, modele, champ: str, entrees: list[dict]) -> int:
    """Insère les entrées dont la valeur de `champ` n'existe pas encore.

    Le seul endroit du seed où « ne pose que ce qui manque » est écrit. Les valeurs
    déjà présentes sont laissées **telles quelles**, personnalisations comprises.

    La lecture se fait en une requête plutôt qu'un `SELECT` par entrée : le seed
    tourne à chaque démarrage du conteneur, et cette boucle voyait passer une
    trentaine de modèles d'e-mail.
    """
    colonne = getattr(modele, champ)
    presentes = set(session.exec(select(colonne)).all())
    poses = 0
    for entree in entrees:
        if entree[champ] in presentes:
            continue
        session.add(modele(**entree))
        presentes.add(entree[champ])
        poses += 1
    return poses


def _copropriete_par_defaut(session: Session) -> None:
    """Copropriété d'exemple et ses bâtiments — uniquement sur une base vierge."""
    if session.exec(select(Copropriete)).first():
        return
    copro = Copropriete(
        nom=COPROPRIETE_EXEMPLE["nom"],
        adresse=COPROPRIETE_EXEMPLE["adresse"],
        annee_construction=2000,
        nb_lots_total=48,
    )
    session.add(copro)
    session.flush()
    for numero in ["1", "2", "3", "4"]:
        session.add(Batiment(copropriete_id=copro.id, numero=numero, nb_etages=5))


#: Les deux comptes techniques d'une installation neuve (#1985) : l'administrateur
#: de la copropriété, et l'opérateur de l'installation — administrateur AUSSI à sa
#: création, car Opérateur s'accorde à un administrateur ; il peut ensuite quitter
#: l'administration et garder sa supervision (#2029).
#: Séparés pour qu'on puisse confier le premier sans livrer le second : l'opérateur
#: tient l'inscription au registre (contrat, bail), la santé et la base.
ADRESSE_ADMIN_INITIAL = "admin@localhost"
ADRESSE_OPERATEUR_INITIAL = "operateur@localhost"


def _compte_technique(nom: str, adresse: str, roles_json: str, mot_de_passe: str) -> Utilisateur:
    return Utilisateur(
        nom=nom,
        prenom="Site",
        email=adresse,
        hashed_password=hash_password(mot_de_passe),
        statut=StatutUtilisateur.admin_technique,
        role=RoleUtilisateur.admin,
        roles_json=roles_json,
        actif=True,
        #  Son adresse ne reçoit rien : sans ce drapeau, la connexion le refuse
        #  (« vérifiez votre adresse ») et une installation neuve reste sans
        #  administrateur. Trouvé par l'essai de bout en bout de DI-4 (10/10/2026).
        email_verifie=True,
        consentement_rgpd=True,
    )


def _admin_initial(session: Session) -> None:
    """Administrateur et opérateur de premier démarrage, mots de passe dans les logs.

    Les mots de passe ne sont **jamais** écrits en dur : ils sont tirés au sort et
    affichés une seule fois, au premier lancement, pour être changés immédiatement.
    Une base qui a déjà un administrateur n'en reçoit aucun : le seed n'insère
    que ce qui manque, et une installation en service garde ses comptes.

    ⚠️ Les deux libellés du journal sont lus par des outils : « Mot de passe
    temporaire » est celui de l'ADMINISTRATEUR (`scripts/ci/essai-mise-a-jour.sh`,
    `test_seed.py`) ; l'opérateur a le sien, qu'aucun `sed` ne confond avec lui.
    """
    if session.exec(select(Utilisateur).where(Utilisateur.role == RoleUtilisateur.admin)).first():
        return

    import logging
    import secrets

    mot_de_passe = secrets.token_urlsafe(16)
    mot_de_passe_operateur = secrets.token_urlsafe(16)
    session.add(
        _compte_technique("Admin", ADRESSE_ADMIN_INITIAL, RoleUtilisateur.admin.value, mot_de_passe)
    )
    session.add(
        _compte_technique(
            "Opérateur",
            ADRESSE_OPERATEUR_INITIAL,
            f"{RoleUtilisateur.admin.value},{ROLE_OPERATEUR}",
            mot_de_passe_operateur,
        )
    )
    logging.getLogger("app.seed").warning(
        "\n"
        + "=" * 60
        + "\n  ADMIN INITIAL CRÉÉ"
        + f"\n  Email : {ADRESSE_ADMIN_INITIAL}"
        + f"\n  Mot de passe temporaire : {mot_de_passe}"
        + f"\n  Opérateur (supervision, registre) : {ADRESSE_OPERATEUR_INITIAL}"
        + f"\n  Mot de passe de l'opérateur : {mot_de_passe_operateur}"
        + "\n  ⚠ Changez-les immédiatement après la 1ʳᵉ connexion."
        + "\n"
        + "=" * 60
    )


def _profils_et_categories(session: Session) -> None:
    """Profils d'accès puis catégories de documents, qui s'y rattachent.

    Les deux ne peuvent pas être posés en une passe : une catégorie référence
    l'identifiant d'un profil, donc les profils sont écrits et vidés du tampon
    (`flush`) avant que les catégories ne les cherchent.
    """
    _poser_les_absents(session, ProfilAccesDocument, "code", PROFILS)
    session.flush()

    profil_id = {
        code: identifiant
        for identifiant, code in session.exec(
            select(ProfilAccesDocument.id, ProfilAccesDocument.code)
        ).all()
    }
    _poser_les_absents(
        session,
        CategorieDocument,
        "code",
        [
            {
                "code": code,
                "libelle": libelle,
                "profil_acces_id": profil_id[profil_code],
                "perimetre_defaut": perimetre,
                "surcharge_autorisee": surcharge,
            }
            for code, libelle, profil_code, perimetre, surcharge in CATEGORIES
        ],
    )


def _configuration_par_defaut(session: Session) -> None:
    """Configuration de sauvegarde et clés de configuration du site."""
    if not session.exec(select(ConfigSauvegarde)).first():
        session.add(ConfigSauvegarde())
    _poser_les_absents(
        session,
        ConfigSite,
        "cle",
        [{"cle": cle, "valeur": valeur} for cle, valeur in CONFIG_SITE_PAR_DEFAUT.items()],
    )
    #  Le SMTP de la copropriété vit dans SA base (#2058) : l'amorce y recopie une
    #  fois ce que le repli sur `MAIL_*` produisait, puis la base décide seule.
    from app.utils.smtp import amorcer

    amorcer(session)


def _modeles_email(session: Session) -> None:
    """Modèles d'e-mail, avec l'intention que chacun annonce au destinataire."""
    _poser_les_absents(
        session,
        ModeleEmail,
        "code",
        [
            {
                "code": code,
                "libelle": libelle,
                "sujet": sujet,
                "corps_html": corps_html,
                "desactivable": desactivable,
                "intention": INTENTIONS_PAR_MODELE.get(code, ""),
            }
            for code, libelle, sujet, corps_html, desactivable in EMAIL_TEMPLATES
        ],
    )


def _questions_frequentes(session: Session) -> None:
    """FAQ initiale sur une base vierge, puis les compléments question par question.

    La distinction est volontaire : `FAQ_INITIALE` est une proposition de départ,
    que le conseil syndical peut supprimer ou réécrire — la reposer plus tard
    ferait réapparaître ce qu'il a retiré. `FAQ_COMPLEMENTAIRE` s'ajoute sans
    écraser, et c'est la voie à suivre pour enrichir la FAQ après coup.
    """

    def en_dict(entrees):
        return [
            {
                "categorie": cat,
                "question": question,
                "reponse": reponse,
                "ordre": ordre,
                "actif": True,
            }
            for cat, question, reponse, ordre in entrees
        ]

    if not session.exec(select(FaqItem)).first():
        for entree in en_dict(FAQ_INITIALE):
            session.add(FaqItem(**entree))
    _poser_les_absents(session, FaqItem, "question", en_dict(FAQ_COMPLEMENTAIRE))


def _types_de_diagnostics(session: Session) -> None:
    """Diagnostics réglementaires et leur fondement légal."""
    _poser_les_absents(session, DiagnosticType, "code", DIAGNOSTICS)


def equipements_par_defaut(session: Session) -> None:
    """Les équipements de départ, sur une table VIDE seulement (#2442).

    Comme `FAQ_INITIALE` : une proposition que l'administrateur remplace. Les
    reposer « s'ils manquent » ferait revenir à chaque démarrage un équipement
    qu'il a supprimé. La table n'est jamais vide une fois amorcée : les codes
    système (`utils/equipements.CODES_SYSTEME`) ne se suppriment pas.
    """
    if not session.exec(select(Equipement)).first():
        for entree in EQUIPEMENTS:
            session.add(Equipement(**entree))


def _arborescence_des_perimetres(session: Session) -> None:
    """Périmètres — où se situe une demande. Proposition de départ, remplaçable.

    Passe après le premier `commit` de `seed()` : les nœuds de bâtiment portent une
    clé étrangère vers `batiment.id`, et sur une base vierge les bâtiments viennent
    d'être créés — sans écriture préalable, ils n'ont pas encore d'identifiant.

    Le cache de `utils/perimetres` est vidé ensuite : il vit 30 secondes, et sans
    cela le premier appel suivant un démarrage servirait un arbre vide.
    """
    from app.utils.perimetres import invalider_cache

    poser_arborescence(session)
    session.commit()
    invalider_cache()


def seed() -> None:
    """Pose toutes les données de démarrage absentes. Sans effet si tout est là."""
    create_db_and_tables()

    with contexte.nouvelle_session() as session:
        _copropriete_par_defaut(session)
        _admin_initial(session)
        _profils_et_categories(session)
        _configuration_par_defaut(session)
        _modeles_email(session)
        session.commit()

        _questions_frequentes(session)
        session.commit()

        _types_de_diagnostics(session)
        session.commit()
        equipements_par_defaut(session)
        session.commit()

        _arborescence_des_perimetres(session)

    print("✅ Seed terminé.")


if __name__ == "__main__":
    import sys

    from app.utils import commande

    #  Sur une installation commune, la copropriété se nomme (#2053).
    sys.exit(commande.lancer(lambda _arguments: seed()))
