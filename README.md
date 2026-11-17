# 詰み — Tsumi

> Lecteur de manga, manhwa, manhua et webtoon. Léger, CPU-only, pensé pour les machines modestes.

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL--3.0-blue.svg" alt="License: GPL-3.0">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/RAM-~20%20Mo-green.svg" alt="RAM ~20 Mo">
  <img src="https://img.shields.io/badge/GPU-Requis%20aucun-orange.svg" alt="No GPU required">
  <img src="https://img.shields.io/badge/Langue-FR%20%7C%20EN-lightgrey.svg" alt="Language">
  <img src="https://img.shields.io/badge/Status-v1--dev-yellow.svg" alt="Status">
</p>

---

## Pourquoi ?

Les lecteurs existants (Komikku, Tachiyomi, YACReader, ...) sont soit trop lourds, soit dépendants de GPU, soit en GTK/Qt qui crashent sur du hardware modeste.

**Tsumi** est un lecteur minimaliste en **Python + Tkinter** qui :
- Tourne sur un **AMD A4-9125** (dual-core, Vega 1, driver Mesa cassé)
- Utilise **zéro GPU** — rendu X11 CPU pur
- Démarre en **< 0.5s**
- Pèse **~20 Mo RAM** en lecture
- Ne dépend que de la **stdlib Python** + Pillow + requests + BeautifulSoup

---

## Features

### Lecture

| Feature | Détail |
|---------|--------|
| Mode **Paged** | Page par page (manga, manhua, manhwa) |
| Mode **Scroll** | Défilement vertical continu (webtoon) |
| **RTL / LTR** | Direction de lecture configurable |
| **Fullscreen** | Touche `F`, double-clic |
| **Continuer** | Reprend au chapitre + page exacts |
| **Préchargement** | Page suivante décodée en thread |
| **Downscale** | Image redimensionnée à l'écran (perf CPU) |

### Bibliothèque

| Feature | Détail |
|---------|--------|
| **Catégories** | Manga / Manhwa / Manhua / Webtoon |
| **Progression** | Chapitre + page sauvegardés (JSON) |
| **Ajouter / Supprimer** | Gestion manuelle de la liste |
| **Tri** | Par nom, date, progression |

### Sources

| Feature | Détail |
|---------|--------|
| **Pluggable** | Un fichier Python = un site |
| **Rimu Scans** | FR |
| **Anime-Sama** | FR |
| **Mangas-Origines** | FR |
| **Autres sources FR populaires** |
| **Download CBZ** | Sauvegarde un chapitre en CBZ pour lecture offline |
| **Recherche** | Par titre |

### UI

| Feature | Détail |
|---------|--------|
| **Thème sombre** | Fond `#0d0d0d` couleur secondaire `#1671e3`, texte `##dddddd` |
| **Boutons custom** | Flat, hover, zéro widget natif visible |
| **HUD** | Overlay temporaire (page X/Y) |
| **2 écrans** | Bibliothèque (fenêtré) + Lecteur (fullscreen) |

### Non-inclus (v1)

- ~~NSFW~~ (plus tard)
- ~~Multi-langue~~ (FR uniquement)
- ~~Cloud sync~~
- ~~Multi-utilisateurs~~

---

## Stack

| Composant | Choix | Raison |
|-----------|-------|--------|
| UI | **Tkinter** (stdlib) | Zéro GPU, zéro install, 15 Mo RAM |
| Images | **Pillow** | Decode JPEG/PNG/WebP, resize |
| Archives | **zipfile** (stdlib) + **rarfile** | CBZ = ZIP, CBR = RAR |
| Scraping | **requests** + **BeautifulSoup** | HTML parsing des sources FR |
| Sauvegarde | **JSON** (`~/.tsumi/`) | Progression + bibliothèque |
| Threads | **threading** (stdlib) | Préchargement, download |

---

## Installation

### Prérequis

- Python **3.10+**
- Linux

### Setup

```bash
git clone https://github.com/Badley08/Tsumi.git
cd Tsumi
pip install -r requirements.txt   
```

- Or just donwload the .AppImage