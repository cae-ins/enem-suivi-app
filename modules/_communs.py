"""Paramètres et traitements partagés entre modules."""

from __future__ import annotations

import pandas as pd

from enem_core import donnees as D
from enem_core.parametres import Colonne, Dossier, Tableau, Texte, TrimestreP, Versions
from enem_core.trimestre import Trimestre

G_BASES = "Bases de données"
G_SORTIE = "Sortie"
G_GENERAL = "Général"


def p_trimestre():
    return TrimestreP("trimestre", "Trimestre en cours", "T3_2026", groupe=G_GENERAL, globale="trimestre",
                      aide="Format T3_2026. Sert aux noms de fichiers et aux libellés.")


def p_versions_menage(libelle="Dossiers des versions de la base ménage / individuelle"):
    return Versions("versions_menage", libelle, groupe=G_BASES, globale="versions_menage",
                    fichier_attendu="ENEM_AAAATq.dta, membres.dta",
                    aide="Un dossier par version téléchargée (ex. ENEM_2026T3_1_STATA_All, _2_, _3_). "
                         "Les versions sont empilées (append). Si les versions ont déjà été fusionnées, "
                         "indiquez un seul dossier.")


def p_fichier_menage():
    return Texte("fichier_menage", "Nom du fichier ménage (vide = automatique)", "", groupe=G_BASES,
                 obligatoire=False, aide="Par défaut : ENEM_AAAATq.dta déduit du trimestre (ex. ENEM_2026T3.dta).")


def p_sortie():
    return Dossier("dossier_sortie", "Dossier racine des résultats", "", groupe=G_SORTIE, globale="dossier_sortie",
                   doit_exister=False,
                   aide="Un sous-dossier daté est créé à chaque exécution : <racine>/<trimestre>/<équipe>/<module>/<date>.")


def p_cohortes(cle="cohortes", avec_dossier=True, libelle="Cohortes de réinterrogation"):
    cols = [Colonne("libelle", "Trimestre d'origine (ex. T2-2025)", "texte", 16),
            Colonne("rgmen", "Valeur rgmen / Cohorte_vrai", "entier", 8)]
    if avec_dossier:
        cols.append(Colonne("dossier", "Dossier des bases de ce trimestre", "dossier", 40))
    return Tableau(cle, libelle, [], groupe="Cohortes", globale="cohortes", colonnes=cols,
                   aide="Saisissez chaque trimestre en réinterrogation, la valeur de rgmen qui lui correspond "
                        "dans la base du trimestre en cours et le dossier contenant ses bases (passage 1).")


def nom_fichier_menage(p: dict) -> str:
    f = (p.get("fichier_menage") or "").strip()
    if f:
        return f if f.lower().endswith(".dta") else f + ".dta"
    return Trimestre.depuis(p["trimestre"]).fichier_menage


def charger_menage(ctx, p, colonnes=None) -> pd.DataFrame:
    ctx.journal(f"Lecture de {nom_fichier_menage(p)}")
    return D.lire_versions(p["versions_menage"], nom_fichier_menage(p), colonnes, journal=ctx.journal)


def charger_membres(ctx, p, colonnes=None) -> pd.DataFrame:
    ctx.journal("Lecture de membres.dta")
    return D.lire_versions(p["versions_menage"], "membres.dta", colonnes, journal=ctx.journal)


def charger_individus(ctx, p, garder_membres=None) -> pd.DataFrame:
    men = charger_menage(ctx, p)
    ctx.verifier_arret()
    mem = charger_membres(ctx, p)
    ind = D.fusion_menage_membres(men, mem, garder_membres)
    ctx.journal(f"  Fusion ménage × membres : {len(men):,} ménages → {len(ind):,} individus".replace(",", " "))
    return ind


def exiger(df: pd.DataFrame, colonnes, base="la base"):
    manq = D.verifier_colonnes(df, colonnes)
    if manq:
        raise D.ErreurDonnees(f"Variable(s) absente(s) de {base} : {', '.join(manq)}")


def colonnes_export(df: pd.DataFrame, colonnes) -> list[str]:
    return D.colonnes_presentes(df, colonnes)


def statut_residence(df: pd.DataFrame) -> pd.Series:
    """Statut_Res si présent ; sinon (M1==2 | M1A==2) | ((M1==1 | M1A==1) & M2==2)."""
    if "Statut_Res" in df.columns:
        return pd.to_numeric(df["Statut_Res"], errors="coerce") == 1
    if all(c in df.columns for c in ("M1", "M1A", "M2")):
        m1, m1a, m2 = (pd.to_numeric(df[c], errors="coerce") for c in ("M1", "M1A", "M2"))
        return ((m1 == 2) | (m1a == 2)) | (((m1 == 1) | (m1a == 1)) & (m2 == 2))
    raise D.ErreurDonnees("Ni Statut_Res ni M1/M1A/M2 ne sont présents : impossible de filtrer les résidents.")


def num(df, col):
    return pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(float("nan"), index=df.index)
