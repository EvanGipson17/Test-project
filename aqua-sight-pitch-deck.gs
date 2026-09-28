/**
 * Creates the AQUA SIGHT 6-Slide Pitch Deck in Google Slides.
 * v3: corrected margins/payback, pilot kits reconciled with budget,
 * post-money valuation, 3-tier risk bar, larger text, optional video embed.
 */
var DESIGN_WIDTH = 1333.33;

// Paste a YouTube link here to embed the pitch video on slide 5.
// Leave empty to keep the placeholder box.
var VIDEO_URL = "";

function createAquaSightPitchDeck() {
  var presentation = SlidesApp.create("AQUA SIGHT - Pitch Deck");
  var defaultSlide = presentation.getSlides()[0];

  var COLOR_NAVY = '#0B3D5C';
  var COLOR_TEAL = '#1F7A8C';
  var COLOR_AQUA = '#3FC1C9';
  var COLOR_BG_LIGHT = '#F7FAFC';
  var COLOR_SLATE = '#4A5568';
  var COLOR_WHITE = '#FFFFFF';
  var COLOR_GREEN = '#2F9E44';
  var COLOR_YELLOW = '#F2C94C';
  var COLOR_RED = '#D64545';

  function style(range, font, size, color, bold) {
    var ts = range.getTextStyle();
    ts.setFontFamily(font).setFontSize(size).setForegroundColor(color);
    if (bold) ts.setBold(true);
  }
  function addLogo(slide, color) {
    var logo = slide.insertTextBox("", 80, 14, 200, 26);
    logo.getText().setText("AQUA SIGHT");
    style(logo.getText(), "Montserrat", 14, color, true);
  }
  function addFooter(slide, num, color) {
    var f = slide.insertTextBox("", 1250, 705, 50, 32);
    f.getText().setText(String(num));
    style(f.getText(), "Inter", 14, color, false);
  }
  function addTitle(slide, text, color) {
    var t = slide.insertTextBox("", 80, 40, 800, 60);
    t.getText().setText(text);
    style(t.getText(), "Montserrat", 36, color, true);
  }

  // ========== SLIDE 1: TITLE ==========
  var slide1 = presentation.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  slide1.getBackground().setSolidFill(COLOR_NAVY);
  var titleBox1 = slide1.insertTextBox("", 80, 220, 800, 300);
  var textRange1 = titleBox1.getText();
  textRange1.setText("AQUA SIGHT\n\nEyes under the water.");
  style(textRange1.getRange(0, 10), "Montserrat", 28, COLOR_AQUA, true);
  style(textRange1.getRange(12, 33), "Montserrat", 48, COLOR_WHITE, true);
  var infoBox1 = slide1.insertTextBox("", 80, 520, 1000, 100);
  infoBox1.getText().setText("Portable AI drowning detection for community pools\n[School Name]  |  [Presenter Names]");
  style(infoBox1.getText(), "Inter", 22, COLOR_AQUA, false);
  addFooter(slide1, 1, COLOR_AQUA);

  // ========== SLIDE 2: SALES PITCH OUTLINE ==========
  var slide2 = presentation.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  slide2.getBackground().setSolidFill(COLOR_BG_LIGHT);
  addTitle(slide2, "Sales Pitch Outline", COLOR_NAVY);
  addLogo(slide2, COLOR_NAVY);

  var cardsData = [
    { num: "01", heading: "The Problem", text: "About 11 Americans drown every day. It's the #1 cause of death for kids ages 1 to 4." },
    { num: "02", heading: "The Market Gap", text: "About 1 in 3 U.S. public pools has been hit by the lifeguard shortage, and detection systems cost $50,000+." },
    { num: "03", heading: "Our Solution", text: "Smart wristbands plus AI underwater cameras that warn lifeguards before a swimmer goes under." },
    { num: "04", heading: "How It Works", text: "Three layers of detection: surface behavior, wristband sensors, and camera confirmation." },
    { num: "05", heading: "Why We Win", text: "The only portable system combining wristbands and cameras. No construction. No video recorded." },
    { num: "06", heading: "The Ask", text: "$150,000 for 15% equity ($1M post-money valuation)." }
  ];
  var cardWidth = 364, cardHeight = 250, gapX = 24, gapY = 20;
  for (var i = 0; i < cardsData.length; i++) {
    var x = 80 + (i % 3) * (cardWidth + gapX);
    var y = 120 + Math.floor(i / 3) * (cardHeight + gapY);
    var card = slide2.insertShape(SlidesApp.ShapeType.ROUND_RECTANGLE, x, y, cardWidth, cardHeight);
    card.getFill().setSolidFill(COLOR_WHITE);
    card.getBorder().setTransparent();
    var r = slide2.insertTextBox("", x + 20, y + 20, cardWidth - 40, cardHeight - 40).getText();
    r.setText(cardsData[i].num + "\n\n" + cardsData[i].heading + "\n" + cardsData[i].text);
    var hl = cardsData[i].heading.length;
    style(r.getRange(0, 2), "Montserrat", 16, COLOR_AQUA, true);
    style(r.getRange(4, hl + 4), "Montserrat", 22, COLOR_NAVY, true);
    style(r.getRange(hl + 5, r.asString().length), "Inter", 18, COLOR_SLATE, false);
  }
  var caption2 = slide2.insertTextBox("", 80, 665, 1170, 40);
  caption2.getText().setText("Market research: [ADD SURVEY RESULT, e.g., 'X of Y pool staff surveyed said they would want this at their pool']");
  style(caption2.getText(), "Inter", 14, COLOR_SLATE, false);
  addFooter(slide2, 2, COLOR_SLATE);

  // ========== SLIDE 3: PRODUCT OVERVIEW ==========
  var slide3 = presentation.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  slide3.getBackground().setSolidFill(COLOR_BG_LIGHT);
  addLogo(slide3, COLOR_NAVY);
  var t3 = slide3.insertTextBox("", 80, 40, 1170, 80).getText();
  t3.setText("Aqua Sight\nThree devices. Three layers of detection. One alarm that comes in time.");
  style(t3.getRange(0, 10), "Montserrat", 40, COLOR_NAVY, true);
  style(t3.getRange(11, t3.asString().length), "Inter", 18, COLOR_SLATE, false);

  var visualCard = slide3.insertShape(SlidesApp.ShapeType.ROUND_RECTANGLE, 80, 130, 520, 420);
  visualCard.getFill().setSolidFill(COLOR_WHITE);
  visualCard.getBorder().setTransparent();
  var vt = slide3.insertTextBox("", 100, 150, 480, 380).getText();
  vt.setText("[ RENDER D: HERO SHOT ]\n\n1. Smart Wristband\n2. Underwater AI Camera\n3. Deck Hub\n\n(Clamps onto any pool in 15 mins. No construction.)");
  style(vt, "Montserrat", 20, COLOR_NAVY, false);

  var lr = slide3.insertTextBox("", 630, 130, 620, 420).getText();
  lr.setText("How Aqua Sight detects drowning\n\nLayer 1: Surface Behavior AI\nCameras recognize Instinctive Drowning Response: body vertical, head back, arms pressing down. Warns lifeguards BEFORE submersion.\n\nLayer 2: Smart Wristband Sensors\nTracks time underwater, sinking speed, and arm stoppage. Beginner & toddler bands trigger faster.\n\nLayer 3: Multi-Camera Confirmation\nCross-checks swimmer position & confirms head depth. Catches swimmers on bottom, band or no band.");
  style(lr.getRange(0, 31), "Montserrat", 24, COLOR_NAVY, true);
  style(lr.getRange(32, lr.asString().length), "Inter", 18, COLOR_SLATE, false);

  // Three-tier risk bar: Green / Yellow / Red
  var tiers = [
    { label: "SAFE: Normal swimming", fill: COLOR_GREEN, text: COLOR_WHITE },
    { label: "WATCH: Smartwatch buzzes 'Check lane 3'", fill: COLOR_YELLOW, text: COLOR_NAVY },
    { label: "ALARM: Siren, strobe, exact spot on dashboard", fill: COLOR_RED, text: COLOR_WHITE }
  ];
  var tierW = 1170 / tiers.length;
  for (var k = 0; k < tiers.length; k++) {
    var seg = slide3.insertShape(SlidesApp.ShapeType.RECTANGLE, 80 + k * tierW, 580, tierW, 56);
    seg.getFill().setSolidFill(tiers[k].fill);
    seg.getBorder().setTransparent();
    seg.setContentAlignment(SlidesApp.ContentAlignment.MIDDLE);
    var st = seg.getText();
    st.setText(tiers[k].label);
    style(st, "Inter", 15, tiers[k].text, true);
    st.getParagraphStyle().setParagraphAlignment(SlidesApp.ParagraphAlignment.CENTER);
  }
  addFooter(slide3, 3, COLOR_SLATE);

  // ========== SLIDE 4: PRODUCT COST ==========
  var slide4 = presentation.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  slide4.getBackground().setSolidFill(COLOR_BG_LIGHT);
  addLogo(slide4, COLOR_NAVY);
  addTitle(slide4, "Product Cost", COLOR_NAVY);

  var pricingCards = [
    { type: "BUY", price: "$9,999", sub: "one time + $99/mo", featured: false },
    { type: "SUBSCRIBE", price: "$399", sub: "per month, $0 upfront", featured: true },
    { type: "RENT", price: "$299", sub: "per weekend (meets/camps)", featured: false }
  ];
  for (var j = 0; j < pricingCards.length; j++) {
    var pc = pricingCards[j];
    var pX = 80 + j * (364 + 24);
    var pCard = slide4.insertShape(SlidesApp.ShapeType.ROUND_RECTANGLE, pX, 110, 364, 130);
    pCard.getFill().setSolidFill(pc.featured ? COLOR_NAVY : COLOR_WHITE);
    pCard.getBorder().setTransparent();
    var pr = slide4.insertTextBox("", pX + 20, 120, 324, 110).getText();
    pr.setText(pc.type + "\n" + pc.price + "\n" + pc.sub);
    var tl = pc.type.length, pl = pc.price.length;
    style(pr.getRange(0, tl), "Inter", 14, pc.featured ? COLOR_AQUA : COLOR_SLATE, true);
    style(pr.getRange(tl + 1, tl + pl + 1), "Montserrat", 36, pc.featured ? COLOR_WHITE : COLOR_NAVY, true);
    style(pr.getRange(tl + pl + 2, pr.asString().length), "Inter", 15, pc.featured ? COLOR_WHITE : COLOR_SLATE, false);
  }

  var cb = slide4.insertTextBox("", 80, 260, 600, 270).getText();
  cb.setText("Unit Cost to Make (One Full Kit):\n• 4 underwater AI camera pods ($395 ea): $1,580\n• 1 deck hub with siren & alarm: $200\n• 100 smart wristbands ($22 ea): $2,200\n• 2 band charging racks: $180\n• Carry case and packaging: $120\nTOTAL COST PER KIT: $4,280\n(Plus $350 setup & staff training per pool)");
  style(cb, "Inter", 17, COLOR_SLATE, false);
  style(cb.getRange(0, cb.asString().indexOf("\n")), "Inter", 17, COLOR_NAVY, true);

  var pb = slide4.insertTextBox("", 700, 260, 550, 270).getText();
  pb.setText("Subscription Profitability:\n• $399 monthly price minus $40 cloud/warranty costs\n• Net: $359 per month per kit\n• Kit + setup ($4,630) paid back in ~13 months, then pure margin\n\nPurchase Margin: $5,369 per system (54%, after setup)\nRental Margin: $224 profit per weekend");
  style(pb, "Inter", 17, COLOR_SLATE, false);
  style(pb.getRange(0, pb.asString().indexOf("\n")), "Inter", 17, COLOR_NAVY, true);

  var cmp = slide4.insertTextBox("", 80, 540, 1170, 150).getText();
  cmp.setText("Competitive Benchmarks:\n• German municipal pool system: €50,000 for AI cameras\n• U.S. school district system: $253,837 total cost\n• Competitor WAVE: up to $399/mo (wearables only)\n• Aqua Sight: $399/mo (cameras + 100 bands included)\nSources: KölnBäder; Fort Wayne Journal Gazette; WAVE published pricing.");
  style(cmp, "Inter", 15, COLOR_SLATE, false);
  style(cmp.getRange(0, cmp.asString().indexOf("\n")), "Inter", 15, COLOR_NAVY, true);
  addFooter(slide4, 4, COLOR_SLATE);

  // ========== SLIDE 5: VIDEO ==========
  var slide5 = presentation.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  slide5.getBackground().setSolidFill(COLOR_NAVY);
  addLogo(slide5, COLOR_AQUA);
  addTitle(slide5, "Our Pitch Video", COLOR_WHITE);

  if (VIDEO_URL) {
    slide5.insertVideo(VIDEO_URL, 200, 140, 933, 525);
  } else {
    var vidBox = slide5.insertShape(SlidesApp.ShapeType.ROUND_RECTANGLE, 200, 140, 933, 500);
    vidBox.getFill().setSolidFill(COLOR_SLATE);
    vidBox.getBorder().setWeight(2);
    vidBox.getBorder().getLineFill().setSolidFill(COLOR_AQUA);

    var vtx = slide5.insertTextBox("", 200, 340, 933, 100).getText();
    vtx.setText("[ INSERT 3-MINUTE PITCH VIDEO HERE ]\nFeaturing both team members");
    style(vtx, "Montserrat", 24, COLOR_WHITE, false);
    vtx.getParagraphStyle().setParagraphAlignment(SlidesApp.ParagraphAlignment.CENTER);
  }
  addFooter(slide5, 5, COLOR_WHITE);

  // ========== SLIDE 6: INVESTOR REQUEST ==========
  var slide6 = presentation.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  slide6.getBackground().setSolidFill(COLOR_BG_LIGHT);
  addLogo(slide6, COLOR_NAVY);
  addTitle(slide6, "Investor Request", COLOR_NAVY);

  var ar = slide6.insertTextBox("", 80, 120, 540, 540).getText();
  var askLine1 = "$150,000", askLine2 = "for 15% equity", askLine3 = "$1,000,000 post-money valuation";
  ar.setText(askLine1 + "\n" + askLine2 + "\n" + askLine3 + "\n\nMilestones:\n• 5 pilot pools at camps and YMCAs, free through summer (April 2027), then converting to paid\n• 31 paying customers by end of 2027 (includes the 5 converted pilots)\n• Safety certification testing and growth round (2028)");
  var a2 = askLine1.length + 1;
  var a3 = a2 + askLine2.length + 1;
  var a4 = a3 + askLine3.length;
  style(ar.getRange(0, askLine1.length), "Montserrat", 60, COLOR_TEAL, true);
  style(ar.getRange(a2, a2 + askLine2.length), "Montserrat", 24, COLOR_NAVY, true);
  style(ar.getRange(a3, a4), "Inter", 20, COLOR_SLATE, false);
  style(ar.getRange(a4, ar.asString().length), "Inter", 17, COLOR_SLATE, false);

  var cr = slide6.insertTextBox("", 650, 120, 600, 500).getText();
  var chartTitle = "Where the money goes (Year 1) — Total: $250,375";
  cr.setText(chartTitle + "\n\n• Hardware fleet (31 kits): $132,680 (53%)\n• Team: $36,000 (14%)\n• Engineering and testing: $29,000 (12%)\n• Marketing and trade shows: $18,100 (7%)\n• Insurance, legal, patents, software: $17,900 (7%)\n• Loan payments: $16,695 (7%)\n\nFunded by: $150k investment + $75k equipment loan + $5k founders + $20,375 customer revenue");
  style(cr, "Inter", 17, COLOR_SLATE, false);
  style(cr.getRange(0, chartTitle.length), "Montserrat", 22, COLOR_NAVY, true);
  addFooter(slide6, 6, COLOR_SLATE);

  defaultSlide.remove();
  scaleToPage_(presentation, DESIGN_WIDTH);

  Logger.log("Presentation generated: " + presentation.getUrl());
}

function scaleToPage_(presentation, designWidth) {
  var s = presentation.getPageWidth() / designWidth;
  if (Math.abs(s - 1) < 0.001) return;
  presentation.getSlides().forEach(function (slide) {
    slide.getPageElements().forEach(function (el) {
      el.setLeft(el.getLeft() * s);
      el.setTop(el.getTop() * s);
      el.setWidth(el.getWidth() * s);
      el.setHeight(el.getHeight() * s);
      if (el.getPageElementType() === SlidesApp.PageElementType.SHAPE) {
        el.asShape().getText().getRuns().forEach(function (run) {
          var fs = run.getTextStyle().getFontSize();
          if (fs) run.getTextStyle().setFontSize(Math.max(7, Math.round(fs * s)));
        });
      }
    });
  });
}
