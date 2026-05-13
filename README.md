# OBSTACLE – Microphone-controlled Pygame obstacle game

Egy Pygame-alapú ügyességi játék, ahol a játékos mozgását mikrofon bemenet vezérli.

## Főbb funkciók

- Valós idejű mikrofon bemenet feldolgozás
- Band-pass szűrés (100–2000 Hz)
- Settings panel (Sensitivity, Threshold)
- Generált hang effektek

## Követelmények

- Python 3.10+
- numpy
- scipy
- pygame
- sounddevice

## Telepítés (Conda)

conda create -n obstacle python=3.11 numpy scipy pygame sounddevice -c conda-forge
conda activate obstacle

## Telepítés (pip + venv)

Windows:
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip numpy scipy pygame sounddevice

Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip numpy scipy pygame sounddevice

## Futtatás

python obstacle.py

## Hibakeresés

- Mikrofon engedélyezése szükséges
- sounddevice hibánál PortAudio hiányozhat
- Pygame hang esetén ellenőrizd az audio eszközt

## Licenc

MIT License (ajánlott)
