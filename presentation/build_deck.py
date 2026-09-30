"""Build the rainy-season access study deck (python-pptx, native charts)."""
import os
import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION

REPO = "/Users/charlesgava/uganda-rainy-season-access-study"
SCRATCH = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(REPO, "presentation", "rainy_season_access_study.pptx")

# Palette: navy of the travel-time maps, laterite (murram) accent of the crossings map
NAVY = RGBColor(0x0D, 0x2B, 0x52)
BLUE = RGBColor(0x2F, 0x6F, 0xB5)
PALE = RGBColor(0x9D, 0xBF, 0xE6)
LAT = RGBColor(0xB5, 0x45, 0x1B)
INK = RGBColor(0x1F, 0x2A, 0x37)
MUTED = RGBColor(0x5B, 0x65, 0x73)
PANEL = RGBColor(0xED, 0xF2, 0xF8)
BG = RGBColor(0xFB, 0xFB, 0xFA)  # matches the map figures' background
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
ICE = RGBColor(0xCA, 0xDC, 0xF2)

HEAD = "Cambria"
BODY = "Calibri"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW = 13.333


def bg(slide, color):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = color


def text(slide, x, y, w, h, runs, size=16, color=INK, font=BODY, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False, space_after=0,
         line_spacing=None):
    """runs: str, or list of paragraphs; each paragraph is str or list of (text, overrides)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        if space_after:
            para.space_after = Pt(space_after)
        if line_spacing:
            para.line_spacing = line_spacing
        segs = p if isinstance(p, list) else [(p, {})]
        for seg, ov in segs:
            r = para.add_run()
            r.text = seg
            f = r.font
            f.name = ov.get("font", font)
            f.size = Pt(ov.get("size", size))
            f.bold = ov.get("bold", bold)
            f.italic = ov.get("italic", italic)
            f.color.rgb = ov.get("color", color)
    return tb


def box(slide, x, y, w, h, fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, line=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def badge(slide, x, y, d, label, fill=LAT, color=WHITE, size=16):
    """Numbered circle: the deck's recurring motif."""
    c = box(slide, x, y, d, d, fill, shape=MSO_SHAPE.OVAL)
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name = HEAD
    r.font.bold = True
    r.font.size = Pt(size)
    r.font.color.rgb = color
    return c


def title(slide, t, kicker=None, color=NAVY):
    if kicker:
        text(slide, 0.6, 0.38, 12, 0.3, kicker.upper(), size=12, color=LAT, bold=True)
    text(slide, 0.6, 0.66, 12.1, 0.9, t, size=28, color=color, font=HEAD, bold=True)


def source(slide, t, color=MUTED):
    text(slide, 0.6, 7.0, 12.1, 0.3, t, size=10, color=color, italic=True)


def picture(slide, path, x, y, w=None, h=None, crop=None):
    """Place an image fitted inside the (w, h) box, centred."""
    im = Image.open(path)
    iw, ih = im.size
    if crop:
        l, t, r, b = crop
        iw, ih = iw * (1 - l - r), ih * (1 - t - b)
    ar = iw / ih
    if w / h > ar:
        pw, ph = h * ar, h
    else:
        pw, ph = w, w / ar
    px, py = x + (w - pw) / 2, y + (h - ph) / 2
    pic = slide.shapes.add_picture(path, Inches(px), Inches(py), Inches(pw), Inches(ph))
    if crop:
        pic.crop_left, pic.crop_top, pic.crop_right, pic.crop_bottom = crop
    return pic, (px, py, pw, ph)


def style_chart(chart, legend=True):
    chart.font.name = BODY
    chart.font.size = Pt(12)
    chart.font.color.rgb = MUTED
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.TOP
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(12)
    va = chart.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RGBColor(0xDD, 0xE2, 0xE8)
    va.major_gridlines.format.line.width = Pt(0.75)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(11)
    ca = chart.category_axis
    ca.format.line.color.rgb = RGBColor(0xB8, 0xC0, 0xCA)
    ca.tick_labels.font.size = Pt(12)
    ca.has_major_gridlines = False


# ---------------------------------------------------------------- data
nat = pd.read_csv(f"{REPO}/outputs/access_national_monthly.csv")
h = nat[(nat.target == "hospital") & (nat.group == "everyone")]
late = h[h.period == "late"].copy()
late["m"] = late.scenario.astype(int)
late = late.sort_values("m")
monthly = (late.share_over_1h * 100).round(1).tolist()
dry = float(h[h.scenario == "dry day"].share_over_1h.iloc[0] * 100)
wet = float(h[h.scenario == "wet day"].share_over_1h.iloc[0] * 100)

wealth = pd.read_csv(f"{REPO}/outputs/access_by_wealth.csv")
wh = wealth[(wealth["mode"] == "motorised") & (wealth.destination == "hospital")].sort_values("quintile")

catch = pd.read_csv(f"{REPO}/outputs/hospital_catchments.csv").sort_values(
    "extra_over_1h_april", ascending=False).head(6)

sens = pd.read_csv(f"{REPO}/outputs/sensitivity.csv")

# ================================================================ 1. Title
s = prs.slides.add_slide(BLANK)
bg(s, NAVY)
text(s, 0.7, 1.35, 6.4, 0.4, "RESEARCH PRESENTATION", size=13, color=PALE, bold=True)
text(s, 0.7, 1.75, 6.6, 1.7, "When the Rains Come", size=48, color=WHITE, font=HEAD, bold=True)
text(s, 0.7, 3.5, 6.3, 1.0,
     "Seasonal access to health care, schools and markets in Uganda",
     size=22, color=ICE, font=HEAD)
text(s, 0.7, 4.75, 6.2, 0.9,
     ["A month-by-month travel-time model built from open data:",
      "OpenStreetMap, WorldPop, CHIRPS rainfall and the Ministry of Health facility list"],
     size=14, color=ICE, space_after=4)
text(s, 0.7, 6.2, 6, 0.4, "Charles Gava  ·  2026", size=14, color=WHITE, bold=True)
# wet-day panel of the dry/wet map as the cover image
card = box(s, 7.75, 0.75, 4.9, 6.0, BG, radius=0.04)
pic, _ = picture(s, f"{REPO}/figures/maps/m01_hospital_dry_wet.png", 7.9, 0.9, 4.6, 5.3,
                 crop=(0.535, 0.16, 0.10, 0.155))
text(s, 7.95, 6.25, 4.5, 0.4, "Travel time to the nearest hospital on a wet day",
     size=11, color=MUTED, italic=True, align=PP_ALIGN.CENTER)
s.notes_slide.notes_text_frame.text = (
    "This study asks how much Uganda's rainy seasons lengthen journeys to essential services, "
    "where, in which months, and for whom. The cover map shows modelled travel time to the nearest "
    "hospital if every road were wet: darker blue means longer journeys.")

# ================================================================ 2. Background
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "Roads, and the journeys on them, change with the seasons", "Background")
rows = [
    ("1", "Two rainy seasons a year",
     "The long rains peak around March to May and the short rains around September to November. "
     "Each brings runs of days wet enough to turn murram roads to mud."),
    ("2", "A largely unpaved network",
     "Most rural roads are earth or gravel, and many cross rivers by fords rather than bridges. "
     "Wet earth roads lose much of their speed; a flooded ford can close a route entirely."),
    ("3", "Many journeys are made on foot",
     "Where there is no vehicle or boda boda at hand, travel is on foot, and it is slowest exactly "
     "when paths are wet."),
]
y = 1.85
for n, head, body in rows:
    badge(s, 0.6, y + 0.05, 0.55, n)
    text(s, 1.4, y, 6.1, 0.4, head, size=19, color=NAVY, font=HEAD, bold=True)
    text(s, 1.4, y + 0.45, 6.1, 1.0, body, size=15, color=INK)
    y += 1.6
box(s, 8.1, 1.85, 4.63, 4.6, NAVY, radius=0.05)
text(s, 8.5, 2.2, 3.9, 0.4, "THE GAP", size=12, color=PALE, bold=True)
text(s, 8.5, 2.6, 3.85, 1.9,
     "Standard accessibility maps assume a single, dry-weather speed for each road, all year round.",
     size=21, color=WHITE, font=HEAD, line_spacing=1.05)
text(s, 8.5, 4.55, 3.85, 1.7,
     "They cannot say how many people lose timely access in the wet months, where, or whether the "
     "loss falls evenly. That is what planners need to schedule maintenance, outreach and bridges.",
     size=14, color=ICE)
s.notes_slide.notes_text_frame.text = (
    "Uganda has a bimodal rainfall regime. Most of its road network is unpaved and many rural routes "
    "cross rivers by fords. Conventional friction-surface accessibility models use one fixed speed per "
    "road class, so they describe access on a dry day and miss the seasonal swing entirely.")

# ================================================================ 3. Research problem
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "Research problem", "What this study asks")
box(s, 0.6, 1.75, 5.6, 4.95, PANEL, radius=0.05)
text(s, 1.0, 2.1, 4.9, 0.4, "MAIN QUESTION", size=12, color=LAT, bold=True)
text(s, 1.0, 2.55, 4.85, 2.5,
     "How much do Uganda's rainy seasons lengthen journeys to hospitals, health centres, schools, "
     "markets and towns?",
     size=24, color=NAVY, font=HEAD, bold=True, line_spacing=1.05)
text(s, 1.0, 5.0, 4.85, 1.5,
     [[("Benchmark: ", {"bold": True, "color": INK}),
       ("the WHO / Lancet Commission target is surgical and obstetric care within 2 hours. "
        "We also use a 1-hour threshold for hospitals.", {})]],
     size=14, color=MUTED)
subs = [
    ("How much?", "How many more people fall beyond 1 hour (or 2 hours) of a service when it rains?"),
    ("When?", "Which months are worst, and has the pattern shifted since 1981–2000?"),
    ("Where?", "Which districts, sub-counties, hospital catchments and river crossings?"),
    ("For whom?", "Women of reproductive age, children under 5, the poorest fifth, refugee-hosting areas, people on foot."),
]
y = 1.75
for i, (q, d) in enumerate(subs):
    badge(s, 6.7, y + 0.1, 0.55, str(i + 1), fill=NAVY)
    text(s, 7.5, y, 5.2, 0.4, q, size=19, color=NAVY, font=HEAD, bold=True)
    text(s, 7.5, y + 0.42, 5.2, 0.75, d, size=14, color=INK)
    y += 1.27
s.notes_slide.notes_text_frame.text = (
    "The central question has four parts: magnitude, timing, geography and equity. "
    "The two-hour benchmark comes from the Lancet Commission on Global Surgery and WHO.")

# ================================================================ 4. Data
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "Data: all public, no new surveys", "Methodology · inputs")
cards = [
    ("Roads", "OpenStreetMap", "~690,000 segments with class, surface (where tagged), bridges and fords"),
    ("Destinations", "Ministry of Health list (Maina et al. 2019)",
     "Public and not-for-profit facilities by level; schools, markets and towns from OSM"),
    ("Population", "WorldPop 2020, 1 km grid",
     "~244,000 populated cells, with age and sex structure for women 15–49 and children under 5"),
    ("Rainfall", "CHIRPS daily, 1981–2025",
     "45 years of satellite rainfall give each cell's share of wet days in each month"),
    ("Wealth & boundaries", "Meta Relative Wealth Index; HDX",
     "Wealth quintiles; district and sub-county boundaries for aggregation"),
    ("Validation", "DHS 2016, 15 regions",
     "Regional health indicators, including women citing distance as a barrier to care"),
]
cw, ch, gx, gy = 3.88, 2.35, 0.23, 0.3
for i, (h1, h2, d) in enumerate(cards):
    cx = 0.6 + (i % 3) * (cw + gx)
    cy = 1.75 + (i // 3) * (ch + gy)
    box(s, cx, cy, cw, ch, WHITE, radius=0.05, line=RGBColor(0xDD, 0xE2, 0xE8))
    badge(s, cx + 0.3, cy + 0.3, 0.45, str(i + 1), size=13)
    text(s, cx + 0.9, cy + 0.3, cw - 1.1, 0.45, h1, size=18, color=NAVY, font=HEAD, bold=True,
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, cx + 0.3, cy + 0.92, cw - 0.55, 0.4, h2, size=13, color=LAT, bold=True)
    text(s, cx + 0.3, cy + 1.3, cw - 0.55, 0.95, d, size=13, color=INK)
s.notes_slide.notes_text_frame.text = (
    "All inputs are open. 22 hospitals and HC IVs with clearly wrong coordinates were moved to their "
    "OpenStreetMap location (see data/facility_relocations.csv).")

# ================================================================ 5. Method: model
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "A friction surface that gets wet", "Methodology · travel-time model")
steps = [
    ("Friction surface", "Each 1 km cell takes the speed of the fastest road through it."),
    ("Wet-day speeds", "Gravel keeps 70%, earth 40%, footpaths 60%. A road over a ford drops to 0.5 km/h."),
    ("Wet-day chance", "CHIRPS: ≥10 mm of rain, or the day after ≥25 mm, gives each cell's share of wet days per month."),
    ("Monthly cost", "Expected crossing time mixes dry and wet speeds by that share."),
    ("Least-cost paths", "Travel time to the nearest destination, every month, by road and on foot."),
]
sw_, gap = 2.3, 0.15
for i, (h1, d) in enumerate(steps):
    x = 0.6 + i * (sw_ + gap)
    box(s, x, 1.8, sw_, 2.75, NAVY if i != 3 else LAT, radius=0.06)
    text(s, x + 0.22, 1.98, 0.6, 0.45, f"0{i + 1}", size=20, color=PALE if i != 3 else WHITE,
         font=HEAD, bold=True)
    text(s, x + 0.22, 2.45, sw_ - 0.4, 0.45, h1, size=17, color=WHITE, font=HEAD, bold=True)
    text(s, x + 0.22, 2.95, sw_ - 0.4, 1.5, d, size=13, color=ICE if i != 3 else WHITE)
# formula panel
box(s, 0.6, 4.85, 7.1, 1.9, PANEL, radius=0.05)
text(s, 0.95, 5.05, 6.5, 0.35, "EXPECTED TIME TO CROSS A CELL IN A MONTH", size=12, color=LAT, bold=True)
text(s, 0.95, 5.45, 6.5, 0.6,
     [[("t = (1 − f) / v", {}), ("dry", {"size": 16}), ("  +  f / v", {}), ("wet", {"size": 16})]],
     size=28, color=NAVY, font=HEAD, bold=True)
text(s, 0.95, 6.15, 6.5, 0.5, "f = share of wet days in that cell and month (CHIRPS)",
     size=13, color=MUTED, italic=True)
box(s, 7.95, 4.85, 4.78, 1.9, PANEL, radius=0.05)
text(s, 8.3, 5.05, 4.2, 0.35, "TWO TRAVEL MODES", size=12, color=LAT, bold=True)
text(s, 8.3, 5.45, 4.2, 1.2,
     [[("Motorised: ", {"bold": True, "color": NAVY}), ("road speeds, motorcycle taxis on paths", {})],
      [("Walking: ", {"bold": True, "color": NAVY}), ("5 km/h, slower on wet earth", {})]],
     size=15, color=INK, space_after=6)
s.notes_slide.notes_text_frame.text = (
    "A ford only cuts off a cell when it is the only way through, because other roads in the same "
    "1 km cell keep their speed. The wet-day rule comes from the companion paper on construction "
    "delays (lost earthworks days). All parameters live in PARAMS in scripts/model.py.")

# ================================================================ 6. Method: design
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "Analysis design", "Methodology · scenarios and breakdowns")
quads = [
    ("Destinations", ["Hospitals", "HC IV or hospital (emergency obstetric care)", "Any health facility",
                      "Secondary schools, markets, towns"]),
    ("Scenarios", ["Every day dry; every day wet", "Each of the 12 months",
                   "Rainfall of 1981–2000 vs 2006–2025"]),
    ("Breakdowns", ["District, sub-county, hospital catchment", "Women 15–49 and children under 5",
                    "Wealth quintiles; refugee-hosting sub-counties"]),
    ("Checks", ["16 sensitivity runs varying every assumption", "Validation against DHS 2016 (15 regions)",
                "72 river crossings ranked by time saved"]),
]
qw, qh = 5.95, 2.4
for i, (h1, items) in enumerate(quads):
    qx = 0.6 + (i % 2) * (qw + 0.23)
    qy = 1.75 + (i // 2) * (qh + 0.25)
    box(s, qx, qy, qw, qh, WHITE if i % 3 else PANEL, radius=0.05,
        line=RGBColor(0xDD, 0xE2, 0xE8))
    badge(s, qx + 0.3, qy + 0.3, 0.5, "ABCD"[i], fill=NAVY, size=15)
    text(s, qx + 1.0, qy + 0.3, qw - 1.3, 0.5, h1, size=20, color=NAVY, font=HEAD, bold=True,
         anchor=MSO_ANCHOR.MIDDLE)
    tb = text(s, qx + 1.0, qy + 0.95, qw - 1.3, qh - 1.1, items, size=15, color=INK, space_after=4)
    for p in tb.text_frame.paragraphs:
        pPr = p._p.get_or_add_pPr()
        pPr.set("marL", str(Emu(Inches(0.22))))
        pPr.set("indent", str(-Emu(Inches(0.22))))
        from pptx.oxml.ns import qn
        from lxml import etree
        bu = etree.SubElement(pPr, qn("a:buChar"))
        bu.set("char", "•")
s.notes_slide.notes_text_frame.text = (
    "Results reported are for 2006–2025 rainfall and the official facility list, unless stated. "
    "Alternative runs use OSM facilities and walking-only travel.")

# ================================================================ 7. Result 1: monthly curve
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "April adds ~2.3 million people beyond an hour of a hospital",
      "Results · when")
stats = [(f"{dry:.1f}%", "every day dry", BLUE),
         (f"{max(monthly):.1f}%", "April, peak of the long rains", LAT),
         (f"{wet:.1f}%", "every day wet", NAVY)]
y = 1.8
for v, lab, col in stats:
    text(s, 0.6, y, 3.4, 0.8, v, size=48, color=col, font=HEAD, bold=True)
    text(s, 0.62, y + 0.82, 3.4, 0.4, lab, size=14, color=MUTED)
    y += 1.55
text(s, 0.6, 6.45, 3.5, 0.5, "of Ugandans more than 1 hour from a hospital by road",
     size=12, color=INK, italic=True)
cd = CategoryChartData()
cd.categories = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
cd.add_series("Monthly expected (2006–2025 rainfall)", monthly)
cd.add_series("Every day dry", [round(dry, 1)] * 12)
gf = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(4.3), Inches(1.7), Inches(8.45),
                        Inches(5.2), cd)
c = gf.chart
style_chart(c)
c.value_axis.minimum_scale = 10
c.value_axis.maximum_scale = 20
c.value_axis.major_unit = 2
c.value_axis.tick_labels.number_format = '0"%"'
c.value_axis.tick_labels.number_format_is_linked = False
s1, s2 = c.plots[0].series
s1.format.line.color.rgb = LAT
s1.format.line.width = Pt(3)
s1.smooth = False
s1.marker.format.fill.solid()
s1.marker.format.fill.fore_color.rgb = LAT
s1.marker.format.line.color.rgb = LAT
s1.marker.size = 7
s2.format.line.color.rgb = BLUE
s2.format.line.width = Pt(2)
s2.format.line.dash_style = 4  # dash
s2.smooth = False
from pptx.enum.chart import XL_MARKER_STYLE
s2.marker.style = XL_MARKER_STYLE.NONE
for idx in (3, 9):
    pt = s1.points[idx]
    pt.data_label.has_text_frame = False
    pt.data_label.show_value = True
    pt.data_label.number_format = '0.0"%"'
    pt.data_label.number_format_is_linked = False
    pt.data_label.position = XL_LABEL_POSITION.ABOVE
    pt.data_label.font.size = Pt(13)
    pt.data_label.font.bold = True
    pt.data_label.font.color.rgb = LAT
source(s, "Share of population more than 1 hour from a hospital by road. April is the worst month in 79 of 135 districts. "
          "Sources: OSM; MoH facility list; WorldPop 2020; CHIRPS 2006–2025.")
s.notes_slide.notes_text_frame.text = (
    "The year has two peaks, following the two rainy seasons: April (18.1%) and October (17.4%). "
    "The difference between dry weather and April is about 5 percentage points, roughly 2.3 million "
    "people. The curve for 1981–2000 rainfall is almost identical: the seasonal cycle matters much "
    "more than the long-term trend.")

# ================================================================ 8. Result 2: dry vs wet map
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "On a wet day, the one-hour hospital zone shrinks sharply", "Results · where")
picture(s, f"{REPO}/figures/maps/m01_hospital_dry_wet.png", 0.45, 1.55, 9.6, 5.35,
        crop=(0.0, 0.0, 0.0, 0.0))
box(s, 10.3, 1.9, 2.43, 4.7, PANEL, radius=0.06)
text(s, 10.55, 2.15, 2.0, 4.3,
     [[("13.1% → 30.5%", {"bold": True, "color": LAT, "size": 20, "font": HEAD})],
      "of people beyond 1 hour, dry vs fully wet.",
      "",
      [("Hardest hit", {"bold": True, "color": NAVY})],
      "The north-east (Karamoja), the west and the Lake Kyoga basin, where hospitals are sparse and "
      "roads unpaved."],
     size=13, color=INK)
s.notes_slide.notes_text_frame.text = (
    "The fully wet map is an upper bound: it assumes every day is wet. Monthly results mix the two "
    "according to each cell's share of wet days.")

# ================================================================ 9. Result 3: wealth
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "The rains fall on everyone, but the burden doesn't", "Results · for whom")
cd = CategoryChartData()
cd.categories = ["Poorest fifth", "2nd", "3rd", "4th", "Richest fifth"]
cd.add_series("Dry weather", (wh.dry * 100).round(1).tolist())
cd.add_series("April", (wh.april * 100).round(1).tolist())
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.65), Inches(7.6),
                        Inches(5.25), cd)
c = gf.chart
style_chart(c)
c.value_axis.maximum_scale = 40
c.value_axis.minimum_scale = 0
c.value_axis.major_unit = 10
c.value_axis.tick_labels.number_format = '0"%"'
c.value_axis.tick_labels.number_format_is_linked = False
c.plots[0].gap_width = 70
c.plots[0].overlap = -10
for ser, col in zip(c.plots[0].series, (PALE, LAT)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
    ser.data_labels.show_value = True
    ser.data_labels.number_format = '0"%"'
    ser.data_labels.number_format_is_linked = False
    ser.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    ser.data_labels.font.size = Pt(12)
    ser.data_labels.font.color.rgb = INK
cards = [
    ("Poorest fifth", "23% → 32%", "beyond 1 h of a hospital, dry vs April. On foot to any facility: 30% → 36%."),
    ("Richest fifth", "0.8% → 1.0%", "the seasons barely touch them."),
    ("Refugee-hosting sub-counties", "22% → 33%", "against 13% → 18% elsewhere (14 sub-counties with an OSM refugee site)."),
]
y = 1.75
for h1, v, d in cards:
    box(s, 8.45, y, 4.28, 1.62, PANEL, radius=0.06)
    text(s, 8.7, y + 0.15, 3.8, 0.3, h1.upper(), size=11, color=MUTED, bold=True)
    text(s, 8.7, y + 0.42, 3.8, 0.5, v, size=24, color=LAT, font=HEAD, bold=True)
    text(s, 8.7, y + 0.95, 3.85, 0.65, d, size=12, color=INK)
    y += 1.77
source(s, "Share more than 1 hour from a hospital by road, by Relative Wealth Index quintile.")
s.notes_slide.notes_text_frame.text = (
    "The poorest start furthest away and the rains add the most to their journeys. Wealthier areas are "
    "close to facilities and on better roads. The seasonal gap is an inequality gap that recurs on a "
    "known timetable.")

# ================================================================ 10. Result 4: walking & EmOC
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "Walking, not roads, is the barrier to obstetric care", "Results · for whom")
picture(s, f"{REPO}/figures/maps/m04_emoc_motorised_walking.png", 0.45, 1.5, 12.45, 4.35)
stats = [("0.9% → 1.2%", "of women 15–49 more than 2 h away by road (dry → April)", BLUE),
         ("41% → 43%", "more than 2 h away on foot (dry → April)", LAT),
         ("16.5% → 19.9%", "of everyone more than 1 h on foot from any facility", NAVY)]
for i, (v, lab, col) in enumerate(stats):
    x = 0.6 + i * 4.1
    text(s, x, 5.95, 3.8, 0.5, v, size=24, color=col, font=HEAD, bold=True)
    text(s, x, 6.5, 3.8, 0.5, lab, size=13, color=INK)
s.notes_slide.notes_text_frame.text = (
    "Emergency obstetric care is proxied by the nearest HC IV or hospital, against the 2-hour benchmark. "
    "A woman with a boda boda or a vehicle is almost always within reach; a woman who has to walk "
    "often is not, and the rains make it worse.")

# ================================================================ 11. Result 5: catchments & sub-counties
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "The loss concentrates in a few catchments and sub-counties", "Results · where")
names = [n.replace(" Regional Referral Hospital", " RRH") for n in catch.hospital]
cd = CategoryChartData()
cd.categories = list(reversed(names))
cd.add_series("Extra people beyond 1 h in April (thousands)",
              list(reversed((catch.extra_over_1h_april / 1000).round(0).tolist())))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(2.1), Inches(6.6),
                        Inches(4.75), cd)
c = gf.chart
style_chart(c, legend=False)
c.value_axis.visible = False
c.value_axis.has_major_gridlines = False
c.value_axis.minimum_scale = 0
c.value_axis.maximum_scale = 180
c.plots[0].gap_width = 55
ser = c.plots[0].series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = NAVY
ser.data_labels.show_value = True
ser.data_labels.number_format = '0"k"'
ser.data_labels.number_format_is_linked = False
ser.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
ser.data_labels.font.size = Pt(13)
ser.data_labels.font.bold = True
ser.data_labels.font.color.rgb = NAVY
c.category_axis.tick_labels.font.size = Pt(13)
c.category_axis.tick_labels.font.color.rgb = INK
text(s, 0.6, 1.65, 6.4, 0.4, "Hospital catchments: extra people beyond 1 hour in April",
     size=15, color=NAVY, bold=True)
text(s, 7.6, 1.65, 5.1, 0.4, "Sub-counties with the largest April jumps", size=15, color=NAVY, bold=True)
subc = [("Malongo", "Mayuge", 59, 93), ("Butoloogo", "Mubende", 26, 84),
        ("Kagulu", "Buyende", 33, 66), ("Kyangwali", "Kikuube · refugee settlement", 54, 77)]
y = 2.2
for nm, dist, a, b in subc:
    box(s, 7.6, y, 5.13, 1.02, WHITE, radius=0.08, line=RGBColor(0xDD, 0xE2, 0xE8))
    text(s, 7.85, y + 0.14, 2.5, 0.4, nm, size=17, color=NAVY, font=HEAD, bold=True)
    text(s, 7.85, y + 0.55, 2.7, 0.35, dist, size=12, color=MUTED)
    text(s, 10.3, y + 0.14, 2.2, 0.75,
         [[(f"{a}%", {"color": BLUE}), (" → ", {"color": MUTED}), (f"{b}%", {"color": LAT})]],
         size=22, font=HEAD, bold=True, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
    y += 1.17
source(s, "Share of people more than 1 hour from a hospital by road, dry weather → April.")
s.notes_slide.notes_text_frame.text = (
    "Clusters are in Busoga, around Mubende and Kassanda, in Lango and along the Lake Victoria shore. "
    "District health teams could use these worst-month figures to pre-position ambulances, stock and outreach.")

# ================================================================ 12. Result 6: crossings
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "A handful of river crossings matter a great deal", "Results · what could be done")
picture(s, f"{REPO}/figures/maps/m08_crossings.png", 0.5, 1.5, 6.3, 5.45, crop=(0.0, 0.08, 0.0, 0.0))
text(s, 7.2, 1.7, 5.5, 0.9,
     "72 distinct fords were ranked by the wet-day travel time a bridge would save on trips to "
     "emergency obstetric care.", size=15, color=INK)
cr = [("1", "Riwo, Bukwo", "~7,000 people brought within 1 h on wet days, incl. 1,500 women 15–49"),
      ("2", "Karita, Amudat", "~1,500 people within 1 h; 630 women"),
      ("3", "Kilembe, Kasese", "Footpath ford: ~2,700 person-hours saved per wet day; next is Panyangara, Kotido")]
y = 2.8
for n, nm, d in cr:
    badge(s, 7.2, y + 0.05, 0.55, n)
    text(s, 7.95, y, 4.8, 0.4, nm, size=19, color=NAVY, font=HEAD, bold=True)
    text(s, 7.95, y + 0.42, 4.8, 0.7, d, size=14, color=INK)
    y += 1.2
text(s, 7.2, 6.4, 5.5, 0.5, "A starting list for district engineers, to be checked on the ground.",
     size=13, color=MUTED, italic=True)
s.notes_slide.notes_text_frame.text = (
    "All top three are on secondary roads in the east and north-east. Crossings within 2 km of a "
    "higher-ranked one are merged.")

# ================================================================ 13. Robustness & validation
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "The seasonal rise survives every robustness test",
      "Results · robustness")
text(s, 0.6, 1.7, 6, 0.4, "Sensitivity: April rise in points, by wet-day definition", size=15,
     color=NAVY, bold=True)
wd = sens[sens.variant.str.contains("Wet day") | (sens.variant == "Baseline")].copy()
wd["label"] = wd.variant.str.replace("Wet day = rain ", "").str.replace("Baseline", "≥10 mm (baseline)")
order = {"≥20 mm": 0, "≥10 mm (baseline)": 1, "≥5 mm": 2}
wd = wd[wd.label.isin(order)].sort_values("label", key=lambda s_: s_.map(order))
cd = CategoryChartData()
cd.categories = wd.label.tolist()
cd.add_series("April minus dry (percentage points)", wd.april_minus_dry_pp.round(1).tolist())
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(2.1), Inches(6.0),
                        Inches(3.2), cd)
c = gf.chart
style_chart(c, legend=False)
c.value_axis.visible = False
c.value_axis.has_major_gridlines = False
c.value_axis.minimum_scale = 0
c.value_axis.maximum_scale = 13
c.plots[0].gap_width = 80
ser = c.plots[0].series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = PALE
ser.points[1].format.fill.solid()
ser.points[1].format.fill.fore_color.rgb = LAT
ser.data_labels.show_value = True
ser.data_labels.number_format = '"+"0.0" pts"'
ser.data_labels.number_format_is_linked = False
ser.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
ser.data_labels.font.size = Pt(14)
ser.data_labels.font.bold = True
ser.data_labels.font.color.rgb = INK
text(s, 0.6, 5.5, 6.0, 1.3,
     [[("16 variants ", {"bold": True, "color": NAVY}),
       ("of speeds, fords, surfaces, walking speed and facility source: the April rise is positive in all.", {})],
      [("District rankings ", {"bold": True, "color": NAVY}),
       ("agree with the baseline (Spearman 0.88–1.00).", {})]],
     size=14, color=INK, space_after=6)
box(s, 7.0, 1.7, 5.73, 5.15, NAVY, radius=0.05)
text(s, 7.4, 2.0, 5.0, 0.4, "VALIDATION AGAINST DHS 2016", size=12, color=PALE, bold=True)
text(s, 7.4, 2.45, 2.5, 0.9, "ρ ≈ 0.8", size=44, color=WHITE, font=HEAD, bold=True)
text(s, 7.4, 3.4, 5.0, 0.9,
     "Modelled access vs share of women citing distance as a barrier to care, across 15 regions "
     "(ρ = 0.81–0.83, p < 0.001).", size=14, color=ICE)
text(s, 7.4, 4.35, 5.0, 0.8,
     [[("Still ρ = 0.52–0.59 ", {"bold": True, "color": WHITE}),
       ("after controlling for wealth (p = 0.02–0.05).", {})]], size=14, color=ICE)
text(s, 7.4, 5.2, 5.0, 1.5,
     [[("Not predictive ", {"bold": True, "color": WHITE}),
       ("of facility births or vaccination at regional level: Karamoja has poor access but ~80% "
        "facility births.", {})]], size=14, color=ICE)
s.notes_slide.notes_text_frame.text = (
    "Report the April rise as a range: about 1 to 10 points, 5 central. The seasonal test of whether "
    "facility births dip in bad months needs DHS birth-level microdata.")

# ================================================================ 14. Discussion
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "Discussion: what the findings mean", "Discussion")
pts = [
    ("Access has a calendar",
     "Dry-weather maps understate exclusion. The worst month, not the average day, should anchor "
     "access targets, and it is predictable years ahead."),
    ("The seasonal gap is an equity gap",
     "The poorest fifth, refugee-hosting areas and people on foot lose the most, on the same timetable every year."),
    ("Transport, not just distance",
     "For emergency obstetric care, a ride matters more than a road. Motorcycle ambulances and maternity "
     "waiting homes target the binding constraint."),
    ("Small, targeted works pay",
     "Grade and drain feeder roads before the long rains, and bridge the few fords that cut off the most people."),
]
cw, ch = 5.95, 2.4
for i, (h1, d) in enumerate(pts):
    cx = 0.6 + (i % 2) * (cw + 0.23)
    cy = 1.75 + (i // 2) * (ch + 0.25)
    box(s, cx, cy, cw, ch, PANEL, radius=0.05)
    badge(s, cx + 0.35, cy + 0.35, 0.55, str(i + 1))
    text(s, cx + 1.15, cy + 0.35, cw - 1.45, 0.55, h1, size=19, color=NAVY, font=HEAD, bold=True,
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, cx + 1.15, cy + 1.0, cw - 1.45, 1.3, d, size=14, color=INK)
s.notes_slide.notes_text_frame.text = (
    "The national seasonal pattern under 1981–2000 rainfall is almost the same as under 2006–2025: "
    "the seasonal cycle, not the long-term rainfall trend, drives access. This links back to the "
    "companion construction-delay paper: when a road contract slips into the rainy season, it delays "
    "the road and extends the isolation it was meant to fix.")

# ================================================================ 15. Limitations
s = prs.slides.add_slide(BLANK)
bg(s, BG)
title(s, "Limitations and next steps", "Discussion")
lims = [
    ("OSM completeness", "Most roads lack a surface tag, so class defaults set wet speeds. "
                         "Treating untagged secondary/tertiary roads as earth shifts district ranks most (ρ 0.90)."),
    ("Facility list", "Dates from about 2018 and excludes private for-profit facilities; relocations need a manual check."),
    ("Refugee sites", "Incomplete in OSM; UNHCR settlement boundaries would allow a full breakdown."),
    ("Ferries", "Not modelled: Kalangala and Buvuma appear cut off."),
    ("Rainfall", "CHIRPS and TAMSAT disagree on northern trends; the seasonal cycle is less affected."),
    ("Validation", "Regional only. Testing whether births shift in bad months needs DHS microdata."),
]
for i, (h1, d) in enumerate(lims):
    col, row = i % 2, i // 2
    x = 0.6 + col * 6.2
    y = 1.8 + row * 1.7
    badge(s, x, y + 0.05, 0.45, "!", fill=NAVY, size=14)
    text(s, x + 0.7, y, 5.3, 0.4, h1, size=17, color=NAVY, font=HEAD, bold=True)
    text(s, x + 0.7, y + 0.42, 5.3, 1.1, d, size=14, color=INK)
text(s, 0.6, 6.85, 12, 0.4,
     "A model describes what the roads allow, not what every family actually does.",
     size=13, color=MUTED, italic=True)
s.notes_slide.notes_text_frame.text = (
    "Next steps: ground-truth the crossing list, add UNHCR settlement boundaries, model ferries, and "
    "run the seasonal births test with DHS birth-level data.")

# ================================================================ 16. Conclusion
s = prs.slides.add_slide(BLANK)
bg(s, NAVY)
text(s, 0.7, 0.8, 12, 0.4, "CONCLUSION", size=13, color=PALE, bold=True)
text(s, 0.7, 1.25, 12, 1.0, "Uganda's access problem has a season, a place and a face",
     size=34, color=WHITE, font=HEAD, bold=True)
tk = [("13% → 18%", "beyond 1 h of a hospital in April: ~2.3 million more people"),
      ("23% → 32%", "the poorest fifth, against ~1% for the richest"),
      ("43%", "of women 15–49 more than 2 h on foot from emergency obstetric care in April")]
for i, (v, d) in enumerate(tk):
    x = 0.7 + i * 4.1
    text(s, x, 2.85, 3.8, 0.9, v, size=38, color=PALE if i != 2 else RGBColor(0xF0, 0x9A, 0x6E),
         font=HEAD, bold=True)
    text(s, x, 3.8, 3.6, 1.0, d, size=15, color=ICE)
text(s, 0.7, 5.35, 11.9, 0.6,
     "Plan by season and by place: time maintenance before April, target the poorest, and bridge the right crossings.",
     size=17, color=WHITE)
text(s, 0.7, 6.35, 12, 0.4,
     [[("Interactive map: ", {"bold": True, "color": WHITE}),
       ("gavacharles.github.io/uganda-rainy-season-access", {})]], size=14, color=ICE)
s.notes_slide.notes_text_frame.text = "Thank you. Questions."

os.makedirs(os.path.dirname(OUT), exist_ok=True)
prs.save(OUT)
print("saved", OUT)
