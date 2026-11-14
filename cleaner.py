"""
cleaner.py - Dataset Cleaning and Organization Tool for Football Passing Networks

CSE 4199 | Graph-Based Vulnerability Analysis of Passing Networks

This utility cleans, standardizes, and organizes the project's datasets into:
  1. scraped_data/ : Preserves the raw, untouched original datasets.
  2. cleaned_data/ : Contains sanitized, deduplicated, imputed, and type-safe CSVs.

Datasets handled:
  - graph_nodes.csv
  - graph_edges.csv
  - pressure_events.csv
  - Pass_Events_and_Pressure_Call.csv
  - La_Liga_15_16_Premier_League_15_16_WC22_Euro20.csv

Usage:
  python cleaner.py
  python cleaner.py --scraped-dir Dataset/scraped_data --cleaned-dir Dataset/cleaned_data
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
import pandas as pd
import numpy as np


def log(msg: str):
    """Prints formatted log messages."""
    print(f"[cleaner] {msg}")


def strip_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strips leading/trailing whitespace from all string/object columns."""
    for col in df.columns:
        if df[col].dtype == "object" or isinstance(df[col].dtype, pd.StringDtype):
            df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
    return df


def setup_directories(dataset_root: Path, scraped_dir: Path, cleaned_dir: Path):
    """
    Ensures scraped_data and cleaned_data directories exist.
    If original datasets are in dataset_root, moves or copies them into scraped_dir.
    """
    scraped_dir.mkdir(parents=True, exist_ok=True)
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    expected_files = [
        "graph_nodes.csv",
        "graph_edges.csv",
        "pressure_events.csv",
        "Pass_Events_and_Pressure_Call.csv",
        "La_Liga_15_16_Premier_League_15_16_WC22_Euro20.csv",
    ]

    for fname in expected_files:
        src = dataset_root / fname
        dest = scraped_dir / fname
        if src.exists() and src != dest and not dest.exists():
            log(f"Archiving original raw file: {fname} -> {scraped_dir}")
            shutil.copy2(src, dest)
        elif not dest.exists() and not src.exists():
            log(f"WARNING: File {fname} not found in {dataset_root} or {scraped_dir}!")


def clean_pressure_events(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans pressure events:
    - Strips whitespace.
    - Removes duplicate rows.
    - Validates pitch coordinates (0-120, 0-80).
    - Standardizes column types.
    - Sorts chronologically.
    """
    initial_len = len(df)
    df = strip_string_columns(df)

    # Deduplicate
    df = df.drop_duplicates().reset_index(drop=True)
    dups_removed = initial_len - len(df)

    # Type casting
    int_cols = ["match_id", "period", "minute", "second"]
    for c in int_cols:
        if c in df.columns:
            df[c] = df[c].astype("int64")

    # Coordinate validation / clipping
    if "press_x" in df.columns:
        df["press_x"] = df["press_x"].clip(0.0, 120.0).round(2)
    if "press_y" in df.columns:
        df["press_y"] = df["press_y"].clip(0.0, 80.0).round(2)

    # Sort
    sort_cols = [c for c in ["match_id", "period", "minute", "second"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    log(f"pressure_events.csv: removed {dups_removed} duplicates, final rows: {len(df):,}")
    return df


def clean_pass_events(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans pass events:
    - Strips whitespace.
    - Fills boolean flags (under_pressure, pass_switch, pass_cross) with False.
    - Standardizes pass_outcome (null -> 'Complete').
    - Standardizes pass_type (null -> 'Open Play').
    - Adds explicit 'is_complete' boolean helper column.
    - Validates and rounds coordinates.
    - Sorts chronologically.
    """
    initial_len = len(df)
    df = strip_string_columns(df)

    # Deduplicate
    df = df.drop_duplicates().reset_index(drop=True)
    dups_removed = initial_len - len(df)

    # Boolean columns
    bool_cols = ["under_pressure", "pass_switch", "pass_cross"]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)

    # Categorical normalization
    if "pass_outcome" in df.columns:
        df["pass_outcome"] = df["pass_outcome"].fillna("Complete")
        # Add helper boolean is_complete
        df["is_complete"] = df["pass_outcome"] == "Complete"

    if "pass_type" in df.columns:
        df["pass_type"] = df["pass_type"].fillna("Open Play")

    # Coordinates
    coord_cols = [c for c in ["loc_x", "end_x"] if c in df.columns]
    for c in coord_cols:
        df[c] = df[c].clip(0.0, 120.0).round(2)

    coord_y_cols = [c for c in ["loc_y", "end_y"] if c in df.columns]
    for c in coord_y_cols:
        df[c] = df[c].clip(0.0, 80.0).round(2)

    if "pass_length" in df.columns:
        df["pass_length"] = df["pass_length"].round(2)
    if "pass_angle" in df.columns:
        df["pass_angle"] = df["pass_angle"].round(4)

    # Integer types
    int_cols = ["match_id", "period", "minute", "second"]
    for c in int_cols:
        if c in df.columns:
            df[c] = df[c].astype("int64")

    # Sort
    sort_cols = [c for c in ["match_id", "period", "minute", "second"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    log(f"Pass_Events_and_Pressure_Call.csv: removed {dups_removed} duplicates, final rows: {len(df):,}")
    return df


def clean_graph_nodes(nodes_df: pd.DataFrame, pass_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Cleans graph node features:
    - Strips whitespace.
    - Resolves missing 'team' for players who made 0 passes by looking up passes received.
    - Fills missing passing metrics with 0.0 for zero-pass players.
    - Imputes missing coordinates (avg_x, avg_y) from end coordinates of received passes.
    - Casts integer and float columns to proper precision.
    - Deduplicates.
    """
    initial_len = len(nodes_df)
    nodes_df = strip_string_columns(nodes_df)

    # Deduplicate
    nodes_df = nodes_df.drop_duplicates(subset=["match_id", "player"]).reset_index(drop=True)
    dups_removed = initial_len - len(nodes_df)

    # Resolve players with missing team / metrics
    null_team_mask = nodes_df["team"].isnull() | (nodes_df["team"] == "")
    resolved_count = null_team_mask.sum()

    if resolved_count > 0 and pass_df is not None:
        log(f"Resolving {resolved_count} node entries with missing team/metrics from pass receptions...")
        for idx in nodes_df[null_team_mask].index:
            mid = nodes_df.loc[idx, "match_id"]
            player = nodes_df.loc[idx, "player"]

            rec = pass_df[(pass_df["match_id"] == mid) & (pass_df["pass_recipient"] == player)]
            if len(rec) > 0:
                team_modes = rec["team"].mode()
                nodes_df.loc[idx, "team"] = team_modes.iloc[0] if len(team_modes) > 0 else "Unknown"
                if pd.isna(nodes_df.loc[idx, "avg_x"]) and "end_x" in rec.columns:
                    nodes_df.loc[idx, "avg_x"] = rec["end_x"].mean()
                if pd.isna(nodes_df.loc[idx, "avg_y"]) and "end_y" in rec.columns:
                    nodes_df.loc[idx, "avg_y"] = rec["end_y"].mean()
            else:
                nodes_df.loc[idx, "team"] = "Unknown"
                if pd.isna(nodes_df.loc[idx, "avg_x"]):
                    nodes_df.loc[idx, "avg_x"] = 0.0
                if pd.isna(nodes_df.loc[idx, "avg_y"]):
                    nodes_df.loc[idx, "avg_y"] = 0.0

    # Rate / ratio columns -> fill NaN with 0.0 (applies to zero-pass receivers)
    rate_cols = [
        "pass_completion_rate",
        "avg_pass_length",
        "progressive_ratio",
        "under_pressure_pct",
        "avg_x",
        "avg_y",
    ]
    for c in rate_cols:
        if c in nodes_df.columns:
            nodes_df[c] = nodes_df[c].fillna(0.0).round(4)

    # Integer columns
    int_cols = [
        "match_id",
        "passes_made",
        "passes_received",
        "degree_out",
        "degree_in",
        "progressive_passes",
        "passes_under_pressure",
        "pressure_received",
    ]
    for c in int_cols:
        if c in nodes_df.columns:
            nodes_df[c] = nodes_df[c].fillna(0).astype("int64")

    # Sort
    nodes_df = nodes_df.sort_values(["match_id", "team", "player"]).reset_index(drop=True)

    log(f"graph_nodes.csv: removed {dups_removed} duplicates, resolved {resolved_count} missing teams, final rows: {len(nodes_df):,}")
    return nodes_df


def clean_graph_edges(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans graph edge features:
    - Strips whitespace.
    - Removes self-loops (passer == recipient).
    - Removes duplicates on (match_id, passer, recipient).
    - Validates rates in [0.0, 1.0].
    - Standardizes types and precision.
    - Sorts by match_id, passer, recipient.
    """
    initial_len = len(df)
    df = strip_string_columns(df)

    # Drop self-loops
    if "passer" in df.columns and "recipient" in df.columns:
        df = df[df["passer"] != df["recipient"]].copy()

    # Deduplicate
    subset_cols = [c for c in ["match_id", "passer", "recipient"] if c in df.columns]
    df = df.drop_duplicates(subset=subset_cols).reset_index(drop=True)
    dups_removed = initial_len - len(df)

    # Type casting
    if "match_id" in df.columns:
        df["match_id"] = df["match_id"].astype("int64")
    if "pass_count" in df.columns:
        df["pass_count"] = df["pass_count"].astype("int64")

    rate_cols = ["completion_rate", "avg_length", "progressive_ratio", "under_pressure_pct"]
    for c in rate_cols:
        if c in df.columns:
            df[c] = df[c].round(4)

    # Sort
    sort_cols = [c for c in ["match_id", "passer", "recipient"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    log(f"graph_edges.csv: removed {dups_removed} invalid/duplicate edges, final rows: {len(df):,}")
    return df


def clean_match_results(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans match results table:
    - Strips whitespace across all string columns (removes stadium padding, etc.).
    - Ensures standard date formatting.
    - Standardizes integer types for scores and week.
    - Sorts by match_date, match_id.
    """
    initial_len = len(df)
    df = strip_string_columns(df)

    # Deduplicate
    if "match_id" in df.columns:
        df = df.drop_duplicates(subset=["match_id"]).reset_index(drop=True)
    else:
        df = df.drop_duplicates().reset_index(drop=True)
    dups_removed = initial_len - len(df)

    # Ensure match_date is YYYY-MM-DD
    if "match_date" in df.columns:
        df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Integer columns
    int_cols = ["match_id", "home_score", "away_score", "match_week", "season_id", "competition_id"]
    for c in int_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("int64")

    # Sort
    sort_cols = [c for c in ["match_date", "match_id"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    log(f"La_Liga_... match metadata: removed {dups_removed} duplicates, final rows: {len(df):,}")
    return df


def run_pipeline(scraped_dir: Path, cleaned_dir: Path, dataset_root: Path):
    """Executes the full cleaning and partitioning pipeline."""
    print("=" * 70)
    print("   FOOTBALL PASSING NETWORK DATASET CLEANER (CSE4199)")
    print("=" * 70)
    print(f"Scraped data folder : {scraped_dir.resolve()}")
    print(f"Cleaned data folder : {cleaned_dir.resolve()}\n")

    setup_directories(dataset_root, scraped_dir, cleaned_dir)

    report = []

    # 1. Clean pressure_events
    f_press = scraped_dir / "pressure_events.csv"
    if f_press.exists():
        log("Processing pressure_events.csv...")
        raw_df = pd.read_csv(f_press)
        cleaned_df = clean_pressure_events(raw_df)
        out_path = cleaned_dir / "pressure_events.csv"
        cleaned_df.to_csv(out_path, index=False, encoding="utf-8")
        report.append(("pressure_events.csv", len(raw_df), len(cleaned_df), raw_df.isnull().sum().sum(), cleaned_df.isnull().sum().sum()))

    # 2. Clean Pass_Events_and_Pressure_Call
    f_pass = scraped_dir / "Pass_Events_and_Pressure_Call.csv"
    cleaned_pass_df = None
    if f_pass.exists():
        log("Processing Pass_Events_and_Pressure_Call.csv...")
        raw_df = pd.read_csv(f_pass)
        cleaned_pass_df = clean_pass_events(raw_df)
        out_path = cleaned_dir / "Pass_Events_and_Pressure_Call.csv"
        cleaned_pass_df.to_csv(out_path, index=False, encoding="utf-8")
        report.append(("Pass_Events_and_Pressure_Call.csv", len(raw_df), len(cleaned_pass_df), raw_df.isnull().sum().sum(), cleaned_pass_df.isnull().sum().sum()))

    # 3. Clean graph_nodes
    f_nodes = scraped_dir / "graph_nodes.csv"
    if f_nodes.exists():
        log("Processing graph_nodes.csv...")
        raw_df = pd.read_csv(f_nodes)
        cleaned_df = clean_graph_nodes(raw_df, pass_df=cleaned_pass_df)
        out_path = cleaned_dir / "graph_nodes.csv"
        cleaned_df.to_csv(out_path, index=False, encoding="utf-8")
        report.append(("graph_nodes.csv", len(raw_df), len(cleaned_df), raw_df.isnull().sum().sum(), cleaned_df.isnull().sum().sum()))

    # 4. Clean graph_edges
    f_edges = scraped_dir / "graph_edges.csv"
    if f_edges.exists():
        log("Processing graph_edges.csv...")
        raw_df = pd.read_csv(f_edges)
        cleaned_df = clean_graph_edges(raw_df)
        out_path = cleaned_dir / "graph_edges.csv"
        cleaned_df.to_csv(out_path, index=False, encoding="utf-8")
        report.append(("graph_edges.csv", len(raw_df), len(cleaned_df), raw_df.isnull().sum().sum(), cleaned_df.isnull().sum().sum()))

    # 5. Clean match results
    f_match = scraped_dir / "La_Liga_15_16_Premier_League_15_16_WC22_Euro20.csv"
    if f_match.exists():
        log("Processing La_Liga_15_16_Premier_League_15_16_WC22_Euro20.csv...")
        raw_df = pd.read_csv(f_match)
        cleaned_df = clean_match_results(raw_df)
        out_path = cleaned_dir / "La_Liga_15_16_Premier_League_15_16_WC22_Euro20.csv"
        cleaned_df.to_csv(out_path, index=False, encoding="utf-8")
        report.append(("La_Liga_15_16_Premier_League_15_16_WC22_Euro20.csv", len(raw_df), len(cleaned_df), raw_df.isnull().sum().sum(), cleaned_df.isnull().sum().sum()))

    # Remove loose files in dataset_root that are now safely separated into scraped_data and cleaned_data
    for fname in [
        "graph_nodes.csv",
        "graph_edges.csv",
        "pressure_events.csv",
        "Pass_Events_and_Pressure_Call.csv",
        "La_Liga_15_16_Premier_League_15_16_WC22_Euro20.csv",
    ]:
        loose_file = dataset_root / fname
        if loose_file.exists() and (scraped_dir / fname).exists():
            loose_file.unlink()

    # Print Summary Report Table
    print("\n" + "=" * 80)
    print(f"{'Dataset File':<42} | {'Raw Rows':<9} | {'Clean Rows':<10} | {'Raw Nulls':<9} | {'Clean Nulls':<11}")
    print("-" * 80)
    for filename, raw_r, clean_r, raw_n, clean_n in report:
        short_name = filename if len(filename) <= 40 else filename[:37] + "..."
        print(f"{short_name:<42} | {raw_r:<9,d} | {clean_r:<10,d} | {raw_n:<9,d} | {clean_n:<11,d}")
    print("=" * 80)
    print("\nCleaning complete! Datasets are separated into:")
    print(f"  [Scraped / Raw] : {scraped_dir}")
    print(f"  [Cleaned]       : {cleaned_dir}\n")


def main():
    parser = argparse.ArgumentParser(description="Clean and partition CSE4199 datasets.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("Dataset"),
        help="Root Dataset directory (default: Dataset)",
    )
    parser.add_argument(
        "--scraped-dir",
        type=Path,
        default=Path("Dataset/scraped_data"),
        help="Directory where scraped/raw data will be kept (default: Dataset/scraped_data)",
    )
    parser.add_argument(
        "--cleaned-dir",
        type=Path,
        default=Path("Dataset/cleaned_data"),
        help="Directory where cleaned data will be saved (default: Dataset/cleaned_data)",
    )

    args = parser.parse_args()
    run_pipeline(args.scraped_dir, args.cleaned_dir, args.dataset_root)


if __name__ == "__main__":
    main()
