"""
Phase 2 - Core Graph Analysis
=============================
CSE 4199 Thesis: Graph-Based Vulnerability Analysis of Passing Networks

For every team in every match (and for every team pooled over its season):
  1. build the directed weighted passing network from completed passes
  2. compute degree / betweenness / closeness / eigenvector centrality
  3. remove each player in turn and measure network degradation -> PVS
  4. attach the validation labels (how often the player was actually pressed)

Outputs (results/):
  player_match_metrics.csv   one row per player per match
  player_season_metrics.csv  one row per player per team-season (pooled network)
  team_match_health.csv      one row per team per match (intact-network properties)

Usage:  python phase2_graph_analysis.py
"""

import pandas as pd

import network_core as nc

MIN_PLAYERS = 7          # skip degenerate team-match networks
MIN_SEASON_MATCHES = 5   # a "season network" needs at least this many matches


def analyse_team(team_passes: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    G = nc.build_graph(team_passes)
    feats = nc.player_table(team_passes).set_index("player")
    out = feats.join(nc.centralities(G)).join(nc.node_removal(G))
    for c in nc.CENTRALITIES:
        out[c + "_norm"] = nc.minmax(out[c])
    out["pvs_norm"] = nc.minmax(out["pvs"])
    h = nc.health(G)
    h.update(n_players=G.number_of_nodes(), n_edges=G.number_of_edges(),
             total_passes=int(team_passes["is_complete"].sum()))
    return out.reset_index(), h


def main():
    nc.RESULTS_DIR.mkdir(exist_ok=True)
    passes = nc.load_passes()
    pressures = nc.load_pressures()
    print(f"Passes: {len(passes):,} | pressure events: {len(pressures):,} | "
          f"matches: {passes['match_id'].nunique()}")

    pressed = nc.pressed_event_counts(passes, pressures)
    print(f"Pressure events attributed to a pressed player: {pressed['pressed_events'].sum():,} "
          f"({pressed['pressed_events'].sum() / len(pressures):.1%})")
    applied = (pressures.groupby(["match_id", "player"]).size()
               .reset_index(name="pressures_applied"))

    # ---- per match --------------------------------------------------------
    rows, health_rows = [], []
    meta_cols = ["match_id", "competition_label", "home_team", "away_team", "match_date"]
    for (mid, team), tp in passes.groupby(["match_id", "team"]):
        if tp["player"].nunique() < MIN_PLAYERS:
            continue
        df, h = analyse_team(tp)
        meta = tp.iloc[0][meta_cols].to_dict()
        for k, v in meta.items():
            df[k] = v
        df["team"] = team
        rows.append(df)
        health_rows.append({**meta, "team": team, **h})
    pm = pd.concat(rows, ignore_index=True)
    pm = pm.merge(pressed, on=["match_id", "player"], how="left")
    pm = pm.merge(applied, on=["match_id", "player"], how="left")
    pm[["pressed_events", "pressures_applied"]] = (
        pm[["pressed_events", "pressures_applied"]].fillna(0).astype(int))
    lead = meta_cols + ["team", "player"]
    pm = pm[lead + [c for c in pm.columns if c not in lead]]
    pm.to_csv(nc.RESULTS_DIR / "player_match_metrics.csv", index=False)
    pd.DataFrame(health_rows).to_csv(nc.RESULTS_DIR / "team_match_health.csv", index=False)
    print(f"Team-match networks analysed: {len(health_rows)} | player rows: {len(pm):,}")

    # ---- per season (pooled network) --------------------------------------
    srows = []
    for (comp, team), tp in passes.groupby(["competition_label", "team"]):
        n_matches = tp["match_id"].nunique()
        if n_matches < MIN_SEASON_MATCHES:
            continue
        # scale the edge threshold with the number of matches pooled
        old = nc.MIN_PASS_THRESHOLD
        nc.MIN_PASS_THRESHOLD = max(old, n_matches)
        G = nc.build_graph(tp, nc.MIN_PASS_THRESHOLD)
        feats = nc.player_table(tp).set_index("player")
        df = feats.join(nc.centralities(G)).join(nc.node_removal(G))
        nc.MIN_PASS_THRESHOLD = old
        for c in nc.CENTRALITIES:
            df[c + "_norm"] = nc.minmax(df[c])
        df["pvs_norm"] = nc.minmax(df["pvs"])
        df = df.reset_index()
        df["competition_label"], df["team"], df["matches"] = comp, team, n_matches
        apps = tp.groupby("player")["match_id"].nunique().rename("appearances")
        df = df.merge(apps, on="player", how="left")
        ev = (pm[(pm["competition_label"] == comp) & (pm["team"] == team)]
              .groupby("player")["pressed_events"].sum())
        df = df.merge(ev, on="player", how="left")
        srows.append(df)
    ps = pd.concat(srows, ignore_index=True)
    ps.to_csv(nc.RESULTS_DIR / "player_season_metrics.csv", index=False)
    print("Season networks:", ps.groupby(["competition_label", "team"]).ngroups)
    print("Done -> results/")


if __name__ == "__main__":
    main()
