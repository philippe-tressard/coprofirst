"""Les signatures de fichier : le contenu dément-il le type annoncé ? (#773)

Extrait de `utils/fichiers` le 31/10/2026 (#2388), qui tenait sa limite de
500 lignes ; `fichiers.signature_incoherente` le ré-exporte.
"""

#: Les signatures de fichier — premiers octets, par extension.
#:
#: 🔴 POURQUOI CE CONTRÔLE EXISTE (#773, audit du 05/09/2026)
#:
#: Les documents n'étaient vérifiés que par `file.content_type` — une chaîne
#: **envoyée par le client**, qu'un `curl` fixe librement. Un exécutable renommé
#: `.pdf` avec `Content-Type: application/pdf` était stocké, puis servi aux
#: résidents. Les images, elles, l'étaient réellement (PIL ouvre le fichier) :
#: le même produit avait donc deux niveaux d'exigence pour la même question.
#:
#: ⚠️ CE CONTRÔLE NE RESTREINT PAS LA LISTE DES TYPES ACCEPTÉS. Chaque écran
#: garde la sienne — les compteurs acceptent des photos, les diagnostics des
#: rapports. Il vérifie la **cohérence** : ce que le fichier dit être, et ce
#: qu'il est. Un format sans signature stable (`.txt`, `.csv`) passe donc sans
#: être inspecté, et c'est voulu : refuser faute de savoir reconnaître serait
#: refuser du légitime.
#:
#: Une marque est des octets attendus EN TÊTE, ou `(décalage, octets)` quand le
#: format la place plus loin : AVIF écrit sa boîte `ftyp` à l'octet 4.
_SIGNATURES: dict[str, tuple[bytes | tuple[int, bytes], ...]] = {
    ".pdf": (b"%PDF-",),
    #  Les formats Office récents sont des archives ZIP.
    ".docx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".xlsx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".pptx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    #  Les anciens (OLE2) partagent la même en-tête.
    ".doc": (b"\xd0\xcf\x11\xe0",),
    ".xls": (b"\xd0\xcf\x11\xe0",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".webp": (b"RIFF",),
    #  Ajoutés le 31/10/2026 (#2388) : toute image se joint, réencodée en JPEG.
    ".avif": ((4, b"ftypavif"), (4, b"ftypavis")),
    ".bmp": (b"BM",),
    ".tiff": (b"II*\x00", b"MM\x00*"),
}


def signature_incoherente(donnees: bytes, extension: str) -> str | None:
    """Le contenu dément-il l'extension ? Rend le motif, ou `None` si tout va bien.

    Rend `None` dans deux cas qu'il ne faut pas confondre :

    * l'extension **n'a pas** de signature connue (`.txt`, `.csv`) — rien à
      vérifier, et inventer un refus ici bloquerait du contenu légitime ;
    * l'extension a une signature, et les octets correspondent.

    ⚠️ Rend un **motif**, pas un booléen : l'appelant doit pouvoir dire à
    l'utilisateur ce qui est refusé, et le journaliser. Un refus sans motif
    ressemble à une panne, et c'est ainsi qu'on désarme un contrôle pour
    « débloquer » quelqu'un.
    """
    attendues = _SIGNATURES.get((extension or "").lower())
    if not attendues:
        return None
    if any(_porte(donnees, m) for m in attendues):
        return None
    return (
        f"le contenu ne correspond pas à un fichier {extension} "
        "(signature du fichier incohérente avec son extension)"
    )


def _porte(donnees: bytes, marque: bytes | tuple[int, bytes]) -> bool:
    decalage, octets = marque if isinstance(marque, tuple) else (0, marque)
    return donnees[decalage : decalage + len(octets)] == octets
