"""Le RENDU d'un courriel : contexte, sujet sur une ligne, corps enveloppé.

Extrait de `utils/email/__init__.py` le 13/10/2026 (#1902) : le moteur dépassait
le plafond de 500 lignes une fois la démo branchée. Le moteur le ré-exporte —
`from app.utils.email import composer_email` reste valable.
"""

from __future__ import annotations

import re as _re

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from sqlmodel import Session

from app.models.core import ModeleEmail
from app.utils import horloge
from app.utils.arrivees_notification import etiqueter_courriel
from app.utils.config_site import config_site
from app.utils.fichiers import nom_lisible
from app.utils.html_sur import filtre_safe
from app.utils.liens import adresse_du_site, nom_site

from .gabarit import _wrap_email


def _render(template_str: str, context: dict, *, html: bool) -> str:
    """Rend un champ de modèle. `html=True` pour le corps, `False` pour l'objet.

    🔴 Le CORPS s'échappe (#2150). Il ne l'était pas : un titre, un nom ou une
    description entrait tel quel dans le HTML, et `| safe` ne faisait que
    confirmer un état de fait. Désormais tout est échappé, et un champ riche
    arrive soit marqué sûr par le code (`html_sur.html_riche`), soit par
    `| safe` — redéfini pour ASSAINIR (`html_sur.filtre_safe`).

    L'OBJET reste du texte : l'échapper y écrirait « &amp; ».
    """
    env = SandboxedEnvironment(loader=BaseLoader(), autoescape=html)
    if html:
        env.filters["safe"] = filtre_safe
    tmpl = env.from_string(template_str)
    return tmpl.render(**context)


def _prefixe_copro(reference: str) -> str:
    """« 🏢 00213 — » en tête d'objet, ou rien si la référence n'est pas renseignée.

    Forme **unique** du rappel de référence, obligatoire sans exception dans tout
    message adressé au syndic — c'est l'identifiant sous lequel il classe ses
    dossiers. Elle était recopiée sept fois dans les modèles, sous deux formes
    déjà différentes (« 🏢 00213 — » et « [🏢 00213] – ») : deux copies d'une même
    notion finissent toujours par diverger, et celles-ci l'avaient déjà fait.

    La composer ici plutôt que dans les modèles a une seconde conséquence, plus
    importante que la forme : un modèle vit en base et se réécrit depuis
    Admin → Emails. Le `{% if reference_copro %}` qui y était recopié pouvait
    être retiré d'un formulaire, et la règle avec lui.
    """
    ref = (reference or "").strip()
    return f"🏢 {ref} — " if ref else ""


def _contexte_rendu(session: Session, context: dict) -> tuple[dict, str, str, str]:
    """(contexte complet du rendu, nom du site, URL du site, pied de page).

    Les deux fonctions d'envoi lisaient ces valeurs chacune de leur côté, en
    trois `session.get` recopiés — la même configuration, deux fois.
    """
    lignes = config_site(session, "email_footer", "reference_copro")
    site_nom = nom_site(lignes.get("site_nom"))
    site_url = adresse_du_site()
    reference = (lignes.get("reference_copro") or "").strip()

    ctx = {
        "annee": horloge.maintenant().year,
        "app": {"url": site_url.rstrip("/")},
        "residence": {"nom": site_nom},
        **context,
        #  Après `context`, donc non surchargeable : la référence vient de la
        #  configuration du site, jamais d'un point d'appel. Cinq d'entre eux la
        #  lisaient séparément et deux ne la fournissaient pas du tout — leurs
        #  objets partaient sans référence, et Jinja évalue un indéfini à faux
        #  sans rien signaler. Lue ici, elle ne peut plus être oubliée.
        "reference_copro": reference,
        "prefixe_copro": _prefixe_copro(reference),
    }
    return ctx, site_nom, site_url, (lignes.get("email_footer") or "").strip()


#  Au-delà, un objet n'informe plus personne : aucun client de messagerie n'en
#  affiche le quart. La borne n'est pas cosmétique — ni `ticket.titre` ni
#  `publication.titre` n'ont de longueur maximale en base, donc rien ne limitait
#  la taille d'un objet depuis qu'ils y figurent.
_SUJET_MAX = 150


def _sujet_sur_une_ligne(sujet: str) -> str:
    """Objet d'un message : une seule ligne, de longueur bornée.

    Depuis le 11/08/2026, l'objet des e-mails de tickets et de publications
    porte le **titre** de l'objet métier — donc une saisie libre, qui n'était
    jusqu'ici rendue que dans le corps HTML. Deux conséquences, et aucune ne
    relève du modèle :

    1. **Sécurité.** Un `\\n` dans un titre coupe l'en-tête `Subject:` et laisse
       injecter un `Bcc:` — le message part alors à un destinataire choisi par
       l'auteur du ticket. Nos objets contiennent aujourd'hui tous un tiret
       cadratin, donc Python les encode en RFC 2047 et la coupure est
       neutralisée : c'est une protection **de circonstance**, qui disparaîtrait
       sans bruit le jour où un objet devient purement ASCII. On ne s'appuie pas
       dessus (`standards/03-securite.md` §4).
    2. **Lisibilité.** Un titre de 400 caractères produisait un objet de 400
       caractères.

    Écrit ici et non dans les modèles pour la même raison que
    `_bandeau_pieces_jointes` : ceux-ci vivent en base et sont réécrivables
    depuis Admin → Emails. Une règle qu'un formulaire peut retirer n'est pas une
    règle. À cet endroit, elle couvre les vingt-quatre modèles et tous ceux à
    venir.
    """
    #  Les caractères de contrôle d'abord : `\\s` ignore NUL, qui ferait lever
    #  la bibliothèque `email` au lieu d'être simplement neutralisé.
    propre = _re.sub(r"[\x00-\x1f\x7f]+", " ", sujet or "")
    propre = _re.sub(r"\s+", " ", propre).strip()
    if len(propre) <= _SUJET_MAX:
        return propre
    return propre[: _SUJET_MAX - 1].rstrip() + "…"


def composer_email(
    template: ModeleEmail,
    ctx: dict,
    *,
    site_nom: str,
    site_url: str,
    email_footer: str,
    attachments: list[str] | None = None,
) -> tuple[str, str]:
    """(objet, corps HTML complet) d'un e-mail — **la seule composition du projet**.

    ## Pourquoi cette fonction existe (#498, 19/08/2026)

    Deux raisons, et la seconde est la vraie.

    1. `send_email` et `send_email_group` portaient ces onze lignes **à
       l'identique**. Deux écritures d'une même règle sont deux valeurs libres de
       diverger (`standards/02` §2).

    2. 🔴 **L'aperçu avant envoi doit montrer ce qui partira, pas une
       reconstitution.** Un aperçu recomposé « à peu près » deviendrait faux à la
       première évolution d'un gabarit — et personne ne s'en apercevrait, puisque
       c'est justement l'aperçu qu'on regarderait pour vérifier. C'est le faux-vert
       de `standards/04` §14 : observer la chose, pas son enregistrement.

    ⚠️ **Toute règle de composition s'écrit ICI.** En ajouter une dans un appelant
    la rendrait invisible à l'aperçu, ce qui est exactement le défaut qu'on ferme.
    `api/tests/test_apercu_diffusion.py` échoue si les deux divergent.

    Ne touche ni au réseau ni à la base : elle reçoit tout ce dont elle a besoin.
    """
    corps = _render(template.corps_html, ctx, html=True)
    html = _wrap_email(
        corps,
        site_nom=site_nom,
        site_url=site_url,
        footer=email_footer,
        annee=ctx["annee"],
        pieces_jointes=[nom_lisible(p) for p in (attachments or [])],
        intention=template.intention,
    )
    #  L'étiquette d'arrivée (#1634), ici et pas dans les modèles : elle vaut pour
    #  tous, et l'aperçu la montre. Jamais sur un lien à jeton ni un courriel de compte.
    html = etiqueter_courriel(html, site_url, template.code)
    return _sujet_sur_une_ligne(_render(template.sujet, ctx, html=False)), html
