"""
Pressing Intelligence Dashboard
===============================
CSE 4199 Thesis: Graph-Based Vulnerability Analysis of Passing Networks

Run:   streamlit run dashboard.py
Needs: results/ produced by phase2_graph_analysis.py and phase3_validation.py

  1. Pitch map of a team's passing network, players coloured by TCS or PVS
  2. "Press" any players out of the game and watch the network degrade
  3. Side-by-side comparison of two teams' vulnerability profiles
"""

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import network_core as nc

st.set_page_config(page_title="Pressing Intelligence Dashboard", layout="wide")
LINE = "#b9b8b2"


@st.cache_data
def load():
    passes = nc.load_passes()
    pm = pd.read_csv(nc.RESULTS_DIR / "player_match_scores.csv")
    with open(nc.RESULTS_DIR / "results_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    return passes, pm, summary


passes, pm, summary = load()
W = [summary["tcs_weights"][c] for c in nc.CENTRALITIES]


def team_options():
    t = (passes.groupby(["competition_label", "team"])["match_id"].nunique()
         .reset_index(name="matches").sort_values(["matches", "team"], ascending=[False, True]))
    return [f"{r.team} | {r.competition_label} ({r.matches} matches)" for r in t.itertuples()], t


@st.cache_data
def analyse(comp: str, team: str, match_id):
    tp = passes[(passes["competition_label"] == comp) & (passes["team"] == team)]
    if match_id is not None:
        tp = tp[tp["match_id"] == match_id]
    n_matches = tp["match_id"].nunique()
    thr = max(nc.MIN_PASS_THRESHOLD, n_matches)
    G = nc.build_graph(tp, thr)
    df = nc.player_table(tp).set_index("player").join(nc.centralities(G)).join(nc.node_removal(G))
    df["tcs"] = sum(w * nc.minmax(df[c]) for w, c in zip(W, nc.CENTRALITIES))
    df["pvs_norm"] = nc.minmax(df["pvs"])
    sub = pm[(pm["competition_label"] == comp) & (pm["team"] == team)]
    if match_id is not None:
        sub = sub[sub["match_id"] == match_id]
    df["pressed"] = sub.groupby("player")["pressed_events"].sum()
    df["pressed_per_match"] = (df["pressed"] / max(n_matches, 1)).fillna(0)
    main = df.sort_values("involvement", ascending=False).head(11).index
    G = G.subgraph(main).copy()
    return G, df.loc[main].reset_index(), n_matches


def pitch_figure(G, df, colour, removed, title):
    fig = go.Figure()
    shapes = [dict(type="rect", x0=0, y0=0, x1=120, y1=80), dict(type="line", x0=60, y0=0, x1=60, y1=80),
              dict(type="circle", x0=50, y0=30, x1=70, y1=50),
              dict(type="rect", x0=0, y0=18, x1=18, y1=62), dict(type="rect", x0=102, y0=18, x1=120, y1=62),
              dict(type="rect", x0=0, y0=30, x1=6, y1=50), dict(type="rect", x0=114, y0=30, x1=120, y1=50)]
    for s in shapes:
        s.update(line=dict(color=LINE, width=1.2), layer="below")
    pos = df.set_index("player")[["avg_x", "avg_y"]]
    wmax = max((d["weight"] for _, _, d in G.edges(data=True)), default=1)
    for u, v, d in G.edges(data=True):
        cut = u in removed or v in removed
        fig.add_trace(go.Scatter(
            x=[pos.at[u, "avg_x"], pos.at[v, "avg_x"]], y=[pos.at[u, "avg_y"], pos.at[v, "avg_y"]],
            mode="lines", hoverinfo="skip", showlegend=False,
            line=dict(width=0.5 + 5 * d["weight"] / wmax, dash="dot" if cut else "solid",
                      color="rgba(227,73,72,0.35)" if cut else f"rgba(110,110,105,{0.15 + 0.5 * d['weight'] / wmax:.2f})")))
    live = df[~df["player"].isin(removed)]
    dead = df[df["player"].isin(removed)]
    size = lambda d: 22 + 30 * d["involvement"] / df["involvement"].max()
    fig.add_trace(go.Scatter(
        x=live["avg_x"], y=live["avg_y"], mode="markers+text", text=live["player"].str.split().str[-1],
        textposition="bottom center", showlegend=False,
        marker=dict(size=size(live), color=live[colour], colorscale="Blues", cmin=0, cmax=1,
                    line=dict(color="white", width=2), colorbar=dict(title=colour.upper()[:3], thickness=12, len=0.6)),
        customdata=live[["player", "tcs", "pvs_norm", "eff_loss", "betweenness", "pressed_per_match"]],
        hovertemplate=("<b>%{customdata[0]}</b><br>TCS %{customdata[1]:.2f} | PVS %{customdata[2]:.2f}"
                       "<br>Efficiency lost if removed: %{customdata[3]:.1%}"
                       "<br>Betweenness %{customdata[4]:.3f}<br>Pressed %{customdata[5]:.1f} per match<extra></extra>")))
    if len(dead):
        fig.add_trace(go.Scatter(
            x=dead["avg_x"], y=dead["avg_y"], mode="markers+text", text=dead["player"].str.split().str[-1],
            textposition="bottom center", showlegend=False, hoverinfo="text",
            hovertext=dead["player"] + " (pressed out)",
            marker=dict(size=size(dead), color="rgba(0,0,0,0)", symbol="x-thin",
                        line=dict(color="#e34948", width=3))))
    fig.update_layout(title=title, shapes=shapes, height=520, margin=dict(l=10, r=10, t=50, b=10),
                      plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(range=[-3, 123], visible=False),
                      yaxis=dict(range=[83, -3], visible=False, scaleanchor="x"))
    return fig


def team_panel(key: str, default: int):
    labels, table = team_options()
    choice = st.selectbox("Team", labels, index=default, key=f"team_{key}")
    row = table.iloc[labels.index(choice)]
    tm = (passes[(passes["competition_label"] == row.competition_label) & (passes["team"] == row.team)]
          [["match_id", "match_date", "home_team", "away_team"]].drop_duplicates().sort_values("match_date"))
    mlabels = ["Whole season (pooled network)"] + [
        f"{r.match_date}  {r.home_team} v {r.away_team}" for r in tm.itertuples()]
    msel = st.selectbox("Scope", mlabels, key=f"match_{key}")
    mid = None if msel == mlabels[0] else int(tm.iloc[mlabels.index(msel) - 1]["match_id"])
    G, df, n = analyse(row.competition_label, row.team, mid)
    colour = st.radio("Colour players by", ["tcs", "pvs_norm"], horizontal=True, key=f"col_{key}",
                      format_func=lambda c: {"tcs": "Tactical Criticality Score",
                                             "pvs_norm": "Pressing Vulnerability Score"}[c])
    ranked = df.sort_values("tcs", ascending=False)
    removed = st.multiselect("Press these players out of the game", list(ranked["player"]), key=f"rm_{key}")
    st.plotly_chart(pitch_figure(G, df, colour, set(removed), row.team), width="stretch", key=f"fig_{key}")

    base = nc.health(G)
    H = G.copy()
    H.remove_nodes_from(removed)
    after = nc.health(H)
    c1, c2, c3, c4 = st.columns(4)
    pct = lambda a, b: f"{(a - b) / b:+.0%}" if b else "n/a"
    c1.metric("Global efficiency", f"{after['efficiency']:.2f}", pct(after["efficiency"], base["efficiency"]) if removed else None)
    c2.metric("Avg path length", f"{after['path_length']:.2f}",
              pct(after["path_length"], base["path_length"]) if removed else None, delta_color="inverse")
    c3.metric("Clustering", f"{after['clustering']:.2f}", pct(after["clustering"], base["clustering"]) if removed else None)
    c4.metric("Connected core", f"{after['connectivity']:.0%}",
              pct(after["connectivity"], base["connectivity"]) if removed else None)

    st.caption("Recommended pressing targets (highest TCS first)")
    show = ranked[["player", "tcs", "pvs_norm", "eff_loss", "betweenness", "involvement", "pressed_per_match"]].copy()
    show.columns = ["Player", "TCS", "PVS", "Efficiency lost if removed", "Betweenness", "Pass involvement",
                    "Pressed per match"]
    st.dataframe(show.style.format({"TCS": "{:.2f}", "PVS": "{:.2f}", "Efficiency lost if removed": "{:.1%}",
                                    "Betweenness": "{:.3f}", "Pressed per match": "{:.1f}"}),
                 hide_index=True, width="stretch")


st.title("Pressing Intelligence Dashboard")
st.caption("Graph-based vulnerability analysis of passing networks. Node size = pass involvement; "
           "line width = completed passes; teams attack left to right. "
           f"TCS weights: " + ", ".join(f"{k} {v:.2f}" for k, v in summary["tcs_weights"].items()))
compare = st.toggle("Compare two teams side by side", value=False)
if compare:
    a, b = st.columns(2)
    with a:
        team_panel("a", 0)
    with b:
        team_panel("b", 1)
else:
    team_panel("a", 0)
