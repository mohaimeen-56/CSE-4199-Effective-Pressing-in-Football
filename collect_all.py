import os, sys, warnings
warnings.filterwarnings('ignore')
os.chdir('/home/claude/thesis_data')

from statsbombpy import sb
import pandas as pd
import numpy as np

os.makedirs('data/statsbomb', exist_ok=True)
os.makedirs('data/combined', exist_ok=True)

# ── STEP 1: Load matches ─────────────────────────────────────────────────────
print("STEP 1: Loading matches...")
matches = pd.read_csv('data/statsbomb/matches.csv')

focus = ['Premier League 2003/04', 'La Liga 2018/19', 'La Liga 2019/20',
         'FIFA World Cup 2018', 'UEFA Euro 2020', 'Champions League 2018/19']
subset = matches[matches['competition_label'].isin(focus)].reset_index(drop=True)
subset.to_csv('data/statsbomb/subset_matches.csv', index=False)
print(f"  Subset: {len(subset)} matches")
for name, grp in subset.groupby('competition_label'):
    print(f"    {name}: {len(grp)}")

# ── STEP 2: Extract events in small batches ──────────────────────────────────
print("\nSTEP 2: Extracting pass & pressure events...")

def flatten(x):
    return x.get('name', '') if isinstance(x, dict) else (x if pd.notna(x) else '')

def get_loc(v, idx):
    try:
        if isinstance(v, list): return v[idx]
        if isinstance(v, str) and v.startswith('['): return float(v.strip('[]').split(',')[idx])
    except: pass
    return np.nan

all_passes = []
all_pressures = []
errors = 0

LIMIT = 120  # process up to 120 matches

for i, row in subset.head(LIMIT).iterrows():
    mid = int(row['match_id'])
    try:
        ev = sb.events(match_id=mid)

        meta = {
            'match_id': mid,
            'competition_label': row.get('competition_label', ''),
            'home_team': row.get('home_team', ''),
            'away_team': row.get('away_team', ''),
            'match_date': row.get('match_date', ''),
        }

        # ── PASSES ──
        p = ev[ev['type'] == 'Pass'].copy()
        for k, v in meta.items():
            p[k] = v

        p['loc_x']  = p['location'].apply(lambda v: get_loc(v, 0))
        p['loc_y']  = p['location'].apply(lambda v: get_loc(v, 1))
        p['end_x']  = p['pass_end_location'].apply(lambda v: get_loc(v, 0)) if 'pass_end_location' in p else np.nan
        p['end_y']  = p['pass_end_location'].apply(lambda v: get_loc(v, 1)) if 'pass_end_location' in p else np.nan

        for c in ['team','player','pass_recipient','pass_outcome','pass_height','pass_type']:
            if c in p.columns:
                p[c] = p[c].apply(flatten)

        keep_p = ['match_id','competition_label','home_team','away_team','match_date',
                  'period','minute','second','team','player',
                  'loc_x','loc_y','end_x','end_y',
                  'pass_length','pass_angle','pass_recipient','pass_outcome',
                  'pass_height','pass_type','under_pressure','pass_switch','pass_cross']
        p = p[[c for c in keep_p if c in p.columns]]
        all_passes.append(p)

        # ── PRESSURES ──
        pr = ev[ev['type'] == 'Pressure'].copy()
        for k, v in meta.items():
            pr[k] = v
        pr['press_x'] = pr['location'].apply(lambda v: get_loc(v, 0))
        pr['press_y'] = pr['location'].apply(lambda v: get_loc(v, 1))
        for c in ['team','player']:
            if c in pr.columns:
                pr[c] = pr[c].apply(flatten)
        keep_pr = ['match_id','competition_label','home_team','away_team','match_date',
                   'period','minute','second','team','player','press_x','press_y']
        pr = pr[[c for c in keep_pr if c in pr.columns]]
        all_pressures.append(pr)

        if (i + 1) % 20 == 0:
            total = sum(len(x) for x in all_passes)
            print(f"  [{i+1:>3}/{min(LIMIT, len(subset))}] matches done | passes so far: {total:,}")

    except Exception as e:
        errors += 1

print(f"\n  Errors: {errors}")

pass_df  = pd.concat(all_passes,    ignore_index=True)
press_df = pd.concat(all_pressures, ignore_index=True)
pass_df.to_csv('data/statsbomb/pass_events.csv',     index=False)
press_df.to_csv('data/statsbomb/pressure_events.csv', index=False)
print(f"  Pass events:     {len(pass_df):,}")
print(f"  Pressure events: {len(press_df):,}")

# ── STEP 3: Build graph node features ────────────────────────────────────────
print("\nSTEP 3: Building graph node features...")

pass_df['is_complete']    = (pass_df['pass_outcome'].isna() | (pass_df['pass_outcome'] == '')).astype(int)
pass_df['is_progressive'] = ((pass_df['end_x'] - pass_df['loc_x']) > 10).astype(int)
pass_df['under_pressure'] = pass_df['under_pressure'].fillna(False).astype(int)

press_counts = press_df.groupby(['match_id','player']).size().reset_index(name='pressure_received')

node_rows = []
for mid, mp in pass_df.groupby('match_id'):
    meta_row = subset[subset['match_id'] == mid]
    if meta_row.empty: continue
    meta_row = meta_row.iloc[0]

    players = set(mp['player'].dropna()) | set(mp['pass_recipient'].dropna())
    for player in players:
        if not player or not isinstance(player, str): continue
        p_out = mp[mp['player']    == player]
        p_in  = mp[mp['pass_recipient'] == player]
        pc = press_counts[(press_counts['match_id']==mid) & (press_counts['player']==player)]

        node_rows.append({
            'match_id':           mid,
            'competition_label':  meta_row.get('competition_label', ''),
            'home_team':          meta_row.get('home_team', ''),
            'away_team':          meta_row.get('away_team', ''),
            'match_date':         meta_row.get('match_date', ''),
            'player':             player,
            'team':               p_out['team'].mode().iloc[0] if len(p_out) > 0 else '',
            'passes_made':        len(p_out),
            'passes_received':    len(p_in),
            'degree_out':         p_out['pass_recipient'].nunique(),
            'degree_in':          p_in['player'].nunique(),
            'pass_completion_rate': p_out['is_complete'].mean() if len(p_out) > 0 else np.nan,
            'avg_pass_length':    p_out['pass_length'].mean() if 'pass_length' in p_out and len(p_out) > 0 else np.nan,
            'progressive_passes': int(p_out['is_progressive'].sum()),
            'progressive_ratio':  p_out['is_progressive'].mean() if len(p_out) > 0 else np.nan,
            'passes_under_pressure': int(p_out['under_pressure'].sum()),
            'under_pressure_pct': p_out['under_pressure'].mean() if len(p_out) > 0 else np.nan,
            'avg_x':              p_out['loc_x'].mean() if 'loc_x' in p_out and len(p_out) > 0 else np.nan,
            'avg_y':              p_out['loc_y'].mean() if 'loc_y' in p_out and len(p_out) > 0 else np.nan,
            'pressure_received':  int(pc['pressure_received'].iloc[0]) if len(pc) > 0 else 0,
        })

nodes_df = pd.DataFrame(node_rows)
nodes_df.to_csv('data/combined/graph_nodes.csv', index=False)
print(f"  Node rows (player × match): {len(nodes_df):,}")
print(f"  Unique players:             {nodes_df['player'].nunique():,}")

# ── STEP 4: Build edge features ───────────────────────────────────────────────
print("\nSTEP 4: Building graph edge features...")

valid = pass_df[pass_df['player'].notna() & pass_df['pass_recipient'].notna() &
                (pass_df['player'] != '') & (pass_df['pass_recipient'] != '')]

edge_rows = []
for (mid, passer, recipient), grp in valid.groupby(['match_id','player','pass_recipient']):
    meta_row = subset[subset['match_id'] == mid]
    if meta_row.empty: continue
    meta_row = meta_row.iloc[0]
    edge_rows.append({
        'match_id':          mid,
        'competition_label': meta_row.get('competition_label', ''),
        'home_team':         meta_row.get('home_team', ''),
        'away_team':         meta_row.get('away_team', ''),
        'passer':            passer,
        'recipient':         recipient,
        'pass_count':        len(grp),
        'completion_rate':   grp['is_complete'].mean(),
        'avg_length':        grp['pass_length'].mean() if 'pass_length' in grp else np.nan,
        'progressive_ratio': grp['is_progressive'].mean(),
        'under_pressure_pct':grp['under_pressure'].mean(),
    })

edges_df = pd.DataFrame(edge_rows)
edges_df.to_csv('data/combined/graph_edges.csv', index=False)
print(f"  Edge rows (A→B per match): {len(edges_df):,}")

# ── FINAL SUMMARY ─────────────────────────────────────────────────────────────
print("\n" + "="*55)
print("  ALL DONE — DATASET SUMMARY")
print("="*55)
print(f"  Matches processed : {pass_df['match_id'].nunique():,}")
print(f"  Pass events       : {len(pass_df):,}")
print(f"  Pressure events   : {len(press_df):,}")
print(f"  Graph nodes       : {len(nodes_df):,}  (player × match)")
print(f"  Graph edges       : {len(edges_df):,}  (A→B pairs per match)")
print(f"  Unique players    : {nodes_df['player'].nunique():,}")
print(f"  Unique teams      : {nodes_df['team'].nunique():,}")
print("="*55)
print("\n  Files saved:")
print("  data/statsbomb/pass_events.csv")
print("  data/statsbomb/pressure_events.csv")
print("  data/combined/graph_nodes.csv   ← NODE features for NetworkX")
print("  data/combined/graph_edges.csv   ← EDGE features for NetworkX")
print("\n  Node feature columns:")
feat = [c for c in nodes_df.columns if c not in
        ['match_id','player','team','competition_label',
         'home_team','away_team','match_date']]
for c in feat:
    print(f"    · {c}")
print("\n  'pressure_received' = your validation label (what your model predicts)")
