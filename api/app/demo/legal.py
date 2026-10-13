"""Les mentions légales et la politique de confidentialité de la DÉMO (spec §9, lot D7 #1907).

Posées par le générateur après le seed, comme l'identité affichée (`identite.py`) :
le seed n'écrit que les clés absentes, ces textes-ci priment. Ils remplacent les
gabarits « À RENSEIGNER » du produit (`seed/contenus_legaux.py`), qui décrivent une
vraie copropriété — des comptes nominatifs, des sauvegardes, des services tiers que
la démo n'appelle pas.

## Ce qui vient du `.env`, et pourquoi

Le dépôt est public et ne nomme aucune personne réelle (`test_identites_fictives`) :
l'ÉDITEUR et l'adresse de CONTACT se lisent dans `DEMO_EDITEUR` et `DEMO_CONTACT`.

- Sans `DEMO_EDITEUR`, la démo se déclare éditée **à titre non professionnel** : la
  LCEN (art. 6, III, 2) permet alors de ne publier que l'identité de l'hébergeur, à
  qui l'éditeur a communiqué la sienne.
- Sans `DEMO_CONTACT`, la page n'a pas d'adresse pour exercer ses droits : le
  générateur le signale (`manques`), et la mise en service ne se fait pas ainsi.

Les hébergeurs sont des sociétés : ils s'écrivent ici. Sources : le contrat d'Oracle
pour la France (Oracle France S.A.S.) et la politique de confidentialité de
Cloudflare, section « Coordonnées » (consultées le 13/10/2026).
"""

from __future__ import annotations

from html import escape

from sqlmodel import Session

from app.config import get_settings
from app.seed.contenus_legaux import PARAGRAPHE_LICENCE
from app.utils.config_site import ecrire_cle

HEBERGEUR = (
    "<p><strong>Oracle France S.A.S.</strong> — 15, boulevard Charles de Gaulle, 92715 "
    "Colombes Cedex, France. Le serveur est une machine d'Oracle Cloud Infrastructure "
    "située dans la région de Paris.</p>"
    "<p><strong>Cloudflare, Inc.</strong> — 101 Townsend St., San Francisco, CA 94107, "
    "États-Unis — gère le nom de domaine et achemine les connexions jusqu'au serveur "
    "(tunnel chiffré) : le serveur n'accepte aucune connexion directe.</p>"
)

NON_PROFESSIONNEL = (
    "Cette démonstration est éditée <strong>à titre non professionnel</strong> par "
    "l'auteur du logiciel. Conformément à l'article 6, III, 2 de la loi n° 2004-575 du "
    "21 juin 2004 pour la confiance dans l'économie numérique, son identité a été "
    "communiquée à l'hébergeur, qui la tient à la disposition des autorités."
)


def _editeur() -> str:
    nom = get_settings().demo_editeur.strip()
    return escape(nom) if nom else ""


def _contact() -> str:
    adresse = get_settings().demo_contact.strip()
    if not adresse:
        return "<strong>adresse de contact non renseignée</strong>"
    a = escape(adresse)
    return f'<a href="mailto:{a}">{a}</a>'


def manques() -> list[str]:
    """Ce qui manque au `.env` pour des textes complets. PURE (lit les réglages)."""
    return [] if get_settings().demo_contact.strip() else ["DEMO_CONTACT"]


def mentions_legales() -> str:
    nom = _editeur()
    editeur = f"<p>{nom}, à titre non professionnel.</p>" if nom else f"<p>{NON_PROFESSIONNEL}</p>"
    return (
        "<h2>Objet du site</h2>"
        "<p>Ce site est une <strong>démonstration</strong> du logiciel CoproFirst, sur une "
        "résidence <strong>fictive</strong>. Les personnes, lots, affaires et documents "
        "qu'il présente sont inventés ; tout ce qu'on y saisit est effacé chaque nuit.</p>"
        "<h2>Éditeur et directeur de la publication</h2>"
        + editeur
        + "<h2>Hébergeur</h2>"
        + HEBERGEUR
        + "<h2>Propriété intellectuelle</h2>"
        + PARAGRAPHE_LICENCE
        + "<h2>Contact</h2>"
        f"<p>{_contact()}</p>"
    )


def politique_confidentialite() -> str:
    return (
        "<h2>1. Responsable du traitement</h2>"
        "<p>L'éditeur de la démonstration (voir les mentions légales), joignable à "
        f"{_contact()}.</p>"
        "<h2>2. Ce que la démonstration traite</h2><ul>"
        "<li><strong>Ce que vous saisissez</strong> — on entre par un personnage partagé, "
        "sans créer de compte : vos saisies sont visibles des autres visiteurs. N'y mettez "
        "aucune donnée personnelle réelle. Elles sont <strong>effacées chaque nuit</strong>, "
        "au plus tard 24 heures après, et ne sont jamais sauvegardées.</li>"
        "<li><strong>Mesure d'audience interne</strong> — les pages vues et les gestes, "
        "rattachés au personnage et non à vous : elle ne désigne personne, ne quitte pas le "
        "serveur et s'efface avec le reste, chaque nuit.</li>"
        "<li><strong>Adresse IP</strong> — le serveur n'en enregistre aucune : son journal "
        "d'accès est anonyme et la base n'en contient pas. Elle n'est tenue qu'en mémoire, "
        "le temps de limiter les abus (nombre de requêtes par minute), et elle est vue par "
        "Cloudflare, qui achemine la connexion.</li>"
        "</ul>"
        "<h2>3. Finalité et base légale</h2>"
        "<p>Faire essayer le logiciel — base : l'intérêt légitime de l'éditeur à présenter "
        "un logiciel libre (art. 6-1-f du RGPD).</p>"
        "<h2>4. Destinataires</h2>"
        "<p>Aucune donnée n'est cédée ni commercialisée. Deux sous-traitants techniques "
        "interviennent :</p><ul>"
        "<li><strong>Oracle</strong> — l'hébergement, dans la région de Paris (France).</li>"
        "<li><strong>Cloudflare</strong> — le nom de domaine et l'acheminement des "
        "connexions, depuis un réseau mondial ; ses transferts hors de l'Union européenne "
        "sont encadrés par le cadre de protection des données UE–États-Unis et des clauses "
        "contractuelles types.</li></ul>"
        "<p>La démonstration n'envoie <strong>rien</strong> ailleurs : aucun courriel, aucun "
        "message WhatsApp, aucun appel à un assistant d'intelligence artificielle — "
        "l'historique note seulement ce qui serait parti.</p>"
        "<h2>5. Cookies</h2>"
        "<p>Seuls les cookies techniques de la session du personnage (<code>access_token</code>, "
        "<code>refresh_token</code>, <code>HttpOnly; Secure; SameSite=Strict</code>), "
        "strictement nécessaires : aucun consentement n'est requis, aucun cookie publicitaire "
        "ou de traçage n'est posé.</p>"
        "<h2>6. Vos droits</h2>"
        "<p>Accès, rectification, effacement, opposition (art. 15 à 21 du RGPD) : écrivez à "
        f"{_contact()}. L'effacement de la nuit les satisfait le plus souvent d'avance. En cas "
        "de litige : <strong>CNIL</strong> — www.cnil.fr.</p>"
    )


def poser(session: Session) -> None:
    ecrire_cle(session, "mentions_legales", mentions_legales())
    ecrire_cle(session, "politique_confidentialite", politique_confidentialite())
