"""
=============================================================================
SOURCE 2 — FBref Player Season Statistics Scraper
=============================================================================
What it collects:
  Per-player, per-season statistics from fbref.com for your graph node features.
  These become the STATISTICAL ENRICHMENT your teacher asked about.

  Tables scraped:
    - Standard stats     (goals, assists, matches, minutes)
    - Passing stats      (pass completion %, progressive passes, key passes)
    - Defensive stats    (tackles, pressures, pressure success %)
    - Possession stats   (carries, progressive carries, dribbles)
    - Playing time       (starts, substitutions, minutes per 90)

Output: data/fbref/player_stats_LEAGUE_SEASON.csv

Legal note: FBref is publicly available. We add a 5-second delay between
requests to be respectful of their servers. This is standard practice.

Run time: ~10–20 minutes per league/season
=============================================================================
"""

import requests
import pandas as pd
import time
import os

OUT = "data/fbref"
os.makedirs(OUT, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

DELAY = 5  # seconds between requests — do NOT reduce this

# ── LEAGUE URL CONFIG ─────────────────────────────────────────────────────────
# FBref stat-table URLs for major leagues
# Format: (competition_code, season_slug, friendly_name)
LEAGUES = [
    # Premier League
    {"comp": "9",  "season": "2022-2023", "name": "Premier_League_2223"},
    {"comp": "9",  "season": "2021-2022", "name": "Premier_League_2122"},
    {"comp": "9",  "season": "2020-2021", "name": "Premier_League_2021"},
    # La Liga
    {"comp": "12", "season": "2022-2023", "name": "La_Liga_2223"},
    {"comp": "12", "season": "2021-2022", "name": "La_Liga_2122"},
    # Champions League
    {"comp": "8",  "season": "2022-2023", "name": "Champions_League_2223"},
]

# ── TABLE TYPES ───────────────────────────────────────────────────────────────
# Each FBref table type has its own URL slug
STAT_TYPES = {
    "standard":    "stats",
    "passing":     "passing",
    "defense":     "defense",
    "possession":  "possession",
    "playing_time":"playingtime",
}


def build_url(comp, season, stat_type_slug):
    """Build the FBref URL for a given league, season and stat type."""
    return (
        f"https://fbref.com/en/comps/{comp}/{season}/{season}-"
        f"{stat_type_slug}-stats"
    )


def clean_df(df):
    """Clean multi-level columns and remove duplicate header rows."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(c).strip('_') for c in df.columns.values]
    # Remove rows where the first column repeats the header
    df = df[df.iloc[:, 0] != df.columns[0]]
    # Remove 'Squad' summary rows
    df = df[df.get('Player', pd.Series(['x'])) != 'Player']
    df = df.reset_index(drop=True)
    return df


def scrape_table(url, table_index=0):
    """Scrape a specific HTML table from FBref."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        tables = pd.read_html(resp.text, header=[0, 1])
        if not tables:
            return None
        df = tables[table_index]
        return clean_df(df)
    except Exception as e:
        print(f"      Failed to scrape {url}: {e}")
        return None


def collect_league_season(league_cfg):
    """Collect all stat tables for one league-season and merge them."""
    name    = league_cfg["name"]
    comp    = league_cfg["comp"]
    season  = league_cfg["season"]

    print(f"\n  Scraping: {name}")
    merged  = None

    for stat_name, stat_slug in STAT_TYPES.items():
        url = build_url(comp, season, stat_slug)
        print(f"    [{stat_name}]  {url}")

        df = scrape_table(url)
        time.sleep(DELAY)       # polite delay

        if df is None:
            print(f"    Skipping {stat_name} — failed")
            continue

        # Prefix columns with stat type to avoid clashes, keep player/squad
        id_cols = ['Player', 'Nation', 'Pos', 'Squad', 'Age', 'Born', 'Matches']
        id_present = [c for c in id_cols if c in df.columns]
        stat_cols  = [c for c in df.columns if c not in id_cols]

        df_renamed = df[id_present].copy()
        for c in stat_cols:
            df_renamed[f"{stat_name}__{c}"] = df[c].values

        if merged is None:
            merged = df_renamed
        else:
            on = [c for c in ['Player', 'Squad'] if c in merged.columns and c in df_renamed.columns]
            if on:
                merged = pd.merge(merged, df_renamed, on=on, how='outer', suffixes=('', f'_{stat_name}'))
            else:
                merged = pd.concat([merged, df_renamed], axis=1)

        print(f"    Collected {len(df)} players, {len(df.columns)} columns")

    if merged is not None:
        out_path = f"{OUT}/player_stats_{name}.csv"
        merged.to_csv(out_path, index=False)
        print(f"  Saved {len(merged)} rows  →  {out_path}")
    return merged


# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*60)
    print("  FBREF PLAYER STATS SCRAPER")
    print("  Collecting: passing, defense, possession, playing time")
    print(f"  Leagues: {len(LEAGUES)} league-seasons")
    print("  Delay between requests: 5 seconds (respectful scraping)")
    print("="*60)

    all_dfs = []
    for league_cfg in LEAGUES:
        df = collect_league_season(league_cfg)
        if df is not None:
            df['league_season'] = league_cfg['name']
            all_dfs.append(df)

    if all_dfs:
        master = pd.concat(all_dfs, ignore_index=True)
        master.to_csv(f"{OUT}/ALL_player_stats.csv", index=False)

        print("\n" + "="*60)
        print("  FBREF SCRAPE COMPLETE")
        print("="*60)
        print(f"  Total rows  : {len(master):,}")
        print(f"  Columns     : {len(master.columns)}")
        print(f"  Leagues     : {len(LEAGUES)}")
        print(f"  Master file : data/fbref/ALL_player_stats.csv")
        print("="*60)
        print("  Key columns for your graph NODE FEATURES:")
        node_feature_cols = [c for c in master.columns if any(
            k in c.lower() for k in ['pass', 'press', 'carry', 'touch', 'prog']
        )]
        for c in node_feature_cols[:20]:
            print(f"    · {c}")
        print("  Next step: run  03_match_results.py")
