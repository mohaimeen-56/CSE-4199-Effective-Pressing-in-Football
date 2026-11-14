# A Graph-Based Vulnerability Analysis of Passing Networks for Identifying Optimal Pressing Targets in the English Premier League

> **Course:** Project/Thesis — CSE 4199 | **Date:** September 2026

---

## Abstract

This project presents a computational framework that treats a football team's passing structure as a complex **directed weighted network** and applies **graph-theoretic vulnerability analysis** — borrowed from the network robustness and targeted-attack literature — to identify which players, when pressed, cause the greatest degradation to a team's tactical system.

Using event-level data from **StatsBomb's open-access** English Premier League dataset, the study:
1. Constructs per-match and per-season passing networks.
2. Computes a composite **Tactical Criticality Score (TCS)** for each player.
3. Validates predictions against actual pressing events recorded in the data.
4. Delivers an **interactive prototype dashboard** that visually communicates each team's pressing vulnerability map on a football pitch layout.

---

## Research Problem & Motivation

Tactical pressing in modern football — popularised by managers such as Jürgen Klopp at Liverpool and Pep Guardiola at Manchester City — has become a defining feature of elite-level play. Yet pressing strategy remains largely intuitive, relying on human observation rather than quantitative, data-driven frameworks.

Existing network-analysis research is primarily **descriptive** (characterising team structure, quantifying interaction patterns). This project shifts the lens to **prescription**:

> *"Which node (player) should an opponent attack to cause maximum network degradation?"*

This adversarial framing — well-established in cybersecurity and epidemiology — has not been formally applied to football tactics, representing the core novelty of this research.

---

## Research Questions & Objectives

### Primary Research Question
> Can graph-based vulnerability analysis of football passing networks reliably identify which players represent the most critical pressing targets, and does real match data from the English Premier League validate these predictions?

### Secondary Research Questions
- Which graph centrality metrics — betweenness, eigenvector, closeness, or degree — are individually or collectively most predictive of a player's tactical criticality?
- How significantly does a team's passing network degrade when its highest-scoring node is removed compared to removing a randomly selected node?
- Does the model's predicted pressing-target ranking correlate with the actual frequency of pressing events recorded in StatsBomb data?

### Objectives
- [x] Construct weighted directed passing networks for Premier League teams from StatsBomb open-access event data.
- [x] Compute and compare multiple centrality and robustness metrics to rank players by tactical criticality.
- [x] Simulate node removal (pressing scenarios) and quantify resulting network degradation.
- [x] Validate predictions against actual StatsBomb pressure event data using Spearman's rank correlation.
- [x] Develop an interactive prototype dashboard that visualises a team's pressing vulnerability map on a pitch layout.

---

## Methodology

### 5.1 Data Source
All match data is sourced from **StatsBomb's open-access repository**, accessed via `statsbombpy`. The dataset contains:
- **Pass events** — origin player, destination player, pitch coordinates, outcome.
- **Pressure events** — player under pressure, location, timing.

Additional historical match results are downloaded from **football-data.co.uk** (Premier League, La Liga, Bundesliga, Serie A).  
Player season statistics are scraped from **FBref** (goals, assists, passing %, defensive actions, etc.).

### 5.2 Passing Network Construction
For each match (and aggregated across a season), a weighted directed graph **G = (V, E)** is constructed:

| Element | Meaning |
|---------|---------|
| **V** (nodes) | Outfield players |
| **E** (directed edges) | Passes from one player to another |
| **Edge weight** | Pass frequency |

A minimum pass threshold is applied to remove noise from very infrequent connections. All graph construction uses Python's **NetworkX** library.

### 5.3 Centrality & Vulnerability Analysis
Four centrality metrics are computed per player node:

| Metric | Description |
|--------|-------------|
| **Degree Centrality** | Number of direct passing connections |
| **Betweenness Centrality** | Frequency of appearing on shortest passing paths between other players |
| **Eigenvector Centrality** | Influence weighted by the influence of connected players |
| **Closeness Centrality** | Speed with which a player can reach all other nodes in the network |

A composite **Tactical Criticality Score (TCS)** is derived by weighting and combining these metrics, with weights optimised against match outcome labels using **scikit-learn**.

**Node removal simulations** are then performed iteratively: each player's node is removed and key network-level properties — average path length, clustering coefficient, network diameter — are recomputed. The degree of degradation constitutes that player's **Pressing Vulnerability Score**.

### 5.4 Validation
Model predictions are validated against StatsBomb pressure event logs using **Spearman's rank correlation coefficient**. A statistically significant positive correlation constitutes evidence for the model's validity.

### 5.5 Prototype Dashboard
An interactive visualisation tool built with **Streamlit** or **Plotly Dash**:
1. Displays a football pitch with players positioned by average coordinate location, colour-coded by Pressing Vulnerability Score.
2. Allows users to simulate pressing any player and observe real-time network degradation.
3. Supports side-by-side comparison of two teams' pressing vulnerability profiles.

---

## Repository Structure

```
CSE4199/
│
├── collect_all.py              # Main pipeline: extracts StatsBomb pass & pressure events,
│                               # builds graph node & edge feature CSVs
│
├── cleaner.py                  # Cleans, imputes, deduplicates, and organizes raw datasets
│                               # into separated scraped_data/ and cleaned_data/ folders
│
├── 02_fbref_scraper.py         # Scrapes per-player season statistics from fbref.com
│                               # (standard, passing, defense, possession, playing time)
│
├── 03_match_results.py         # Downloads historical match results from football-data.co.uk
│                               # (Premier League, La Liga, Bundesliga, Serie A)
│
├── Dataset/
│   ├── scraped_data/           # Preserved original/raw datasets from scrapers & APIs
│   │   ├── Pass_Events_and_Pressure_Call.csv
│   │   ├── pressure_events.csv
│   │   ├── graph_nodes.csv
│   │   ├── graph_edges.csv
│   │   └── La_Liga_15_16_Premier_League_15_16_WC22_Euro20.csv
│   │
│   └── cleaned_data/           # Validated, deduplicated, imputed, and standardized datasets
│       ├── Pass_Events_and_Pressure_Call.csv
│       ├── pressure_events.csv
│       ├── graph_nodes.csv
│       ├── graph_edges.csv
│       └── La_Liga_15_16_Premier_League_15_16_WC22_Euro20.csv
│
└── Published Papers/
    ├── Football Thesis Proposal.docx
    ├── Measuring the Effectiveness of Pressing in Soccer by - S Merckx.pdf
    ├── A network theory analysis of football strategies by - Javiar Lopez and Hugo Touchette.pdf
    ├── Using Network Science to analyse Football Passing Netweorks by - Javier M. Baldu and Javier Busquets.pdf
    ├── Match Analysis, Big Data and Tactics by - Memmert D, Rein R.pdf
    ├── Spatial and Temporal Entropies in the Spanish Football League by - Johann H. Martinez and Jose L. Herrera-Diestra.pdf
    └── Graph neural networks A review of methods and applications by - Jie Johu.pdf
```

---

## Dataset Description

### `graph_nodes.csv` — Node Feature Table *(player x match)*

| Column | Description |
|--------|-------------|
| `match_id` | StatsBomb match identifier |
| `competition_label` | Competition name |
| `player` | Player name |
| `team` | Team name |
| `passes_made` | Total passes attempted |
| `passes_received` | Total passes received |
| `degree_out` | Number of unique recipients |
| `degree_in` | Number of unique passers to this player |
| `pass_completion_rate` | Fraction of passes completed |
| `avg_pass_length` | Mean pass distance (metres) |
| `progressive_passes` | Passes advancing >= 10 m toward opponent goal |
| `progressive_ratio` | Progressive passes / total passes |
| `passes_under_pressure` | Passes made while being pressed |
| `under_pressure_pct` | Fraction of passes made under pressure |
| `avg_x`, `avg_y` | Average pitch position |
| **`pressure_received`** | **Validation label — times this player was pressed** |

### `graph_edges.csv` — Edge Feature Table *(passer to recipient per match)*

| Column | Description |
|--------|-------------|
| `passer`, `recipient` | Player names |
| `pass_count` | Number of passes on this edge |
| `completion_rate` | Fraction completed |
| `avg_length` | Mean pass distance |
| `progressive_ratio` | Fraction that were progressive |
| `under_pressure_pct` | Fraction made under pressure |

---

## Scripts

### `collect_all.py`
Main data-collection pipeline using **StatsBomb open data** via `statsbombpy`.

**Competitions processed:**
- Premier League 2003/04
- La Liga 2018/19 & 2019/20
- FIFA World Cup 2018
- UEFA Euro 2020
- Champions League 2018/19

**Pipeline steps:**
1. Load & filter matches to `data/statsbomb/subset_matches.csv`
2. Extract pass & pressure events to `data/statsbomb/pass_events.csv` and `pressure_events.csv`
3. Build graph **node** features to `data/combined/graph_nodes.csv`
4. Build graph **edge** features to `data/combined/graph_edges.csv`

### `02_fbref_scraper.py`
Scrapes per-player season statistics from **fbref.com** for node feature enrichment.

**Leagues scraped:** Premier League (2020–2023), La Liga (2021–2023), Champions League (2022–23)

**Tables collected:** Standard stats · Passing · Defense · Possession · Playing time

> Warning: Enforces a **5-second delay** between requests to respect FBref's servers. Estimated run time: ~10–20 minutes per league/season.

**Output:** `data/fbref/player_stats_<LEAGUE>.csv` + `data/fbref/ALL_player_stats.csv`

### `03_match_results.py`
Downloads historical match result CSVs directly from **football-data.co.uk** — no scraping, just HTTP downloads.

**Coverage:** Premier League (2014–2024), La Liga (2018–2024), Bundesliga (2021–2024), Serie A (2021–2024)

**Key output columns:** `home_team`, `away_team`, `home_goals`, `away_goals`, `result`, shots, corners, fouls, cards, betting odds.

**Output:** `data/results/results_<LEAGUE>.csv` + `data/results/ALL_results.csv`

---

## Analysis Pipeline and Results

```bash
python phase2_graph_analysis.py   # networks, centralities, node-removal scores -> results/
python phase3_validation.py       # TCS weights, validation, attack simulation, figures -> results/
streamlit run dashboard.py        # Pressing Intelligence Dashboard
```

| File | Role |
|------|------|
| `network_core.py` | Shared graph construction, centrality, network health, node removal and the pressed-player label |
| `phase2_graph_analysis.py` | Per-match and per-season networks, centralities and Pressing Vulnerability Score (PVS) |
| `phase3_validation.py` | Cross-validated Tactical Criticality Score (TCS), validation statistics, attack curves, figures |
| `dashboard.py` | Streamlit dashboard: pitch map, press simulation, two-team comparison |
| `pitch_component.py` | The dashboard's interactive pitch (custom Streamlit component: click-to-press, live tiles, target list) |
| `results/` | Score tables, `results_summary.json` and `figures/` |
| `deliverables/` | Mid-project update and final report (Word), presentation (PowerPoint) and the script that builds the slides |

**Headline results** (120 matches, 240 team-match networks):

- Removing the highest-TCS player costs 15.3% of global efficiency, against 4.3% for a random first-eleven player (worse in all 240 networks).
- After five targeted removals 39% of efficiency remains, against 70% for random removal.
- TCS vs actual pressing: mean within-team Spearman rho = 0.79 on unseen matches (0.80 on held-out Premier League matches).
- Pass volume alone reaches rho = 0.78; after controlling for it, TCS keeps a partial correlation of 0.27.
- Learned TCS weights: eigenvector 0.41, degree 0.33, closeness 0.17, betweenness 0.10.

> **Label note.** StatsBomb pressure events name the player *applying* pressure, so the `pressure_received`
> column in `graph_nodes.csv` actually counts pressures applied. The analysis rebuilds the label in
> `network_core.pressed_event_counts` by attributing each pressure event to the opposing player on the ball.

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| **Python 3.x** | Core language |
| **statsbombpy** | StatsBomb open-data access |
| **pandas / NumPy** | Data wrangling |
| **NetworkX** | Graph construction & centrality analysis |
| **scikit-learn** | TCS weight optimisation & ML |
| **Matplotlib / Plotly** | Visualisation |
| **Streamlit** | Interactive dashboard prototype |
| **requests** | Web scraping / HTTP downloads |
| **SQL** | Structured storage & batch querying |

---

## Expected Outcomes & Contributions

1. A validated **graph-theoretic framework** for identifying optimal pressing targets from passing network data (reported for English Premier League teams).
2. A comparative quantitative analysis of centrality metrics and their predictive power for tactical disruption.
3. An empirically validated **Tactical Criticality Score (TCS)** metric, cross-referenced against real pressing event data.
4. An interactive **Pressing Intelligence Dashboard** available as an open-source Python prototype.
5. A research manuscript suitable for submission to a sports analytics or computational intelligence venue.

> The primary academic contribution is the formal application of **network vulnerability theory** — specifically targeted node-attack analysis — to football tactical prescription. By reframing pressing strategy as a network-attack optimisation problem, this research introduces a novel and generalisable framework extendable to other team sports.

---

## Literature Review Summary

| Paper | Key Contribution |
|-------|-----------------|
| Albert, Jeong & Barabasi (2000) | Scale-free networks are robust to random failures but vulnerable to targeted high-degree node removal — the theoretical backbone of this work |
| Buldu et al. (2019) | Football passing networks as dynamic multilayer systems; clustering, path length & flow centrality for tactical style analysis |
| Grund (2012) | Passing network diversity significantly correlates with team performance in the EPL |
| Goncalves et al. (2017) | Betweenness centrality reliably identifies critical bridge players in youth football build-up play |
| Rein & Memmert (2016) | Big data in elite football — tactical analysis identified as most promising underdeveloped area |
| Pappalardo et al. (2019) | Public spatio-temporal match event dataset underpinning contemporary computational football research |
| Kipf & Welling (2017) | Graph convolutional networks — potential extension of the GNN methodology |
| Merckx (S.) | Measuring pressing effectiveness in soccer — direct methodological precedent |
| Newman (2010) | Comprehensive theoretical treatment of network centrality metrics and robustness measures |

---

## Getting Started

### Prerequisites
```bash
pip install statsbombpy pandas numpy networkx scikit-learn matplotlib streamlit requests python-docx
```

### Run the Pipeline
```bash
# Step 1 — collect StatsBomb pass & pressure events and build graph CSVs
python collect_all.py

# Step 2 — enrich node features with FBref player season stats
python 02_fbref_scraper.py

# Step 3 — download supplementary match result data
python 03_match_results.py
```

### Data Flow

```
StatsBomb API (statsbombpy)
        |
        v
  collect_all.py
        |
        |---> data/statsbomb/pass_events.csv
        |---> data/statsbomb/pressure_events.csv
        |---> data/combined/graph_nodes.csv   <- node features for NetworkX
        `---> data/combined/graph_edges.csv   <- edge features for NetworkX

fbref.com ---------> 02_fbref_scraper.py -----> data/fbref/ALL_player_stats.csv

football-data.co.uk -> 03_match_results.py ----> data/results/ALL_results.csv
```

---

## References

- Albert, R., Jeong, H. and Barabasi, A.L. (2000) 'Error and attack tolerance of complex networks', *Nature*, 406(6794), pp. 378–382.
- Buldu, J.M. et al. (2019) 'Using network science to analyse football passing networks', *Frontiers in Psychology*, 10, p. 1900.
- Goncalves, B. et al. (2017) 'Exploring team passing networks and player movement dynamics in youth association football', *PLOS ONE*, 12(1), e0171156.
- Grund, T.U. (2012) 'Network structure and team performance', *Social Networks*, 34(4), pp. 682–690.
- Kipf, T.N. and Welling, M. (2017) 'Semi-supervised classification with graph convolutional networks', *ICLR 2017*.
- Newman, M.E.J. (2010) *Networks: An Introduction*. Oxford: Oxford University Press.
- Pappalardo, L. et al. (2019) 'A public data set of spatio-temporal match events in soccer competitions', *Scientific Data*, 6(1), pp. 1–15.
- Rein, R. and Memmert, D. (2016) 'Big data and tactical analysis in elite soccer', *SpringerPlus*, 5(1), p. 1410.

---

*CSE 4199 — Project/Thesis | September 2026*
