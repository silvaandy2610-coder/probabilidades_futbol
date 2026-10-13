"""
Descarga los resultados terminados desde football-data.org y los guarda como CSV
en la carpeta data/. La web lee esos archivos automáticamente.

El token se lee de la variable de entorno FOOTBALL_DATA_TOKEN (nunca va escrito aquí).
"""
import csv
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

# (código en la API, nombre que verás en la web, pestaña: "liga" o "champions")
# Puedes borrar las que no quieras. Todas estas están en el plan gratis.
COMPETITIONS = [
    ("PL", "Premier League", "liga"),
    ("PD", "LaLiga", "liga"),
    ("SA", "Serie A", "liga"),
    ("BL1", "Bundesliga", "liga"),
    ("FL1", "Ligue 1", "liga"),
    ("CL", "Champions League", "champions"),
]

SEASONS_BACK = 1  # temporada actual + cuántas anteriores (1 = actual y la anterior)
PAUSE = 7         # segundos entre llamadas (el plan gratis permite 10 por minuto)
DATA_DIR = "data"


def current_season_year():
    today = datetime.datetime.utcnow()
    return today.year if today.month >= 7 else today.year - 1


def fetch_matches(token, code, season):
    url = f"https://api.football-data.org/v4/competitions/{code}/matches?season={season}&status=FINISHED"
    for attempt in range(2):
        req = urllib.request.Request(url, headers={"X-Auth-Token": token})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt == 0:
                print("  límite de llamadas alcanzado, espero un minuto...")
                time.sleep(65)
                continue
            print(f"  aviso: {code} temporada {season} -> error {err.code}")
            return None
        except Exception as err:  # red, JSON, etc.
            print(f"  aviso: {code} temporada {season} -> {err}")
            return None
    return None


def rows_from(data):
    """Devuelve (fecha, local, visita, goles_local, goles_visita) a los 90 minutos."""
    out = []
    for m in data.get("matches", []):
        score = m.get("score") or {}
        duration = score.get("duration")
        part = score.get("regularTime")
        if not part and duration in (None, "REGULAR"):
            part = score.get("fullTime")
        if not part:
            continue
        hg, ag = part.get("home"), part.get("away")
        if hg is None or ag is None:
            continue
        home, away = m.get("homeTeam") or {}, m.get("awayTeam") or {}
        h = home.get("shortName") or home.get("name")
        a = away.get("shortName") or away.get("name")
        if not h or not a:
            continue
        out.append((m.get("utcDate", ""), h, a, hg, ag))
    return out


def main():
    token = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()
    if not token:
        sys.exit("Falta el token: configura el secreto FOOTBALL_DATA_TOKEN.")

    os.makedirs(DATA_DIR, exist_ok=True)
    cur = current_season_year()
    seasons = list(range(cur - SEASONS_BACK, cur + 1))
    manifest = []
    first_call = True

    for code, name, tab in COMPETITIONS:
        print(f"{name} ({code})")
        rows = []
        for season in seasons:
            if not first_call:
                time.sleep(PAUSE)
            first_call = False
            data = fetch_matches(token, code, season)
            if data:
                got = rows_from(data)
                print(f"  temporada {season}: {len(got)} partidos")
                rows.extend(got)
        if not rows:
            print("  sin partidos, no se genera archivo para esta competición")
            continue
        rows.sort(key=lambda r: r[0])  # de más antiguo a más reciente
        path = os.path.join(DATA_DIR, f"{code}.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])
            for r in rows:
                w.writerow([r[0][:10], r[1], r[2], r[3], r[4]])
        manifest.append({"file": f"{code}.csv", "name": name, "tab": tab})

    if not manifest:
        sys.exit("No se pudo descargar ninguna competición. Revisa el token y los avisos de arriba.")

    with open(os.path.join(DATA_DIR, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files": manifest,
        }, fh, ensure_ascii=False, indent=2)
    print("Listo.")


if __name__ == "__main__":
    main()
