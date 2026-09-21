"""Manipulation des codes de trimestre (ex. « T3_2026 »)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MOTIF = re.compile(r"^\s*T\s*([1-4])\s*[-_ ]?\s*(\d{4})\s*$", re.IGNORECASE)
_MOTIF_INVERSE = re.compile(r"^\s*(\d{4})\s*[-_ ]?\s*T\s*([1-4])\s*$", re.IGNORECASE)


@dataclass(frozen=True, order=True)
class Trimestre:
    annee: int
    numero: int

    @classmethod
    def depuis(cls, texte: "str | Trimestre") -> "Trimestre":
        """Accepte T3_2026, T3-2026, T32026, 2026T3, 2026-T3."""
        if isinstance(texte, Trimestre):
            return texte
        t = str(texte).strip()
        m = _MOTIF.match(t)
        if m:
            return cls(int(m.group(2)), int(m.group(1)))
        m = _MOTIF_INVERSE.match(t)
        if m:
            return cls(int(m.group(1)), int(m.group(2)))
        raise ValueError(f"Code de trimestre non reconnu : « {texte} » (format attendu : T3_2026)")

    # --- représentations -------------------------------------------------
    @property
    def code(self) -> str:          # T3_2026
        return f"T{self.numero}_{self.annee}"

    @property
    def libelle(self) -> str:       # T3-2026
        return f"T{self.numero}-{self.annee}"

    @property
    def code_porte(self) -> str:    # T32026 (numéro de porte)
        return f"T{self.numero}{self.annee}"

    @property
    def nom_base(self) -> str:      # ENEM_2026T3
        return f"ENEM_{self.annee}T{self.numero}"

    @property
    def fichier_menage(self) -> str:
        return f"{self.nom_base}.dta"

    @property
    def fichier_denombrement(self) -> str:
        return f"{self.nom_base}_DenomVF.dta"

    def __str__(self) -> str:
        return self.code

    # --- arithmétique ----------------------------------------------------
    def decale(self, n: int) -> "Trimestre":
        idx = self.annee * 4 + (self.numero - 1) + n
        return Trimestre(idx // 4, idx % 4 + 1)


def valide(texte: str) -> bool:
    try:
        Trimestre.depuis(texte)
        return True
    except ValueError:
        return False


def cohortes_suggerees(trimestre: str) -> list[dict]:
    """Pré-remplissage indicatif (règle 2-(2)-2). L'utilisateur valide toujours."""
    t = Trimestre.depuis(trimestre)
    return [
        {"libelle": t.libelle, "rgmen": 1, "passage": 1},
        {"libelle": t.decale(-1).libelle, "rgmen": 2, "passage": 2},
        {"libelle": t.decale(-4).libelle, "rgmen": 3, "passage": 3},
        {"libelle": t.decale(-5).libelle, "rgmen": 4, "passage": 4},
    ]
