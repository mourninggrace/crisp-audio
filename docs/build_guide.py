"""Build AudioCleanUpTool_User_Guide.pdf using ReportLab."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    Table, TableStyle, HRFlowable, PageBreak, KeepTogether,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUT = Path(__file__).parent / "AudioCleanUpTool_User_Guide.pdf"

# ── Colours ──────────────────────────────────────────────────────────────────
DARK   = colors.HexColor("#1a1a2e")
ACCENT = colors.HexColor("#4fc3f7")
MID    = colors.HexColor("#334155")
LIGHT  = colors.HexColor("#e2e8f0")
WHITE  = colors.white
GREY   = colors.HexColor("#94a3b8")
CODE_BG = colors.HexColor("#0f172a")

W, H = A4

# ── Styles ───────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, **kw)

TITLE_S = S("DocTitle",
    fontName="Helvetica-Bold", fontSize=28, leading=34,
    textColor=WHITE, alignment=TA_CENTER, spaceAfter=6)

SUBTITLE_S = S("DocSubtitle",
    fontName="Helvetica", fontSize=13, leading=18,
    textColor=ACCENT, alignment=TA_CENTER, spaceAfter=4)

VERSION_S = S("DocVersion",
    fontName="Helvetica", fontSize=10, leading=14,
    textColor=GREY, alignment=TA_CENTER, spaceAfter=30)

H1 = S("H1",
    fontName="Helvetica-Bold", fontSize=18, leading=22,
    textColor=ACCENT, spaceBefore=18, spaceAfter=8,
    borderPad=0)

H2 = S("H2",
    fontName="Helvetica-Bold", fontSize=13, leading=17,
    textColor=LIGHT, spaceBefore=14, spaceAfter=6)

H3 = S("H3",
    fontName="Helvetica-BoldOblique", fontSize=11, leading=15,
    textColor=GREY, spaceBefore=10, spaceAfter=4)

BODY = S("Body",
    fontName="Helvetica", fontSize=10, leading=15,
    textColor=LIGHT, alignment=TA_JUSTIFY, spaceAfter=6)

BODY_SMALL = S("BodySmall",
    fontName="Helvetica", fontSize=9, leading=13,
    textColor=LIGHT, alignment=TA_LEFT, spaceAfter=4)

BULLET = S("Bullet",
    fontName="Helvetica", fontSize=10, leading=15,
    textColor=LIGHT, leftIndent=18, bulletIndent=6,
    spaceAfter=3)

CODE = S("Code",
    fontName="Courier", fontSize=9, leading=13,
    textColor=ACCENT, backColor=CODE_BG,
    leftIndent=12, rightIndent=12, spaceBefore=4, spaceAfter=8,
    borderPad=6)

NOTE = S("Note",
    fontName="Helvetica-Oblique", fontSize=9, leading=13,
    textColor=GREY, leftIndent=12, spaceAfter=6)

TOC_H1 = S("TOC1",
    fontName="Helvetica-Bold", fontSize=11, leading=16,
    textColor=ACCENT, leftIndent=0, spaceAfter=3)

TOC_H2 = S("TOC2",
    fontName="Helvetica", fontSize=10, leading=14,
    textColor=LIGHT, leftIndent=16, spaceAfter=2)


# ── Helpers ──────────────────────────────────────────────────────────────────
def h1(text): return Paragraph(text, H1)
def h2(text): return Paragraph(text, H2)
def h3(text): return Paragraph(text, H3)
def p(text):  return Paragraph(text, BODY)
def ps(text): return Paragraph(text, BODY_SMALL)
def note(text): return Paragraph(f"ℹ️  {text}", NOTE)
def code(text): return Paragraph(text, CODE)
def sp(n=6):  return Spacer(1, n)
def hr():     return HRFlowable(width="100%", thickness=0.5, color=MID, spaceAfter=8, spaceBefore=4)

def bullets(items):
    return [Paragraph(f"• {i}", BULLET) for i in items]

def table(data, col_widths=None, header=True):
    t = Table(data, colWidths=col_widths)
    style = [
        ("BACKGROUND", (0,0), (-1,0 if header else -1), MID),
        ("TEXTCOLOR",  (0,0), (-1,-1), LIGHT),
        ("FONTNAME",   (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTNAME",   (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("LEADING",    (0,0), (-1,-1), 13),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [DARK, MID]),
        ("GRID",       (0,0), (-1,-1), 0.3, GREY),
        ("LEFTPADDING",(0,0), (-1,-1), 8),
        ("RIGHTPADDING",(0,0),(-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("VALIGN",     (0,0), (-1,-1), "TOP"),
    ]
    t.setStyle(TableStyle(style))
    return t


# ── Document setup ────────────────────────────────────────────────────────────
class TwoColumnDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        self.toc = TableOfContents()
        self.toc.levelStyles = [TOC_H1, TOC_H2]
        self._build_templates()

    def _build_templates(self):
        margin = 2 * cm
        fw = W - 2 * margin
        fh = H - 2 * margin - 1.2 * cm  # space for footer

        frame = Frame(margin, 1.8 * cm, fw, fh, id="main")
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[frame], onPage=self._cover_page),
            PageTemplate(id="body",  frames=[frame], onPage=self._body_page),
        ])

    @staticmethod
    def _draw_bg(canvas, doc):
        canvas.setFillColor(DARK)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)

    def _cover_page(self, canvas, doc):
        self._draw_bg(canvas, doc)
        # Top accent bar
        canvas.setFillColor(ACCENT)
        canvas.rect(0, H - 0.5*cm, W, 0.5*cm, fill=1, stroke=0)
        # Bottom accent bar
        canvas.rect(0, 0, W, 0.5*cm, fill=1, stroke=0)

    def _body_page(self, canvas, doc):
        self._draw_bg(canvas, doc)
        # Header bar
        canvas.setFillColor(MID)
        canvas.rect(0, H - 1.2*cm, W, 1.2*cm, fill=1, stroke=0)
        canvas.setFillColor(ACCENT)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(2*cm, H - 0.75*cm, "AudioCleanUpTool — User Guide")
        canvas.setFillColor(GREY)
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(W - 2*cm, H - 0.75*cm, f"v0.1.0")

        # Footer
        canvas.setFillColor(MID)
        canvas.rect(0, 0, W, 1.4*cm, fill=1, stroke=0)
        canvas.setFillColor(GREY)
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(W/2, 0.5*cm, f"Page {doc.page}")

    def afterFlowable(self, flowable):
        """Register headings so the TOC can find them."""
        if isinstance(flowable, Paragraph):
            style = flowable.style.name
            text  = flowable.getPlainText()
            if style == "H1":
                self.notify("TOCEntry", (0, text, self.page))
            elif style == "H2":
                self.notify("TOCEntry", (1, text, self.page))


# ── Content ───────────────────────────────────────────────────────────────────
def build_story(toc):
    s = []

    # ── Cover ────────────────────────────────────────────────────────────────
    s += [
        sp(80),
        Paragraph("AudioCleanUpTool", TITLE_S),
        Paragraph("Crisp — Audio Cleanup for Everyone", SUBTITLE_S),
        sp(8),
        Paragraph("User Guide &nbsp;·&nbsp; v0.1.0", VERSION_S),
        sp(20),
        HRFlowable(width="60%", thickness=1, color=ACCENT, hAlign="CENTER"),
        sp(20),
        Paragraph(
            "Free &amp; Open Source &nbsp;·&nbsp; MIT License &nbsp;·&nbsp; "
            "github.com/mourninggrace/crisp-audio",
            S("CoverMeta", fontName="Helvetica", fontSize=9, leading=14,
              textColor=GREY, alignment=TA_CENTER)),
        PageBreak(),
    ]

    # Switch to body template after cover
    from reportlab.platypus import NextPageTemplate
    s.insert(-1, NextPageTemplate("body"))

    # ── Table of Contents ───────────────────────────────────────────────────
    s += [
        h1("Table of Contents"),
        toc,
        PageBreak(),
    ]

    # ── 1. Introduction ─────────────────────────────────────────────────────
    s += [
        h1("1. Introduction"),
        p("AudioCleanUpTool (code name: <i>Crisp</i>) is a free, open-source desktop "
          "application for cleaning and polishing audio recordings. Whether you record "
          "podcasts, church services, voice-overs, or anything in between, Crisp gives "
          "you professional results without needing to know anything about audio engineering."),
        p("The entire processing pipeline runs locally on your machine — no cloud, no "
          "subscription, no internet connection required. Your audio never leaves your computer."),
        sp(4),
        h2("1.1  Who is this for?"),
        *bullets([
            "Podcasters who want clean, loud, professional-sounding episodes",
            "Church AV teams cleaning up recordings of sermons and services",
            "Voice-over artists preparing recordings to ACX or broadcast spec",
            "Anyone who records speech and wants it to sound better quickly",
            "Developers who want a scriptable Python audio pipeline",
        ]),
        sp(4),
        h2("1.2  Key principles"),
        *bullets([
            "<b>Non-destructive:</b> the original file is never overwritten — you always export a new copy.",
            "<b>Transparent:</b> every processing step is visible, adjustable, and can be toggled off.",
            "<b>A/B comparison:</b> switch between the original and cleaned version at any time to judge the difference.",
            "<b>One-click option:</b> Auto Clean analyses your audio and picks the right settings automatically.",
        ]),
        sp(8),
    ]

    # ── 2. Installation ─────────────────────────────────────────────────────
    s += [
        h1("2. Installation"),
        h2("2.1  Windows installer (recommended)"),
        p("Download <b>AudioCleanUpTool-0.1.0-Setup.exe</b> from the "
          "Releases page on GitHub and run it. The installer:"),
        *bullets([
            "Installs the app to <i>C:\\Program Files\\AudioCleanUpTool</i> (or a folder of your choice)",
            "Creates a Start Menu entry",
            "Optionally creates a Desktop shortcut",
            "Bundles Python, all dependencies, and ffmpeg — nothing else to install",
        ]),
        note("No administrator rights are required. The installer defaults to a per-user installation."),
        sp(6),
        h2("2.2  Running from source (developers)"),
        p("Requires Python 3.10 or later."),
        code("git clone https://github.com/mourninggrace/crisp-audio.git\n"
             "cd crisp-audio\n"
             "python -m venv .venv\n"
             ".venv\\Scripts\\Activate.ps1     # PowerShell\n"
             "pip install -e .[dev]\n"
             "python -m crisp"),
        sp(6),
        h2("2.3  Building the executable yourself"),
        code("pip install -e .[dev]\n"
             "pyinstaller crisp.spec\n"
             "# Produces dist\\Crisp.exe\n\n"
             '& "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe" installer\\crisp.iss\n'
             "# Produces dist\\AudioCleanUpTool-0.1.0-Setup.exe"),
    ]

    # ── 3. Getting Started ──────────────────────────────────────────────────
    s += [
        h1("3. Getting Started"),
        h2("3.1  The interface at a glance"),
        p("The window is divided into three areas:"),
        table([
            ["Area", "Location", "What it does"],
            ["Left panel",   "Left column",   "Source input, cleanup processors, export controls"],
            ["Waveform area","Centre",         "Before/after waveform display + playback transport"],
            ["Menu bar",     "Top",            "File, Edit, View, Settings, Help"],
            ["Status bar",   "Bottom",         "Live status messages and progress feedback"],
        ], col_widths=[3.5*cm, 3.5*cm, 10*cm]),
        sp(6),
        note("All three left-panel sections (Source, Cleanup, Export) are resizable — drag the dividers between them."),
        sp(6),
        h2("3.2  Quick start: clean a file in 4 steps"),
        table([
            ["Step", "Action"],
            ["1", "Click <b>Open file…</b> and choose any WAV, FLAC, MP3, AAC, OGG, or AIFF file."],
            ["2", "Click <b>✨ Auto Clean</b>. Crisp analyses the audio and applies the right settings automatically."],
            ["3", "Use the <b>A · Original</b> / <b>B · Cleaned</b> buttons to compare."],
            ["4", "Choose an export preset and click <b>Export cleaned…</b>."],
        ], col_widths=[1.5*cm, 15.5*cm]),
        sp(6),
        h2("3.3  Recording audio directly"),
        p("Instead of opening a file, you can record from a microphone:"),
        *bullets([
            "Select your input device from the <b>Input device</b> drop-down in the Source section.",
            "Click <b>● Record</b>. The level meter shows the incoming signal.",
            "Click <b>■ Stop</b> when done. The recording appears in the waveform view automatically.",
            "Proceed with Auto Clean or manual cleanup as normal.",
        ]),
    ]

    # ── 4. Audio Processors ─────────────────────────────────────────────────
    s += [
        h1("4. Audio Processors"),
        p("Crisp has 10 processing stages, each with its own on/off toggle and parameter controls. "
          "They are organised into five tabs in the Cleanup section."),
        p("Processing runs in a fixed pipeline order that is designed to give the best results: "
          "noise removal first, then reverb, plosives, EQ, clarity, loudness, trim, then effects."),
        sp(4),

        h2("Tab 1 — Noise Reduction"),

        h3("Noise Reduction"),
        p("Removes constant background noise: hum, hiss, fan noise, air conditioning, "
          "electrical interference. Uses spectral gating — frequencies that are consistently "
          "present at low levels are identified as noise and suppressed."),
        table([
            ["Parameter", "Range", "Default", "What it does"],
            ["Strength", "0.0 – 1.0", "0.85", "How aggressively noise is reduced. Higher = more reduction, but too high can introduce artefacts."],
            ["Constant noise floor", "On/Off", "Off", "On: assumes the noise floor is constant throughout (best for steady hum/hiss). Off: adapts to changing noise levels."],
        ], col_widths=[3.5*cm, 2.5*cm, 2.5*cm, 8.5*cm]),
        note("Start with default settings. Only increase Strength if the noise is clearly still audible after processing."),

        sp(6),
        h3("Plosive Removal"),
        p("Removes plosives — the sharp low-frequency 'pop' caused by breath hitting the microphone "
          "on P, B, and T sounds. Detects frames where sub-120 Hz energy spikes well above the "
          "rolling average and ducks the low band at those moments, leaving normal speech untouched."),
        table([
            ["Parameter", "Range", "Default", "What it does"],
            ["Crossover", "60 – 200 Hz", "120 Hz", "Frequency below which energy is monitored for pops."],
            ["Sensitivity", "1.5× – 6.0×", "3.0×", "How much louder than average the low end must be to count as a plosive. Lower = more aggressive."],
            ["Reduction", "0.0 – 1.0", "0.85", "How much of the low-band energy to remove at detected plosives."],
        ], col_widths=[3.5*cm, 2.5*cm, 2.5*cm, 8.5*cm]),

        sp(6),
        h2("Tab 2 — Dereverb"),
        h3("Reduce reverb / room sound"),
        p("Suppresses the diffuse room tail — the way sound bounces around a room and "
          "makes recordings sound distant or echoey. Uses spectral over-subtraction on the "
          "slowly-varying energy floor. Works well on speech recorded in untreated rooms. "
          "This stage is the most likely to colour the sound, so it's off by default — "
          "enable it when the room is clearly audible."),
        table([
            ["Parameter", "Range", "Default", "What it does"],
            ["Strength", "0.0 – 1.0", "0.60", "How much of the room tail to remove."],
            ["Tail smoothing", "20 – 200 ms", "60 ms", "Smoothing window for the reverb tail estimate. Longer = smoother but slower to react."],
        ], col_widths=[3.5*cm, 2.5*cm, 2.5*cm, 8.5*cm]),

        sp(6),
        h2("Tab 3 — EQ & Clarity"),
        h3("Balance EQ"),
        p("Corrective EQ for spoken voice. Applies three gentle adjustments:"),
        *bullets([
            "<b>Rumble cut:</b> high-pass filter that removes sub-sonic low-frequency content (mic handling noise, HVAC rumble, vibration). Adjustable from 40–150 Hz.",
            "<b>De-box:</b> a small dip around 300 Hz — the 'boxy' or 'muddy' frequency range where many untreated rooms and budget microphones build up. Usually −2 to −3 dB.",
            "<b>Air:</b> a gentle boost around 12 kHz adds sparkle and openness. Usually 1–3 dB.",
        ]),
        table([
            ["Parameter", "Range", "Default", "What it does"],
            ["Rumble cut", "40 – 150 Hz", "80 Hz", "High-pass filter cutoff frequency."],
            ["De-box", "−6 – 0 dB", "−2.5 dB", "Reduction at ~300 Hz."],
            ["Air", "0 – 6 dB", "+2.0 dB", "Boost at ~12 kHz."],
        ], col_widths=[3.5*cm, 2.5*cm, 2.5*cm, 8.5*cm]),

        sp(6),
        h3("Enhance voice clarity"),
        p("Lifts the 2–5 kHz presence range — where consonants and speech intelligibility live — "
          "and optionally runs a gentle compressor to bring quiet consonants forward without "
          "letting louder vowels clip. Run after noise and reverb are dealt with so "
          "you're not amplifying artefacts."),
        table([
            ["Parameter", "Range", "Default", "What it does"],
            ["Presence freq", "2000 – 6000 Hz", "3500 Hz", "Centre of the presence boost."],
            ["Presence lift", "0 – 6 dB", "+3.0 dB", "Amount of boost."],
            ["Gentle leveling", "On/Off", "On", "Enables the soft compressor for even dynamics."],
            ["Leveling ratio", "1.5 – 4.0:1", "2.5:1", "Compression ratio. Higher = more evening-out."],
        ], col_widths=[3.5*cm, 2.5*cm, 2.5*cm, 8.5*cm]),

        sp(6),
        h2("Tab 4 — Loudness"),
        h3("Normalize loudness (LUFS)"),
        p("Measures integrated loudness using the ITU-R BS.1770 standard (LUFS — Loudness Units "
          "relative to Full Scale) and applies the exact gain needed to hit the target. "
          "Then guards the output with a peak ceiling to prevent clipping. "
          "This is the last corrective stage before effects."),
        table([
            ["Parameter", "Range", "Default", "What it does"],
            ["Target", "−30 – −9 LUFS", "−16 LUFS", "Target integrated loudness. Common values: −14 (YouTube/Spotify), −16 (podcast), −23 (broadcast EBU R128)."],
            ["Peak ceiling", "−3 – 0 dBFS", "−1 dBFS", "Maximum allowed sample peak after gain is applied."],
        ], col_widths=[3.5*cm, 3*cm, 2*cm, 9*cm]),
        note("The current LUFS reading for the loaded clip is shown in the bottom-right of the waveform area, next to the A/B buttons."),

        sp(6),
        h2("Tab 5 — Effects"),
        h3("Trim (gain)"),
        p("Simple dB gain adjustment. Useful when the loudness normaliser can't bring "
          "the level up enough on its own, or when you want to manually reduce gain "
          "before other stages. Clips output to ±1.0 (0 dBFS) to prevent overflow."),
        table([
            ["Parameter", "Range", "Default", "What it does"],
            ["Gain", "−24 – +24 dB", "0 dB", "Gain adjustment. Positive = louder, negative = quieter."],
        ], col_widths=[3.5*cm, 3*cm, 2*cm, 9*cm]),

        sp(6),
        h3("Chorus"),
        p("Thickens audio by layering multiple LFO-modulated delay copies of the signal "
          "over the dry signal. Each voice uses a slightly different LFO phase offset, "
          "giving a lush ensemble effect. Useful for music and creative voice processing."),
        table([
            ["Parameter", "Range", "Default", "What it does"],
            ["Rate", "0.1 – 5.0 Hz", "0.8 Hz", "LFO modulation speed. Faster = more movement."],
            ["Depth", "0.001 – 0.030 s", "0.010 s", "LFO delay swing. More depth = wider modulation."],
            ["Mix", "0.0 – 1.0", "0.40", "Wet/dry blend. 0 = dry only, 1 = fully wet."],
            ["Voices", "1 – 3", "2", "Number of chorus voices. More voices = thicker but heavier CPU."],
        ], col_widths=[3.5*cm, 3*cm, 2*cm, 8.5*cm]),

        sp(6),
        h3("Widener"),
        p("Applies M/S (mid-side) stereo widening. Increases or decreases the width of "
          "the stereo image without affecting mono compatibility. "
          "Mono input is automatically upmixed to stereo before widening."),
        table([
            ["Parameter", "Range", "Default", "What it does"],
            ["Width", "0.0 – 2.0", "1.0", "0 = mono (all mid), 1 = unchanged, >1 = wider stereo image."],
        ], col_widths=[3.5*cm, 3*cm, 2*cm, 9*cm]),
        note("Width values above 1.5 can cause some elements to become very wide or phase-y on speakers. Use on headphone mixes cautiously."),

        sp(6),
        h3("Panner"),
        p("Positions the signal in the stereo field using a constant-power pan law "
          "(sin/cos) so perceived loudness stays stable as you pan. "
          "Mono input is upmixed to stereo before panning. "
          "Output is always stereo."),
        table([
            ["Parameter", "Range", "Default", "What it does"],
            ["Pan position", "0.0 – 1.0", "0.5", "0.0 = hard left, 0.5 = centre, 1.0 = hard right."],
        ], col_widths=[3.5*cm, 3*cm, 2*cm, 9*cm]),
    ]

    # ── 5. Auto Clean ───────────────────────────────────────────────────────
    s += [
        h1("5. Auto Clean"),
        p("Auto Clean is the one-button shortcut. It analyses your audio across six dimensions "
          "and automatically configures and applies the most appropriate settings. "
          "It's a good starting point even if you plan to tweak afterwards — the analysis "
          "report tells you exactly what it measured and what it applied."),
        sp(4),
        h2("5.1  What Auto Clean measures"),
        table([
            ["Measurement", "What it is"],
            ["Content type",    "Speech/voice vs music/instrument, using autocorrelation pitch detection."],
            ["Loudness",        "Integrated loudness in LUFS (ITU-R BS.1770)."],
            ["Estimated SNR",   "Signal-to-noise ratio using Welch PSD + minimum noise floor tracking."],
            ["Reverb tail",     "RT60 estimate — how long the room echo takes to decay by 60 dB."],
            ["Plosives",        "Whether breath pops are present in the low-frequency band."],
            ["Spectral tilt",   "Whether the audio is bright or dull/muffled (high vs low-mid energy ratio)."],
        ], col_widths=[4.5*cm, 12.5*cm]),
        sp(6),
        h2("5.2  What happens after analysis"),
        *bullets([
            "A settings configuration is built automatically based on the measurements.",
            "The processor panels in the Cleanup section update to show the applied settings.",
            "The cleanup pipeline runs in the background.",
            "When done, a report dialog summarises the measurements and what was applied.",
            "You can switch to B (Cleaned) to hear the result, then tweak any settings manually and re-apply if needed.",
        ]),
        sp(6),
        h2("5.3  When to use Auto Clean vs manual"),
        table([
            ["Situation", "Recommendation"],
            ["Quick turnaround, don't want to think about audio", "Auto Clean — done."],
            ["Good recording, just needs loudness normalising", "Manual: enable Loudness only, pick a preset target."],
            ["Very reverberant room", "Auto Clean, then increase Dereverb strength if needed."],
            ["Music recording (not voice)", "Auto Clean detects music and adjusts; or manual with effects."],
            ["Specific platform target (e.g. Apple Podcasts)", "Auto Clean, then use Export Presets for the correct LUFS/format."],
        ], col_widths=[6*cm, 11*cm]),
    ]

    # ── 6. A/B Comparison & Waveform View ───────────────────────────────────
    s += [
        h1("6. A/B Comparison & Waveform View"),
        h2("6.1  The waveform display"),
        p("The centre panel shows two waveforms side by side:"),
        *bullets([
            "<b>A (top):</b> the original, unprocessed audio.",
            "<b>B (bottom):</b> the cleaned/processed audio (appears after cleanup runs).",
        ]),
        p("Both waveforms are x-linked — zooming or scrolling one scrolls both, "
          "so you can compare the same section of audio at the same position."),
        sp(4),
        h2("6.2  Playback and A/B toggle"),
        table([
            ["Control", "Action"],
            ["▶ Play / ■ Stop", "Start or stop playback of the selected version."],
            ["A · Original",    "Switch playback to the original recording. The live LUFS reading updates."],
            ["B · Cleaned",     "Switch playback to the processed result. The live LUFS reading updates."],
            ["LUFS: — (label)", "Shows the current integrated loudness of whichever version is selected."],
        ], col_widths=[4.5*cm, 12.5*cm]),
        note("Switching A/B while playing takes effect immediately — no need to stop first."),
        sp(4),
        h2("6.3  The playhead"),
        p("A vertical line follows playback position in real time across both waveforms. "
          "Playback stops automatically when the clip ends."),
    ]

    # ── 7. Export ───────────────────────────────────────────────────────────
    s += [
        h1("7. Exporting Audio"),
        h2("7.1  Single file export"),
        *bullets([
            "Choose a <b>Preset</b> (or leave on Custom for manual control).",
            "Choose a <b>Format</b>.",
            "For lossless formats (WAV/FLAC/AIFF), choose a <b>Bit depth</b>.",
            "For lossy formats (MP3/AAC/OGG/OPUS), choose a <b>Bitrate</b>.",
            "Click <b>Export cleaned…</b> and choose where to save.",
        ]),
        p("If cleanup has been applied, the cleaned audio is exported. "
          "If not, the original is exported."),
        sp(6),
        h2("7.2  Export presets"),
        table([
            ["Preset", "Format", "LUFS Target", "Bit depth / Bitrate", "Use case"],
            ["YouTube",            "MP3",  "−14",  "192 kbps", "Video uploads"],
            ["Spotify",            "MP3",  "−14",  "320 kbps", "Music streaming"],
            ["Podcast (general)",  "MP3",  "−16",  "128 kbps", "Podcast hosts"],
            ["Apple Podcasts",     "AAC",  "−16",  "128 kbps", "Apple Podcasts spec"],
            ["Broadcast (EBU R128)","WAV", "−23",  "24-bit",   "European broadcast"],
            ["Broadcast TV (ATSC A/85)","WAV","−24","24-bit",  "US broadcast TV"],
            ["Church / Livestream","AAC",  "−16",  "256 kbps", "Live stream uploads"],
            ["Voice-Over / ACX",   "MP3",  "−20",  "192 kbps", "Audiobooks / ACX"],
            ["Archival (lossless)","FLAC", "none", "24-bit",   "Master archive"],
        ], col_widths=[4.5*cm, 1.8*cm, 2*cm, 3*cm, 5.7*cm]),
        sp(6),
        h2("7.3  Supported formats"),
        table([
            ["Format", "Extension", "Type", "Notes"],
            ["WAV",  ".wav",  "Lossless", "PCM 16-bit, 24-bit, or 32-bit float. Universal compatibility."],
            ["FLAC", ".flac", "Lossless", "Compressed lossless. Smaller than WAV, bit-perfect."],
            ["MP3",  ".mp3",  "Lossy",    "Universal. 128–320 kbps. Requires bundled ffmpeg."],
            ["AAC",  ".m4a",  "Lossy",    "Better quality than MP3 at same bitrate. Apple/YouTube standard."],
            ["OGG",  ".ogg",  "Lossy",    "Open format. Good quality. Widely supported on Linux/web."],
            ["OPUS", ".opus", "Lossy",    "Excellent quality at low bitrates. Great for voice. Via ffmpeg."],
            ["AIFF", ".aiff", "Lossless", "Uncompressed. Mac-friendly equivalent of WAV."],
        ], col_widths=[1.8*cm, 2*cm, 2*cm, 11.2*cm]),
        note("ffmpeg is bundled with the installer — no separate download needed for MP3, AAC, or OPUS export."),
        sp(6),
        h2("7.4  Batch processing"),
        p("Batch processing runs the entire cleanup pipeline over a folder of audio files "
          "and exports them all at once:"),
        *bullets([
            "Click <b>Batch folder…</b> in the Export section.",
            "Select the folder of source audio files.",
            "Select an output folder.",
            "Crisp processes every supported audio file using the currently configured cleanup settings.",
            "A summary dialog reports how many files were processed successfully.",
        ]),
        note("The cleanup settings used for batch processing are whatever is currently configured in the Cleanup panel — the same settings you'd use for a single file. Set them up first, then batch."),
    ]

    # ── 8. Settings ─────────────────────────────────────────────────────────
    s += [
        h1("8. Settings & Preferences"),
        h2("8.1  Saving and loading cleanup settings"),
        p("Your processor settings (which stages are enabled and all parameter values) "
          "can be saved and reloaded as <b>.crisp.json</b> files. This lets you build "
          "preset configurations for different recording scenarios:"),
        *bullets([
            "Click <b>Save settings…</b> in the Cleanup section to save the current configuration.",
            "Click <b>Load settings…</b> to load a saved configuration. All processor panels update immediately.",
            "These files are plain JSON — you can edit them manually or share them with others.",
        ]),
        sp(6),
        h2("8.2  Preferences dialog (Ctrl+,)"),
        p("Open <b>Settings → Preferences…</b> or press <b>Ctrl+,</b> to access:"),
        *bullets([
            "<b>Colour theme:</b> choose from 7 themes. The theme is also accessible from View → Colour theme.",
            "<b>Playback volume:</b> adjust the monitoring level.",
        ]),
        sp(6),
        h2("8.3  Colour themes"),
        table([
            ["Theme", "Description"],
            ["Dark Default",   "Deep navy with cyan accents. The default."],
            ["Midnight Blue",  "Deep blue-black with blue highlights."],
            ["Charcoal Orange","Dark charcoal with orange accent colour."],
            ["Deep Purple",    "Dark purple palette with lavender highlights."],
            ["Hacker Green",   "Black with terminal green. For those of a certain disposition."],
            ["Light Clean",    "White/grey light theme with blue accents."],
            ["Warm Cream",     "Warm off-white light theme with earthy tones."],
        ], col_widths=[4.5*cm, 12.5*cm]),
        p("Theme selection is saved automatically and restored next time you open the app."),
    ]

    # ── 9. Keyboard shortcuts ───────────────────────────────────────────────
    s += [
        h1("9. Keyboard Shortcuts"),
        table([
            ["Shortcut", "Action"],
            ["Ctrl+O",  "Open audio file"],
            ["Ctrl+E",  "Export cleaned audio"],
            ["Ctrl+,",  "Open Preferences dialog"],
            ["Ctrl+Q",  "Quit the application"],
        ], col_widths=[4*cm, 13*cm]),
    ]

    # ── 10. Tips ─────────────────────────────────────────────────────────────
    s += [
        h1("10. Tips & Best Practices"),
        h2("10.1  Signal chain order"),
        p("Crisp always runs processors in the same fixed order, regardless of tab order. "
          "This order is designed to give the best results:"),
        table([
            ["Order", "Processor", "Why this position"],
            ["1", "Noise Reduction", "Remove broadband noise first so later stages don't amplify it."],
            ["2", "Dereverb",        "Remove room before EQ so you're not EQ-ing the room character."],
            ["3", "Plosive Removal", "Duck plosives before clarity boost to avoid amplifying pops."],
            ["4", "EQ Balance",      "Corrective EQ on a now-clean signal."],
            ["5", "Voice Clarity",   "Enhance presence and dynamics on a clean, EQ'd signal."],
            ["6", "Loudness",        "Normalise loudness after all colouring is done."],
            ["7", "Trim",            "Fine-tune gain if needed after normalisation."],
            ["8", "Chorus",          "Creative effects go last."],
            ["9", "Widener",         "Width after everything else is balanced."],
            ["10","Panner",          "Final stereo placement."],
        ], col_widths=[1.5*cm, 3.5*cm, 12*cm]),
        sp(6),
        h2("10.2  Common scenarios"),
        h3("Noisy room recording (fan/AC noise)"),
        *bullets([
            "Enable Noise Reduction. Start at Strength 0.85.",
            "If artefacts (musical noise) appear, reduce Strength slightly.",
            "Enable Constant noise floor if the noise is steady throughout.",
        ]),
        h3("Echoey/reverberant room"),
        *bullets([
            "Enable Dereverb. Start at Strength 0.6.",
            "Increase gradually — more strength removes more room but can also affect voice quality.",
            "Dereverb works best on voice, less well on music.",
        ]),
        h3("Plosive microphone pops"),
        *bullets([
            "Enable Plosive Removal.",
            "If pops remain, lower Sensitivity (try 2.0×) to detect more aggressively.",
            "If normal speech is being affected, raise Sensitivity (try 4.0×).",
        ]),
        h3("Preparing for a podcast platform"),
        *bullets([
            "Run Auto Clean, or enable noise/plosives/EQ/clarity manually.",
            "Enable Loudness, set target to −16 LUFS.",
            "Choose the Podcast (general) export preset for correctly-targeted MP3.",
        ]),
        h3("Church livestream recording"),
        *bullets([
            "Use Auto Clean for the initial pass.",
            "Choose the Church / Livestream export preset (−16 LUFS, 256 kbps AAC).",
            "For batch processing multiple service recordings, use Batch folder….",
        ]),
        sp(4),
        h2("10.3  LUFS reference targets"),
        table([
            ["Platform / Standard", "Target LUFS"],
            ["YouTube",              "−14 LUFS integrated"],
            ["Spotify",              "−14 LUFS integrated"],
            ["Apple Music",          "−16 LUFS integrated"],
            ["Apple Podcasts",       "−16 LUFS integrated"],
            ["General podcasts",     "−16 LUFS integrated"],
            ["Voice-over / ACX",     "−18 to −23 LUFS (aim for −20)"],
            ["EBU R128 (broadcast)", "−23 LUFS integrated"],
            ["ATSC A/85 (US TV)",    "−24 LUFS integrated"],
        ], col_widths=[8*cm, 9*cm]),
    ]

    # ── 11. Troubleshooting ──────────────────────────────────────────────────
    s += [
        h1("11. Troubleshooting"),
        table([
            ["Problem", "Solution"],
            ["App doesn't launch",
             "Make sure you ran the full installer, not just Crisp.exe directly. "
             "Try right-clicking and running as administrator once."],
            ["No input devices listed",
             "Check your microphone is plugged in and Windows has given Crisp permission "
             "to access it (Settings → Privacy → Microphone)."],
            ["Export failed",
             "MP3/AAC/OPUS export requires ffmpeg, which is bundled in the installer. "
             "If running from source, install imageio-ffmpeg: pip install imageio-ffmpeg."],
            ["Audio sounds worse after processing",
             "Reduce Noise Reduction strength. Too-aggressive denoising causes 'watery' artefacts. "
             "Also check Dereverb strength isn't too high."],
            ["Loudness normalisation didn't work",
             "The clip must be at least 400 ms long for LUFS measurement to work. "
             "Very short clips are left at their original level."],
            ["Batch processing skipped some files",
             "Only WAV, FLAC, OGG, AIFF, MP3, M4A/AAC files are processed. "
             "The summary dialog shows how many succeeded vs failed."],
            ["Settings file won't load",
             "The .crisp.json file must have been saved by Crisp. "
             "Processor keys not matching any known processor are silently ignored."],
        ], col_widths=[4.5*cm, 12.5*cm]),
    ]

    # ── 12. Open Source & Licence ─────────────────────────────────────────────
    s += [
        h1("12. Open Source & Licence"),
        p("AudioCleanUpTool is free and open-source software, released under the "
          "<b>MIT License</b>. You are free to:"),
        *bullets([
            "Use it for any purpose, including commercial work",
            "Modify the source code",
            "Distribute copies or modified versions",
            "Include it in other projects",
        ]),
        p("The only requirement is that the copyright notice and licence text are "
          "included in any copies or substantial portions of the software."),
        sp(6),
        h2("Source code"),
        p("GitHub: <b>https://github.com/mourninggrace/crisp-audio</b>"),
        sp(4),
        h2("Built with"),
        table([
            ["Library", "Licence", "Purpose"],
            ["PySide6",        "LGPL v3",   "Qt GUI framework"],
            ["scipy",          "BSD",       "DSP filters and signal processing"],
            ["numpy",          "BSD",       "Array operations"],
            ["noisereduce",    "MIT",       "Spectral gating noise reduction"],
            ["pyloudnorm",     "MIT",       "LUFS measurement (ITU-R BS.1770)"],
            ["soundfile",      "BSD",       "WAV/FLAC/AIFF/OGG read/write"],
            ["sounddevice",    "MIT",       "Real-time audio recording"],
            ["pydub",          "MIT",       "MP3/AAC encoding via ffmpeg"],
            ["imageio-ffmpeg", "BSD",       "Bundled ffmpeg binaries"],
            ["pyqtgraph",      "MIT",       "Waveform display"],
        ], col_widths=[4*cm, 2.5*cm, 10.5*cm]),
    ]

    return s


# ── Build ─────────────────────────────────────────────────────────────────────
def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = TwoColumnDoc(
        str(OUT),
        pagesize=A4,
        title="AudioCleanUpTool User Guide",
        author="Gateway West Church Media",
        subject="User documentation for AudioCleanUpTool (Crisp) v0.1.0",
        creator="AudioCleanUpTool build_guide.py",
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm,
    )

    story = build_story(doc.toc)

    # First element switches to body template after cover
    from reportlab.platypus import NextPageTemplate
    story.insert(len(story) - len(story) + 1, NextPageTemplate("body"))

    doc.multiBuild(story)
    print(f"PDF written: {OUT}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
