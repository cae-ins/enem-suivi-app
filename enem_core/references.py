"""Lecture des fichiers de référence (Semaine_ref.xlsx, information_agent.xlsx)."""

from __future__ import annotations

import datetime as dt
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .donnees import ErreurDonnees
from .trimestre import Trimestre


def normaliser_nom(texte) -> str:
    """Majuscules, sans accents ni espaces superflus (GÔH -> GOH)."""
    t = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode()
    return " ".join(t.replace("\t", " ").upper().split())


def _fichier(chemin) -> Path:
    p = Path(chemin or "")
    if not p.is_file():
        raise ErreurDonnees(f"Fichier de référence introuvable : {chemin}")
    return p


@lru_cache(maxsize=16)
def _feuille(chemin: str, feuille: str, mtime: float) -> pd.DataFrame:
    return pd.read_excel(chemin, sheet_name=feuille)


def feuille(chemin, nom: str) -> pd.DataFrame:
    p = _fichier(chemin)
    try:
        return _feuille(str(p), nom, p.stat().st_mtime).copy()
    except ValueError as e:
        raise ErreurDonnees(f"Feuille « {nom} » absente de {p.name}") from e


def libelles(chemin, feuille_nom: str, code: str, libelle: str) -> dict:
    df = feuille(chemin, feuille_nom)
    df = df.dropna(subset=[code])
    res = {}
    for c, l in zip(df[code], df[libelle]):
        try:
            c = int(float(c))
        except (TypeError, ValueError):
            pass
        res[c] = " ".join(str(l).replace("\t", " ").split())
    return res


def regions(chemin) -> dict:
    """{code HH2: nom de région} (33 régions, feuille label_region)."""
    return libelles(chemin, "label_region", "HH2", "label_HH2")


def calendrier_zd(chemin, trimestre: str) -> pd.DataFrame:
    """Feuille Automate_envoie filtrée : REGION, Ordre_passage_zd, debut, fin (dates)."""
    t = Trimestre.depuis(trimestre)
    df = feuille(chemin, "Automate_envoie")
    df = df[df["Trimestre"].astype(str).str.strip().str.upper() == t.code.upper()].copy()
    if df.empty:
        return df
    df["debut"] = pd.to_datetime(df["Date_debut_sem_ref"], errors="coerce").dt.date
    df["fin"] = pd.to_datetime(df["Date_fin_sem_ref"], errors="coerce").dt.date
    df["REGION"] = df["REGION"].map(normaliser_nom)
    return df.dropna(subset=["debut"]).sort_values(["REGION", "Ordre_passage_zd"])


def premier_lundi(chemin, trimestre: str) -> dt.date | None:
    try:
        cal = calendrier_zd(chemin, trimestre)
    except ErreurDonnees:
        return None
    return None if cal.empty else min(cal["debut"])


def equipes(chemin) -> tuple[pd.DataFrame, pd.DataFrame]:
    res = []
    for nom in ("Equipe_teleoperateur", "Equipe_terrain"):
        d = feuille(chemin, nom)
        if "responsible" not in d.columns:
            raise ErreurDonnees(f"Colonne « responsible » absente de la feuille {nom}")
        d = d.dropna(subset=["responsible"])
        for c in d.columns:
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else str(v).strip()).astype(object)
        res.append(d[d["responsible"] != ""])
    return res[0], res[1]
