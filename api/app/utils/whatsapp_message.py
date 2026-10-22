"""Le TEXTE d'un message pour le groupe de la résidence — sa composition seule.

Extrait de `utils/whatsapp.py` le 28/09/2026, au fil de l'eau (#779) : le module
faisait 532 lignes et mêlait deux notions — COMPOSER le message (titre, contenu
converti du HTML, périmètre, version restreinte d'un message réservé, lien) et
le TRANSPORTER (bridge, journal, verdict d'envoi). Le premier ne dépend d'aucun
réseau ni d'aucune base : c'est ce qui se teste et s'aperçoit sans rien envoyer
(`apercu_diffusion`, `test_actualite_acces`).

⚠️ `whatsapp.py` ré-exporte `construire_message`, `message_sans_contenu` et
`TITRE_CONFIDENTIEL` : les importeurs existants ne bougent pas.
"""

import html
import json
import re

from app.utils.arrivees_notification import SOURCE_WHATSAPP, etiqueter_lien
from app.utils.liens import adresse_du_site, nom_site
from app.utils.perimetres import est_perimetre_par_defaut, perimetre_label

#: La signature d'un message quand la configuration n'en porte pas — **neutre**.
#:
#: 🔴 Le repli était « — Conseil Syndical 5Hostachy », écrit TROIS fois (deux
#: ici, une dans `whatsapp_scheduler`) : le nom de CETTE résidence, qu'une autre
#: copropriété aurait signé à sa place le jour où son pied serait vide (#1725).
#: Le seed pose la même valeur (`seed.CONFIG_DEFAUTS`), et il l'importe d'ici.
PIED_WHATSAPP_PAR_DEFAUT = "— Le Conseil Syndical"


def pied_whatsapp(footer: str | None) -> str:
    """La signature d'un message : celle de la configuration, sinon le repli.

    >>> pied_whatsapp("  — Le CS du Parc  ")
    '— Le CS du Parc'
    >>> pied_whatsapp("")
    '— Le Conseil Syndical'
    >>> pied_whatsapp(None)
    '— Le Conseil Syndical'
    """
    return (footer or "").strip() or PIED_WHATSAPP_PAR_DEFAUT


def _libelle_perimetre(perimetre_cible: str | list | None) -> str:
    """Le périmètre affiché dans l'en-tête — « Copropriété » quand c'est le défaut.

    Écrit DEUX fois dans ce module jusqu'au 02/10/2026, chaque copie comparant
    `lieux[0] == "résidence"` : le code de la racine en dur, là où l'arbre le
    désigne (#1567). La question se pose maintenant à `est_perimetre_par_defaut`,
    comme `estPerimetreParDefaut` côté front.

    Les autres lieux se lisent par `perimetre_label`, le rendu de tout le site :
    le groupe recevait le code brut, « bat:4/ascenseur » (22/10/2026).
    """
    try:
        lieux = (
            json.loads(perimetre_cible)
            if isinstance(perimetre_cible, str)
            else (perimetre_cible or [])
        )
    except Exception:
        lieux = []
    if not isinstance(lieux, list) or est_perimetre_par_defaut(lieux):
        return "Copropriété"
    return perimetre_label([str(lieu) for lieu in lieux])


def _entete(titre: str, urgente: bool, perimetre_cible: str | list | None) -> str:
    """La première ligne du message — commune au message complet et au restreint.

    Écrite dans chacun des deux jusqu'au 02/10/2026, avec le calcul du périmètre
    qu'elle affiche (#1567).
    """
    perimetre_label = _libelle_perimetre(perimetre_cible)
    if urgente:
        return f"🚨 URGENT — 🔹 {perimetre_label} — *{titre}*"
    return f"📢 🔹 {perimetre_label} — *{titre}*"


def _build_message(
    titre: str,
    contenu: str,
    urgente: bool,
    perimetre_cible: str | None,
    footer: str | None = None,
    lien: str | None = None,
) -> str:
    """Construit le texte du message WhatsApp.

    `lien` ajoute, avant la signature, un renvoi vers l'application — « voir
    le contenu complet ». Demandé le 18/08/2026 pour le SUIVI d'un événement,
    dont le commentaire est souvent lu hors de son contexte : sans lien, le
    lecteur du groupe voit un commentaire sans savoir sur quoi il porte.

    ⚠️ Le message **restreint** en portait déjà un, codé chez lui
    (`_build_message_restreint`), et c'était le seul du site. Le paramètre est
    donc facultatif et ne change RIEN aux appels existants : une actualité
    ordinaire continue de partir sans lien tant que personne ne l'a demandé à
    l'écran (R5 — un enrichissement se propage, donc il se constate d'abord
    sur UN cas).
    """
    header = _entete(titre, urgente, perimetre_cible)

    # Contenu : convertir le formatage HTML en markdown WhatsApp
    # Gras : <b>, <strong>  → *texte*
    text = re.sub(
        r"<(b|strong)(\s[^>]*)?>(.+?)</(b|strong)>",
        r"*\3*",
        contenu,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Italique : <i>, <em>  → _texte_
    text = re.sub(
        r"<(i|em)(\s[^>]*)?>(.+?)</(i|em)>", r"_\3_", text, flags=re.IGNORECASE | re.DOTALL
    )
    # Barré : <s>, <strike>, <del>  → ~texte~
    text = re.sub(
        r"<(s|strike|del)(\s[^>]*)?>(.+?)</(s|strike|del)>",
        r"~\3~",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Saut de ligne : <br>, </p>
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    # Supprimer les balises HTML restantes
    text = re.sub(r"<[^>]+>", "", text)
    # Décoder les entités HTML (&nbsp; → espace, &amp; → &, etc.)
    text = html.unescape(text)
    # Remplacer les espaces insécables résiduels par des espaces normaux
    text = text.replace("\u00a0", " ")
    text = text.strip()

    footer = pied_whatsapp(footer)
    #  Le lien vient APRÈS le texte et AVANT la signature : c'est la place
    #  qu'il occupe déjà dans le message restreint, et le lecteur d'un groupe
    #  WhatsApp cherche l'action en bas du message, jamais au milieu.
    renvoi = f"\n\n👉 Voir le contenu complet :\n{(lien or chr(32)).strip()}"
    renvoi = renvoi if (lien or "").strip() else ""
    return f"{header}\n\n{text}{renvoi}\n\n{footer}"


def _is_restreint(public_cible: str | list | None) -> bool:
    """Retourne True si la publication n'est pas destinée à tous les résidents."""
    if public_cible is None:
        return False
    try:
        lst = json.loads(public_cible) if isinstance(public_cible, str) else public_cible
    except Exception:
        return False
    return "résidents" not in lst


#: Titre de repli, employé quand une actualité n'en a pas.
#:
#: 🔴 **CE N'EST PLUS LE TITRE DES CONFIDENTIELLES** — #347 renversé par #623
#: le 29/08/2026 : le titre part, et l'écran avertit son auteur de n'y rien
#: mettre de confidentiel. Le contenu, lui, ne sort jamais.
TITRE_CONFIDENTIEL = "Information réservée au périmètre concerné"


def _build_message_restreint(
    titre: str,
    urgente: bool,
    perimetre_cible: str | None,
    site_url: str,
    footer: str | None = None,
    lien: str | None = None,
    site_nom: str | None = None,
) -> str:
    """Construit un message WhatsApp court pour une publication à audience restreinte.

    `titre` est le titre **à afficher**, pas nécessairement celui de la
    publication : le cas confidentiel y passe `TITRE_CONFIDENTIEL`. C'est la
    seule différence entre les deux usages, et elle tient dans un argument — une
    seconde fonction jumelle aurait divergé dès la première retouche de l'en-tête
    ou du lien (`standards/02-factorisation.md` §2).
    """
    header = _entete(titre, urgente, perimetre_cible)

    avertissement = (
        "🔒 Cette publication est réservée à un public ciblé.\n"
        "Elle n'est pas accessible à tous.\n"
        f"Si vous êtes concerné(e), connectez-vous sur {nom_site(site_nom)} pour la consulter :"
    )
    #  🔴 Le lien FOURNI (#1091) : l'actualité est devenue une affaire, son
    #  adresse est celle de sa fiche. `pub_id` et `/actualites#pub-<id>` ont été
    #  retirés avec l'entité ; sans lien, le message renvoie à l'accueil du site.
    if not lien:
        lien = site_url.rstrip("/") + "/"

    return f"{header}\n\n{avertissement}\n{lien}\n\n{pied_whatsapp(footer)}"


def message_sans_contenu(public_cible: str | list | None, confidentiel: bool = False) -> bool:
    """Ce message doit-il se réduire à « avertissement + périmètre + lien » ?

    Deux raisons, une seule forme de message :
      - **public restreint** — le groupe est commun, le contenu ne s'adresse pas
        à tous ceux qui le liraient ;
      - **confidentiel** (#347) — même raison, sur l'axe bâtiment cette fois, et
        le titre lui-même est retiré.
    """
    return bool(confidentiel) or _is_restreint(public_cible)


def construire_message(
    titre: str,
    contenu: str,
    urgente: bool,
    perimetre_cible: str | None,
    config: dict,
    public_cible: str | None = None,
    confidentiel: bool = False,
    *,
    lien: str | None = None,
) -> str:
    """Le texte du message, décidé **une seule fois**.

    `envoyer_whatsapp` et `envoyer_whatsapp_avec_log` construisaient chacun leur
    message avec le même `if _is_restreint(...)`, si bien que le texte journalisé
    et le texte envoyé étaient deux calculs distincts d'une même chose. Ajouter
    le cas confidentiel en aurait fait deux copies à tenir alignées — dont l'une
    décide de ce qui part dans le groupe, l'autre de ce qu'on croit y avoir
    envoyé.
    """
    footer = config.get("whatsapp_footer", "").strip()
    site_url = adresse_du_site()
    #  L'étiquette d'arrivée (#1634) : écrite une fois, pour les deux formes.
    lien = etiqueter_lien(lien, SOURCE_WHATSAPP, site_url) if lien else None
    if message_sans_contenu(public_cible, confidentiel):
        #  🔴 Le titre PART, confidentiel compris (#623) ; le repli ne sert
        #  plus qu'aux actualités sans titre.
        titre_affiche = titre or TITRE_CONFIDENTIEL
        return _build_message_restreint(
            titre_affiche,
            urgente,
            perimetre_cible,
            site_url,
            footer,
            lien or etiqueter_lien(site_url + "/", SOURCE_WHATSAPP, site_url),
            config.get("site_nom"),
        )
    #  Le lien ne concerne QUE le message normal : le message restreint en porte
    #  déjà un, qui renvoie vers l'application parce que le contenu n'y est pas.
    #  Lui en ajouter un second en donnerait deux, dont l'un ferait double emploi.
    return _build_message(titre, contenu, urgente, perimetre_cible, footer, lien)
