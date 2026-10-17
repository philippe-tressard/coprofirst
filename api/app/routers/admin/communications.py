"""Admin — Historique des e-mails, modèles, notifications et télémétrie.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import (
    HistoriqueEmail,
    HistoriqueTelemetrie,
    ModeleEmail,
    Utilisateur,
)
from app.seed.emails import est_desactivable
from app.utils import horloge

router = APIRouter()


# ── Historique emails ─────────────────────────────────────────────────────────


@router.get("/emails/historique")
def emails_historique(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    return derniers_rapports(session, HistoriqueEmail)


#  🔴 `POST /telemetry/agreger` A ÉTÉ RETIRÉ D'ICI (18/09/2026).
#
#  Il était déclaré DEUX fois, sur le même chemin : ici, et dans
#  `exploitation.py` (#876), qui l'avait ajouté pour que le bouton de
#  `TachesPlanifiees` cesse de rendre 404. Les deux sous-routeurs sont
#  montés sur le préfixe `/admin`, et `exploitation` passe EN PREMIER :
#  Starlette retient la première route qui correspond, donc ce
#  gestionnaire-ci n'a jamais répondu depuis.
#
#  ⚠️ Rien ne le signalait, et le schéma OpenAPI disait même le contraire :
#  sa génération écrase l'entrée d'un chemin par la DERNIÈRE rencontrée,
#  donc `/admin/telemetry/agreger` y était documenté par ce gestionnaire
#  mort. Le schéma décrivait ce qui ne s'exécutait pas.
#
#  🔒 `tests/test_routes_uniques.py` refuse désormais qu'un couple
#  (méthode, chemin) soit déclaré deux fois.


@router.get("/telemetry/historique")
def telemetry_history(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    return derniers_rapports(session, HistoriqueTelemetrie)


# ── Modèles e-mail ────────────────────────────────────────────────────────────────────────

from app.utils.recuperer import derniers_rapports, ou_404


def _variables_du_modele(modele: ModeleEmail) -> str:
    """Les variables que ce modèle emploie RÉELLEMENT, en JSON, pour l'écran.

    ## 🔴 Pourquoi ce n'est plus la colonne `variables_disponibles`

    Cette colonne était une **copie**, posée à la main par la migration qui créait
    le modèle et jamais reprise ensuite. Signalé par Philippe le 08/09/2026, en
    capture d'écran : `nouvel_arrivant_bal` venait de gagner trois variables
    (`role_destinataire`, `lien_consignes`, `destinataire`) et l'écran annonçait
    toujours les trois de la migration 0066 — celles de mars.

    Une liste recopiée diverge au premier enrichissement. Celle-ci avait six mois
    de retard, et **rien ne pouvait le dire** : le modèle et sa liste vivent dans
    la même ligne, personne ne les compare, et le contrat de variables du dépôt
    (`tests/test_email_templates.py`) ne lit que le code — pas la base.

    La conséquence n'était pas cosmétique : cet encart est ce qu'un membre du
    conseil lit **avant de modifier un modèle**. Il y voyait trois variables sur
    six, et aurait écrit un message amputé en croyant employer tout ce qui
    existe.

    ## Ce que ça retire

    Les variables du gabarit commun (`residence`, `app`, `annee`…) : elles sont
    injectées d'office par `email._contexte_rendu` et valent pour tous les
    modèles. Les annoncer ici les ferait passer pour propres à celui-ci.

    ⚠️ La liste est calculée sur le texte **en base**, pas sur celui du dépôt :
    c'est ce que la personne édite qui doit être décrit. Un modèle retouché
    depuis cet écran annonce donc ses propres variables, ce qui est exact.
    """
    #  🔴 La lecture elle-même vit dans `utils/email/variables.py` (#852) : elle
    #  était écrite ici, dans le contrôle quotidien et dans les tests, avec trois
    #  fois sa propre liste de variables du gabarit — celle d'ici en était une
    #  quatrième copie, locale à la fonction.
    from app.utils.email.variables import ModeleIllisible, variables_de

    try:
        return json.dumps(sorted(variables_de(modele.sujet, modele.corps_html)))
    except ModeleIllisible:
        #  Un modèle au Jinja invalide ne peut pas être analysé. Rendre la
        #  colonne stockée plutôt que rien : elle est peut-être périmée, mais
        #  l'écran doit continuer d'aider — et le modèle, lui, échouera à
        #  l'envoi, ce qui est le vrai signal.
        return modele.variables_disponibles or "[]"


def _modele_lu(modele: ModeleEmail) -> dict:
    """Un modèle tel que l'écran le LIT — la ligne, variables CALCULÉES.

    🔴 Écrit une fois pour les trois routes qui rendent un modèle (#1682). Seule
    la liste calculait les variables : la modification et la remise à zéro
    rendaient la ligne brute, donc la colonne stockée — et l'écran, qui remplace
    sa ligne par la réponse, réaffichait après chaque enregistrement la copie
    périmée que `_variables_du_modele` a cessé de servir (#850).
    """
    #  `desactivable` aussi est CALCULÉ (#2054) : la colonne dit ce que la ligne a
    #  reçu à son insertion, le code dit ce qui vaut — et c'est lui que l'envoi lit.
    return {
        **modele.model_dump(),
        "variables_disponibles": _variables_du_modele(modele),
        "desactivable": est_desactivable(modele.code),
    }


@router.get("/modeles-email")
def list_modeles_email(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Les modèles, avec leurs variables **calculées** et non recopiées.

    La colonne `variables_disponibles` reste en base — quatre migrations figées
    l'écrivent — mais ce qui est SERVI est calculé. Une colonne qu'on n'affiche
    plus cesse de mentir sans qu'il faille la supprimer partout.
    """
    modeles = session.exec(select(ModeleEmail).order_by(ModeleEmail.code)).all()
    return [_modele_lu(m) for m in modeles]


@router.patch("/modeles-email/{modele_id}")
def update_modele_email(
    modele_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    modele = ou_404(session, ModeleEmail, modele_id, "Modèle")
    #  🔴 `corps_texte` a QUITTÉ cette liste blanche le 08/09/2026, avec le champ
    #  de l'écran. Il était stocké, affiché, modifiable — et envoyé nulle part :
    #  aucun code ne le lisait, le gabarit produit toujours du HTML. Le laisser
    #  ici permettrait à un appelant direct de continuer d'écrire un texte que
    #  personne ne reçoit, et de croire l'avoir envoyé.
    #
    #  La colonne reste en base : quatre migrations figées l'écrivent, et la
    #  retirer casserait `alembic upgrade` sur une base neuve.
    allowed = {"sujet", "corps_html", "actif", "intention"}

    #  🔴 Un modèle illisible ne s'enregistre PAS (#852).
    #
    #  Ce champ est un `<textarea>` où l'on saisit du Jinja à la main : un
    #  `{% endif %}` de trop, un `{%` non refermé, et le modèle ne se rend plus.
    #  Rien ne le disait — ni ici, ni à l'envoi : `send_email` capture toute
    #  exception et n'en garde trace que dans `historique_email`. Le message
    #  cessait simplement de partir, et le contrôle quotidien lui-même lisait
    #  l'échec comme un écart de variables.
    #
    #  Le refus est le bon geste plutôt qu'une alerte a posteriori : la personne
    #  est DEVANT le texte, elle vient de l'écrire, et Jinja dit à quel caractère.
    #  Découvrir la même erreur le lendemain matin par un e-mail d'alerte n'a
    #  aucune commune mesure — c'est le contrôle qui remplace la prévention.
    from app.utils.email.variables import ModeleIllisible, variables_de

    #  Seuls les champs que la requête ÉCRIT sont relus. Reprendre ceux déjà en
    #  base fermerait la seule voie de réparation : une ligne dont le corps est
    #  cassé ne pourrait plus être touchée du tout, pas même pour la remettre
    #  d'aplomb — l'écran servirait à réparer et refuserait d'agir.
    try:
        variables_de(
            payload.get("sujet") if "sujet" in payload else None,
            payload.get("corps_html") if "corps_html" in payload else None,
        )
    except ModeleIllisible as illisible:
        raise HTTPException(
            422,
            f"Le champ « {illisible.champ} » contient du Jinja invalide : "
            f"{illisible.cause}. Le modèle n'est pas enregistré — il ne pourrait "
            "plus être envoyé, et l'échec ne se verrait que dans l'historique.",
        )

    #  🔴 Un modèle non désactivable ne se décoche pas (#2054) — mot de passe
    #  oublié, vérification d'adresse, alerte système… L'envoi l'ignorerait de
    #  toute façon ; le refus évite que l'écran affiche « Non » sur un courriel
    #  qui part.
    if "actif" in payload and not payload["actif"] and not est_desactivable(modele.code):
        raise HTTPException(
            422,
            f"« {modele.libelle} » ne se désactive pas : c'est un courriel que "
            "l'application doit toujours pouvoir envoyer (sécurité d'un compte, "
            "message au syndic, préavis avant effacement).",
        )

    for key, value in payload.items():
        if key not in allowed:
            continue
        # L'intention est rendue telle quelle dans le gabarit : liste blanche,
        # jamais la valeur reçue. `""` reste permis — c'est « aucun bandeau ».
        if key == "intention":
            from app.utils.email import INTENTIONS

            value = (value or "").strip()
            if value and value not in INTENTIONS:
                raise HTTPException(
                    422,
                    f"Intention inconnue : {value!r}. Valeurs admises : "
                    + ", ".join(sorted(INTENTIONS)),
                )
        setattr(modele, key, value)

    modele.modifie_le = horloge.maintenant()
    modele.modifie_par_id = _.id
    session.add(modele)
    session.commit()
    session.refresh(modele)
    return _modele_lu(modele)


def _remettre_par_defaut(session: Session, modele: ModeleEmail, par_id: int) -> bool:
    """Remet UN modèle au texte du seed. Rend False si le code n'y est plus.

    Écrit une fois et appelée par les deux routes de réinitialisation — celle
    d'un modèle et celle de tous. Deux boucles jumelles auraient divergé sur
    l'intention exactement comme elles avaient divergé ailleurs : « remettre par
    défaut » doit remettre le bandeau aussi, sans quoi un modèle réinitialisé
    garderait une intention modifiée au-dessus d'un corps redevenu d'origine.
    """
    from app.seed import EMAIL_TEMPLATES, INTENTIONS_PAR_MODELE

    defaut = next((t for t in EMAIL_TEMPLATES if t[0] == modele.code), None)
    if not defaut:
        #  Un modèle que le code ne connaît plus n'a pas de version par défaut.
        return False
    _code, _libelle, sujet, corps_html, _desactivable = defaut
    modele.sujet = sujet
    modele.corps_html = corps_html
    modele.intention = INTENTIONS_PAR_MODELE.get(modele.code, "")
    modele.modifie_le = horloge.maintenant()
    modele.modifie_par_id = par_id
    session.add(modele)
    return True


@router.post("/modeles-email/{modele_id}/reinitialiser")
def reinitialiser_un_modele_email(
    modele_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Remet UN modèle au texte du code, sans toucher aux vingt-trois autres.

    🔴 Il n'existait que la remise à zéro **globale** (#852). Réparer un seul
    modèle — celui dont le Jinja a été cassé d'un caractère, celui qui a manqué
    un enrichissement — imposait donc de détruire les textes choisis pour tous
    les autres. C'est le genre de remède qu'on n'applique pas, et le défaut reste
    alors en place : le contrôle quotidien signale, et personne ne peut agir.
    """
    modele = ou_404(session, ModeleEmail, modele_id, "Modèle")
    if not _remettre_par_defaut(session, modele, _.id):
        raise HTTPException(
            422,
            f"Le code ne porte plus de version par défaut pour « {modele.code} » : "
            "ce modèle n'existe qu'en base, il n'y a rien à quoi le ramener.",
        )
    session.commit()
    session.refresh(modele)
    return _modele_lu(modele)


@router.post("/modeles-email/reinitialiser")
def reinitialiser_modeles_email(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Remet tous les modèles e-mail aux valeurs par défaut (seed)."""
    modeles = session.exec(select(ModeleEmail)).all()
    updated = sum(_remettre_par_defaut(session, m, _.id) for m in modeles)
    session.commit()
    return {"message": f"{updated} modèles réinitialisés"}


#  🔴 LES DEUX ROUTES « NOTIFICATIONS » DE CE FICHIER SONT PARTIES (18/09/2026).
#
#  `GET /admin/notifications` et `POST /admin/notifications/{id}/lue`
#  doublaient `GET /notifications` et `PATCH /notifications/{id}/lue`, au
#  même acte près : elles lisaient et marquaient les notifications de
#  L'UTILISATEUR CONNECTÉ (`destinataire_id == user.id`).
#
#  ⚠️ Elles étaient déclarées « sans consommateur front » avec pour raison
#  « API d'administration exposée pour l'exploitation » — ce qui n'était pas
#  vrai : un administrateur qui les appelait voyait SES propres
#  notifications, exactement ce que `/notifications` lui donne déjà. Une
#  exception dont la raison est fausse est pire qu'absente : elle ferme la
#  question.
#
#  Et la règle d'appartenance — « une notification n'appartient qu'à son
#  destinataire » — s'écrivait ici une TROISIÈME et une QUATRIÈME fois.
#  `standards/03` §1 : l'autorisation est centralisée. Elle vit désormais
#  dans `routers/notifications.py`, par `ma_notification`.
