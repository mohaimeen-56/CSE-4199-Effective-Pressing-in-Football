"""
network_core.py - shared building blocks for the passing-network vulnerability analysis.

CSE 4199 | Graph-Based Vulnerability Analysis of Passing Networks

Everything that phase 2 (graph analysis), phase 3 (validation) and the dashboard
have in common lives here, so the three always agree on how a network is built
and how a "pressed" player is measured.
"""

from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "Dataset" / "cleaned_data"
RESULTS_DIR = ROOT / "results"
FIG_DIR = RESULTS_DIR / "figures"

PASS_FILE = DATA_DIR / "Pass_Events_and_Pressure_Call.csv"
PRESSURE_FILE = DATA_DIR / "pressure_events.csv"
MATCH_FILE = DATA_DIR / "La_Liga_15_16_Premier_League_15_16_WC22_Euro20.csv"

MIN_PASS_THRESHOLD = 2      # an edge needs at least this many completed passes
PRESS_WINDOW = (-2, 5)      # seconds around a pressure event searched for the pressed pass

CENTRALITIES = ["degree", "betweenness", "closeness", "eigenvector"]
PVS_PARTS = ["eff_loss", "path_increase", "clustering_loss", "connectivity_loss"]


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def load_passes() -> pd.DataFrame:
    p = pd.read_csv(PASS_FILE)
    p["t"] = p["minute"] * 60 + p["second"]
    p["pass_recipient"] = p["pass_recipient"].where(p["pass_recipient"].notna(), None)
    return p


def load_pressures() -> pd.DataFrame:
    pr = pd.read_csv(PRESSURE_FILE)
    pr["t"] = pr["minute"] * 60 + pr["second"]
    return pr


def load_matches() -> pd.DataFrame:
    m = pd.read_csv(MATCH_FILE)
    return m[["match_id", "home_team", "away_team", "home_score", "away_score"]]


# --------------------------------------------------------------------------
# Validation label: how often was each player pressed?
# --------------------------------------------------------------------------
def pressed_event_counts(passes: pd.DataFrame, pressures: pd.DataFrame) -> pd.DataFrame:
    """
    StatsBomb 'Pressure' events name the player APPLYING pressure, not the one
    receiving it.  To recover the target we attribute each pressure event to the
    opposing player who releases the ball closest in time to it (inside
    PRESS_WINDOW seconds, same period).  Returns match_id, player, pressed_events.
    """
    out = []
    lo, hi = PRESS_WINDOW
    for (mid, period), pr in pressures.groupby(["match_id", "period"]):
        mp = passes[(passes["match_id"] == mid) & (passes["period"] == period)]
        for team, prt in pr.groupby("team"):
            opp = mp[mp["team"] != team].sort_values("t")
            if opp.empty:
                continue
            ot = opp["t"].to_numpy()
            oplayer = opp["player"].to_numpy()
            for t in prt["t"].to_numpy():
                i0 = np.searchsorted(ot, t + lo, side="left")
                i1 = np.searchsorted(ot, t + hi, side="right")
                if i1 <= i0:
                    continue
                # nearest pass in time; ties resolved toward the pass after the press
                cand = ot[i0:i1] - t
                j = i0 + int(np.argmin(np.abs(cand - 0.5)))
                out.append((mid, oplayer[j]))
    df = pd.DataFrame(out, columns=["match_id", "player"])
    return df.groupby(["match_id", "player"]).size().reset_index(name="pressed_events")


# --------------------------------------------------------------------------
# Graph construction
# --------------------------------------------------------------------------
def build_graph(team_passes: pd.DataFrame, min_pass: int = MIN_PASS_THRESHOLD) -> nx.DiGraph:
    """
    Directed weighted passing network of ONE team (one match, or many matches
    pooled).  Nodes: every player who made or received a pass.  Edge u->v:
    completed passes from u to v, kept if count >= min_pass.
      weight = pass count          (strength of the connection)
      dist   = 1 / weight          (cost of using it, for shortest paths)
    """
    done = team_passes[team_passes["is_complete"] & team_passes["pass_recipient"].notna()]
    done = done[done["player"] != done["pass_recipient"]]
    players = set(team_passes["player"]) | set(done["pass_recipient"])
    G = nx.DiGraph()
    G.add_nodes_from(sorted(players))
    counts = done.groupby(["player", "pass_recipient"]).size()
    for (u, v), w in counts.items():
        if w >= min_pass:
            G.add_edge(u, v, weight=int(w), dist=1.0 / w)
    return G


def player_table(team_passes: pd.DataFrame) -> pd.DataFrame:
    """Per-player descriptive features for one team (match or pooled)."""
    made = team_passes.groupby("player").agg(
        passes_made=("is_complete", "size"),
        passes_completed=("is_complete", "sum"),
        pressed_passes=("under_pressure", "sum"),
        avg_x=("loc_x", "mean"),
        avg_y=("loc_y", "mean"),
    )
    done = team_passes[team_passes["is_complete"] & team_passes["pass_recipient"].notna()]
    recv = done.groupby("pass_recipient").agg(
        passes_received=("is_complete", "size"),
        rx=("end_x", "mean"),
        ry=("end_y", "mean"),
    )
    t = made.join(recv, how="outer")
    t.index.name = "player"
    for c in ["passes_made", "passes_completed", "pressed_passes", "passes_received"]:
        t[c] = t[c].fillna(0).astype(int)
    t["avg_x"] = t["avg_x"].fillna(t["rx"])
    t["avg_y"] = t["avg_y"].fillna(t["ry"])
    t["involvement"] = t["passes_made"] + t["passes_received"]
    return t.drop(columns=["rx", "ry"]).reset_index()


# --------------------------------------------------------------------------
# Centrality
# --------------------------------------------------------------------------
def centralities(G: nx.DiGraph) -> pd.DataFrame:
    n = G.number_of_nodes()
    if n < 2:
        return pd.DataFrame(0.0, index=list(G.nodes()), columns=CENTRALITIES)
    deg = nx.degree_centrality(G)                                   # (in + out) / (n - 1)
    btw = nx.betweenness_centrality(G, weight="dist", normalized=True)
    clo = nx.closeness_centrality(G, distance="dist")               # inward, Wasserman-Faust
    try:
        eig = nx.eigenvector_centrality(G, weight="weight", max_iter=2000, tol=1e-8)
    except Exception:
        try:
            eig = nx.eigenvector_centrality_numpy(G, weight="weight")
            eig = {k: abs(v) for k, v in eig.items()}
        except Exception:
            eig = {k: 0.0 for k in G.nodes()}
    return pd.DataFrame({"degree": deg, "betweenness": btw,
                         "closeness": clo, "eigenvector": eig}).fillna(0.0)


# --------------------------------------------------------------------------
# Network health and node removal
# --------------------------------------------------------------------------
def global_efficiency(G: nx.DiGraph) -> float:
    """Mean of 1/d(u,v) over all ordered pairs; unreachable pairs contribute 0."""
    n = G.number_of_nodes()
    if n < 2:
        return 0.0
    total = 0.0
    for _, dists in nx.all_pairs_dijkstra_path_length(G, weight="dist"):
        total += sum(1.0 / d for d in dists.values() if d > 0)
    return total / (n * (n - 1))


def health(G: nx.DiGraph) -> dict:
    n = G.number_of_nodes()
    if n < 2:
        return dict(efficiency=0.0, path_length=np.nan, clustering=0.0,
                    connectivity=0.0, diameter=np.nan)
    scc = max(nx.strongly_connected_components(G), key=len)
    core = G.subgraph(scc)
    if len(scc) > 1:
        path_length = nx.average_shortest_path_length(core)      # hops
        diameter = nx.diameter(core)
    else:
        path_length, diameter = np.nan, np.nan
    return dict(
        efficiency=global_efficiency(G),
        path_length=path_length,
        clustering=nx.average_clustering(G.to_undirected()),
        connectivity=len(scc) / n,
        diameter=diameter,
    )


def _rel(before, after, loss=True):
    if before is None or np.isnan(before) or before == 0 or np.isnan(after):
        return 0.0 if (before is None or np.isnan(before) or before == 0) else 1.0
    d = (before - after) / before
    return d if loss else -d


def degradation(base: dict, after: dict) -> dict:
    """Relative damage in each health property (positive = network got worse)."""
    return dict(
        eff_loss=_rel(base["efficiency"], after["efficiency"]),
        path_increase=_rel(base["path_length"], after["path_length"], loss=False),
        clustering_loss=_rel(base["clustering"], after["clustering"]),
        connectivity_loss=_rel(base["connectivity"], after["connectivity"]),
        diameter_change=(0.0 if np.isnan(base["diameter"]) or np.isnan(after["diameter"])
                         else after["diameter"] - base["diameter"]),
    )


def node_removal(G: nx.DiGraph) -> pd.DataFrame:
    """
    Simulate pressing each player out of the game: delete the node, re-measure
    the network, record the damage.  PVS = mean of the four relative damages.
    """
    base = health(G)
    rows = {}
    for v in G.nodes():
        H = G.copy()
        H.remove_node(v)
        d = degradation(base, health(H))
        d["pvs"] = float(np.mean([d[k] for k in PVS_PARTS]))
        rows[v] = d
    return pd.DataFrame.from_dict(rows, orient="index")


def attack_curve(G: nx.DiGraph, order: list, steps: int) -> list:
    """Efficiency (relative to intact network) after removing order[:k], k=0..steps."""
    base = global_efficiency(G)
    H = G.copy()
    out = [1.0]
    for v in order[:steps]:
        H.remove_node(v)
        out.append(global_efficiency(H) / base if base > 0 else 0.0)
    return out


def minmax(s: pd.Series) -> pd.Series:
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng > 0 else s * 0.0
