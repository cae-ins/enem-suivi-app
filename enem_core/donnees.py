"""Lecture des bases Stata (.dta), empilement des versions, fusions et libellés.

Les métadonnées Stata (libellés de variables et de modalités) sont conservées dans
``df.attrs["libelles_variables"]`` et ``df.attrs["libelles_valeurs"]``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

try:  # lecture plus rapide si disponible
    import pyreadstat  # type: ignore
except Exception:  # pragma: no cover
    pyreadstat = None

LV = "libelles_valeurs"      # {variable: {code: libellé}}
LVAR = "libelles_variables"  # {variable: libellé}


class ErreurDonnees(Exception):
    """Erreur lisible par l'utilisateur (fichier absent, variable manquante...)."""


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------
def lire_dta(chemin: str | Path, colonnes: Iterable[str] | None = None) -> pd.DataFrame:
    chemin = Path(chemin)
    if not chemin.exists():
        raise ErreurDonnees(f"Fichier introuvable : {chemin}")
    cols = list(colonnes) if colonnes else None
    if cols:
        dispo = set(colonnes_dta(chemin))
        cols = [c for c in cols if c in dispo]
    if pyreadstat is not None:
        df, meta = pyreadstat.read_dta(str(chemin), usecols=cols, apply_value_formats=False)
        vv = {}
        for var, nom in (meta.variable_to_label or {}).items():
            if nom in (meta.value_labels or {}):
                vv[var] = dict(meta.value_labels[nom])
        df.attrs[LV] = vv
        df.attrs[LVAR] = {k: v for k, v in zip(meta.column_names, meta.column_labels) if v}
    else:
        with pd.io.stata.StataReader(chemin) as lecteur:
            df = lecteur.read(convert_categoricals=False, columns=cols)
            etiquettes = lecteur.value_labels()
            liste = getattr(lecteur, "_lbllist", [])
            noms = getattr(lecteur, "_varlist", list(df.columns))
            vv = {}
            for var, nom in zip(noms, liste):
                if nom and nom in etiquettes and var in df.columns:
                    vv[var] = dict(etiquettes[nom])
            df.attrs[LV] = vv
            df.attrs[LVAR] = {k: v for k, v in lecteur.variable_labels().items() if v}
    df.attrs["source"] = str(chemin)
    return _normaliser(df)


def colonnes_dta(chemin: str | Path) -> list[str]:
    if pyreadstat is not None:
        _, meta = pyreadstat.read_dta(str(chemin), metadataonly=True)
        return list(meta.column_names)
    with pd.io.stata.StataReader(chemin) as lecteur:
        return list(lecteur.variable_labels().keys())


def _normaliser(df: pd.DataFrame) -> pd.DataFrame:
    """Chaînes : on remplace les valeurs nulles par "" (comme Stata)."""
    for c in df.columns:
        if pd.api.types.is_string_dtype(df[c]) or df[c].dtype == object:
            non_nuls = df[c].dropna()
            if non_nuls.empty or isinstance(non_nuls.iloc[0], str):
                df[c] = df[c].fillna("").astype(str).astype(object)
    return df


def lire_versions(dossiers: Iterable[str | Path], fichier: str,
                  colonnes: Iterable[str] | None = None, obligatoire: bool = True,
                  journal=None) -> pd.DataFrame:
    """Lit ``fichier`` dans chaque dossier de version et empile (append)."""
    dossiers = [Path(d) for d in dossiers if str(d).strip()]
    if not dossiers:
        raise ErreurDonnees("Aucun dossier de base n'a été renseigné.")
    morceaux = []
    for d in dossiers:
        chemin = d / fichier
        if not chemin.exists():
            if obligatoire:
                raise ErreurDonnees(f"Fichier « {fichier} » introuvable dans {d}")
            if journal:
                journal(f"  (absent) {chemin}")
            continue
        df = lire_dta(chemin, colonnes)
        if journal:
            journal(f"  - {chemin.name} [{d.name}] : {len(df):,} lignes".replace(",", " "))
        morceaux.append(df)
    if not morceaux:
        if obligatoire:
            raise ErreurDonnees(f"Aucune version de « {fichier} » n'a été trouvée.")
        return pd.DataFrame()
    return empiler(morceaux)


def empiler(morceaux: list[pd.DataFrame]) -> pd.DataFrame:
    if len(morceaux) == 1:
        return morceaux[0]
    res = pd.concat(morceaux, ignore_index=True, sort=False)
    res.attrs = fusion_attrs(*morceaux)
    for c in res.columns:  # chaînes absentes d'une version -> ""
        if any(c in m.columns and m[c].dtype == object for m in morceaux) and res[c].dtype == object:  # noqa
            res[c] = res[c].fillna("")
    return res


def fusion_attrs(*dfs: pd.DataFrame) -> dict:
    lv, lvar = {}, {}
    for d in dfs:
        for k, v in d.attrs.get(LV, {}).items():
            lv.setdefault(k, {}).update(v)
        for k, v in d.attrs.get(LVAR, {}).items():
            lvar.setdefault(k, v)
    return {LV: lv, LVAR: lvar}


def fusionner(maitre: pd.DataFrame, utilisant: pd.DataFrame, cles: list[str],
              garder: Iterable[str] | None = None, how: str = "inner") -> pd.DataFrame:
    """Équivalent de ``merge ... keepusing()`` + ``keep if _merge==3``.

    Comme dans Stata, en cas de variable présente dans les deux bases, la valeur
    de la base maître est conservée.
    """
    manquantes = [c for c in cles if c not in maitre.columns or c not in utilisant.columns]
    if manquantes:
        raise ErreurDonnees(f"Clé(s) de fusion absente(s) : {', '.join(manquantes)}")
    cols = list(garder) if garder is not None else list(utilisant.columns)
    cols = [c for c in cols if c in utilisant.columns and c not in maitre.columns and c not in cles]
    droite = utilisant[cles + cols]
    res = maitre.merge(droite, on=cles, how=how)
    res.attrs = fusion_attrs(maitre, utilisant)
    return res


def fusion_menage_membres(menage: pd.DataFrame, membres: pd.DataFrame,
                          garder: Iterable[str] | None = None) -> pd.DataFrame:
    return fusionner(menage, membres, ["interview__key"], garder)


# ---------------------------------------------------------------------------
# Libellés
# ---------------------------------------------------------------------------
def libelle_valeur(df: pd.DataFrame, var: str, valeur):
    lab = df.attrs.get(LV, {}).get(var, {})
    try:
        if valeur is None or (isinstance(valeur, float) and np.isnan(valeur)):
            return ""
        cle = int(valeur) if float(valeur).is_integer() else valeur
    except (TypeError, ValueError):
        return valeur
    return lab.get(cle, lab.get(float(cle), valeur))


def appliquer_libelles(df: pd.DataFrame, colonnes: Iterable[str] | None = None,
                       source: pd.DataFrame | None = None) -> pd.DataFrame:
    """Remplace les codes par leurs libellés (comme ``export excel`` de Stata)."""
    src = source if source is not None else df
    lv = src.attrs.get(LV, {})
    res = df.copy()
    for c in (colonnes or res.columns):
        if c in res.columns and c in lv and pd.api.types.is_numeric_dtype(res[c]):
            carte = {}
            for k, v in lv[c].items():
                carte[float(k)] = v
            res[c] = res[c].map(lambda x: carte.get(float(x), x) if pd.notna(x) else x)
    res.attrs = dict(df.attrs)
    return res


def ajouter_libelle(df: pd.DataFrame, var: str, nouvelle: str | None = None,
                    source: pd.DataFrame | None = None) -> pd.DataFrame:
    """Ajoute une colonne ``<var>_lib`` avec le libellé de la modalité."""
    src = source if source is not None else df
    nouvelle = nouvelle or f"{var}_lib"
    if var in df.columns:
        df[nouvelle] = df[var].map(lambda v: libelle_valeur(src, var, v))
    return df


def entetes_libelles(df: pd.DataFrame, source: pd.DataFrame | None = None) -> pd.DataFrame:
    """Renomme les colonnes avec leur libellé de variable (firstrow(varlabels))."""
    lvar = (source if source is not None else df).attrs.get(LVAR, {})
    vus, noms = set(), []
    for c in df.columns:
        n = lvar.get(c) or c
        if n in vus:
            n = f"{n} ({c})"
        vus.add(n)
        noms.append(n)
    res = df.copy()
    res.columns = noms
    return res


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
def verifier_colonnes(df: pd.DataFrame, colonnes: Iterable[str], contexte: str = "") -> list[str]:
    return [c for c in colonnes if c not in df.columns]


def colonnes_presentes(df: pd.DataFrame, colonnes: Iterable[str]) -> list[str]:
    return [c for c in colonnes if c in df.columns]


def manquant(serie: pd.Series) -> pd.Series:
    """Valeur manquante au sens de Stata (numérique : NaN ; chaîne : "")."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie.isna()
    return serie.isna() | (serie.astype(str).str.strip() == "")


def en_numerique(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce")


def sauver_dta(df: pd.DataFrame, chemin: str | Path) -> None:
    """Sauvegarde .dta en conservant, autant que possible, les libellés."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    d = df.copy()
    strl = []
    for c in d.columns:
        if d[c].dtype == object or pd.api.types.is_string_dtype(d[c]):
            d[c] = d[c].fillna("").astype(str).astype(object)
            longueur = d[c].map(len).max() if len(d) else 0
            if longueur > 2000:
                strl.append(c)
        elif pd.api.types.is_bool_dtype(d[c]):
            d[c] = d[c].astype("int8")
    lv = {}
    for k, v in df.attrs.get(LV, {}).items():
        if k in d.columns and pd.api.types.is_numeric_dtype(d[k]):
            try:
                vals = d[k].dropna()
                if len(vals) and not (vals == vals.round()).all():
                    continue
                lv[k] = {int(a): str(b)[:32000] for a, b in v.items()}
            except Exception:
                pass
    lvar = {k: str(v)[:80] for k, v in df.attrs.get(LVAR, {}).items() if k in d.columns}
    d.attrs = {}
    try:
        d.to_stata(chemin, write_index=False, version=118, value_labels=lv or None,
                   variable_labels=lvar or None, convert_strl=strl or None)
    except Exception:
        d.to_stata(chemin, write_index=False, version=118, convert_strl=strl or None)
