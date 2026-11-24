"""Ce qui est SERVI diffère-t-il de ce que le code dit ? (#850)

## Le trou que ce contrôle bouche

Un modèle d'e-mail vit **en base**. `_poser_les_absents` ne pose que ce qui
manque : une ligne existante n'est **jamais** reprise par le seed. Enrichir un
modèle demande donc une migration, et cette migration porte une clause `WHERE`
sur le texte attendu — pour ne pas écraser une installation qui l'aurait retouché
depuis Admin → Emails.

🔴 **Si ce `WHERE` ne correspond à rien, il ne se passe RIEN.** Pas d'erreur, pas
de trace, aucune ligne de journal : la migration réussit en ayant modifié zéro
ligne. Le code contient la nouvelle version, tous les tests passent —
`test_email_templates.py` lit le dépôt — et l'installation continue d'envoyer
l'ancienne.

C'est ce qui serait arrivé à `nouvel_arrivant_bal` le 08/09/2026 : l'arrivant et
le conseil auraient reçu la version rédigée pour le syndic, sans le lien vers les
consignes, et personne n'aurait pu le savoir sans ouvrir l'écran. C'est d'ailleurs
en l'ouvrant que Philippe a trouvé les deux colonnes restées en arrière.

C'est le raisonnement de `health_monitor._check_reference_copro` : la règle est
vérifiable sur les modèles, elle reste fausse sur l'installation, et le seul
endroit d'où l'écart se voit est un contrôle qui regarde **la base réelle**.

## Trois axes, et pourquoi pas le texte

Comparer le **texte** alerterait à chaque reformulation faite depuis
Admin → Emails — un droit que le conseil a, et que les migrations protègent
exprès. L'alerte deviendrait du bruit, puis serait ignorée : un contrôle qu'on
ignore est un contrôle absent (`standards/04`).

Sont donc regardés les trois axes qui ne changent **pas** quand on reformule :

0. **le modèle se rend-il ?** Un Jinja invalide en base n'est pas un écart :
   c'est un message qui ne part plus, et dont l'échec ne se voit que dans
   `historique_email`. Ce cas passait ici pour « toutes les variables du code
   sont absentes », avec une cause affirmée qui n'était pas la bonne (#852).

1. **les variables**. Un écart signifie l'une de deux choses, toutes deux graves :

   * le modèle servi n'a **pas** reçu un enrichissement que le code fournit — il
     rend une version incomplète, ou identique pour des publics qui devraient
     différer ;
   * le modèle servi lit une variable que **personne ne fournit** — Jinja
     l'évalue à vide, en silence. C'est la famille `'destinataire' is undefined`,
     survenue trois fois en deux mois, et le seul cas que
     `test_email_templates.py` ne peut pas voir : il n'inspecte que le dépôt.

2. **l'intention**, quand la ligne n'en porte aucune. Elle décide du bandeau
   **et** de l'adresse d'expédition : une ligne muette repart sur le choix du
   code, ce qui est le repli voulu, mais mérite d'être signalé — c'est le signe
   d'une ligne posée avant la migration 0130.

   ⚠️ Une intention **différente** de celle du code n'est PAS un écart : l'écran
   permet de la changer, et depuis le 08/09/2026 c'est bien celle de la ligne qui
   décide de l'expéditeur. La signaler ferait crier le contrôle sur une décision
   d'administrateur.
"""

from __future__ import annotations

from sqlmodel import Session, select

#  🔴 `variables_de` VIVAIT ICI, en deuxième exemplaire (#852). L'écran des
#  modèles et le contrat de variables du dépôt posaient la même question avec
#  leur propre code, et la liste du gabarit était écrite deux fois. Elle vit
#  désormais dans `utils/email/variables.py`, avec les raisons du regroupement.
from app.utils.email.variables import (  # réexport historique
    VARIABLES_DU_GABARIT,
    ModeleIllisible,
    variables_de,
)


def _extrait(modele, largeur: int = 70) -> str:
    """Le début de ce qui est SERVI, pour trancher sans ouvrir l'écran.

    Sans lui, l'alerte disait « ces variables manquent » et il fallait aller voir
    le texte pour comprendre ce qu'on regardait. Deux allers-retours, dont un
    derrière une session admin — c'est-à-dire une alerte qu'on ne peut pas
    exploiter là où on la lit (#852).

    ⚠️ Un modèle d'e-mail ne contient aucune donnée personnelle : ce sont des
    emplacements, remplis à l'envoi. L'extrait peut donc partir dans l'alerte.
    """

    def court(valeur: str | None) -> str:
        texte = " ".join((valeur or "").split())
        return (texte[:largeur] + "…") if len(texte) > largeur else (texte or "(vide)")

    return f"Servi — objet : « {court(modele.sujet)} » · corps : « {court(modele.corps_html)} »"


def controler(session: Session) -> list[str]:
    """Les écarts entre les modèles servis et ceux du code, en clair."""
    from app.models.core import ModeleEmail
    from app.seed import EMAIL_TEMPLATES
    from app.seed.emails import INTENTIONS_PAR_MODELE

    attendus = {code: (sujet, corps) for code, _l, sujet, corps, _d in EMAIL_TEMPLATES}
    lignes = session.exec(select(ModeleEmail)).all()

    #  🔴 Cas zéro : une base sans aucun modèle rendrait « aucun écart », donc un
    #  vert — alors que plus rien ne partirait, ni alerte ni réinitialisation de
    #  mot de passe. Un contrôle qui ne peut pas s'exécuter rend INCONNU, jamais
    #  OK (`standards/04` §1).
    if not lignes:
        return [
            "Aucun modèle d'e-mail en base : le contrôle ne peut pas conclure.\n"
            "Aucun message ne peut partir dans cet état — ni alerte système, ni "
            "réinitialisation de mot de passe.\n"
            "Vérifier que le seed s'est exécuté au démarrage de l'API."
        ]

    ecarts: list[str] = []
    for modele in lignes:
        if modele.code not in attendus:
            #  Un modèle en base que le code ignore : ancien, ou créé à la main.
            #  Il n'a pas de version de référence — ce n'est pas un écart.
            continue

        sujet_code, corps_code = attendus[modele.code]

        #  🔴 D'ABORD : ce modèle peut-il seulement être RENDU ? (#852)
        #
        #  Un Jinja invalide en base n'est pas un écart de variables, c'est un
        #  envoi qui échoue. Et il échoue en silence : `send_email` capture toute
        #  exception et n'en garde trace que dans `historique_email`, derrière une
        #  session admin — personne ne le voit passer.
        #
        #  Ce cas ARRIVAIT ici sans être nommé : la lecture rendait un ensemble
        #  vide, et le contrôle annonçait alors « toutes les variables du code
        #  sont absentes », en affirmant une cause — « une migration n'a rien
        #  touché » — qui n'était pas la bonne. Chercher une migration fantôme
        #  pendant qu'un modèle ne part plus, c'est le symptôme attendu à la place
        #  du fait (`standards/04`). Le texte se saisit à la main dans un simple
        #  `<textarea>` : un `{% endif %}` de trop suffit.
        try:
            servies = variables_de(modele.sujet, modele.corps_html)
        except ModeleIllisible as illisible:
            ecarts.append(
                f"Modèle d'e-mail « {modele.code} » : Jinja INVALIDE en base — "
                "ce message ne part plus du tout.\n"
                f"Champ « {illisible.champ} » : {illisible.cause}\n"
                "L'échec est silencieux : il n'apparaît que dans "
                "Admin → Emails → Historique, en « erreur ».\n"
                "À corriger dans Admin → Emails, ou à remettre par défaut avec "
                "« Réinitialiser les modèles »."
            )
            continue

        #  Le modèle du dépôt, lui, est verrouillé par `test_email_templates.py` :
        #  s'il ne se parse pas, la CI est rouge et rien n'a pu être déployé. Le
        #  laisser lever ici serait donc juste — mais `run_health_check` capture
        #  tout, et le contrôle entier disparaîtrait pour un modèle. On le dit.
        try:
            du_code = variables_de(sujet_code, corps_code)
        except ModeleIllisible as illisible:
            ecarts.append(
                f"Modèle d'e-mail « {modele.code} » : le modèle du CODE ne se "
                "parse pas.\n"
                f"Champ « {illisible.champ} » : {illisible.cause}\n"
                "Aucune comparaison n'est possible — corriger `seed/emails/` et "
                "vérifier pourquoi la CI l'a laissé passer."
            )
            continue

        if du_code != servies:
            detail = []
            manquantes = sorted(du_code - servies)
            en_trop = sorted(servies - du_code)
            if manquantes and not servies:
                #  🔴 AUCUNE variable du code, et aucune en trop : ce n'est pas une
                #  dérive, c'est un modèle BOUCHON — une ligne qui occupe la place
                #  sans porter le message (#852, 09/09/2026).
                #
                #  Vu en production sur `ticket_externe` et `publication_externe` :
                #  objet « Notification ticket externe » (le LIBELLÉ du modèle),
                #  corps « <p>Notification.</p> ». Chaque ticket transmis à
                #  l'extérieur partait ainsi — sans numéro, sans titre, sans lien —
                #  depuis la migration 0105, dont l'`INSERT` gardé par
                #  `if not existing:` n'avait rien fait : le bouchon était déjà là.
                #
                #  L'alerte accusait une migration d'enrichissement, et envoyait
                #  donc chercher au mauvais endroit. « Tout manque, rien en excès »
                #  n'est pas une dérive : c'est une absence.
                detail.append(
                    "Le modèle servi n'emploie AUCUNE des variables du code ("
                    + ", ".join(manquantes)
                    + ") — c'est un modèle BOUCHON : une ligne qui occupe la place "
                    "sans porter le message. Il part, et il ne dit rien."
                )
                detail.append(_extrait(modele))
                detail.append(
                    "À remettre par « ↩️ Par défaut » dans Admin → Emails : le "
                    "modèle reprend le texte du code, sans toucher aux autres."
                )
            elif manquantes:
                detail.append(
                    "Variables du code absentes du modèle servi : "
                    + ", ".join(manquantes)
                    + " — une migration d'enrichissement n'a probablement rien "
                    "touché : sa clause WHERE ne correspondait plus au texte en base."
                )
            if en_trop:
                detail.append(
                    "Variables lues par le modèle servi et fournies par personne : "
                    + ", ".join(en_trop)
                    + " — Jinja les rend VIDES, en silence."
                )
            #  ⚠️ La conduite à tenir dépend du cas, et elle était générique :
            #  « réappliquer la migration concernée » n'a aucun sens devant un
            #  modèle bouchon, qui porte sa propre ligne de remède ci-dessus. Une
            #  alerte qui propose le mauvais geste vaut celle qui affirme la
            #  mauvaise cause.
            if servies:
                detail.append(
                    "À comparer dans Admin → Emails, puis réappliquer la migration "
                    "concernée ou corriger le texte à la main."
                )
            ecarts.append(
                f"Modèle d'e-mail « {modele.code} » : ce qui part diffère du code.\n"
                + "\n".join(detail)
            )

        if not (modele.intention or "").strip() and INTENTIONS_PAR_MODELE.get(modele.code):
            ecarts.append(
                f"Modèle d'e-mail « {modele.code} » : aucune intention en base.\n"
                "Le bandeau du message est vide, et l'adresse d'expédition retombe "
                f"sur le choix du code (« {INTENTIONS_PAR_MODELE[modele.code]} »).\n"
                "À choisir dans Admin → Emails → Intention."
            )

    return ecarts


__all__ = ["ModeleIllisible", "VARIABLES_DU_GABARIT", "controler", "variables_de"]
