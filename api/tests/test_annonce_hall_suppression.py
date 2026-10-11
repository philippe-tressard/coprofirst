"""Supprimer une affiche de hall n'efface que ce qu'elle a produit : son PDF (#1828).

Ses images ne lui appartiennent pas. Une affiche reprise d'une affaire reçoit les
photos de l'affaire (`images_de`), une affiche reprise d'une autre affiche les
mêmes adresses que l'originale : la suppression définitive les effaçait du
disque, et l'affaire restait avec des photos disparues. Aucune autre suppression
de l'application n'efface les photos qu'un objet référence — l'affiche s'aligne.
"""

from __future__ import annotations

from app.models.core import RoleUtilisateur
from app.routers import annonces_hall
from app.utils.stockage import stockage
from tests.aides_annonce_hall import contexte_fixture, creer  # noqa: F401 — la fixture `contexte`
from tests.aides_base import compte


def _photo(cle: str) -> str:
    """Une photo déjà au stockage — celle d'une affaire —, rendue par son adresse."""
    st = stockage()
    st.ecrire(cle, b"\xff\xd8\xff photo")
    return st.url(cle)


def _supprimer(session, annonce_id: int) -> None:
    admin = compte(session, prefixe="admin", roles_json=RoleUtilisateur.admin.value)
    annonces_hall.delete_annonce_hall(annonce_id=annonce_id, session=session, _=admin)


def test_la_photo_d_une_affaire_reprise_survit_a_l_affiche(contexte):
    session, cs = contexte
    url = _photo("photos/fuite-hall.jpg")
    annonce = creer(session, cs, images=[url])
    _supprimer(session, annonce.id)
    assert stockage().existe("photos/fuite-hall.jpg")


def test_deux_affiches_d_une_meme_image_la_seconde_garde_la_sienne(contexte):
    session, cs = contexte
    url = _photo("photos/ascenseur.jpg")
    premiere = creer(session, cs, images=[url])
    creer(session, cs, images=[url])
    _supprimer(session, premiere.id)
    assert stockage().existe("photos/ascenseur.jpg")


def test_le_pdf_de_l_affiche_part_avec_elle(contexte):
    session, cs = contexte
    annonce = creer(session, cs)
    st = stockage()
    cle_pdf = st.cle_de_chemin(annonce.pdf_chemin)
    assert cle_pdf is not None and st.existe(cle_pdf)
    _supprimer(session, annonce.id)
    assert not st.existe(cle_pdf)
