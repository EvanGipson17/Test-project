/**
 * AQUA SIGHT deck updater.
 * Edits an existing Google Slides deck in place (SlidesApp only).
 * Run: updateAquaSightDeck
 */
var DECK_URL = "PASTE_YOUR_DECK_LINK_HERE";

var NAVY = '#0B3D5C';
var TEAL = '#1F7A8C';
var AQUA = '#3FC1C9';
var OFF_WHITE = '#F7FAFC';
var SLATE = '#4A5568';
var WHITE = '#FFFFFF';
var TITLE_FONT = 'Montserrat';
var BODY_FONT = 'Inter';

function updateAquaSightDeck() {
  // With a link, open that deck. Without one, edit the deck this script is attached to
  // (Extensions > Apps Script inside Google Slides), which avoids cross-account access issues.
  var pres = DECK_URL.indexOf('docs.google.com') !== -1
    ? SlidesApp.openByUrl(DECK_URL)
    : SlidesApp.getActivePresentation();
  if (!pres) throw new Error('Open this from inside the deck (Extensions > Apps Script) or paste the deck link into DECK_URL.');
  var ctx = { pres: pres, W: pres.getPageWidth(), H: pres.getPageHeight() };
  Logger.log('Opened "' + pres.getName() + '": ' + pres.getSlides().length + ' slides, page ' +
             Math.round(ctx.W) + ' x ' + Math.round(ctx.H) + ' pt.');

  task1RemoveBenchmarks_(ctx);
  task4FixText_(ctx);
  task2RevenueSlide_(ctx);
  task3CompareSlide_(ctx);
  task4MoveVideo_(ctx);
  renumberFooters_(ctx);
  logFinalOrder_(ctx);
  Logger.log('All done.');
}

// ---------- TASK 1 ----------
function task1RemoveBenchmarks_(ctx) {
  Logger.log('TASK 1: Remove "Competitive Benchmarks" box from the Product Cost slide');
  var found = findSlide_(ctx.pres, 'Product Cost');
  if (!found) { Logger.log('  Product Cost slide not found. Skipped.'); return; }
  var removed = 0;
  found.slide.getShapes().forEach(function (sh) {
    if (textOf_(sh).indexOf('Competitive Benchmarks') !== -1) { sh.remove(); removed++; }
  });
  Logger.log(removed
    ? '  Removed ' + removed + ' text box from slide ' + (found.index + 1) + '.'
    : '  No "Competitive Benchmarks" box found (already removed?). Nothing changed.');
}

// ---------- TASK 2 ----------
function task2RevenueSlide_(ctx) {
  Logger.log('TASK 2: Add "How Much We\'ve Made So Far" slide');
  if (findSlide_(ctx.pres, 'Made So Far')) { Logger.log('  Slide already exists. Skipped so it is not duplicated.'); return; }
  var inv = findSlide_(ctx.pres, 'Investor Request');
  if (!inv) { Logger.log('  Investor Request slide not found. Skipped.'); return; }

  var W = ctx.W, H = ctx.H, L = W * 0.06;
  var s = newSlide_(ctx, inv.index + 1, inv.slide, "How Much We've Made So Far");

  // Left half: revenue numbers
  var label = s.insertTextBox('Revenue to date', L, H * 0.20, W * 0.40, H * 0.05);
  style_(label.getText(), BODY_FONT, pt_(ctx, 0.013), TEAL, true);

  var big = s.insertTextBox('$5,185', L, H * 0.25, W * 0.40, H * 0.16);
  style_(big.getText(), TITLE_FONT, pt_(ctx, 0.0625), TEAL, true);

  var lines = [
    'Subscriptions: $2,793 (7 pools × $399, September)',
    'Event rentals: $2,392 (8 summer weekends × $299)',
    '',
    'Monthly recurring revenue today: $2,793',
    'On pace for $33,516 a year, before any new customers.'
  ];
  var body = s.insertTextBox(lines.join('\n'), L, H * 0.44, W * 0.40, H * 0.44);
  var bt = body.getText();
  style_(bt, BODY_FONT, pt_(ctx, 0.0135), SLATE, false);
  ['Subscriptions:', 'Event rentals:', 'Monthly recurring revenue today:'].forEach(function (lbl) {
    styleSub_(bt, lbl, BODY_FONT, pt_(ctx, 0.0135), SLATE, true);
  });

  // Right half: vertical timeline
  var items = [
    ['Summer 2026', '5 free pilot pools at camps and YMCAs'],
    ['September 2026', '4 of 5 pilots converted to paid subscriptions'],
    ['Fall 2026', 'Round Rock, Leander, and Austin ISD pools signed on']
  ];
  var lineX = W * 0.535, dot = W * 0.018;
  var cardX = W * 0.56, cardW = W * 0.38, cardH = H * 0.17, top0 = H * 0.20, gap = H * 0.055;
  var centers = items.map(function (_, i) { return top0 + i * (cardH + gap) + cardH / 2; });

  var line = s.insertLine(SlidesApp.LineCategory.STRAIGHT, lineX, centers[0], lineX, centers[centers.length - 1]);
  line.setWeight(1.5);
  line.getLineFill().setSolidFill(AQUA);

  items.forEach(function (it, i) {
    var c = s.insertShape(SlidesApp.ShapeType.ELLIPSE, lineX - dot / 2, centers[i] - dot / 2, dot, dot);
    c.getFill().setSolidFill(AQUA);
    c.getBorder().setTransparent();

    var card = s.insertShape(SlidesApp.ShapeType.ROUND_RECTANGLE, cardX, top0 + i * (cardH + gap), cardW, cardH);
    card.getFill().setSolidFill(WHITE);
    card.getBorder().setTransparent();
    card.setContentAlignment(SlidesApp.ContentAlignment.MIDDLE);
    var ct = card.getText();
    ct.setText(it[0] + '\n' + it[1]);
    style_(ct, BODY_FONT, pt_(ctx, 0.012), SLATE, false);
    styleSub_(ct, it[0], TITLE_FONT, pt_(ctx, 0.014), NAVY, true);
    ct.getParagraphStyle().setParagraphAlignment(SlidesApp.ParagraphAlignment.START);
  });
  Logger.log('  Inserted at position ' + (inv.index + 2) + ' (right after Investor Request).');
}

// ---------- TASK 3 ----------
function task3CompareSlide_(ctx) {
  Logger.log('TASK 3: Add "How We Compare" slide');
  if (findSlide_(ctx.pres, 'How We Compare')) { Logger.log('  Slide already exists. Skipped so it is not duplicated.'); return; }
  var prev = findSlide_(ctx.pres, 'Made So Far') || findSlide_(ctx.pres, 'Investor Request');
  if (!prev) { Logger.log('  Neither the revenue slide nor Investor Request was found. Skipped.'); return; }

  var W = ctx.W, H = ctx.H, L = W * 0.06, CW = W * 0.88;
  var s = newSlide_(ctx, prev.index + 1, prev.slide, 'How We Compare');

  var rows = [
    ['Competitor', 'Approach', 'Price', 'Installation'],
    ['Lynxight (one German pool)', 'AI cameras only', '€50,000', 'Permanent install'],
    ['Ellis (Fort Wayne school district)', 'Cameras only', '$253,837', 'Permanent install'],
    ['WAVE', "Wearables only, can't see the swimmer", 'Up to $399/month', 'Wireless'],
    ['Coral Manta', 'One camera, built for home pools', 'About $2,500', 'Pool edge'],
    ['Aqua Sight', 'Cameras + 100 wristbands', '$399/month', 'Clamps on in 15 minutes']
  ];
  var table = s.insertTable(rows.length, 4, L, H * 0.20, CW, H * 0.50);
  var size = pt_(ctx, 0.0115);
  for (var r = 0; r < rows.length; r++) {
    var isHeader = r === 0, isUs = r === rows.length - 1;
    for (var c = 0; c < 4; c++) {
      var cell = table.getCell(r, c);
      cell.getText().setText(rows[r][c]);
      cell.getFill().setSolidFill(isHeader ? NAVY : (isUs ? AQUA : WHITE));
      cell.setContentAlignment(SlidesApp.ContentAlignment.MIDDLE);
      style_(cell.getText(), BODY_FONT, size, isHeader ? WHITE : (isUs ? NAVY : SLATE), isHeader || isUs);
    }
  }

  var tagY = Math.min(H * 0.80, Math.max(H * 0.74, table.getTop() + table.getHeight() + H * 0.03));
  var tag = s.insertTextBox('The only portable system that combines wristbands and AI cameras.', L, tagY, CW, H * 0.07);
  style_(tag.getText(), BODY_FONT, pt_(ctx, 0.0145), NAVY, true);

  var src = s.insertTextBox('Sources: KölnBäder; Fort Wayne Journal Gazette; WAVE published pricing; GovTech.',
                            L, H * 0.89, W * 0.70, H * 0.045);
  style_(src.getText(), BODY_FONT, pt_(ctx, 0.0085), SLATE, false);
  Logger.log('  Inserted at position ' + (prev.index + 2) + '.');
}

// ---------- TASK 4 ----------
function task4FixText_(ctx) {
  Logger.log('TASK 4a: Text fixes');
  // "Total: $150,00" -> "Total: $150,000" only where the trailing zero is actually missing.
  var fixed = 0;
  ctx.pres.getSlides().forEach(function (slide, si) {
    slide.getShapes().forEach(function (sh) {
      var text;
      try { text = sh.getText(); } catch (e) { return; }
      var str = text.asString(), re = /Total:\s*\$150,00(?!\d)/g, m, ends = [];
      while ((m = re.exec(str)) !== null) ends.push(m.index + m[0].length);
      for (var k = ends.length - 1; k >= 0; k--) {
        text.insertText(ends[k], '0');
        fixed++;
        Logger.log('  Slide ' + (si + 1) + ': "Total: $150,00" -> "Total: $150,000"');
      }
    });
  });
  if (!fixed) Logger.log('  "Total: $150,00" typo not found (already correct). Nothing changed.');

  var n1 = ctx.pres.replaceAllText('Hardware fleet (19 kits)', 'Hardware fleet (18 kits)');
  Logger.log('  "Hardware fleet (19 kits)" -> "(18 kits)": ' + n1 + ' replacement(s).');

  var n2 = ctx.pres.replaceAllText('Roundrock', 'Round Rock');
  Logger.log('  "Roundrock" -> "Round Rock": ' + n2 + ' replacement(s).');
}

function task4MoveVideo_(ctx) {
  Logger.log('TASK 4b: Move video slide to position 5');
  var v = findSlide_(ctx.pres, 'Aqua Sight Video');
  if (!v) { Logger.log('  Slide containing "Aqua Sight Video" not found. Skipped.'); return; }
  if (v.index === 4) { Logger.log('  Already at position 5.'); return; }
  v.slide.move(4);
  Logger.log('  Moved from position ' + (v.index + 1) + ' to position 5.');
}

// Keeps the small bottom-right page numbers in sync with the new order.
function renumberFooters_(ctx) {
  Logger.log('Updating slide numbers');
  ctx.pres.getSlides().forEach(function (slide, i) {
    slide.getShapes().forEach(function (sh) {
      var text;
      try { text = sh.getText(); } catch (e) { return; }
      var cur = text.asString().trim();
      if (!/^\d{1,2}$/.test(cur)) return;
      if (sh.getLeft() < ctx.W * 0.8 || sh.getTop() < ctx.H * 0.8) return;
      var want = String(i + 1);
      if (cur !== want) {
        text.replaceAllText(cur, want);
        Logger.log('  Slide ' + want + ': number ' + cur + ' -> ' + want);
      }
    });
  });
}

function logFinalOrder_(ctx) {
  Logger.log('FINAL SLIDE ORDER:');
  ctx.pres.getSlides().forEach(function (slide, i) {
    Logger.log('  ' + (i + 1) + '. ' + firstLine_(slide));
  });
}

// ---------- HELPERS ----------
function pt_(ctx, k) { return Math.max(6, Math.round(ctx.W * k)); }

function textOf_(el) {
  try {
    var type = el.getPageElementType();
    if (type === SlidesApp.PageElementType.SHAPE) return el.asShape().getText().asString();
    if (type === SlidesApp.PageElementType.TABLE) {
      var t = el.asTable(), out = [];
      for (var r = 0; r < t.getNumRows(); r++) {
        for (var c = 0; c < t.getNumColumns(); c++) {
          try { out.push(t.getCell(r, c).getText().asString()); } catch (e) {}
        }
      }
      return out.join('\n');
    }
  } catch (e) {}
  return '';
}

function slideText_(slide) {
  return slide.getPageElements().map(textOf_).join('\n');
}

// Case-insensitive; also treats curly and straight apostrophes the same.
function findSlide_(pres, needle) {
  var norm = function (s) { return s.replace(/[‘’]/g, "'").toLowerCase(); };
  var want = norm(needle), slides = pres.getSlides();
  for (var i = 0; i < slides.length; i++) {
    if (norm(slideText_(slides[i])).indexOf(want) !== -1) return { slide: slides[i], index: i };
  }
  return null;
}

function firstLine_(slide) {
  var lines = slideText_(slide).split(/[\n\u000b]/)
    .map(function (l) { return l.trim(); })
    .filter(function (l) { return l && l.toUpperCase() !== 'AQUA SIGHT' && !/^\d+$/.test(l); });
  return lines.length ? lines[0] : '(no text)';
}

function style_(range, font, size, color, bold) {
  if (range.isEmpty()) return;
  range.getTextStyle().setFontFamily(font).setFontSize(size).setForegroundColor(color).setBold(!!bold);
}

function styleSub_(text, sub, font, size, color, bold) {
  var i = text.asString().indexOf(sub);
  if (i === -1) { Logger.log('  (styling skipped: "' + sub + '" not found)'); return; }
  style_(text.getRange(i, i + sub.length), font, size, color, bold);
}

function newSlide_(ctx, index, refSlide, title) {
  var s;
  try {
    s = ctx.pres.insertSlide(index, SlidesApp.PredefinedLayout.BLANK);
  } catch (e) {
    Logger.log('  No BLANK layout in this deck (' + e.message + '). Using a neighboring slide\'s layout instead.');
    s = ctx.pres.insertSlide(index, refSlide.getLayout());
  }
  // Clear any placeholder boxes the layout added to the new slide.
  s.getPageElements().forEach(function (el) { el.remove(); });
  s.getBackground().setSolidFill(OFF_WHITE);

  var W = ctx.W, H = ctx.H, L = W * 0.06;
  var label = s.insertTextBox('AQUA SIGHT', L, H * 0.019, W * 0.30, H * 0.045);
  style_(label.getText(), TITLE_FONT, pt_(ctx, 0.0105), NAVY, true);
  var t = s.insertTextBox(title, L, H * 0.055, W * 0.88, H * 0.11);
  style_(t.getText(), TITLE_FONT, pt_(ctx, 0.027), NAVY, true);
  var f = s.insertTextBox('0', W * 0.9375, H * 0.94, W * 0.04, H * 0.045);
  style_(f.getText(), BODY_FONT, pt_(ctx, 0.0105), SLATE, false);
  return s;
}
