"""Builds deliverables/Thesis_Presentation.pptx from the figures in results/figures.
Run from the project root:  python deliverables/build_pptx.py
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "results" / "figures"
OUT = ROOT / "deliverables" / "Thesis_Presentation.pptx"

DARK, LIGHT, INK, PALE = "0F2A22", "FBFBF8", "14261F", "F3F1E8"
BLUE, BLUE_D, SKY, ORANGE, PEACH = "1F5FB0", "184C8F", "8FC0F5", "A8431A", "F29A70"
MUTED, MUTED_D, CARD, CARD_D, GREY = "4A5A53", "B9CFC6", "ECEFE7", "1B3D32", "6B7A73"
HEAD, BODY = "Calibri", "Calibri"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
px = lambda v: Inches(v / 144)          # the design grid is 1920 x 1080
rgb = lambda h: RGBColor.from_string(h)
state = {"n": 0}


def slide(bg=LIGHT, notes=""):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(bg)
    s.notes_slide.notes_text_frame.text = notes
    state["n"] += 1
    s.dark = bg != LIGHT
    return s


def text(s, x, y, w, h, content, size=32, color=None, bold=False, font=BODY, anchor="top", spacing=1.15,
         bullets=False, align=None):
    """content: str, or list of paragraphs; a paragraph is str or list of (text, bold) runs."""
    tb = s.shapes.add_textbox(px(x), px(y), px(w), px(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}[anchor]
    color = color or (PALE if s.dark else INK)
    paras = content if isinstance(content, list) else [content]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = spacing
        if align:
            p.alignment = align
        if i:
            p.space_before = Pt(size * 0.25)
        runs = para if isinstance(para, list) else [(para, bold)]
        if bullets:
            runs = [("•  ", False)] + runs
        for t, b in runs:
            r = p.add_run()
            r.text = t
            r.font.size, r.font.bold, r.font.name = Pt(size / 2), b, font
            r.font.color.rgb = rgb(color)
    return tb


def eyebrow(s, t):
    text(s, 128, 118, 1664, 40, t, size=26, bold=True, color=PEACH if s.dark else ORANGE)


def title(s, t, y=178):
    text(s, 128, y, 1664, 90, t, size=64, bold=True, font=HEAD, spacing=1.0)


def pageno(s):
    from pptx.enum.text import PP_ALIGN
    text(s, 1672, 990, 120, 34, str(state["n"]), size=24, color=MUTED_D if s.dark else MUTED, align=PP_ALIGN.RIGHT)


def card(s, x, y, w, h, fill=None):
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(x), px(y), px(w), px(h))
    sh.adjustments[0] = 0.05
    sh.fill.solid()
    sh.fill.fore_color.rgb = rgb(fill or (CARD_D if s.dark else CARD))
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def step_card(s, x, y, w, h, step, head, body, body_size=28):
    card(s, x, y, w, h)
    text(s, x + 36, y + 32, w - 72, 40, step, size=28, bold=True, color=SKY if s.dark else BLUE)
    text(s, x + 36, y + 80, w - 72, 100, head, size=40, bold=True, font=HEAD, spacing=1.0)
    text(s, x + 36, y + (190 if len(head) > 16 and w < 420 else 146), w - 72, h - 170, body, size=body_size, spacing=1.2)


def stat(s, x, y, w, value, label, size=72, color=None, label_size=28):
    text(s, x, y, w, size * 1.2, value, size=size, bold=True, font=HEAD, color=color or (SKY if s.dark else BLUE),
         spacing=1.0)
    text(s, x, y + size * 1.25, w, 120, label, size=label_size, spacing=1.15)


def image(s, name, x, y, w=None, h=None):
    kw = {}
    if w:
        kw["width"] = px(w)
    if h:
        kw["height"] = px(h)
    return s.shapes.add_picture(str(FIG / name), px(x), px(y), **kw)


def table(s, x, y, w, rows, widths, row_h=62, size=30):
    shape = s.shapes.add_table(len(rows), len(rows[0]), px(x), px(y), px(w), px(row_h * len(rows)))
    t = shape.table
    for j, f in enumerate(widths):
        t.columns[j].width = px(w * f)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = rgb(CARD if i == 0 else LIGHT)
            c.text_frame.text = ""
            r = c.text_frame.paragraphs[0].add_run()
            r.text = val
            r.font.size, r.font.bold, r.font.name = Pt(size / 2), i == 0, BODY
            r.font.color.rgb = rgb(INK)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE


# 1 cover -------------------------------------------------------------------
s = slide(DARK, "Good morning. My thesis asks a simple football question with a network science answer: if you "
                "could press one opposing player out of the game, who should it be?")
text(s, 128, 128, 1664, 40, "CSE 4199 PROJECT / THESIS  ·  FINAL PRESENTATION", size=26, bold=True, color=PEACH)
text(s, 128, 330, 1664, 120, "Who should you press?", size=104, bold=True, font=HEAD, spacing=1.0)
text(s, 128, 480, 1400, 130, "A graph-based vulnerability analysis of passing networks for identifying optimal "
                            "pressing targets", size=40, spacing=1.25)
ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, px(128), px(650), px(160), px(4))
ln.fill.solid(); ln.fill.fore_color.rgb = rgb(PEACH); ln.line.fill.background()
text(s, 128, 800, 760, 40, "Presented by", size=26, color=MUTED_D)
text(s, 128, 842, 760, 110, ["Mohaimeen Islam Pial", "ID 11230121094  ·  Section 7A"], size=32)
text(s, 960, 800, 760, 40, "Supervisor", size=26, color=MUTED_D)
text(s, 960, 842, 760, 110, ["Md. Shamim Parvez", "Senior Lecturer, Department of CSE"], size=32)

# 2 problem -----------------------------------------------------------------
s = slide(notes="Pressing is central to the modern game, but the choice of target is still mostly intuition. "
                "Existing network studies describe teams. This thesis moves from description to prescription.")
eyebrow(s, "THE PROBLEM"); title(s, "Pressing is planned by eye")
text(s, 128, 320, 940, 240, "Coaches decide whom to press from experience and video. There is no accepted, "
     "quantitative way to say which opposing player matters most to his team’s passing.", size=40, spacing=1.25)
text(s, 128, 610, 940, 200, "Research on passing networks has been descriptive: what a team’s structure looks like. "
     "It has not asked which player an opponent should attack.", size=32, color=MUTED, spacing=1.3)
for y, h, b in [(320, "Description", "“What does this team’s network look like?”"),
                (560, "Prescription", "“Which player should we press to break it?”")]:
    card(s, 1150, y, 642, 210)
    text(s, 1190, y + 36, 562, 50, h, size=40, bold=True, font=HEAD)
    text(s, 1190, y + 100, 562, 90, b, size=28)
pageno(s)

# 3 idea --------------------------------------------------------------------
s = slide(DARK, "The idea comes from network robustness theory. The internet survives random router failures but "
                "not a targeted attack on its hubs. I ask whether a passing network behaves the same way, and "
                "whether the hubs are the players opponents actually press.")
text(s, 128, 300, 1664, 40, "THE IDEA", size=26, bold=True, color=PEACH)
text(s, 128, 370, 1664, 200, "Treat pressing as an attack on a network.", size=84, bold=True, font=HEAD, spacing=1.05)
text(s, 128, 600, 1500, 220, "Albert, Jeong and Barabási (2000): networks with a few dominant hubs survive random "
     "failures and collapse when the hubs are targeted. A football team is a network of 11 nodes joined by passes.",
     size=40, color=MUTED_D, spacing=1.3)
pageno(s)

# 4 questions ---------------------------------------------------------------
s = slide(notes="These are the questions from the proposal. I will answer each of them with a number.")
eyebrow(s, "RESEARCH QUESTIONS"); title(s, "One main question, three parts")
text(s, 128, 300, 1664, 120, "Can vulnerability analysis of passing networks identify the most critical pressing "
     "targets, and does real match data agree?", size=40, spacing=1.25)
for i, (st, h, b) in enumerate([
        ("RQ1", "Which metric?", "Which of degree, betweenness, closeness and eigenvector centrality best predicts criticality?"),
        ("RQ2", "How much damage?", "How much more does a network degrade when its top player is removed than a random one?"),
        ("RQ3", "Does it match reality?", "Does the model’s ranking correlate with how often players are really pressed?")]):
    step_card(s, 128 + i * 565, 480, 533, 390, st, h, b)
pageno(s)

# 5 data --------------------------------------------------------------------
s = slide(notes="All data is StatsBomb open data, accessed with statsbombpy. The open Premier League coverage for "
                "2003/04 is Arsenal's unbeaten season, so Arsenal is the Premier League case study and the other "
                "competitions add statistical power.")
eyebrow(s, "DATA"); title(s, "120 matches of StatsBomb open event data")
for i, (v, l) in enumerate([("125,502", "pass events"), ("39,354", "pressure events"),
                            ("240", "team-match passing networks"), ("1,200", "players from 66 teams")]):
    x = 128 + i * 423
    card(s, x, 300, 395, 220)
    stat(s, x + 36, 330, 323, v, l)
table(s, 128, 570, 1664, [["Competition", "Matches", "Coverage"],
                          ["Premier League 2003/04", "38", "Every Arsenal league match"],
                          ["La Liga 2018/19 and 2019/20", "67", "Barcelona matches"],
                          ["FIFA World Cup 2018", "14", "National teams"],
                          ["Champions League 2018/19", "1", "Final"]], [0.46, 0.14, 0.40])
pageno(s)

# 6 method ------------------------------------------------------------------
s = slide(notes="Four steps. Build a directed weighted graph per team per match. Score players with four "
                "centralities combined into the TCS. Simulate pressing as node removal to get the Pressing "
                "Vulnerability Score. Then validate against real pressure events, always out of sample.")
eyebrow(s, "METHOD"); title(s, "From passes to pressing targets")
for i, (st, h, b) in enumerate([
        ("1 · BUILD", "Passing network", "Players are nodes. A directed edge carries the number of completed passes. Distance is 1 / passes."),
        ("2 · SCORE", "Centrality → TCS", "Four centralities combined into a Tactical Criticality Score. Weights learned with scikit-learn."),
        ("3 · ATTACK", "Node removal → PVS", "Delete each player, re-measure efficiency, path length, clustering and connectivity."),
        ("4 · VALIDATE", "Real pressing", "Spearman correlation with how often each player was pressed, on unseen matches.")]):
    x = 128 + i * 423
    card(s, x, 300, 395, 470)
    text(s, x + 32, 332, 331, 40, st, size=28, bold=True, color=BLUE)
    text(s, x + 32, 380, 331, 100, h, size=38, bold=True, font=HEAD, spacing=1.0)
    text(s, x + 32, 490, 331, 270, b, size=27, spacing=1.2)
text(s, 128, 810, 1664, 100, "Weights are fitted with 5-fold cross-validation grouped by match, so every score is "
     "tested on matches the model never saw.", size=32, color=MUTED, spacing=1.3)
pageno(s)

# 7 label -------------------------------------------------------------------
s = slide(notes="Midway through, I found that the validation label measured the wrong thing: a player's own "
                "defensive pressures. I rebuilt it by matching each pressure event to the opponent on the ball. "
                "Without this fix, every validation number would have been meaningless.")
eyebrow(s, "A PROBLEM FOUND ALONG THE WAY"); title(s, "The pressure data names the presser, not the pressed")
text(s, 128, 400, 800, 480, [
    [("A StatsBomb pressure event records the player ", False), ("applying", True),
     (" pressure. The first dataset counted these and called the column “pressure received”.", False)],
    "The label was rebuilt: each pressure event is assigned to the opposing player who releases the ball within "
    "2 seconds before to 5 seconds after it."], size=32, spacing=1.3)
for i, (v, l) in enumerate([("88.7%", "of pressure events attributed to a pressed player"),
                            ("ρ = 0.83", "agreement with StatsBomb’s own under-pressure flag on passes"),
                            ("ρ = 0.51", "agreement of the old, mislabelled column with the corrected one")]):
    stat(s, 1010, 400 + i * 185, 782, v, l)
pageno(s)

# 8 removal -----------------------------------------------------------------
s = slide(notes="Research question two. Removing the player the model ranks first costs the network fifteen percent "
                "of its global efficiency. A random starter costs four percent. The targeted removal was worse in "
                "every one of the 240 networks.")
eyebrow(s, "RESULT 1 · RQ2"); title(s, "Removing the top player costs 3.5 times more")
stat(s, 128, 310, 620, "15.3%", "of global efficiency lost when the highest-TCS player is removed", size=120)
stat(s, 128, 560, 620, "4.3%", "lost when a random first-eleven player is removed", size=120, color=GREY)
text(s, 128, 820, 620, 100, "Targeted removal was worse in all 240 networks (Wilcoxon p < 0.001).", size=26,
     color=MUTED, spacing=1.3)
image(s, "fig4_targeted_vs_random.png", 832, 310, w=960)
pageno(s)

# 9 attack ------------------------------------------------------------------
s = slide(notes="Removing players one after another, in order of TCS, leaves 39 percent of the original efficiency "
                "after five removals. Random removal leaves 70 percent. This is the same shape Albert and "
                "colleagues found for scale-free networks: robust to failure, fragile to attack.")
eyebrow(s, "RESULT 2 · RQ2"); title(s, "Repeated attack: 39% left against 70%")
image(s, "fig3_attack_curves.png", 240, 290, w=1440)
text(s, 128, 885, 1500, 80, "Random removal is drawn from the main eleven, averaged over 20 random orders per "
     "network. The right panel counts the removed players’ own connections as lost.", size=26, color=MUTED,
     spacing=1.3)
pageno(s)

# 10 validation -------------------------------------------------------------
s = slide(notes="Research questions one and three. The combined score correlates at 0.79 with real pressing inside a "
                "team, on matches it never saw, and 0.80 on held-out Premier League matches. Note the orange bars "
                "and the dashed line: that is the next slide.")
eyebrow(s, "RESULT 3 · RQ1 AND RQ3"); title(s, "The score matches who really gets pressed")
stat(s, 128, 310, 640, "ρ = 0.79", "mean within-team Spearman correlation between TCS and times pressed, on "
     "unseen matches", size=120)
text(s, 128, 600, 640, 360, [
    "0.80 on Premier League matches held out of training",
    "Top target is among the three most-pressed players in 67% of networks (22% by chance)",
    "Eigenvector and degree predict pressing best, betweenness worst"], size=28, bullets=True, spacing=1.2)
image(s, "fig2_metric_validation.png", 832, 310, w=960)
pageno(s)

# 11 ball -------------------------------------------------------------------
s = slide(BLUE, "This is the most important slide. Most of that 0.79 is explained by how much a player has the "
                "ball. After controlling for volume, network position adds a partial correlation of 0.27. And "
                "critical players receive pressure exactly in proportion to their possession. So real pressing "
                "follows the ball. The structural targets my model finds are not being exploited, and that is "
                "where a prescriptive tool adds something.")
text(s, 128, 128, 1664, 40, "THE HONEST FINDING", size=26, bold=True, color=LIGHT)
text(s, 128, 200, 1664, 210, "Opponents press the ball, not the structure.", size=84, bold=True, font=HEAD,
     color=LIGHT, spacing=1.05)
for i, (v, l) in enumerate([
        ("0.78", "Pass volume alone predicts pressing almost as well as TCS (0.79)"),
        ("0.27", "Partial correlation of TCS with pressing once volume is removed: real, and modest"),
        ("36% vs 36%", "Top-3 TCS players’ share of pressure (36.3%) against their share of the ball (36.0%)")]):
    x = 128 + i * 565
    card(s, x, 470, 533, 300, fill=BLUE_D)
    stat(s, x + 36, 505, 461, v, l, color=LIGHT)
text(s, 128, 830, 1664, 60, "Betweenness predicts structural damage best and real pressing worst.", size=40,
     color=LIGHT)
pageno(s)

# 12 arsenal ----------------------------------------------------------------
s = slide(notes="The season network of Arsenal's unbeaten side. Vieira is the most critical node and Pires the most "
                "damaging removal, which matches football intuition. The less obvious result is the full-backs: "
                "Lauren and Cole cost more efficiency than Henry. At Barcelona, Pique shows the same thing.")
eyebrow(s, "CASE STUDY · PREMIER LEAGUE 2003/04"); title(s, "Arsenal: press Vieira, watch the full-backs")
image(s, "fig1_arsenal_vulnerability_map.png", 128, 300, w=880)
table(s, 1060, 300, 732, [["Player", "TCS", "Efficiency lost if removed"], ["Vieira", "1.00", "11.8%"],
                          ["Pirès", "0.92", "12.4%"], ["Henry", "0.85", "7.4%"], ["Lauren", "0.80", "10.8%"],
                          ["Cole", "0.78", "10.5%"]], [0.36, 0.20, 0.44], row_h=66, size=28)
text(s, 1060, 730, 732, 200, "Removing either full-back costs more than removing Henry. Same pattern at Barcelona: "
     "Piqué is a top-two removal in both seasons yet pressed about 12 times a match, against 18 to 21 for Messi.",
     size=26, color=MUTED, spacing=1.3)
pageno(s)

# 13 dashboard --------------------------------------------------------------
s = slide(notes="The fifth objective was a dashboard. It does the three things in the proposal. Switch to the "
                "browser here and demonstrate: pick Arsenal, press Vieira out, show the efficiency drop, then turn "
                "on compare mode with Barcelona.")
eyebrow(s, "PROTOTYPE"); title(s, "The Pressing Intelligence Dashboard")
for i, (st, h, b) in enumerate([
        ("1", "Vulnerability map", "The main eleven on a pitch at their average positions, coloured by TCS or PVS. Hover for each player’s scores."),
        ("2", "Press simulation", "Select players to press out of the game. Their links are cut and efficiency, path length and clustering update live."),
        ("3", "Team comparison", "Two teams side by side, whole season or a single match, each with a ranked list of targets.")]):
    step_card(s, 128 + i * 565, 300, 533, 380, st, h, b)
text(s, 128, 730, 1664, 120, [[("Built with Streamlit and Plotly. Runs with ", False), ("streamlit run dashboard.py", True),
                               (" on the outputs of the analysis scripts.", False)]], size=40, spacing=1.25)
text(s, 128, 880, 1400, 50, "A live demonstration follows this slide.", size=32, color=MUTED)
pageno(s)

# 14 limits -----------------------------------------------------------------
s = slide(notes="The main limitation is causal. I show who is structurally critical and who is pressed, not that "
                "pressing the critical player wins the ball. That is the natural next study, along with softer "
                "models of pressing and more teams.")
eyebrow(s, "LIMITATIONS AND FUTURE WORK"); title(s, "What this does not show yet")
for x, h, items in [
        (128, "Limitations", ["Removing a node is a perfect, permanent press; real pressing is partial and brief",
                              "Observational data: no proof that pressing these players works",
                              "Arsenal and Barcelona supply 105 of 120 matches",
                              "The pressed player is inferred, and 11% of events are unassigned"]),
        (992, "Next steps", ["Test whether pressure on high-PVS players wins turnovers",
                             "Soft removal: weaken a pressed player’s links, not delete them",
                             "Time-resolved networks and StatsBomb 360 positions",
                             "Graph neural networks, with TCS as the baseline"])]:
    text(s, x, 310, 800, 50, h, size=40, bold=True, font=HEAD)
    text(s, x, 400, 780, 520, items, size=36, bullets=True, spacing=1.2)
pageno(s)

# 15 conclusion -------------------------------------------------------------
s = slide(DARK, "To conclude: the network attack framing works, the score is validated out of sample, and the most "
                "useful result is the mismatch between where teams press and where the network is weakest. "
                "Thank you.")
text(s, 128, 128, 1664, 40, "CONCLUSION", size=26, bold=True, color=PEACH)
text(s, 128, 210, 1664, 160, "Passing networks are robust to chance and fragile to attack", size=64, bold=True,
     font=HEAD, spacing=1.05)
text(s, 128, 420, 1664, 380, [
    "Removing the top-TCS player costs 15.3% of efficiency, 3.5 times a random starter",
    "TCS matches real pressing at ρ = 0.79 on unseen matches",
    "Real pressing follows possession; structural targets get no extra pressure",
    "All five objectives delivered, with an open-source pipeline and dashboard"], size=38, bullets=True, spacing=1.2)
ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, px(128), px(850), px(160), px(4))
ln.fill.solid(); ln.fill.fore_color.rgb = rgb(PEACH); ln.line.fill.background()
text(s, 128, 880, 1664, 60, "Thank you. Questions?", size=40)

prs.save(OUT)
print("saved", OUT, len(prs.slides.__iter__.__self__._sldIdLst), "slides")
