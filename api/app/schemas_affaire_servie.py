"""Ce qu'une affaire SERT, en plus de ses colonnes, aux deux clients (#2508).

## Pourquoi ces champs

Le site calculait dans son front l'urgence (⚡), la colonne du Kanban, le libellé
de la catégorie et de l'état, l'affaire close, le badge NEW, le nom affiché d'une
affaire « saisie pour », et les gestes offerts. L'app iOS ne lit que le contrat : elle les
recopiait depuis le front publié (`standards/09` §8, règle 1). Ils sont désormais
servis ici, et les deux clients LISENT.

## Deux natures de champs, et pourquoi

- **calculés** (`computed_field`) : ils ne dépendent que des colonnes de
  l'affaire. Calculés par le schéma, ils sont vrais partout où `TicketRead` est
  rendu — la liste, la fiche, la ligne de pastilles du fil (`pastilles_affaire`),
  sans qu'un appelant puisse les oublier. Chacun appelle la fonction du serveur
  qui porte la règle, jamais une copie ;
- **posés par la lecture** (`tickets/commun.ticket_read`) : ils dépendent du
  LECTEUR (les gestes) ou de l'arbre des périmètres. Leur défaut est FERMÉ — un
  geste qu'on n'a pas calculé n'est pas offert (`CLAUDE.md`, « Ce que l'écran
  MONTRE est ce qui PART »).

Le contrat les déclare en lecture (`exporter_openapi`) ; aucun n'est accepté en
entrée.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, computed_field

from app.utils.categories_ticket import libelle_categorie, ticket_urgent
from app.utils.etat_affaire import affaire_close, libelle_etat
from app.utils.frequence_contrat import frequence_libelle as _frequence_libelle
from app.utils.kanban_tickets import colonne_du_ticket
from app.utils.nouveaute import est_nouveau


class AffaireServie(BaseModel):
    """Les champs servis d'une affaire. Mêlé à `TicketRead`, qui porte les colonnes lues."""

    #: 🔹 Le lieu lisible (« Bât. 2 › Toit »), VIDE pour le périmètre par défaut —
    #: que le badge tait (`est_perimetre_par_defaut`). Posé par la lecture.
    perimetre_libelle: str = ""
    #: 📦 Archiver (`gestes_affaire.peut_archiver`).
    peut_archiver: bool = False
    #: Une Suite qui change l'état (`gestes_affaire.peut_changer_etat`).
    peut_changer_etat: bool = False
    #: Glisser la carte au Kanban — le conseil seul (`gestes_affaire.peut_deplacer_au_kanban`).
    peut_deplacer_au_kanban: bool = False
    #: « Répondre » : une Suite sans état (`gestes_affaire.peut_repondre`).
    peut_repondre: bool = False
    #: ✏️ Corriger le contenu (`gestes_affaire.peut_modifier`).
    peut_modifier: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def urgente(self) -> bool:
        """⚡ L'affaire presse : sa priorité le dit (`categories_ticket.ticket_urgent`)."""
        return ticket_urgent(self)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def categorie_libelle(self) -> str:
        """« Étude & travaux » — la valeur brute si elle est inconnue, jamais vide."""
        return libelle_categorie(getattr(self, "categorie", None))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def statut_libelle(self) -> str:
        """« Chez le syndic » — la valeur brute si elle est inconnue, jamais vide."""
        return libelle_etat(getattr(self, "statut", None))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def suivi_actualite_libelle(self) -> str:
        """L'état du suivi d'une actualité en clair — vide sans suivi (#2633)."""
        return libelle_etat(getattr(self, "suivi_actualite", None))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def close(self) -> bool:
        """Résolue ou annulée (`etat_affaire.affaire_close`) — elle quitte le suivi."""
        return affaire_close(getattr(self, "statut", None))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def colonne_kanban(self) -> Optional[str]:
        """La colonne du Kanban (`kanban_tickets.colonne_du_ticket`), `None` hors tableau."""
        return colonne_du_ticket(getattr(self, "statut", None))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def frequence_libelle(self) -> str:
        """« ↺ Mensuel » — le rythme SAISI sur l'affaire, vide sans fréquence (#2633).

        Sous contrat, le rythme qui fait foi est celui du contrat
        (`contrat.frequence_libelle`) : le client lit celui-là d'abord.
        """
        return _frequence_libelle(
            getattr(self, "frequence_type", None), getattr(self, "frequence_valeur", None)
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def nouveau(self) -> bool:
        """Le badge NEW : créée depuis moins de 48 h (`nouveaute.est_nouveau`, #2506)."""
        return est_nouveau(getattr(self, "cree_le", None))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def nom_proprietaire(self) -> str:
        """Le nom AFFICHÉ : la personne « saisie pour », sinon le rédacteur (#1104).

        `proprietaire_nom` vient de `utils/saisi_pour.noms_derives` ; vide s'il n'y
        a ni l'un ni l'autre (un compte supprimé), jamais `None`.
        """
        proprietaire = getattr(self, "proprietaire_nom", None)
        if proprietaire is not None:
            return proprietaire
        return getattr(self, "auteur_nom", None) or ""


__all__ = ["AffaireServie"]
