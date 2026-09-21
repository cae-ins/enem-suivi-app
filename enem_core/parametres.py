"""Description déclarative des paramètres d'un module.

L'interface génère automatiquement le formulaire à partir de ces objets.
``globale`` indique la clé d'un paramètre global (Paramètres généraux) utilisée
pour pré-remplir la valeur la première fois.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .trimestre import valide as trimestre_valide


@dataclass
class Param:
    cle: str
    libelle: str
    defaut: Any = None
    aide: str = ""
    groupe: str = "Paramètres"
    obligatoire: bool = True
    globale: str | None = None
    note: str = ""          # message affiché en surbrillance au-dessus du champ
    type: str = field(default="texte", init=False)

    def convertir(self, valeur):
        return valeur

    def verifier(self, valeur) -> str | None:
        if self.obligatoire and (valeur is None or (isinstance(valeur, (str, list)) and not valeur)):
            return f"« {self.libelle} » est obligatoire."
        return None


@dataclass
class Texte(Param):
    def __post_init__(self):
        self.type = "texte"


@dataclass
class TrimestreP(Param):
    def __post_init__(self):
        self.type = "trimestre"

    def verifier(self, valeur):
        e = super().verifier(valeur)
        if e:
            return e
        if valeur and not trimestre_valide(valeur):
            return f"« {self.libelle} » : format attendu T3_2026."
        return None


@dataclass
class Entier(Param):
    mini: int | None = None
    maxi: int | None = None

    def __post_init__(self):
        self.type = "entier"

    def convertir(self, valeur):
        try:
            return int(str(valeur).strip())
        except (TypeError, ValueError):
            return None

    def verifier(self, valeur):
        v = self.convertir(valeur)
        if v is None:
            return f"« {self.libelle} » doit être un nombre entier."
        if self.mini is not None and v < self.mini or self.maxi is not None and v > self.maxi:
            return f"« {self.libelle} » doit être compris entre {self.mini} et {self.maxi}."
        return None


@dataclass
class Reel(Param):
    mini: float | None = None

    def __post_init__(self):
        self.type = "reel"

    def convertir(self, valeur):
        try:
            return float(str(valeur).replace(",", ".").strip())
        except (TypeError, ValueError):
            return None

    def verifier(self, valeur):
        v = self.convertir(valeur)
        if v is None:
            return f"« {self.libelle} » doit être un nombre."
        if self.mini is not None and v < self.mini:
            return f"« {self.libelle} » doit être supérieur ou égal à {self.mini}."
        return None


@dataclass
class Booleen(Param):
    def __post_init__(self):
        self.type = "booleen"
        self.obligatoire = False

    def convertir(self, valeur):
        return bool(valeur)


@dataclass
class Choix(Param):
    options: list = field(default_factory=list)

    def __post_init__(self):
        self.type = "choix"


@dataclass
class Dossier(Param):
    doit_exister: bool = True

    def __post_init__(self):
        self.type = "dossier"

    def verifier(self, valeur):
        e = super().verifier(valeur)
        if e:
            return e
        if valeur and self.doit_exister and not Path(valeur).is_dir():
            return f"« {self.libelle} » : dossier introuvable ({valeur})."
        return None


@dataclass
class Fichier(Param):
    types: list = field(default_factory=lambda: [("Tous les fichiers", "*.*")])
    sauvegarde: bool = False

    def __post_init__(self):
        self.type = "fichier"

    def verifier(self, valeur):
        e = super().verifier(valeur)
        if e:
            return e
        if valeur and not self.sauvegarde and not Path(valeur).is_file():
            return f"« {self.libelle} » : fichier introuvable ({valeur})."
        return None


@dataclass
class Versions(Param):
    """Liste de dossiers (une version de base par dossier), 1 à ``maxi``."""
    maxi: int = 7
    fichier_attendu: str = ""   # indicatif, pour l'aide et la détection

    def __post_init__(self):
        self.type = "versions"
        if self.defaut is None:
            self.defaut = [""]

    def convertir(self, valeur):
        return [v for v in (valeur or []) if str(v).strip()]

    def verifier(self, valeur):
        v = self.convertir(valeur)
        if self.obligatoire and not v:
            return f"« {self.libelle} » : indiquez au moins un dossier."
        for d in v:
            if not Path(d).is_dir():
                return f"« {self.libelle} » : dossier introuvable ({d})."
        return None


@dataclass
class DateP(Param):
    def __post_init__(self):
        self.type = "date"

    def convertir(self, valeur):
        if isinstance(valeur, dt.date):
            return valeur
        if not valeur:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return dt.datetime.strptime(str(valeur).strip(), fmt).date()
            except ValueError:
                pass
        return None

    def verifier(self, valeur):
        if not valeur and not self.obligatoire:
            return None
        if self.convertir(valeur) is None:
            return f"« {self.libelle} » : date invalide (format JJ/MM/AAAA)."
        return None


@dataclass
class Liste(Param):
    """Liste de mots saisie sur une ligne (séparés par des espaces ou des virgules)."""

    def __post_init__(self):
        self.type = "liste"

    def convertir(self, valeur):
        if isinstance(valeur, list):
            return valeur
        return [x for x in str(valeur or "").replace(",", " ").split() if x]


@dataclass
class Colonne:
    cle: str
    libelle: str
    type: str = "texte"          # texte | entier | dossier | fichier
    largeur: int = 14


@dataclass
class Tableau(Param):
    colonnes: list = field(default_factory=list)
    maxi_lignes: int = 10

    def __post_init__(self):
        self.type = "tableau"
        if self.defaut is None:
            self.defaut = []

    def convertir(self, valeur):
        lignes = []
        for ligne in valeur or []:
            if not any(str(ligne.get(c.cle, "")).strip() for c in self.colonnes):
                continue
            nl = {}
            for c in self.colonnes:
                v = ligne.get(c.cle, "")
                if c.type == "entier":
                    try:
                        v = int(str(v).strip())
                    except ValueError:
                        v = None
                nl[c.cle] = v
            lignes.append(nl)
        return lignes

    def verifier(self, valeur):
        lignes = self.convertir(valeur)
        if self.obligatoire and not lignes:
            return f"« {self.libelle} » : ajoutez au moins une ligne."
        for i, l in enumerate(lignes, 1):
            for c in self.colonnes:
                v = l.get(c.cle)
                if c.type == "entier" and v is None:
                    return f"« {self.libelle} », ligne {i} : « {c.libelle} » doit être un entier."
                if c.type == "dossier" and v and not Path(v).is_dir():
                    return f"« {self.libelle} », ligne {i} : dossier introuvable ({v})."
        return None


def valider(params: list[Param], valeurs: dict) -> tuple[dict, list[str]]:
    """Retourne (valeurs converties, erreurs)."""
    erreurs, propres = [], {}
    for p in params:
        v = valeurs.get(p.cle, p.defaut)
        e = p.verifier(v)
        if e:
            erreurs.append(e)
        propres[p.cle] = p.convertir(v)
    return propres, erreurs
