"""
Pressing Intelligence Dashboard
===============================
CSE 4199 Thesis: Graph-Based Vulnerability Analysis of Passing Networks

Run:   streamlit run dashboard.py
Needs: results/ produced by phase2_graph_analysis.py and phase3_validation.py

  1. Pitch map of a team's passing network, players coloured by TCS or PVS
  2. Click players (or pick them in the combo box) to press them out of the
     game and watch the network degrade
  3. Side-by-side comparison of two teams' vulnerability profiles

The pitch, the metric tiles and the target list are one custom component
(pitch_component.py) so that a click is drawn at once and confirmed by the
exact graph computation a moment later.
"""

import json
import math

import pandas as pd
import streamlit as st

import network_core as nc
from pitch_component import press_pitch

st.set_page_config(page_title="Pressing Intelligence Dashboard", layout="wide")


@st.cache_data
def load():
    passes = nc.load_passes()
    pm = pd.read_csv(nc.RESULTS_DIR / "player_match_scores.csv")
    with open(nc.RESULTS_DIR / "results_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    return passes, pm, summary


passes, pm, summary = load()
WEIGHTS = summary["tcs_weights"]


@st.cache_data
def team_table():
    return (passes.groupby(["competition_label", "team"])["match_id"].nunique()
            .reset_index(name="matches").sort_values(["matches", "team"], ascending=[False, True])
            .reset_index(drop=True))


@st.cache_resource
def analyse(comp: str, team: str, match_id):
    """Network of the main eleven plus every per-player score the page shows."""
    tp = passes[(passes["competition_label"] == comp) & (passes["team"] == team)]
    if match_id is not None:
        tp = tp[tp["match_id"] == match_id]
    n_matches = tp["match_id"].nunique()
    G_all = nc.build_graph(tp, max(nc.MIN_PASS_THRESHOLD, n_matches))
    df = nc.player_table(tp).set_index("player").join(nc.centralities(G_all)).join(nc.node_removal(G_all))
    for c in nc.CENTRALITIES:
        df[c + "_norm"] = nc.minmax(df[c])
    df["tcs"] = sum(WEIGHTS[c] * df[c + "_norm"] for c in nc.CENTRALITIES)
    df["pvs_norm"] = nc.minmax(df["pvs"])
    sub = pm[(pm["competition_label"] == comp) & (pm["team"] == team)]
    if match_id is not None:
        sub = sub[sub["match_id"] == match_id]
    df["pressed_per_match"] = (sub.groupby("player")["pressed_events"].sum() / max(n_matches, 1))
    df["pressed_per_match"] = df["pressed_per_match"].fillna(0)

    main = df.sort_values("involvement", ascending=False).head(11).index
    G = G_all.subgraph(main).copy()
    df = df.loc[main].copy()
    # loss when this one player leaves the eleven: the instant estimate the page shows on click
    df["loss_xi"] = nc.node_removal(G)["eff_loss"]
    return G, df.sort_values("tcs", ascending=False).reset_index(), n_matches


def clean(h: dict) -> dict:
    return {k: (None if isinstance(v, float) and math.isnan(v) else float(v)) for k, v in h.items()}


def payload(G, df, removed, colour, ack, ident):
    pairs = {}
    for u, v, d in G.edges(data=True):
        k = tuple(sorted((u, v)))
        pairs[k] = pairs.get(k, 0) + d["weight"]
    H = G.copy()
    H.remove_nodes_from(removed)
    players = [dict(
        name=r.player, label=r.player.split()[-1], x=float(r.avg_x), y=float(r.avg_y),
        inv=int(r.involvement), tcs=float(r.tcs), pvs=float(r.pvs_norm), loss=float(r.loss_xi),
        pressed=float(r.pressed_per_match),
        parts={c: float(getattr(r, c + "_norm")) for c in nc.CENTRALITIES},
    ) for r in df.itertuples()]
    return dict(id=ident, players=players, edges=[dict(u=u, v=v, w=int(w)) for (u, v), w in pairs.items()],
                removed=list(removed), ack=ack, colour=colour, weights=WEIGHTS,
                base=clean(nc.health(G)), after=clean(nc.health(H)))


@st.fragment
def team_panel(slot: str, default: int):
    table = team_table()
    labels = [f"{r.team} | {r.competition_label} ({r.matches} matches)" for r in table.itertuples()]
    c1, c2, c3 = st.columns([5, 5, 2], vertical_alignment="bottom")
    choice = c1.selectbox("Team", labels, index=default, key=f"team_{slot}",
                          help="Combo box: click and type any part of a team or competition name to filter.")
    row = table.iloc[labels.index(choice)]
    tm = (passes[(passes["competition_label"] == row.competition_label) & (passes["team"] == row.team)]
          [["match_id", "match_date", "home_team", "away_team"]].drop_duplicates().sort_values("match_date"))
    mlabels = ["Whole season (pooled network)"] + [
        f"{r.match_date}  {r.home_team} v {r.away_team}" for r in tm.itertuples()]
    msel = c2.selectbox("Scope", mlabels, key=f"match_{slot}_{choice}",
                        help="Type a date or an opponent to jump to a single match.")
    mid = None if msel == mlabels[0] else int(tm.iloc[mlabels.index(msel) - 1]["match_id"])
    with c3.popover("Display", width="stretch"):
        colour = st.radio("Colour players by", ["tcs", "pvs"], key=f"col_{slot}",
                          format_func=lambda c: {"tcs": "Tactical Criticality Score (centrality)",
                                                 "pvs": "Pressing Vulnerability Score (node removal)"}[c])

    G, df, _ = analyse(row.competition_label, row.team, mid)
    scope = f"{slot}|{row.competition_label}|{row.team}|{mid}"
    ms_key, comp_key, seq_key = f"rm|{scope}", f"pitch|{scope}", f"seq|{scope}"
    names = list(df["player"])

    def from_pitch():
        """A click on the pitch arrived: mirror it into the combo box."""
        state = st.session_state.get(comp_key)
        val = getattr(state, "removed", None) if state is not None else None
        if val is None and isinstance(state, dict):
            val = state.get("removed")
        if val:
            st.session_state[ms_key] = [p for p in val["players"] if p in names]
            st.session_state[seq_key] = int(val["seq"])

    removed = st.multiselect("Press these players out of the game", names, key=ms_key,
                             placeholder="Click a player on the pitch, or type a name here")
    press_pitch(key=comp_key, on_removed_change=from_pitch,
                data=payload(G, df, removed, colour, st.session_state.get(seq_key, 0), scope))


st.title("Pressing Intelligence Dashboard")
st.caption("Which player should you press? Each team's passing network, scored by how much it depends on "
           "every player. Click a player to press them out of the game.")
compare = st.toggle("Compare two teams side by side", value=False)
if compare:
    a, b = st.columns(2, gap="large")
    with a:
        team_panel("a", 0)
    with b:
        team_panel("b", 1)
else:
    team_panel("a", 0)

with st.expander("How these scores are computed"):
    st.markdown(
        "**Network.** Players are nodes; a line joins two players who completed passes to each other, "
        "thicker for more passes. The map shows the eleven most involved players, attacking left to right.\n\n"
        "**Tactical Criticality Score (TCS).** A weighted sum of four centralities, each scaled 0 to 1 within "
        "the team: " + ", ".join(f"{k} {v:.2f}" for k, v in WEIGHTS.items()) + ". "
        "The weights were learned from how often players are actually pressed, cross-validated by match.\n\n"
        "**Pressing Vulnerability Score (PVS).** Remove the player, then measure the relative loss in global "
        "efficiency, path length, clustering and connectivity. PVS is the mean of the four, scaled 0 to 1.\n\n"
        "**Pressing a player** deletes them from the network. The tiles show the exact figures for whoever is "
        "pressed out; while the exact figure is on its way, efficiency shows an estimate marked with ≈.")
    v = summary["validation"]["tcs_oof"]
    st.caption(f"Validation across 240 networks: TCS matches real pressing at a within-team Spearman ρ of "
               f"{v['mean_rho']:.2f} on unseen matches; removing the top-TCS player costs "
               f"{summary['targeted_vs_random']['mean_eff_loss_top_tcs']:.1%} of efficiency against "
               f"{summary['targeted_vs_random']['mean_eff_loss_random_starter']:.1%} for a random starter.")
