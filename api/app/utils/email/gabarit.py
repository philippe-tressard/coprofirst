"""Courriels — la mise en forme : gabarit HTML, bandeaux, logo.

Extrait de `email.py` (686 lignes) le 11/08/2026, au fil de l'eau : la
factorisation du préambule de référence l'avait fait passer de 618 à 686, et
c'est le garde-fou de modularité qui a refusé le lot.

Le partage est net : ici on décide de ce que le destinataire **voit** ; dans
`__init__.py`, de ce qu'on **envoie** et à qui. Les deux ont des raisons de
changer distinctes — une retouche de charte graphique ne touche pas au SMTP.
"""

import re as _re

from app.utils.fichiers import libelle_pieces_jointes
from app.utils.logo import adresse_logo


# Intention d'un e-mail : ce qui est attendu du destinataire, annoncé d'emblée.
#
# La plupart des modèles entrent dans le détail sans annoncer la couleur : le
# lecteur doit lire jusqu'au bout pour savoir si on l'informe ou si on attend
# quelque chose de lui. Un bandeau en tête le dit en trois mots.
#
# Le bandeau est rendu par le gabarit commun, à partir d'une colonne de
# `modele_email` — surtout pas recopié dans chaque corps : il resterait
# introuvable le jour où il faudrait le changer, et une migration qui réécrit
# vingt-quatre corps écraserait les personnalisations faites depuis
# Admin → Emails.
#
# code → (libellé affiché, fond, texte)
INTENTIONS: dict[str, tuple[str, str, str]] = {
    "information": ("Pour information", "#EEF2F7", "#1E3A5F"),
    "action_requise": ("Action requise", "#FEF3E2", "#8A5A0B"),
    "reponse_attendue": ("Réponse attendue", "#F0F7F2", "#2C5138"),
    # Un envoi qu'on garde sans avoir à en faire quoi que ce soit — le CR validé
    # d'un point CS / Syndic, PDF joint (#2082), et ce qu'Admin → Emails y range.
    "archive": ("À conserver", "#F4F2ED", "#5A6070"),
}


def _bandeau_intention(intention: str | None) -> str:
    """Bandeau « ce qu'on attend de vous », ou rien si l'intention est inconnue.

    Une intention vide ou non reconnue ne rend rien plutôt que d'afficher une
    étiquette fausse : un modèle sans intention déclarée reste exactement ce
    qu'il était.
    """
    entree = INTENTIONS.get((intention or "").strip())
    if not entree:
        return ""
    libelle, fond, couleur = entree
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" '
        f'style="width:100%;margin:0 0 20px"><tr>'
        f'<td style="background:{fond};border-radius:6px;padding:10px 14px">'
        f'<span style="font-size:12px;font-weight:700;letter-spacing:.6px;'
        f'text-transform:uppercase;color:{couleur}">{libelle}</span>'
        f"</td></tr></table>"
    )


# ── Logo ──
#
#  Le logo était redessiné ici, tracé pour tracé, alors que `CLAUDE.md` pose
#  `utils/pdf_theme.py` comme sa source unique (14/08/2026) ; puis il en était
#  importé en SVG inline — que Gmail et Outlook retirent souvent.
#
#  🔴 Depuis #1728 (08/10/2026, arbitré) : une IMAGE PAR ADRESSE PUBLIQUE,
#  `GET /config/logo.png`, qui sert le logo téléversé par la résidence ou le
#  logo neutre. Un client qui bloque les images distantes affiche le `alt` : le
#  nom de la résidence, déjà écrit à côté — rien n'est perdu.
TAILLE_LOGO_COURRIEL = 48


def _linkify_urls(text: str) -> str:
    """Transforme les URLs brutes en liens cliquables dans le footer."""
    return _re.sub(
        r"(https?://\S+|(?<!\w)([a-zA-Z0-9-]+\.)+[a-z]{2,}(?:/\S*)?)",
        lambda m: (
            f'<a href="{m.group(0) if m.group(0).startswith("http") else "https://" + m.group(0)}" '
            f'style="color:#1E3A5F;text-decoration:underline">{m.group(0)}</a>'
        ),
        text,
    )


def _html_echappe(texte: str) -> str:
    """Un nom de fichier est une donnée : il ne doit pas pouvoir injecter de balise.

    Les noms produits par `nom_stocke` sont déjà réduits à `[A-Za-z0-9_.-]`, mais
    les fichiers antérieurs à ce nommage n'ont pas eu ce traitement. On ne fait
    donc pas confiance à la provenance — cf. `standards/03-securite.md` §4.
    """
    return (
        (texte or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _bandeau_pieces_jointes(noms: list[str]) -> str:
    """Sommaire des pièces jointes, en pied de contenu : décompte puis liste nommée.

    Écrite **ici** et pas dans les modèles, pour trois raisons :

    1. Les modèles vivent en **base** (`modele_email`) et `seed()` ne les met à jour
       que s'ils n'existent pas encore : modifier `seed.EMAIL_TEMPLATES` n'a aucun
       effet sur une installation en service. Ce qui est écrit dans le code, si.
    2. Le nombre vient de la liste **réellement transmise** au constructeur du
       message, pas d'un drapeau de contexte. Un drapeau peut mentir — deux le
       faisaient encore le 03/08/2026, l'un annonçant des pièces jointes sans en
       attacher, l'autre l'inverse. Ici, la mention et la pièce jointe ont la même
       source : elles ne peuvent pas diverger.
    3. Un seul endroit couvre les six modèles susceptibles de porter des pièces
       jointes, et tous ceux à venir.

    La liste nommée n'est pas un doublon de ce que montre la messagerie : c'est le
    **repli**. Le nom d'origine est déjà rétabli dans l'en-tête
    `Content-Disposition` (cf. `_preparer_pieces_jointes`), mais un client ou une
    passerelle peut l'ignorer, tronquer, ou retirer la pièce jointe sans le dire.
    Écrit dans le corps du message, le sommaire survit à tout cela — et il permet
    au destinataire de constater qu'il manque quelque chose.

    ⚠️ `ticket_syndic` et `publication_syndic` portent en base une mention
    « Pièces jointes disponibles ci-dessous », **conservée volontairement**
    (décision du 03/08/2026). Ce n'est pas un doublon : elle est imbriquée dans
    `{% if is_commentaire %}` et rendue *à l'intérieur du cadre du commentaire*,
    donc elle dit **à quoi** les pièces jointes se rattachent — ce commentaire-ci,
    pas l'historique. Le sommaire, lui, dit combien et lesquelles. Sur un ticket
    à dix messages, les deux informations sont utiles.
    Elle ne s'affiche jamais à la création (`is_commentaire` faux).

    Les noms viennent de `nom_lisible`, comme l'en-tête : une seule règle, donc
    aucune divergence possible entre ce qui est annoncé et ce qui est joint.
    """
    if not noms:
        return ""
    #  « 1 photo » plutôt que « 1 pièce jointe » quand l'extension permet de le
    #  dire : le décompte seul oblige le destinataire à ouvrir pour savoir de quoi
    #  il s'agit. Repli sur le libellé générique si aucune extension n'est
    #  exploitable — mieux vaut vague qu'inexact.
    libelle = libelle_pieces_jointes(noms) or (
        "1 pièce jointe" if len(noms) == 1 else f"{len(noms)} pièces jointes"
    )
    lignes = "".join(
        f'<tr><td style="padding:2px 0;font-size:13px;color:#1A1A2E">'
        f'<span style="color:#8A8FA0">{i}.</span>&nbsp;{_html_echappe(nom)}</td></tr>'
        for i, nom in enumerate(noms, start=1)
    )
    return (
        '<tr><td style="background-color:#FFFFFF;padding:0 32px 20px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-top:1px solid #E4E7EC">'
        '<tr><td style="padding-top:14px;font-size:13px;color:#5A6070">'
        f"📎 Ce message comporte <strong>{libelle}</strong> :"
        "</td></tr>"
        f'<tr><td style="padding-top:6px"><table role="presentation" cellpadding="0" '
        f'cellspacing="0">{lignes}</table></td></tr>'
        '<tr><td style="padding-top:8px;font-size:12px;color:#8A8FA0">'
        "Si l'une d'elles n'apparaît pas, votre messagerie a pu la filtrer."
        "</td></tr>"
        "</table></td></tr>"
    )


def _wrap_email(
    body_html: str,
    site_nom: str,
    site_url: str,
    footer: str,
    annee: int,
    pieces_jointes: list[str] | None = None,
    intention: str | None = None,
) -> str:
    """Encapsule le contenu HTML dans un gabarit email aux couleurs du site."""
    bandeau_pj = _bandeau_pieces_jointes(pieces_jointes or [])
    bandeau_intention = _bandeau_intention(intention)
    safe_footer = ""
    if footer:
        linked_footer = _linkify_urls(footer)
        safe_footer = (
            f'<tr><td style="background-color:#FAFAF7;padding:20px 32px 24px;text-align:center">'
            f'<p style="margin:0;font-size:13px;color:#5A6070">{linked_footer}</p>'
            f"</td></tr>"
        )
    return f'''<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{site_nom}</title></head>
<body style="margin:0;padding:0;background-color:#F2EFE9;font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,Roboto,'Helvetica Neue',Arial,sans-serif;color:#1A1A2E;-webkit-text-size-adjust:100%">

<!-- Wrapper -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F2EFE9;padding:24px 0">
<tr><td align="center">

<!-- Container -->
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(30,58,95,0.12)">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#1E3A5F 0%,#16304F 100%);padding:28px 32px;text-align:center">
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto"><tr>
      <td style="vertical-align:middle;padding-right:14px"><img src="{adresse_logo(site_url, TAILLE_LOGO_COURRIEL * 2)}" width="{TAILLE_LOGO_COURRIEL}" height="{TAILLE_LOGO_COURRIEL}" alt="" style="display:block;border:0"></td>
      <td style="vertical-align:middle;text-align:left">
        <div style="font-family:Georgia,'Palatino Linotype','Book Antiqua',Palatino,serif;font-size:22px;font-weight:700;color:#FFFFFF;letter-spacing:0.3px">{site_nom}</div>
        <div style="font-size:12px;color:#C9983A;letter-spacing:1.5px;text-transform:uppercase;margin-top:2px;font-weight:600">Espace numérique de résidence</div>
      </td>
    </tr></table>
  </td></tr>

  <!-- Accent bar -->
  <tr><td style="height:4px;background:linear-gradient(90deg,#C9983A 0%,#1E3A5F 50%,#3D6B4F 100%)"></td></tr>

  <!-- Body -->
  <tr><td style="background-color:#FFFFFF;padding:32px 32px 24px;font-size:15px;line-height:1.65;color:#1A1A2E">
    {bandeau_intention}{body_html}
  </td></tr>

  <!-- Pièces jointes -->
  {bandeau_pj}

  <!-- Notification preferences -->
  <tr><td style="background-color:#FFFFFF;padding:0 32px 20px;text-align:center">
    <p style="margin:0;font-size:12px;color:#8A8FA0">Pour gérer vos préférences de notification, rendez-vous dans votre <a href="{site_url.rstrip("/")}/profil" style="color:#1E3A5F;text-decoration:underline">profil</a>.</p>
  </td></tr>

  <!-- Footer -->
  {safe_footer}

</table>
<!-- /Container -->

</td></tr>
</table>
<!-- /Wrapper -->
</body>
</html>'''
