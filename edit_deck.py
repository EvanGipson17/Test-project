"""Applies the requested edits to the AQUA SIGHT deck (10in x 5.625in Google Slides export)."""
import copy, sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree

SRC, OUT = sys.argv[1], sys.argv[2]
NAVY, TEAL, AQUA = "0B3D5C", "1F7A8C", "3FC1C9"
OFF_WHITE, SLATE, WHITE = "F7FAFC", "4A5568", "FFFFFF"
MONT, INTER = "Montserrat", "Inter"

prs = Presentation(SRC)
W, H = prs.slide_width, prs.slide_height
BLANK = next(l for l in prs.slide_layouts if l.name == "BLANK")


def rgb(h):
    return RGBColor.from_string(h)


def set_font(run, font, size, color, bold=False):
    f = run.font
    f.name = font
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = rgb(color)
    # Google Slides keys off these too; keep them consistent so Slides shows the right font.
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set("typeface", font)


def textbox(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, name=None):
    """paras: list of paragraphs. Each is a list of runs (text, font, size, color, bold)
    or a single run tuple. Use [] for a blank spacer paragraph (sized by `spacer`)."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    first = True
    for p in paras:
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.alignment = align
        runs = p if isinstance(p, list) else [p]
        for t, font, size, color, bold in runs:
            set_font(para.add_run(), font, size, color, bold)
            para.runs[-1].text = t
    return tb


def blank_para(size):
    return [("", INTER, size, SLATE, False)]


def shape(slide, kind, x, y, w, h, fill, name=None):
    sh = slide.shapes.add_shape(kind, x, y, w, h)
    if name:
        sh.name = name
    sh.fill.solid()
    sh.fill.fore_color.rgb = rgb(fill)
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def chrome(slide, title):
    """Matches the existing slides: label at (0.60,0.10), title at (0.60,0.30), footer at (9.38,5.29)."""
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = rgb(OFF_WHITE)
    textbox(slide, Emu(548641), Emu(96012), Emu(1371600), Emu(178500),
            [("AQUA SIGHT", MONT, 8, NAVY, True)], name="Label")
    textbox(slide, Emu(548641), Emu(274321), Inches(8.0), Emu(411600),
            [(title, MONT, 19, NAVY, True)], name="Title")
    textbox(slide, Emu(8572521), Emu(4834902), Emu(342900), Emu(219600),
            [("0", INTER, 8, SLATE, False)], name="Footer")


def find_shape(slide, needle):
    for sh in slide.shapes:
        if sh.has_text_frame and needle in sh.text_frame.text:
            return sh
    return None


def slide_text(slide):
    return "\n".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


def find_slide(needle):
    for s in prs.slides:
        if needle in slide_text(s):
            return s
    raise SystemExit(f"slide containing {needle!r} not found")


def replace_run_text(slide, old, new, exact=False):
    """Replace inside single runs so formatting is untouched. Returns count."""
    n = 0
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                if (r.text == old) if exact else (old in r.text):
                    r.text = r.text.replace(old, new)
                    n += 1
    return n


# ---------------------------------------------------------------- TASK 4a: text fixes
inv = find_slide("Investor Request")
assert replace_run_text(inv, "150,00", "150,000", exact=True) == 1   # "$150,000" also contains it
assert replace_run_text(inv, "19", "18", exact=True) == 1
assert replace_run_text(inv, "Roundrock", "Round Rock") == 1
print("text fixes applied")

# ---------------------------------------------------------------- TASK 2: revenue slide
s = prs.slides.add_slide(BLANK)
chrome(s, "How Much We've Made So Far")
L = Inches(0.60)

textbox(s, L, Inches(1.00), Inches(4.0), Inches(0.30), [("Revenue to date", INTER, 9, TEAL, True)])
textbox(s, L, Inches(1.22), Inches(4.2), Inches(0.95), [("$5,185", MONT, 44, TEAL, True)])
textbox(s, L, Inches(2.25), Inches(4.2), Inches(2.6), [
    [("Subscriptions: ", INTER, 10, SLATE, True), ("$2,793 (7 pools × $399, September)", INTER, 10, SLATE, False)],
    [("Event rentals: ", INTER, 10, SLATE, True), ("$2,392 (8 summer weekends × $299)", INTER, 10, SLATE, False)],
    blank_para(8),
    [("Monthly recurring revenue today: ", INTER, 10, SLATE, True), ("$2,793", INTER, 10, SLATE, False)],
    [("On pace for $33,516 a year, before any new customers.", INTER, 10, SLATE, False)],
])

items = [
    ("Summer 2026", "5 free pilot pools at camps and YMCAs"),
    ("September 2026", "4 of 5 pilots converted to paid subscriptions"),
    ("Fall 2026", "Round Rock, Leander, and Austin ISD pools signed on"),
]
line_x = Inches(5.35)
card_x, card_w, card_h = Inches(5.65), Inches(3.75), Inches(1.05)
top0, gap = Inches(1.00), Inches(0.30)
dot = Inches(0.16)
centers = [top0 + i * (card_h + gap) + card_h // 2 for i in range(len(items))]

ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, line_x, centers[0], line_x, centers[-1])
ln.line.color.rgb = rgb(AQUA)
ln.line.width = Pt(1.5)
ln.name = "Timeline line"
for i, (when, what) in enumerate(items):
    y = top0 + i * (card_h + gap)
    card = shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, card_x, y, card_w, card_h, WHITE, name=f"Timeline card {i+1}")
    card.adjustments[0] = 0.12
    tf = card.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.18)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    set_font(p.add_run(), MONT, 11, NAVY, True)
    p.runs[-1].text = when
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.LEFT
    set_font(p2.add_run(), INTER, 9.5, SLATE, False)
    p2.runs[-1].text = what
    d = shape(s, MSO_SHAPE.OVAL, line_x - dot // 2, centers[i] - dot // 2, dot, dot, AQUA, name=f"Timeline dot {i+1}")
revenue = s
print("added revenue slide")

# ---------------------------------------------------------------- TASK 3: comparison slide
s = prs.slides.add_slide(BLANK)
chrome(s, "How We Compare")
rows = [
    ["Competitor", "Approach", "Price", "Installation"],
    ["Lynxight (one German pool)", "AI cameras only", "€50,000", "Permanent install"],
    ["Ellis (Fort Wayne school district)", "Cameras only", "$253,837", "Permanent install"],
    ["WAVE", "Wearables only, can't see the swimmer", "Up to $399/month", "Wireless"],
    ["Coral Manta", "One camera, built for home pools", "About $2,500", "Pool edge"],
    ["Aqua Sight", "Cameras + 100 wristbands", "$399/month", "Clamps on in 15 minutes"],
]
CW = Inches(8.80)
tbl_shape = s.shapes.add_table(len(rows), 4, L, Inches(1.00), CW, Inches(2.85))
tbl_shape.name = "Comparison table"
tbl = tbl_shape.table
# drop the built-in banded style so our fills are the only styling
tblPr = tbl._tbl.tblPr
for attr in ("firstRow", "bandRow"):
    tblPr.set(attr, "0")
style_id = tblPr.find(qn("a:tableStyleId"))
if style_id is not None:
    tblPr.remove(style_id)
col_w = [Inches(2.45), Inches(2.75), Inches(1.55), Inches(2.05)]
for i, w in enumerate(col_w):
    tbl.columns[i].width = w
row_h = Inches(2.85) // len(rows)
for r, row in enumerate(rows):
    tbl.rows[r].height = row_h
    header, us = r == 0, r == len(rows) - 1
    for c, val in enumerate(row):
        cell = tbl.cell(r, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = rgb(NAVY if header else AQUA if us else WHITE)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = cell.margin_right = Inches(0.10)
        cell.margin_top = cell.margin_bottom = Inches(0.03)
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        set_font(p.add_run(), INTER, 9.5, WHITE if header else NAVY if us else SLATE, header or us)
        p.runs[-1].text = val
        # thin light borders instead of the default black grid
        tcPr = cell._tc.get_or_add_tcPr()
        for side in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
            ln_el = etree.SubElement(tcPr, qn(side), w="6350", cap="flat", cmpd="sng", algn="ctr")
            sf = etree.SubElement(ln_el, qn("a:solidFill"))
            etree.SubElement(sf, qn("a:srgbClr"), val="E2E8F0")
        # OOXML requires borders before fill inside tcPr
        fill = tcPr.find(qn("a:solidFill"))
        if fill is not None:
            tcPr.remove(fill)
            tcPr.append(fill)

textbox(s, L, Inches(4.05), CW, Inches(0.40),
        [("The only portable system that combines wristbands and AI cameras.", INTER, 11, NAVY, True)])
textbox(s, L, Inches(4.92), Inches(7.5), Inches(0.28),
        [("Sources: KölnBäder; Fort Wayne Journal Gazette; WAVE published pricing; GovTech.", INTER, 7, SLATE, False)])
compare = s
print("added comparison slide")

# ---------------------------------------------------------------- TASK 1: competitor info
# In this export "Competitive Benchmarks" is its own slide (no longer a box on Product Cost).
# It is superseded by the new "How We Compare" slide, so it goes.
bench = find_slide("Competitive Benchmarks")
assert "Product Cost" not in slide_text(bench)
sldIdLst = prs.slides._sldIdLst
for sldId in list(sldIdLst):
    if prs.slides.part.related_part(sldId.rId) is bench.part:   # noqa
        prs.part.drop_rel(sldId.rId)
        sldIdLst.remove(sldId)
print("removed Competitive Benchmarks slide")

# ---------------------------------------------------------------- order
def slide_id_of(slide):
    for sldId in sldIdLst:
        if prs.slides.part.related_part(sldId.rId) is slide.part:
            return sldId
    raise SystemExit("slide id not found")

title_s = prs.slides[0]
order = [
    title_s,
    find_slide("What’s the need?"),
    find_slide("Three devices"),
    find_slide("Product Cost"),
    find_slide("Aqua Sight Video"),      # requested: position 5
    inv,
    revenue,
    compare,
    find_slide("Thank"),
]
ids = [slide_id_of(x) for x in order]
assert len(ids) == len(sldIdLst), (len(ids), len(sldIdLst))
for sldId in ids:
    sldIdLst.remove(sldId)
for sldId in ids:
    sldIdLst.append(sldId)

# ---------------------------------------------------------------- footers
for i, slide in enumerate(prs.slides, 1):
    for sh in slide.shapes:
        if not sh.has_text_frame or sh.left < W * 0.85 or sh.top < H * 0.85:
            continue
        if sh.text_frame.text.strip().isdigit():
            sh.text_frame.paragraphs[0].runs[0].text = str(i)
            for extra in sh.text_frame.paragraphs[0].runs[1:]:
                extra.text = ""

prs.save(OUT)
print("saved", OUT)
for i, slide in enumerate(prs.slides, 1):
    first = [l for l in slide_text(slide).split("\n") if l.strip() and l.strip() != "AQUA SIGHT" and not l.strip().isdigit()]
    print(f"  {i}. {first[0] if first else '(no text)'}")
