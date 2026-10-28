"""Le pied de page du site — ce que le serveur en sait (`#lib/piedDePage` côté front).

Tout ce qu'il affiche est déjà public : ses clés se lisent sans connexion
(`GET /config`). Le texte libre et le préfixe du nom tiennent sur une ligne,
et ils sont bornés à l'enregistrement comme à la saisie — la même borne des
deux côtés, faute de fichier partagé entre `./api` et `./front`.
"""

from __future__ import annotations

TEXTE_PIED_MAX = 120
PREFIXE_NOM_MAX = 40

#: Éléments retirés, année de création, texte libre, ordre, préfixe du nom.
CLES_PUBLIQUES = frozenset(
    {
        "pied_de_page_masques",
        "pied_de_page_annee_debut",
        "pied_de_page_texte",
        "pied_de_page_ordre",
        "pied_de_page_prefixe_nom",
    }
)


def _une_ligne(valeur: str, maximum: int) -> str:
    return " ".join(str(valeur).split())[:maximum]


#: Ce que `PUT /config` récrit avant d'enregistrer.
NORMALISEURS = {
    "pied_de_page_texte": lambda v: _une_ligne(v, TEXTE_PIED_MAX),
    "pied_de_page_prefixe_nom": lambda v: _une_ligne(v, PREFIXE_NOM_MAX),
}
