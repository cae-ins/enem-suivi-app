"""Composants réutilisables : défilement, calendrier, sélecteurs, grille type Excel, graphiques."""

from __future__ import annotations

import calendar
import datetime as dt
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pandas as pd

from . import theme as T

MOIS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre",
           "Octobre", "Novembre", "Décembre"]


# ---------------------------------------------------------------------------
class Defilant(ttk.Frame):
    """Cadre à défilement vertical (molette active au survol)."""

    def __init__(self, parent, fond=T.FOND, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, bg=fond, highlightthickness=0, bd=0)
        self.barre = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.interieur = tk.Frame(self.canvas, bg=fond)
        self._id = self.canvas.create_window((0, 0), window=self.interieur, anchor="nw")
        self.canvas.configure(yscrollcommand=self.barre.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.barre.pack(side="right", fill="y")
        self.interieur.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._id, width=e.width))
        self.bind_all_molette()

    def bind_all_molette(self):
        def dedans(_):
            self.canvas.bind_all("<MouseWheel>", self._molette)
            self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
            self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))

        def dehors(_):
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        self.canvas.bind("<Enter>", dedans)
        self.canvas.bind("<Leave>", dehors)

    def _molette(self, e):
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")

    def haut(self):
        self.canvas.yview_moveto(0)


# ---------------------------------------------------------------------------
class Calendrier(tk.Toplevel):
    """Mini-calendrier cliquable (lundi en premier)."""

    def __init__(self, parent, date_initiale: dt.date | None, rappel):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=T.VERT, padx=1, pady=1)
        self.rappel = rappel
        self.courant = date_initiale or dt.date.today()
        self.selection = date_initiale
        self.cadre = tk.Frame(self, bg=T.BLANC)
        self.cadre.pack()
        self._dessiner()
        x, y = parent.winfo_rootx(), parent.winfo_rooty() + parent.winfo_height()
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(50, self._saisir)

    def _saisir(self):
        try:
            self.grab_set()
            self.focus_set()
        except tk.TclError:
            pass
        self.bind("<FocusOut>", lambda e: None)

    def _dessiner(self):
        for w in self.cadre.winfo_children():
            w.destroy()
        entete = tk.Frame(self.cadre, bg=T.VERT)
        entete.grid(row=0, column=0, columnspan=7, sticky="ew")
        tk.Button(entete, text="◀", command=lambda: self._decaler(-1), bg=T.VERT, fg=T.BLANC, relief="flat",
                  bd=0, activebackground=T.ORANGE).pack(side="left", padx=4)
        tk.Label(entete, text=f"{MOIS_FR[self.courant.month - 1]} {self.courant.year}", bg=T.VERT, fg=T.BLANC,
                 font=(T.POLICE, 10, "bold"), width=16).pack(side="left", expand=True)
        tk.Button(entete, text="▶", command=lambda: self._decaler(1), bg=T.VERT, fg=T.BLANC, relief="flat",
                  bd=0, activebackground=T.ORANGE).pack(side="right", padx=4)
        for j, nom in enumerate(["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"]):
            tk.Label(self.cadre, text=nom, bg=T.BLANC, fg=T.GRIS, width=4).grid(row=1, column=j)
        for i, semaine in enumerate(calendar.Calendar(0).monthdatescalendar(self.courant.year, self.courant.month)):
            for j, jour in enumerate(semaine):
                autre = jour.month != self.courant.month
                choisi = jour == self.selection
                fond = T.ORANGE if choisi else (T.ORANGE_CLAIR if jour == dt.date.today() else T.BLANC)
                b = tk.Button(self.cadre, text=str(jour.day), width=3, relief="flat", bd=0, bg=fond,
                              fg="#AAAAAA" if autre else (T.BLANC if choisi else T.TEXTE),
                              activebackground=T.VERT_CLAIR, command=lambda d=jour: self._choisir(d))
                b.grid(row=i + 2, column=j, padx=1, pady=1)
        pied = tk.Frame(self.cadre, bg=T.BLANC)
        pied.grid(row=9, column=0, columnspan=7, sticky="ew", pady=3)
        tk.Button(pied, text="Aujourd'hui", relief="flat", bg=T.GRIS_CLAIR,
                  command=lambda: self._choisir(dt.date.today())).pack(side="left", padx=4)
        tk.Button(pied, text="Fermer", relief="flat", bg=T.GRIS_CLAIR, command=self.destroy).pack(side="right", padx=4)

    def _decaler(self, n):
        m = self.courant.month - 1 + n
        self.courant = dt.date(self.courant.year + m // 12, m % 12 + 1, 1)
        self._dessiner()

    def _choisir(self, d):
        self.rappel(d)
        self.destroy()


class ChampDate(ttk.Frame):
    def __init__(self, parent, valeur="", largeur=12):
        super().__init__(parent)
        self.var = tk.StringVar(value=self._texte(valeur))
        self.entree = ttk.Entry(self, textvariable=self.var, width=largeur)
        self.entree.pack(side="left")
        b = T.Bouton(self, "📅", self._ouvrir, style="secondaire", padx=6, pady=1)
        b.pack(side="left", padx=(3, 0))
        T.InfoBulle(b, "Choisir la date dans le calendrier")

    @staticmethod
    def _texte(v):
        if isinstance(v, (dt.date, dt.datetime)):
            return v.strftime("%d/%m/%Y")
        return str(v or "")

    def _ouvrir(self):
        Calendrier(self.entree, self.date(), lambda d: self.var.set(d.strftime("%d/%m/%Y")))

    def date(self):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return dt.datetime.strptime(self.var.get().strip(), fmt).date()
            except ValueError:
                pass
        return None

    def get(self):
        return self.var.get().strip()

    def set(self, v):
        self.var.set(self._texte(v))


class ChampChemin(ttk.Frame):
    def __init__(self, parent, valeur="", mode="dossier", types=None, largeur=60, sauvegarde=False):
        super().__init__(parent)
        self.mode, self.types, self.sauvegarde = mode, types, sauvegarde
        self.var = tk.StringVar(value=valeur or "")
        ttk.Entry(self, textvariable=self.var, width=largeur).pack(side="left", fill="x", expand=True)
        T.Bouton(self, "Parcourir…", self._choisir, style="neutre", padx=8, pady=1).pack(side="left", padx=(4, 0))
        b = T.Bouton(self, "📂", self._ouvrir, style="neutre", padx=6, pady=1)
        b.pack(side="left", padx=(2, 0))
        T.InfoBulle(b, "Ouvrir dans l'explorateur")

    def _choisir(self):
        init = self.var.get() or str(Path.home())
        if self.mode == "dossier":
            v = filedialog.askdirectory(initialdir=init if Path(init).is_dir() else None, mustexist=False)
        elif self.sauvegarde:
            v = filedialog.asksaveasfilename(filetypes=self.types or [("Tous", "*.*")])
        else:
            v = filedialog.askopenfilename(initialdir=str(Path(init).parent) if init else None,
                                           filetypes=self.types or [("Tous", "*.*")])
        if v:
            self.var.set(str(Path(v)))

    def _ouvrir(self):
        p = Path(self.var.get())
        cible = p if p.exists() else p.parent
        if cible.exists():
            T.ouvrir(cible if cible.is_dir() else cible.parent)
        else:
            messagebox.showinfo("Chemin", "Ce chemin n'existe pas encore.")

    def get(self):
        return self.var.get().strip()

    def set(self, v):
        self.var.set(v or "")


class ChampVersions(ttk.Frame):
    """Nombre de versions (1 à maxi) + un sélecteur de dossier par version."""

    def __init__(self, parent, valeurs=None, maxi=7, fichier_attendu=""):
        super().__init__(parent)
        self.maxi, self.fichier_attendu = maxi, fichier_attendu
        haut = ttk.Frame(self)
        haut.pack(fill="x")
        ttk.Label(haut, text="Nombre de versions :").pack(side="left")
        self.nb = tk.IntVar(value=max(1, len(valeurs or [""])))
        sp = ttk.Spinbox(haut, from_=1, to=maxi, width=4, textvariable=self.nb, command=self._redessiner,
                         state="readonly")
        sp.pack(side="left", padx=4)
        T.Bouton(haut, "Détecter les versions dans un dossier…", self._detecter, style="secondaire",
                 padx=8, pady=1).pack(side="left", padx=8)
        if fichier_attendu:
            ttk.Label(haut, text=f"Fichiers attendus : {fichier_attendu}", style="Aide.TLabel").pack(side="left")
        self.zone = ttk.Frame(self)
        self.zone.pack(fill="x", pady=(3, 0))
        self.champs: list[ChampChemin] = []
        self._memo = list(valeurs or [""])
        self._redessiner()

    def _redessiner(self):
        self._memo = [c.get() for c in self.champs] + self._memo[len(self.champs):]
        for w in self.zone.winfo_children():
            w.destroy()
        self.champs = []
        for i in range(self.nb.get()):
            ligne = ttk.Frame(self.zone)
            ligne.pack(fill="x", pady=1)
            ttk.Label(ligne, text=f"Version {i + 1}", width=10).pack(side="left")
            c = ChampChemin(ligne, self._memo[i] if i < len(self._memo) else "", largeur=55)
            c.pack(side="left", fill="x", expand=True)
            self.champs.append(c)

    def _detecter(self):
        parent = filedialog.askdirectory(title="Dossier contenant les sous-dossiers de versions")
        if not parent:
            return
        sous = sorted(d for d in Path(parent).iterdir() if d.is_dir() and any(d.glob("*.dta")))
        if not sous:
            if any(Path(parent).glob("*.dta")):
                sous = [Path(parent)]
            else:
                messagebox.showwarning("Versions", "Aucun sous-dossier contenant des fichiers .dta.")
                return
        sous = sous[: self.maxi]
        self._memo = [str(s) for s in sous]
        self.champs = []
        self.nb.set(len(sous))
        self._redessiner()

    def get(self):
        return [c.get() for c in self.champs if c.get()]

    def set(self, valeurs):
        valeurs = list(valeurs or [""])
        self._memo = valeurs
        self.champs = []
        self.nb.set(max(1, min(self.maxi, len(valeurs))))
        self._redessiner()


class ChampTableau(ttk.Frame):
    """Tableau éditable (lignes ajoutables / supprimables), colonnes alignées."""

    def __init__(self, parent, colonnes, valeurs=None, maxi=10, suggestion=None):
        super().__init__(parent)
        self.colonnes, self.maxi, self.suggestion = colonnes, maxi, suggestion
        self.lignes: list[dict] = []
        self.grille = ttk.Frame(self)
        self.grille.pack(fill="x")
        for j, c in enumerate(colonnes):
            tk.Label(self.grille, text=c.libelle, bg=T.VERT, fg=T.BLANC, anchor="w", padx=4,
                     wraplength=max(90, 8 * c.largeur)).grid(row=0, column=j, sticky="nsew", padx=1)
            if c.type in ("dossier", "fichier"):
                self.grille.columnconfigure(j, weight=1)
        tk.Label(self.grille, text="", bg=T.VERT, width=4).grid(row=0, column=len(colonnes), sticky="nsew", padx=1)
        self.grille.columnconfigure(len(colonnes), minsize=42)   # place pour le bouton de suppression
        self._rang = 1
        bas = ttk.Frame(self)
        bas.pack(fill="x", pady=3)
        T.Bouton(bas, "+ Ajouter une ligne", lambda: self.ajouter({}), style="secondaire", padx=8,
                 pady=1).pack(side="left")
        if suggestion:
            T.Bouton(bas, "Pré-remplir (règle 2-(2)-2, à vérifier)", self._suggerer, style="neutre", padx=8,
                     pady=1).pack(side="left", padx=6)
        for v in valeurs or []:
            self.ajouter(v)

    def ajouter(self, valeurs):
        if len(self.lignes) >= self.maxi:
            return
        r = self._rang
        self._rang += 1
        champs, widgets = {}, []
        for j, c in enumerate(self.colonnes):
            if c.type in ("dossier", "fichier"):
                w = ChampChemin(self.grille, valeurs.get(c.cle, ""), mode=c.type, largeur=26,
                                types=[("Stata", "*.dta"), ("Tous", "*.*")] if c.type == "fichier" else None)
            else:
                w = ttk.Entry(self.grille, width=c.largeur)
                w.insert(0, "" if valeurs.get(c.cle) is None else str(valeurs.get(c.cle, "")))
            w.grid(row=r, column=j, sticky="ew", padx=1, pady=1)
            champs[c.cle] = w
            widgets.append(w)
        ligne = {"widgets": widgets, "champs": champs}
        b = tk.Button(self.grille, text="✕", fg=T.ROUGE, relief="flat", bg=T.FOND, cursor="hand2",
                      font=(T.POLICE, 10, "bold"), width=3, command=lambda l=ligne: self.supprimer(l))
        b.grid(row=r, column=len(self.colonnes), padx=(6, 2), sticky="w")
        T.InfoBulle(b, "Supprimer cette ligne")
        widgets.append(b)
        self.lignes.append(ligne)

    def supprimer(self, ligne):
        for w in ligne["widgets"]:
            w.destroy()
        self.lignes.remove(ligne)

    def _suggerer(self):
        trimestre = self.suggestion()
        if not trimestre:
            return
        from enem_core.trimestre import cohortes_suggerees
        try:
            lignes = cohortes_suggerees(trimestre)[1:]
        except ValueError as e:
            messagebox.showerror("Trimestre", str(e))
            return
        existants = self.get()
        self.set([{**l, "dossier": next((e.get("dossier", "") for e in existants if e.get("libelle") == l["libelle"]), "")}
                  for l in lignes])
        messagebox.showinfo("Cohortes", "Cohortes pré-remplies selon la règle de rotation.\n"
                                        "Vérifiez-les et supprimez celles qui ne sont pas collectées ce trimestre "
                                        "(ex. pas de passage 2 en T3_2026).")

    def get(self):
        return [{k: w.get().strip() for k, w in l["champs"].items()} for l in self.lignes]

    def set(self, valeurs):
        for l in list(self.lignes):
            self.supprimer(l)
        for v in valeurs or []:
            self.ajouter(v)


# ---------------------------------------------------------------------------
class Formulaire(ttk.Frame):
    """Formulaire généré à partir d'une liste de paramètres (enem_core.parametres)."""

    def __init__(self, parent, parametres, valeurs, trimestre_courant=None):
        super().__init__(parent)
        self.parametres = parametres
        self.widgets = {}
        groupes: dict[str, ttk.LabelFrame] = {}
        for p in parametres:
            if p.groupe not in groupes:
                lf = ttk.LabelFrame(self, text=f"  {p.groupe}  ", padding=(10, 6))
                lf.pack(fill="x", padx=4, pady=5)
                lf.columnconfigure(1, weight=1)
                groupes[p.groupe] = lf
            lf = groupes[p.groupe]
            ligne = lf.grid_size()[1]
            v = valeurs.get(p.cle, p.defaut)
            if p.type == "booleen":
                var = tk.BooleanVar(value=bool(v))
                w = ttk.Checkbutton(lf, text=p.libelle, variable=var)
                w.grid(row=ligne, column=0, columnspan=2, sticky="w", pady=2)
                w.get, w.set = var.get, var.set
                self.widgets[p.cle] = w
                if p.aide:
                    T.InfoBulle(w, p.aide)
                continue
            if getattr(p, "note", ""):
                note = tk.Label(lf, text="ℹ  " + p.note, bg=T.ORANGE_CLAIR, fg=T.TEXTE, anchor="w",
                                justify="left", wraplength=880, padx=8, pady=5,
                                font=(T.POLICE, 9, "bold"))
                note.grid(row=ligne, column=0, columnspan=2, sticky="ew", pady=(6, 4))
                ligne += 1
            lab = ttk.Label(lf, text=p.libelle + (" *" if p.obligatoire else ""))
            lab.grid(row=ligne, column=0, sticky="nw", pady=3, padx=(0, 10))
            if p.type in ("texte", "trimestre", "entier", "reel"):
                w = ttk.Entry(lf, width=18 if p.type != "texte" else 40)
                w.insert(0, "" if v is None else str(v))
                w.set = (lambda e: lambda val: (e.delete(0, "end"), e.insert(0, "" if val is None else str(val))))(w)
                w.grid(row=ligne, column=1, sticky="w", pady=3)
            elif p.type == "liste":
                w = ttk.Entry(lf, width=70)
                w.insert(0, " ".join(v) if isinstance(v, list) else str(v or ""))
                w.set = (lambda e: lambda val: (e.delete(0, "end"),
                                                e.insert(0, " ".join(val) if isinstance(val, list) else str(val or ""))))(w)
                w.grid(row=ligne, column=1, sticky="ew", pady=3)
            elif p.type == "choix":
                w = ttk.Combobox(lf, values=p.options, state="readonly", width=38)
                w.set(v if v in p.options else (p.options[0] if p.options else ""))
                w.grid(row=ligne, column=1, sticky="w", pady=3)
            elif p.type in ("dossier", "fichier"):
                w = ChampChemin(lf, v, p.type, getattr(p, "types", None), sauvegarde=getattr(p, "sauvegarde", False))
                w.grid(row=ligne, column=1, sticky="ew", pady=3)
            elif p.type == "date":
                w = ChampDate(lf, v)
                w.grid(row=ligne, column=1, sticky="w", pady=3)
            elif p.type == "versions":
                w = ChampVersions(lf, v if isinstance(v, list) else [v or ""], p.maxi, p.fichier_attendu)
                w.grid(row=ligne, column=1, sticky="ew", pady=3)
            elif p.type == "tableau":
                sugg = (lambda: self.valeur("trimestre")) if p.cle == "cohortes" else None
                w = ChampTableau(lf, p.colonnes, v, p.maxi_lignes, suggestion=sugg)
                w.grid(row=ligne, column=1, sticky="ew", pady=3)
            else:
                w = ttk.Entry(lf, width=40)
                w.insert(0, str(v or ""))
                w.grid(row=ligne, column=1, sticky="w")
            self.widgets[p.cle] = w
            if p.aide:
                ttk.Label(lf, text=p.aide, style="Aide.TLabel", wraplength=620, justify="left").grid(
                    row=ligne + 1, column=1, sticky="w", pady=(0, 4))
                T.InfoBulle(lab, p.aide)

    def valeur(self, cle):
        w = self.widgets.get(cle)
        return w.get() if w is not None else None

    def valeurs(self) -> dict:
        return {k: w.get() for k, w in self.widgets.items()}

    def definir(self, valeurs: dict):
        for k, v in valeurs.items():
            w = self.widgets.get(k)
            if w is not None and v is not None:
                w.set(v)


# ---------------------------------------------------------------------------
def en_texte(serie: pd.Series) -> pd.Series:
    """Conversion en texte sûre (pandas 3 conserve les manquants avec astype(str))."""
    return serie.map(lambda v: "" if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v))


class Grille(ttk.Frame):
    """Grille de données façon Excel : tri, filtres par colonne, recherche, couleurs, export.

    L'affichage est paginé (``LIMITE`` lignes à la fois) et inséré par paquets :
    même avec des centaines de milliers de lignes, l'application reste réactive.
    """

    LIMITE = 2000
    PAQUET = 400

    def __init__(self, parent, df: pd.DataFrame | None = None, surlignage=None, titre=""):
        super().__init__(parent)
        self.limite = self.LIMITE
        self.df_source = pd.DataFrame()
        self.df_vue = pd.DataFrame()
        self.surlignage = surlignage
        self.filtres: dict[str, set] = {}
        self.tri: tuple[str, bool] | None = None
        self.titre = titre
        barre = ttk.Frame(self)
        barre.pack(fill="x", pady=(0, 4))
        ttk.Label(barre, text="🔍 Rechercher :").pack(side="left")
        self.recherche = tk.StringVar()
        e = ttk.Entry(barre, textvariable=self.recherche, width=30)
        e.pack(side="left", padx=4)
        e.bind("<KeyRelease>", lambda ev: self.after(250, self.rafraichir))
        T.Bouton(barre, "Effacer les filtres", self.effacer_filtres, style="neutre", padx=8, pady=1).pack(side="left", padx=4)
        self.b_plus = T.Bouton(barre, "Afficher plus de lignes", self.afficher_plus, style="neutre", padx=8, pady=1)
        T.Bouton(barre, "Exporter la vue en Excel", self.exporter, style="secondaire", padx=8, pady=1).pack(side="right")
        T.Bouton(barre, "Copier", self.copier, style="neutre", padx=8, pady=1).pack(side="right", padx=4)
        self.info = ttk.Label(barre, text="", style="Aide.TLabel")
        self.info.pack(side="left", padx=10)
        cadre = ttk.Frame(self)
        cadre.pack(fill="both", expand=True)
        self.arbre = ttk.Treeview(cadre, show="headings", selectmode="extended")
        vs = ttk.Scrollbar(cadre, orient="vertical", command=self.arbre.yview)
        hs = ttk.Scrollbar(cadre, orient="horizontal", command=self.arbre.xview)
        self.arbre.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.arbre.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        cadre.rowconfigure(0, weight=1)
        cadre.columnconfigure(0, weight=1)
        for nom, coul in T.COULEURS_LIGNES.items():
            self.arbre.tag_configure(nom, background=coul)
        self.arbre.tag_configure("pair", background="#F7FAF8")
        self.arbre.bind("<Button-3>", self._menu_entete)
        self.arbre.bind("<Control-c>", lambda e: self.copier())
        ttk.Label(self, text="Clic sur un en-tête : trier  •  Clic droit sur un en-tête : filtrer (comme dans Excel)",
                  style="Aide.TLabel").pack(anchor="w")
        if df is not None:
            self.charger(df, surlignage)

    def charger(self, df: pd.DataFrame, surlignage=None):
        self.df_source = df.reset_index(drop=True)
        self.surlignage = surlignage
        self.filtres, self.tri = {}, None
        cols = [str(c) for c in df.columns]
        self.arbre.configure(columns=cols)
        for c in cols:
            self.arbre.heading(c, text=c, command=lambda col=c: self._trier(col))
            echantillon = en_texte(df[c].head(200)) if len(df) else pd.Series([], dtype=str)
            largeur = max([len(c)] + [len(x) for x in echantillon]) if len(echantillon) else len(c)
            self.arbre.column(c, width=max(60, min(320, 8 * largeur + 16)), stretch=False,
                              anchor="e" if pd.api.types.is_numeric_dtype(df[c]) else "w")
        self.rafraichir()

    def _trier(self, col):
        asc = not (self.tri and self.tri[0] == col and self.tri[1])
        self.tri = (col, asc)
        self.rafraichir()

    def _menu_entete(self, ev):
        if self.arbre.identify_region(ev.x, ev.y) != "heading":
            return
        col_id = self.arbre.identify_column(ev.x)
        idx = int(col_id.replace("#", "")) - 1
        cols = list(self.arbre["columns"])
        if idx < 0 or idx >= len(cols):
            return
        FiltreColonne(self, cols[idx], ev.x_root, ev.y_root)

    def appliquer_filtre(self, col, valeurs: set | None):
        if valeurs is None:
            self.filtres.pop(col, None)
        else:
            self.filtres[col] = valeurs
        self.rafraichir()

    def effacer_filtres(self):
        self.filtres, self.tri = {}, None
        self.recherche.set("")
        self.rafraichir()

    def afficher_plus(self):
        self.limite += 10000
        self.rafraichir()

    @staticmethod
    def _cellule(v):
        if v is None:
            return ""
        if isinstance(v, float):
            if v != v:                      # NaN
                return ""
            if v == int(v) and abs(v) < 1e15:
                return str(int(v))
            return f"{v:.2f}"
        return str(v)

    def rafraichir(self):
        df = self.df_source
        if df is None:
            return
        df2 = df
        if self.filtres or self.recherche.get().strip():
            df2 = df.copy()
            df2.columns = [str(c) for c in df2.columns]
            for col, vals in self.filtres.items():
                if col in df2.columns:
                    df2 = df2[en_texte(df2[col]).isin(vals)]
            q = self.recherche.get().strip().lower()
            if q:
                masque = df2.apply(lambda s: en_texte(s).str.lower().str.contains(q, regex=False)).any(axis=1)
                df2 = df2[masque]
        if self.tri:
            col, asc = self.tri
            if col in df2.columns:
                try:
                    df2 = df2.sort_values(col, ascending=asc, kind="mergesort")
                except TypeError:
                    df2 = df2.sort_values(col, ascending=asc, key=en_texte, kind="mergesort")
        self.df_vue = df2
        for c in self.arbre["columns"]:
            marque = ""
            if self.tri and self.tri[0] == c:
                marque += " ▲" if self.tri[1] else " ▼"
            if c in self.filtres:
                marque += " ⧩"
            self.arbre.heading(c, text=c + marque)
        self.arbre.delete(*self.arbre.get_children())
        affiche = df2.head(self.limite)
        n, total = len(df2), len(df)
        self.info.configure(text="Chargement de l'affichage…")
        self.update_idletasks()
        lignes = affiche.to_numpy(dtype=object)
        couleurs = []
        if self.surlignage is not None:
            for _, ligne in affiche.iterrows():
                try:
                    couleurs.append(self.surlignage(ligne))
                except Exception:
                    couleurs.append(None)
        inserer = self.arbre.insert
        for depart in range(0, len(lignes), self.PAQUET):
            for i in range(depart, min(depart + self.PAQUET, len(lignes))):
                coul = couleurs[i] if i < len(couleurs) else None
                tags = (coul,) if coul else (("pair",) if i % 2 else ())
                inserer("", "end", values=[self._cellule(v) for v in lignes[i]], tags=tags)
            if len(lignes) > self.PAQUET:
                self.info.configure(text=f"Chargement de l'affichage… {min(depart + self.PAQUET, len(lignes)):,}"
                                         .replace(",", " ") + f" / {len(lignes)}")
                self.update_idletasks()
        txt = f"{n:,} ligne(s)".replace(",", " ") + (f" sur {total:,}".replace(",", " ") if n != total else "")
        if n > len(lignes):
            txt += f" — {len(lignes):,} affichée(s) ; l'export et le fichier Excel contiennent tout".replace(",", " ")
            self.b_plus.pack(side="left", padx=4)
        else:
            self.b_plus.pack_forget()
        self.info.configure(text=txt)

    def exporter(self):
        from enem_core.exports import exporter_excel
        f = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
                                         initialfile=f"{self.titre or 'extraction'}.xlsx")
        if f:
            exporter_excel(f, {self.titre or "Donnees": self.df_vue})
            if messagebox.askyesno("Export", "Fichier enregistré. L'ouvrir maintenant ?"):
                T.ouvrir(f)

    def copier(self):
        sel = self.arbre.selection()
        cols = list(self.arbre["columns"])
        lignes = ["\t".join(cols)]
        items = sel or self.arbre.get_children()
        for it in items:
            lignes.append("\t".join(str(v) for v in self.arbre.item(it, "values")))
        self.clipboard_clear()
        self.clipboard_append("\n".join(lignes))
        self.info.configure(text=f"{len(items)} ligne(s) copiée(s) dans le presse-papiers (coller dans Excel)")


class FiltreColonne(tk.Toplevel):
    """Fenêtre de filtre d'une colonne (valeurs à cocher)."""

    def __init__(self, grille: Grille, col: str, x, y):
        super().__init__(grille)
        self.grille, self.col = grille, col
        self.title(f"Filtrer : {col}")
        self.geometry(f"280x380+{x}+{y}")
        self.transient(grille.winfo_toplevel())
        serie = en_texte(grille.df_source[[c for c in grille.df_source.columns if str(c) == col][0]])
        valeurs = sorted(serie.unique(), key=lambda v: (len(v) > 0, v))[:500]
        actifs = grille.filtres.get(col, set(valeurs))
        barre = ttk.Frame(self, padding=4)
        barre.pack(fill="x")
        T.Bouton(barre, "Trier ▲", lambda: self._trier(True), style="neutre", padx=6, pady=1).pack(side="left")
        T.Bouton(barre, "Trier ▼", lambda: self._trier(False), style="neutre", padx=6, pady=1).pack(side="left", padx=3)
        self.var_tout = tk.BooleanVar(value=len(actifs) == len(valeurs))
        ttk.Checkbutton(self, text="(Tout sélectionner)", variable=self.var_tout, command=self._tout).pack(anchor="w", padx=6)
        zone = Defilant(self, fond=T.BLANC)
        zone.pack(fill="both", expand=True, padx=4)
        self.vars = {}
        for v in valeurs:
            var = tk.BooleanVar(value=v in actifs)
            tk.Checkbutton(zone.interieur, text=v if v else "(vide)", variable=var, bg=T.BLANC,
                           anchor="w").pack(fill="x")
            self.vars[v] = var
        bas = ttk.Frame(self, padding=4)
        bas.pack(fill="x")
        T.Bouton(bas, "OK", self._ok, padx=12, pady=2).pack(side="right")
        T.Bouton(bas, "Annuler", self.destroy, style="neutre", padx=8, pady=2).pack(side="right", padx=4)

    def _tout(self):
        for v in self.vars.values():
            v.set(self.var_tout.get())

    def _trier(self, asc):
        self.grille.tri = (self.col, asc)
        self.grille.rafraichir()
        self.destroy()

    def _ok(self):
        choisis = {k for k, v in self.vars.items() if v.get()}
        self.grille.appliquer_filtre(self.col, None if len(choisis) == len(self.vars) else choisis)
        self.destroy()


# ---------------------------------------------------------------------------
class Graphique(ttk.Frame):
    """Graphique matplotlib intégré (barres, barres horizontales, courbes, Gantt)."""

    def __init__(self, parent):
        super().__init__(parent)
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure
        self.figure = Figure(figsize=(9, 5), dpi=96)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        barre = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
        barre.update()
        barre.pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def tracer(self, spec: dict, df: pd.DataFrame):
        import matplotlib.dates as mdates
        fig = self.figure
        fig.clear()
        ax = fig.add_subplot(111)
        x, ys, typ = spec["x"], [y for y in spec["y"] if y in df.columns], spec.get("type", "bar")
        d = df.copy()
        if typ == "gantt":
            d = d.dropna(subset=[x, ys[0]])
            debut = pd.to_datetime(d[x])
            fin = pd.to_datetime(d[ys[0]]) + pd.Timedelta(days=1)
            etiq = en_texte(d[spec.get("etiquette", x)]).str.slice(0, 55)
            couleurs = [T.ORANGE if e.startswith("Point de suivi") else T.VERT for e in etiq]
            ax.barh(range(len(d)), (fin - debut).dt.days, left=mdates.date2num(debut), color=couleurs)
            ax.set_yticks(range(len(d)))
            ax.set_yticklabels(etiq, fontsize=7)
            ax.invert_yaxis()
            ax.xaxis_date()
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
            fig.set_size_inches(10, max(4, 0.22 * len(d)))
        elif not ys or x not in d.columns:
            ax.text(0.5, 0.5, "Données non disponibles pour ce graphique", ha="center", va="center")
        else:
            d = d[[x] + ys].dropna(subset=ys, how="all")
            for y in ys:
                d[y] = pd.to_numeric(d[y], errors="coerce")
            etiq = en_texte(d[x]).str.slice(0, 40)
            n, k = len(d), len(ys)
            if typ == "line":
                for i, y in enumerate(ys):
                    ax.plot(etiq, d[y], marker="o", color=T.COULEURS_GRAPHIQUES[i % 7], label=y)
                ax.tick_params(axis="x", rotation=45, labelsize=8)
            elif typ == "barh":
                d = d.sort_values(ys[-1])
                etiq = en_texte(d[x]).str.slice(0, 40)
                h = 0.8 / k
                for i, y in enumerate(ys):
                    ax.barh([j + i * h for j in range(n)], d[y], height=h, color=T.COULEURS_GRAPHIQUES[i % 7], label=y)
                ax.set_yticks([j + h * (k - 1) / 2 for j in range(n)])
                ax.set_yticklabels(etiq, fontsize=7 if n > 25 else 8)
                fig.set_size_inches(9, max(4, 0.25 * n * max(1, k * 0.7)))
            else:
                w = 0.8 / k
                for i, y in enumerate(ys):
                    ax.bar([j + i * w for j in range(n)], d[y], width=w, color=T.COULEURS_GRAPHIQUES[i % 7], label=y)
                ax.set_xticks([j + w * (k - 1) / 2 for j in range(n)])
                ax.set_xticklabels(etiq, rotation=45 if n > 6 else 0, ha="right" if n > 6 else "center", fontsize=8)
            if spec.get("etiquettes") and typ in ("bar", "barh"):
                for conteneur in ax.containers:
                    try:
                        ax.bar_label(conteneur, fmt="%g", fontsize=7, padding=2,
                                     labels=[spec["etiquettes_texte"][i] for i in range(len(d))]
                                     if spec.get("etiquettes_texte") else None)
                    except Exception:
                        pass
                if typ == "bar":
                    ax.margins(y=0.15)
                else:
                    ax.margins(x=0.15)
            if k > 1 or typ == "line":
                ax.legend(fontsize=8)
            ax.grid(axis="x" if typ == "barh" else "y", alpha=0.3)
        ax.set_title(spec.get("titre", ""), color=T.VERT, fontsize=11, fontweight="bold")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        fig.tight_layout()
        w, h = fig.get_size_inches() * fig.dpi
        self.canvas.get_tk_widget().configure(height=int(h))
        self.canvas.draw()

    def tracer_series(self, titre: str, series: dict[str, pd.DataFrame], ylabel: str = "", cibles=None):
        """series : {nom: DataFrame(date, valeur)} -> courbes temporelles (cibles en pointillés)."""
        import matplotlib.dates as mdates
        fig = self.figure
        fig.clear()
        fig.set_size_inches(9, 5)
        ax = fig.add_subplot(111)
        dates = []
        for i, (nom, d) in enumerate(series.items()):
            coul = T.COULEURS_GRAPHIQUES[i % 7] if i < 7 else None
            x = pd.to_datetime(d["date"])
            dates += list(x)
            ligne, = ax.plot(x, d["valeur"], marker="o", label=nom[:45], color=coul)
            if cibles and nom in cibles:
                c = cibles[nom]
                ax.plot(pd.to_datetime(c["date"]), c["valeur"], linestyle="--", color=ligne.get_color(),
                        alpha=0.7, label="cible (pointillés)" if i == 0 else None)
        if dates:
            d0, d1 = min(dates), max(dates)
            marge = max(pd.Timedelta(days=3), (d1 - d0) * 0.05)
            ax.set_xlim(d0 - marge, d1 + marge)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y"))
        ax.set_title(titre, color=T.VERT, fontsize=11, fontweight="bold")
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
        if series:
            ax.legend(fontsize=7, ncol=2 if len(series) > 8 else 1)
        fig.autofmt_xdate()
        fig.tight_layout()
        self.canvas.draw()
