"""Charte graphique ANSTAT : orange, vert et blanc."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

VERT = "#4A675A"
VERT_FONCE = "#36503F"
VERT_CLAIR = "#DCEFE3"
ORANGE = "#F39422"
ORANGE_FONCE = "#D97A0B"
ORANGE_CLAIR = "#FDEBD3"
BLANC = "#FFFFFF"
FOND = "#F6F7F5"
GRIS = "#6B6B6B"
GRIS_CLAIR = "#E4E7E3"
ROUGE = "#C0392B"
ROUGE_CLAIR = "#F8D7DA"
TEXTE = "#1F2A24"

COULEURS_LIGNES = {"ROUGE": ROUGE_CLAIR, "VERT": VERT_CLAIR, "ORANGE": ORANGE_CLAIR}
COULEURS_GRAPHIQUES = [VERT, ORANGE, "#1F6F8B", "#9C5A1E", "#8A9A3B", "#C0661A", "#3E8E7E"]

POLICE = "Segoe UI" if sys.platform.startswith("win") else "DejaVu Sans"


def appliquer(racine: tk.Tk):
    racine.configure(bg=FOND)
    familles = set(tkfont.families(racine))
    police = POLICE if POLICE in familles else "TkDefaultFont"
    for nom in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(nom).configure(family=police, size=10)
        except tk.TclError:
            pass
    style = ttk.Style(racine)
    try:
        style.theme_use("clam")  # thème qui respecte les couleurs personnalisées
    except tk.TclError:
        pass
    style.configure(".", font=(police, 10), background=FOND, foreground=TEXTE)
    style.configure("TFrame", background=FOND)
    style.configure("Carte.TFrame", background=BLANC, relief="flat")
    style.configure("TLabel", background=FOND, foreground=TEXTE)
    style.configure("Carte.TLabel", background=BLANC)
    style.configure("Aide.TLabel", background=FOND, foreground=GRIS, font=(police, 8))
    style.configure("AideCarte.TLabel", background=BLANC, foreground=GRIS, font=(police, 8))
    style.configure("Titre.TLabel", font=(police, 16, "bold"), foreground=VERT, background=FOND)
    style.configure("SousTitre.TLabel", font=(police, 11, "bold"), foreground=VERT_FONCE, background=FOND)
    style.configure("TLabelframe", background=FOND)
    style.configure("TLabelframe.Label", font=(police, 10, "bold"), foreground=VERT, background=FOND)
    style.configure("TCheckbutton", background=FOND)
    style.configure("Treeview", rowheight=24, font=(police, 9), fieldbackground=BLANC, background=BLANC)
    style.configure("Treeview.Heading", font=(police, 9, "bold"), background=VERT, foreground=BLANC)
    style.map("Treeview", background=[("selected", ORANGE)], foreground=[("selected", BLANC)])
    style.configure("TNotebook.Tab", padding=(12, 5), font=(police, 10))
    style.configure("Orange.Horizontal.TProgressbar", background=ORANGE)
    return police


class Bouton(tk.Button):
    """Bouton plat aux couleurs ANSTAT."""

    STYLES = {
        "principal": (ORANGE, BLANC, ORANGE_FONCE),
        "secondaire": (VERT, BLANC, VERT_FONCE),
        "neutre": (GRIS_CLAIR, TEXTE, "#CDD2CC"),
        "danger": (ROUGE, BLANC, "#992D22"),
    }

    def __init__(self, parent, texte, commande=None, style="principal", **kw):
        fond, avant, survol = self.STYLES[style]
        super().__init__(parent, text=texte, command=commande, bg=fond, fg=avant, activebackground=survol,
                         activeforeground=avant, relief="flat", bd=0, padx=kw.pop("padx", 14),
                         pady=kw.pop("pady", 6), cursor="hand2", disabledforeground="#EEEEEE", **kw)
        self._fond, self._survol = fond, survol
        self.bind("<Enter>", lambda e: self["state"] != "disabled" and self.configure(bg=self._survol))
        self.bind("<Leave>", lambda e: self["state"] != "disabled" and self.configure(bg=self._fond))

    def activer(self, actif: bool):
        self.configure(state="normal" if actif else "disabled", bg=self._fond if actif else "#B9BFB9")


class InfoBulle:
    def __init__(self, widget, texte: str):
        self.widget, self.texte, self.fenetre = widget, texte, None
        widget.bind("<Enter>", self.afficher, add="+")
        widget.bind("<Leave>", self.masquer, add="+")

    def afficher(self, _=None):
        if not self.texte or self.fenetre:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.fenetre = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.texte, bg="#FFFDE7", fg=TEXTE, relief="solid", bd=1, wraplength=420,
                 justify="left", padx=6, pady=4).pack()

    def masquer(self, _=None):
        if self.fenetre:
            self.fenetre.destroy()
            self.fenetre = None


def eclaircir(couleur: str, facteur: float = 0.85) -> str:
    c = couleur.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(v + (255 - v) * facteur) for v in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def ouvrir(chemin):
    """Ouvre un fichier ou un dossier avec l'application par défaut du système."""
    chemin = str(chemin)
    if sys.platform.startswith("win"):
        os.startfile(chemin)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", chemin])
    else:
        subprocess.Popen(["xdg-open", chemin])
