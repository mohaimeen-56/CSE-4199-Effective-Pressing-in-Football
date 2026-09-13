"""
=============================================================================
SOURCE 3 — football-data.co.uk Match Results Downloader
=============================================================================
What it collects:
  Historical match results — no scraping needed, they provide direct CSV links.
  Covers Premier League, La Liga, Bundesliga, Serie A — multiple seasons each.

  Columns include:
    - Date, HomeTeam, AwayTeam
    - FTHG / FTAG (full-time goals home/away)
    - HTHG / HTAG (half-time goals)
    - Referee
    - HS/AS (home/away shots), HST/AST (shots on target)
    - HC/AC (corners), HF/AF (fouls), HY/AY (yellow cards), HR/AR (reds)
    - Betting odds from multiple bookmakers

Output: data/results/results_LEAGUE_SEASON.csv + data/results/ALL_results.csv

This data is useful for:
  - Contextualising your network analysis results
  - Correlating high-TCS matches with match outcomes
  - Building supplementary features (form, home/away, momentum)

Run time: ~2 minutes (just downloading CSVs)
=============================================================================
"""

import requests
import pandas as pd
import os
import time

OUT = "data/results"
os.makedirs(OUT, exist_ok=True)

# ── DATA SOURCES ──────────────────────────────────────────────────────────────
# football-data.co.uk URL format:
#   https://www.football-data.co.uk/mmz4281/{SEASON}/{LEAGUE_CODE}.csv
#   Seasons: 9394, 9495, ... 2223, 2324
#   League codes: E0=PL, SP1=La Liga, D1=Bundesliga, I1=Serie A, F1=Ligue 1

DATASETS = [
    # ── Premier League ───────────────────────────────────────────────────
    {"url": "https://www.football-data.co.uk/mmz4281/2324/E0.csv", "name": "PL_2324"},
    {"url": "https://www.football-data.co.uk/mmz4281/2223/E0.csv", "name": "PL_2223"},
    {"url": "https://www.football-data.co.uk/mmz4281/2122/E0.csv", "name": "PL_2122"},
    {"url": "https://www.football-data.co.uk/mmz4281/2021/E0.csv", "name": "PL_2021"},
    {"url": "https://www.football-data.co.uk/mmz4281/1920/E0.csv", "name": "PL_1920"},
    {"url": "https://www.football-data.co.uk/mmz4281/1819/E0.csv", "name": "PL_1819"},
    {"url": "https://www.football-data.co.uk/mmz4281/1718/E0.csv", "name": "PL_1718"},
    {"url": "https://www.football-data.co.uk/mmz4281/1617/E0.csv", "name": "PL_1617"},
    {"url": "https://www.football-data.co.uk/mmz4281/1516/E0.csv", "name": "PL_1516"},
    {"url": "https://www.football-data.co.uk/mmz4281/1415/E0.csv", "name": "PL_1415"},
    # ── La Liga ──────────────────────────────────────────────────────────
    {"url": "https://www.football-data.co.uk/mmz4281/2324/SP1.csv", "name": "LaLiga_2324"},
    {"url": "https://www.football-data.co.uk/mmz4281/2223/SP1.csv", "name": "LaLiga_2223"},
    {"url": "https://www.football-data.co.uk/mmz4281/2122/SP1.csv", "name": "LaLiga_2122"},
    {"url": "https://www.football-data.co.uk/mmz4281/2021/SP1.csv", "name": "LaLiga_2021"},
    {"url": "https://www.football-data.co.uk/mmz4281/1920/SP1.csv", "name": "LaLiga_1920"},
    {"url": "https://www.football-data.co.uk/mmz4281/1819/SP1.csv", "name": "LaLiga_1819"},
    # ── Bundesliga ───────────────────────────────────────────────────────
    {"url": "https://www.football-data.co.uk/mmz4281/2324/D1.csv",  "name": "Bundesliga_2324"},
    {"url": "https://www.football-data.co.uk/mmz4281/2223/D1.csv",  "name": "Bundesliga_2223"},
    {"url": "https://www.football-data.co.uk/mmz4281/2122/D1.csv",  "name": "Bundesliga_2122"},
    # ── Serie A ──────────────────────────────────────────────────────────
    {"url": "https://www.football-data.co.uk/mmz4281/2324/I1.csv",  "name": "SerieA_2324"},
    {"url": "https://www.football-data.co.uk/mmz4281/2223/I1.csv",  "name": "SerieA_2223"},
    {"url": "https://www.football-data.co.uk/mmz4281/2122/I1.csv",  "name": "SerieA_2122"},
]

HEADERS = {"User-Agent": "Mozilla/5.0"}


def download_csv(url, name):
    """Download a CSV from football-data.co.uk."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        # Try reading with different encodings (some older files use latin-1)
        try:
            df = pd.read_csv(pd.io.common.StringIO(resp.text))
        except Exception:
            df = pd.read_csv(pd.io.common.StringIO(resp.content.decode('latin-1')))

        # Drop rows where all values are NaN (trailing empty rows)
        df = df.dropna(how='all')

        # Add source column
        df['source_name'] = name
        df['league']      = name.split('_')[0]
        df['season']      = name.split('_')[1] if '_' in name else 'unknown'

        out_path = f"{OUT}/results_{name}.csv"
        df.to_csv(out_path, index=False)
        print(f"  ✓  {name:25s}  {len(df):>4} matches  →  {out_path}")
        return df

    except requests.exceptions.HTTPError as e:
        print(f"  ✗  {name:25s}  HTTP {e.response.status_code} — skipped")
        return None
    except Exception as e:
        print(f"  ✗  {name:25s}  Error: {e}")
        return None


# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*60)
    print("  MATCH RESULTS DOWNLOADER")
    print("  Source: football-data.co.uk (free, direct CSV)")
    print(f"  Datasets: {len(DATASETS)} league-seasons")
    print("="*60)

    all_dfs = []

    for ds in DATASETS:
        df = download_csv(ds["url"], ds["name"])
        if df is not None:
            all_dfs.append(df)
        time.sleep(0.5)   # light delay

    if all_dfs:
        master = pd.concat(all_dfs, ignore_index=True)

        # Standardise key columns
        rename_map = {
            'HomeTeam': 'home_team', 'AwayTeam': 'away_team',
            'FTHG': 'home_goals',   'FTAG': 'away_goals',
            'FTR': 'result',
            'HS': 'home_shots',     'AS': 'away_shots',
            'HST': 'home_shots_target', 'AST': 'away_shots_target',
            'HC': 'home_corners',   'AC': 'away_corners',
            'HF': 'home_fouls',     'AF': 'away_fouls',
            'HY': 'home_yellows',   'AY': 'away_yellows',
            'HR': 'home_reds',      'AR': 'away_reds',
        }
        master.rename(columns={k: v for k, v in rename_map.items() if k in master.columns}, inplace=True)

        master.to_csv(f"{OUT}/ALL_results.csv", index=False)

        print("\n" + "="*60)
        print("  DOWNLOAD COMPLETE")
        print("="*60)
        print(f"  Total matches : {len(master):,}")
        print(f"  Leagues       : {master['league'].nunique()}")
        print(f"  Seasons       : {master['season'].nunique()}")
        print(f"  Columns       : {len(master.columns)}")
        print(f"  Master file   : data/results/ALL_results.csv")
        print("="*60)
        print("\n  Column reference:")
        print("  home_team, away_team, home_goals, away_goals, result (H/D/A)")
        print("  home_shots, away_shots, home_shots_target, away_shots_target")
        print("  home_corners, away_corners, home_fouls, away_fouls")
        print("  home_yellows, away_yellows, home_reds, away_reds")
        print("\n  Next step: run  04_build_passing_network_features.py")
