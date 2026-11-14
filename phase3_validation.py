"""
Phase 3 - TCS, Validation and Attack Simulation
===============================================
CSE 4199 Thesis: Graph-Based Vulnerability Analysis of Passing Networks

  A. Learn Tactical Criticality Score (TCS) weights with scikit-learn,
     cross-validated by match so the score is always tested on unseen matches.
  B. Validate every metric against how often players were actually pressed
     (Spearman, within team-match, with and without controlling for ball volume).
  C. Targeted vs random node removal (RQ2) and sequential attack curves.
  D. Do opponents really concentrate pressure on high-TCS players?
  E. Sensitivity to the edge threshold; team-level link to match outcome.
  F. Figures -> results/figures, numbers -> results/results_summary.json

Usage:  python phase3_validation.py      (run phase2_graph_analysis.py first)
"""

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold

import network_core as nc

RNG = np.random.default_rng(4199)
GROUP = ["match_id", "team"]
LABEL = "pressed_events"          # primary validation label
LABEL2 = "pressed_passes"         # secondary: StatsBomb under_pressure flag on passes
FEATS = [c + "_norm" for c in nc.CENTRALITIES]
N_RANDOM_ORDERS = 20
ATTACK_STEPS = 5

# chart style (light surface, fixed categorical order)
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
    "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False,
})
NICE = {"degree": "Degree", "betweenness": "Betweenness", "closeness": "Closeness",
        "eigenvector": "Eigenvector", "pvs": "PVS (node removal)", "tcs_oof": "TCS (out-of-fold)",
        "involvement": "Pass volume (baseline)"}


# --------------------------------------------------------------------------
# statistics helpers
# --------------------------------------------------------------------------
def group_rho(df, x, y):
    """Spearman rho inside every team-match network."""
    out = []
    for _, g in df.groupby(GROUP):
        if g[x].nunique() > 1 and g[y].nunique() > 1:
            out.append(stats.spearmanr(g[x], g[y])[0])
    return np.array(out)


def summarise(rhos):
    boot = [RNG.choice(rhos, len(rhos)).mean() for _ in range(2000)]
    w = stats.wilcoxon(rhos)
    return dict(mean_rho=float(rhos.mean()), ci_low=float(np.percentile(boot, 2.5)),
                ci_high=float(np.percentile(boot, 97.5)), share_positive=float((rhos > 0).mean()),
                n_networks=int(len(rhos)), wilcoxon_p=float(w.pvalue))


def pct_rank(df, col):
    return df.groupby(GROUP)[col].rank(pct=True)


def partial_corr(x, y, z):
    """Correlation of x and y after removing what each shares linearly with z."""
    rx = x - np.polyval(np.polyfit(z, x, 1), z)
    ry = y - np.polyval(np.polyfit(z, y, 1), z)
    r, p = stats.pearsonr(rx, ry)
    return float(r), float(p)


def fit_weights(df):
    y = pct_rank(df, LABEL)
    m = LinearRegression(positive=True).fit(df[FEATS], y)
    w = np.clip(m.coef_, 0, None)
    return w / w.sum() if w.sum() > 0 else np.full(len(FEATS), 1 / len(FEATS))


# --------------------------------------------------------------------------
def main():
    nc.FIG_DIR.mkdir(parents=True, exist_ok=True)
    pm = pd.read_csv(nc.RESULTS_DIR / "player_match_metrics.csv")
    ps = pd.read_csv(nc.RESULTS_DIR / "player_season_metrics.csv")
    th = pd.read_csv(nc.RESULTS_DIR / "team_match_health.csv")
    S = {"dataset": dict(
        matches=int(pm["match_id"].nunique()), team_match_networks=int(pm.groupby(GROUP).ngroups),
        player_match_rows=int(len(pm)), unique_players=int(pm["player"].nunique()),
        unique_teams=int(pm["team"].nunique()),
        matches_by_competition=pm.groupby("competition_label")["match_id"].nunique().to_dict(),
        mean_players_per_network=float(th["n_players"].mean()),
        mean_edges_per_network=float(th["n_edges"].mean()),
        mean_clustering=float(th["clustering"].mean()),
        mean_path_length=float(th["path_length"].mean()),
        mean_diameter=float(th["diameter"].mean()),
        min_pass_threshold=nc.MIN_PASS_THRESHOLD,
        label_agreement_rho=float(stats.spearmanr(pm[LABEL], pm[LABEL2])[0]),
        old_label_vs_true_rho=float(stats.spearmanr(pm["pressures_applied"], pm[LABEL])[0]),
    )}

    # ---------------- A. TCS weights -------------------------------------
    pm["tcs_equal"] = pm[FEATS].mean(axis=1)
    pm["tcs_oof"] = np.nan
    fold_w = []
    for tr, te in GroupKFold(n_splits=5).split(pm, groups=pm["match_id"]):
        w = fit_weights(pm.iloc[tr])
        fold_w.append(w)
        pm.loc[pm.index[te], "tcs_oof"] = pm.iloc[te][FEATS].to_numpy() @ w
    W = fit_weights(pm)
    pm["tcs"] = pm[FEATS].to_numpy() @ W
    pm["tcs_rank"] = pm.groupby(GROUP)["tcs"].rank(ascending=False, method="first").astype(int)
    ps["tcs"] = ps[FEATS].to_numpy() @ W
    S["tcs_weights"] = dict(zip(nc.CENTRALITIES, map(float, W)))
    S["tcs_weight_fold_sd"] = dict(zip(nc.CENTRALITIES, map(float, np.std(fold_w, axis=0))))

    # hold-out by competition: learn without the Premier League, test on it
    is_pl = pm["competition_label"].str.contains("Premier")
    w_nopl = fit_weights(pm[~is_pl])
    pm["tcs_nopl"] = pm[FEATS].to_numpy() @ w_nopl
    S["holdout_premier_league"] = dict(
        weights=dict(zip(nc.CENTRALITIES, map(float, w_nopl))),
        **summarise(group_rho(pm[is_pl], "tcs_nopl", LABEL)))

    # ---------------- B. validation --------------------------------------
    metrics = nc.CENTRALITIES + ["pvs", "tcs_oof", "involvement"]
    starters = pm[pm.groupby(GROUP)["involvement"].rank(ascending=False, method="first") <= 11]
    rate = pm[pm["involvement"] >= 20].copy()
    rate["press_rate"] = rate[LABEL] / rate["involvement"]
    val = {}
    for m in metrics:
        r = summarise(group_rho(pm, m, LABEL))
        pooled = stats.spearmanr(pm[m], pm[LABEL])
        r["pooled_rho"], r["pooled_p"] = float(pooled[0]), float(pooled[1])
        r["mean_rho_pressed_passes"] = float(group_rho(pm, m, LABEL2).mean())
        r["mean_rho_starters_only"] = float(group_rho(starters, m, LABEL).mean())
        if m != "involvement":
            pr, pp = partial_corr(pct_rank(pm, m).to_numpy(), pct_rank(pm, LABEL).to_numpy(),
                                  pct_rank(pm, "involvement").to_numpy())
            r["partial_rho_given_volume"], r["partial_p"] = pr, pp
            rr = group_rho(rate, m, "press_rate")
            r["mean_rho_press_rate"] = float(rr.mean())
            r["press_rate_wilcoxon_p"] = float(stats.wilcoxon(rr).pvalue)
        val[m] = r
    S["validation"] = val
    S["pvs_vs_tcs_rho"] = float(group_rho(pm, "pvs", "tcs").mean())
    S["centrality_intercorrelation"] = (
        pm[nc.CENTRALITIES + ["pvs", "involvement"]].corr("spearman").round(3).to_dict())

    # top-3 overlap: model's three targets vs the three most-pressed players
    hits, chance, top1 = [], [], []
    for _, g in pm.groupby(GROUP):
        a = set(g.nlargest(3, "tcs_oof")["player"])
        b = set(g.nlargest(3, LABEL)["player"])
        hits.append(len(a & b))
        chance.append(9 / len(g))
        top1.append(g.loc[g["tcs_oof"].idxmax(), "player"] in b)
    S["top3_overlap"] = dict(mean_overlap=float(np.mean(hits)), chance=float(np.mean(chance)),
                             top1_in_actual_top3=float(np.mean(top1)),
                             top1_chance=float(np.mean(chance) / 3))

    # ---------------- D. pressure concentration ---------------------------
    conc = []
    for _, g in pm.groupby(GROUP):
        top = g["tcs_rank"] <= 3
        if g[LABEL].sum() == 0:
            continue
        conc.append(dict(press_share=g.loc[top, LABEL].sum() / g[LABEL].sum(),
                         volume_share=g.loc[top, "involvement"].sum() / g["involvement"].sum(),
                         equal_share=3 / len(g)))
    conc = pd.DataFrame(conc)
    S["pressure_concentration_top3"] = dict(
        press_share=float(conc["press_share"].mean()), volume_share=float(conc["volume_share"].mean()),
        equal_share=float(conc["equal_share"].mean()),
        press_vs_volume_wilcoxon_p=float(stats.wilcoxon(conc["press_share"], conc["volume_share"]).pvalue))
    by_rank = (pm[pm["tcs_rank"] <= 11].groupby("tcs_rank")
               .agg(pressed=(LABEL, "mean"), involvement=("involvement", "mean")))
    by_rank["per_100"] = 100 * by_rank["pressed"] / by_rank["involvement"]
    S["pressed_by_tcs_rank"] = by_rank.round(3).to_dict()

    # ---------------- C. targeted vs random removal -----------------------
    tr = []
    for _, g in pm.groupby(GROUP):
        n = len(g)
        tot = 1 - (1 - g["eff_loss"]) * (n - 2) / n      # loss of total capacity (fixed denominator)
        xi = g["involvement"].rank(ascending=False, method="first") <= 11
        row = dict(random=g["eff_loss"].mean(), random_pvs=g["pvs"].mean(),
                   random_xi=g.loc[xi, "eff_loss"].mean(), random_tot=tot[xi].mean(),
                   tcs_tot=tot[g["tcs"].idxmax()],
                   tcs=g.loc[g["tcs"].idxmax(), "eff_loss"], tcs_pvs=g.loc[g["tcs"].idxmax(), "pvs"],
                   worst=g["eff_loss"].max())
        for c in nc.CENTRALITIES:
            row[c] = g.loc[g[c].idxmax(), "eff_loss"]
        tr.append(row)
    tr = pd.DataFrame(tr)
    S["targeted_vs_random"] = dict(
        mean_eff_loss_random=float(tr["random"].mean()),
        mean_eff_loss_top_tcs=float(tr["tcs"].mean()),
        mean_eff_loss_worst_case=float(tr["worst"].mean()),
        ratio=float(tr["tcs"].mean() / tr["random"].mean()),
        share_networks_targeted_worse=float((tr["tcs"] > tr["random"]).mean()),
        wilcoxon_p=float(stats.wilcoxon(tr["tcs"], tr["random"]).pvalue),
        mean_pvs_random=float(tr["random_pvs"].mean()), mean_pvs_top_tcs=float(tr["tcs_pvs"].mean()),
        by_single_metric={c: float(tr[c].mean()) for c in nc.CENTRALITIES},
        mean_eff_loss_random_starter=float(tr["random_xi"].mean()),
        ratio_vs_random_starter=float(tr["tcs"].mean() / tr["random_xi"].mean()),
        wilcoxon_p_vs_random_starter=float(stats.wilcoxon(tr["tcs"], tr["random_xi"]).pvalue),
        total_capacity_loss_top_tcs=float(tr["tcs_tot"].mean()),
        total_capacity_loss_random_starter=float(tr["random_tot"].mean()),
        total_capacity_wilcoxon_p=float(stats.wilcoxon(tr["tcs_tot"], tr["random_tot"]).pvalue),
        top_tcs_is_worst_case=float((tr["tcs"] >= tr["worst"] - 1e-12).mean()))

    print("Sequential attack simulation ...")
    passes = nc.load_passes()
    curves = {"TCS-targeted": [], "Betweenness-targeted": [], "Random": []}
    sens = {1: [], 2: [], 3: []}
    scale = []
    for (mid, team), tp in passes.groupby(GROUP):
        g = pm[(pm["match_id"] == mid) & (pm["team"] == team)]
        if g.empty:
            continue
        G = nc.build_graph(tp)
        curves["TCS-targeted"].append(
            nc.attack_curve(G, list(g.sort_values("tcs", ascending=False)["player"]), ATTACK_STEPS))
        curves["Betweenness-targeted"].append(
            nc.attack_curve(G, list(g.sort_values("betweenness", ascending=False)["player"]), ATTACK_STEPS))
        nodes = list(g.nlargest(11, "involvement")["player"])     # random among the main XI
        n = G.number_of_nodes()
        scale.append([(n - k) * (n - k - 1) / (n * (n - 1)) for k in range(ATTACK_STEPS + 1)])
        rnd = [nc.attack_curve(G, list(RNG.permutation(nodes)), ATTACK_STEPS)
               for _ in range(N_RANDOM_ORDERS)]
        curves["Random"].append(np.mean(rnd, axis=0))
        # E. threshold sensitivity (centralities only)
        lab = g.set_index("player")[LABEL]
        for k in sens:
            c = nc.centralities(nc.build_graph(tp, k))
            tcs_k = sum(W[i] * nc.minmax(c[m]) for i, m in enumerate(nc.CENTRALITIES))
            j = pd.concat([tcs_k.rename("t"), lab], axis=1).dropna()
            if j["t"].nunique() > 1 and j[LABEL].nunique() > 1:
                sens[k].append(stats.spearmanr(j["t"], j[LABEL])[0])
    curves = {k: np.array(v) for k, v in curves.items()}
    S["attack_curve"] = {k: v.mean(axis=0).round(4).tolist() for k, v in curves.items()}
    scale = np.array(scale)
    S["attack_curve_total_capacity"] = {k: (v * scale).mean(axis=0).round(4).tolist()
                                        for k, v in curves.items()}
    curves_total = {k: v * scale for k, v in curves.items()}
    S["threshold_sensitivity"] = {f"min_{k}_passes": float(np.mean(v)) for k, v in sens.items()}

    # ---------------- E. team level: vulnerability vs outcome -------------
    team = pm.groupby(GROUP).agg(max_eff_loss=("eff_loss", "max"), max_btw=("betweenness", "max"),
                                 top3_share=("involvement", lambda s: s.nlargest(3).sum() / s.sum()),
                                 pressed=(LABEL, "sum")).reset_index()
    mt = nc.load_matches()
    team = team.merge(mt, on="match_id")
    home = team["team"] == team["home_team"]
    team["goal_diff"] = np.where(home, team["home_score"] - team["away_score"],
                                 team["away_score"] - team["home_score"])
    team = team.merge(th[GROUP + ["efficiency", "clustering", "total_passes"]], on=GROUP)
    out = {}
    for c in ["max_eff_loss", "max_btw", "top3_share", "clustering", "total_passes"]:
        r, p = stats.spearmanr(team[c], team["goal_diff"])
        out[c] = dict(rho=float(r), p=float(p))
    S["team_outcome_correlation"] = out
    S["team_outcome_n"] = int(len(team))

    # ---------------- season tables ---------------------------------------
    S["season_top_targets"] = {}
    for (comp, t), g in ps.groupby(["competition_label", "team"]):
        g = g[g["appearances"] >= g["matches"] * 0.25].sort_values("tcs", ascending=False)
        g = g.assign(pressed_per_match=g[LABEL] / g["appearances"])
        S["season_top_targets"][f"{t} {comp}"] = (
            g.head(8)[["player", "appearances", "tcs", "pvs", "betweenness", "eff_loss",
                       "pressed_per_match"]].round(3).to_dict("records"))

    pm.to_csv(nc.RESULTS_DIR / "player_match_scores.csv", index=False)
    ps.to_csv(nc.RESULTS_DIR / "player_season_scores.csv", index=False)
    with open(nc.RESULTS_DIR / "results_summary.json", "w", encoding="utf-8") as f:
        json.dump(S, f, indent=2, ensure_ascii=False)

    make_figures(pm, ps, S, tr, curves, curves_total, passes)
    print(json.dumps({k: S[k] for k in ["tcs_weights", "targeted_vs_random", "top3_overlap",
                                         "pressure_concentration_top3", "threshold_sensitivity",
                                         "holdout_premier_league"]}, indent=1))
    print(pd.DataFrame(S["validation"]).T.round(3).to_string())


# --------------------------------------------------------------------------
# figures
# --------------------------------------------------------------------------
def draw_pitch(ax):
    line = dict(color="#b9b8b2", lw=1.1, zorder=1)
    ax.plot([0, 120, 120, 0, 0], [0, 0, 80, 80, 0], **line)
    ax.plot([60, 60], [0, 80], **line)
    ax.add_patch(plt.Circle((60, 40), 10, fill=False, ec="#b9b8b2", lw=1.1))
    for x0, w in [(0, 18), (102, 18)]:
        ax.add_patch(plt.Rectangle((x0, 18), w, 44, fill=False, ec="#b9b8b2", lw=1.1))
    for x0, w in [(0, 6), (114, 6)]:
        ax.add_patch(plt.Rectangle((x0, 30), w, 20, fill=False, ec="#b9b8b2", lw=1.1))
    ax.set_xlim(-3, 123); ax.set_ylim(83, -3); ax.set_aspect("equal"); ax.axis("off")


def short(name):
    alias = {"Laureano Bisan-Etame Mayer": "Lauren", "Gilberto Aparecido da Silva": "Gilberto Silva",
             "Kolo Habib Touré": "K. Touré", "Eduardo César Daude Gaspar": "Edu",
             "José Antonio Reyes Calderón": "Reyes", "Sulzeer Jeremiah ''Sol' Campbell": "Campbell",
             "Lionel Andrés Messi Cuccittini": "Messi", "Sergio Busquets i Burgos": "Busquets",
             "Gerard Piqué Bernabéu": "Piqué", "Jordi Alba Ramos": "Jordi Alba",
             "Philippe Coutinho Correia": "Coutinho", "Arthur Henrique Ramos de Oliveira Melo": "Arthur",
             "Luis Alberto Suárez Díaz": "Suárez", "Arturo Erasmo Vidal Pardo": "Vidal",
             "Sergi Roberto Carnicer": "Sergi Roberto", "Nélson Cabral Semedo": "Semedo",
             "Marc-André ter Stegen": "ter Stegen", "Clément Lenglet": "Lenglet"}
    if name in alias:
        return alias[name]
    parts = name.split()
    return parts[-1] if len(parts) <= 2 else " ".join(parts[-1:])


def pitch_network(ax, tp, sc, min_pass, title, top_n=11):
    sc = sc.sort_values("involvement", ascending=False).head(top_n).set_index("player")
    G = nc.build_graph(tp, min_pass)
    draw_pitch(ax)
    wmax = max((d["weight"] for u, v, d in G.edges(data=True) if u in sc.index and v in sc.index), default=1)
    for u, v, d in G.edges(data=True):
        if u in sc.index and v in sc.index:
            ax.plot([sc.at[u, "avg_x"], sc.at[v, "avg_x"]], [sc.at[u, "avg_y"], sc.at[v, "avg_y"]],
                    color="#8a8983", lw=0.4 + 4.5 * d["weight"] / wmax,
                    alpha=0.15 + 0.5 * d["weight"] / wmax, zorder=2, solid_capstyle="round")
    size = 250 + 900 * sc["involvement"] / sc["involvement"].max()
    pts = ax.scatter(sc["avg_x"], sc["avg_y"], s=size, c=sc["tcs"], cmap="Blues", vmin=0, vmax=1,
                     edgecolors=SURFACE, linewidths=2, zorder=3)
    for p, r in sc.iterrows():
        ax.annotate(short(p), (r["avg_x"], r["avg_y"]), xytext=(0, -np.sqrt(size[p]) / 2 - 9),
                    textcoords="offset points", ha="center", fontsize=8.5, color=INK, zorder=4)
    ax.set_title(title, loc="left")
    return pts


def make_figures(pm, ps, S, tr, curves, curves_total, passes):
    V = S["validation"]

    # Fig 1 - Arsenal season pressing-vulnerability map
    comp, t = "Premier League 2003/04", "Arsenal"
    tp = passes[(passes["competition_label"] == comp) & (passes["team"] == t)]
    sc = ps[(ps["competition_label"] == comp) & (ps["team"] == t)]
    fig, ax = plt.subplots(figsize=(9.5, 6.6))
    pts = pitch_network(ax, tp, sc, tp["match_id"].nunique(),
                        "Arsenal 2003/04 pressing-vulnerability map (season network)")
    cb = fig.colorbar(pts, ax=ax, shrink=0.6, pad=0.01)
    cb.set_label("Tactical Criticality Score"); cb.outline.set_visible(False)
    ax.text(0, 86.5, "Node size = pass involvement, line width = completed passes between the pair. "
            "Attack direction: left to right.", fontsize=8.5, color=MUTED)
    fig.savefig(nc.FIG_DIR / "fig1_arsenal_vulnerability_map.png", dpi=180, bbox_inches="tight"); plt.close(fig)

    # Fig 2 - validation by metric (raw vs volume-controlled)
    order = ["tcs_oof", "eigenvector", "closeness", "degree", "betweenness", "pvs"]
    order = sorted(order, key=lambda m: V[m]["mean_rho"])
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    y = np.arange(len(order)); h = 0.36
    raw = [V[m]["mean_rho"] for m in order]
    par = [V[m]["partial_rho_given_volume"] for m in order]
    err = [[V[m]["mean_rho"] - V[m]["ci_low"] for m in order], [V[m]["ci_high"] - V[m]["mean_rho"] for m in order]]
    ax.barh(y + h / 2 + 0.02, raw, h, color=BLUE, xerr=err, error_kw=dict(ecolor=INK, lw=1, capsize=2),
            label="Spearman ρ with times pressed (mean within team-match, 95% CI)")
    ax.barh(y - h / 2 - 0.02, par, h, color=ORANGE, label="Partial ρ after controlling for pass volume")
    for yi, a, b in zip(y, raw, par):
        ax.text(a + 0.03, yi + h / 2 + 0.02, f"{a:.2f}", va="center", fontsize=9)
        ax.text(max(b, 0) + 0.012, yi - h / 2 - 0.02, f"{b:.2f}", va="center", fontsize=9)
    ax.axvline(V["involvement"]["mean_rho"], color=MUTED, lw=1, ls="--")
    ax.text(V["involvement"]["mean_rho"], len(order) - 0.42, " pass-volume baseline", color=MUTED, fontsize=8.5,
            ha="right")
    ax.set_yticks(y, [NICE[m] for m in order]); ax.set_xlim(0, 1); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Correlation with actual pressing frequency")
    ax.set_title("How well does each metric predict who gets pressed?")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.16), ncol=1, fontsize=8.5)
    fig.savefig(nc.FIG_DIR / "fig2_metric_validation.png", dpi=180, bbox_inches="tight"); plt.close(fig)

    # Fig 3 - attack curves (two views of the same simulation)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), sharey=True)
    x = np.arange(ATTACK_STEPS + 1)
    views = [(curves, "Efficiency among the remaining players"),
             (curves_total, "Total passing capacity (removed players count as lost)")]
    for ax, (cv, sub) in zip(axes, views):
        ends = {}
        for (name, arr), col in zip(cv.items(), [BLUE, ORANGE, AQUA]):
            m = arr.mean(axis=0) * 100
            ax.plot(x, m, color=col, lw=2, marker="o", ms=6, mec=SURFACE, mew=1.5, label=name)
            ends[name] = m[-1]
        lo = min(ends, key=ends.get)
        for name, v in ends.items():
            dy = -9 if name == lo else (9 if name != "Random" else 0)
            ax.annotate(f"{v:.0f}%", (x[-1], v), xytext=(8, dy), textcoords="offset points",
                        va="center", fontsize=9, color=INK)
        ax.set_xlim(0, ATTACK_STEPS + 0.7); ax.set_xticks(x); ax.set_ylim(0, 105)
        ax.set_xlabel("Players removed"); ax.set_title(sub, fontsize=10.5)
    axes[0].set_ylabel("Remaining (% of intact network)")
    axes[0].legend(loc="lower left", fontsize=9)
    fig.suptitle("Passing networks degrade far faster under targeted attack than random removal",
                 x=0.07, ha="left", fontweight="bold", fontsize=12.5)
    fig.tight_layout()
    fig.savefig(nc.FIG_DIR / "fig3_attack_curves.png", dpi=180, bbox_inches="tight"); plt.close(fig)

    # Fig 4 - single removal: targeted vs random
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    bins = np.linspace(-5, 45, 41)
    ax.hist(tr["random_xi"] * 100, bins, color=AQUA, alpha=0.85, label="Random first-XI player (expected loss)", edgecolor=SURFACE)
    ax.hist(tr["tcs"] * 100, bins, color=BLUE, alpha=0.8, label="Highest-TCS player", edgecolor=SURFACE)
    for v, col in [(tr["random_xi"].mean() * 100, AQUA), (tr["tcs"].mean() * 100, BLUE)]:
        ax.axvline(v, color=col, lw=2, ls="--")
        ax.text(v + 0.5, ax.get_ylim()[1] * 0.93, f"mean {v:.1f}%", fontsize=9, color=INK)
    ax.set_xlabel("Loss of global efficiency after removing one player (%)"); ax.set_ylabel("Team-match networks")
    ax.set_title("Removing the top TCS player vs a random player"); ax.legend(fontsize=9)
    fig.savefig(nc.FIG_DIR / "fig4_targeted_vs_random.png", dpi=180, bbox_inches="tight"); plt.close(fig)

    # Fig 5 - TCS weights
    w = S["tcs_weights"]; sd = S["tcs_weight_fold_sd"]
    keys = sorted(w, key=w.get)
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    ax.barh([NICE[k] for k in keys], [w[k] for k in keys], color=BLUE, height=0.55,
            xerr=[sd[k] for k in keys], error_kw=dict(ecolor=INK, lw=1, capsize=2))
    for i, k in enumerate(keys):
        ax.text(w[k] + sd[k] + 0.015, i, f"{w[k]:.2f}", va="center", fontsize=9)
    ax.set_xlim(0, max(w.values()) + 0.15); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Weight in TCS (error bar = SD across 5 folds)")
    ax.set_title("Learned Tactical Criticality Score weights")
    fig.savefig(nc.FIG_DIR / "fig5_tcs_weights.png", dpi=180, bbox_inches="tight"); plt.close(fig)

    # Fig 6 - pressure received by TCS rank
    br = pd.DataFrame(S["pressed_by_tcs_rank"])
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.bar(br.index.astype(int), br["pressed"], color=BLUE, width=0.7)
    for r, v in zip(br.index.astype(int), br["pressed"]):
        ax.text(r, v + 0.3, f"{v:.1f}", ha="center", fontsize=8.5)
    ax.set_xticks(br.index.astype(int)); ax.grid(axis="x", visible=False)
    ax.set_xlabel("Player's TCS rank within the team (1 = most critical)")
    ax.set_ylabel("Times pressed per match (mean)")
    ax.set_title("Opponents press the players the model ranks as critical")
    fig.savefig(nc.FIG_DIR / "fig6_pressed_by_tcs_rank.png", dpi=180, bbox_inches="tight"); plt.close(fig)

    # Fig 7 - Arsenal top targets
    g = sc[sc["appearances"] >= 10].sort_values("tcs").tail(10)
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    ax.barh([short(p) for p in g["player"]], g["tcs"], color=BLUE, height=0.6)
    for i, (v, pr, ap) in enumerate(zip(g["tcs"], g["pressed_events"], g["appearances"])):
        ax.text(v + 0.01, i, f"{v:.2f}   pressed {pr / ap:.1f}/match", va="center", fontsize=8.5)
    ax.set_xlim(0, 1.45); ax.grid(axis="y", visible=False); ax.set_xlabel("Tactical Criticality Score (season network)")
    ax.set_title("Arsenal 2003/04: recommended pressing targets")
    fig.savefig(nc.FIG_DIR / "fig7_arsenal_targets.png", dpi=180, bbox_inches="tight"); plt.close(fig)

    # Fig 8 - Barcelona 2018/19 map
    comp, t = "La Liga 2018/19", "Barcelona"
    tp = passes[(passes["competition_label"] == comp) & (passes["team"] == t)]
    sc2 = ps[(ps["competition_label"] == comp) & (ps["team"] == t)]
    fig, ax = plt.subplots(figsize=(9.5, 6.6))
    pts = pitch_network(ax, tp, sc2, tp["match_id"].nunique(),
                        "Barcelona 2018/19 pressing-vulnerability map (season network)")
    cb = fig.colorbar(pts, ax=ax, shrink=0.6, pad=0.01)
    cb.set_label("Tactical Criticality Score"); cb.outline.set_visible(False)
    fig.savefig(nc.FIG_DIR / "fig8_barcelona_vulnerability_map.png", dpi=180, bbox_inches="tight"); plt.close(fig)
    print("Figures saved ->", nc.FIG_DIR)


if __name__ == "__main__":
    main()
