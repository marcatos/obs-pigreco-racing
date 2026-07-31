"""Generate a PiGreco-branded Italian PDF guide (streaming visual language)."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Flowable,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pdf_guide")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Guida_PiGreco_OBS.pdf"
SHOWCASE = ROOT / "showcase"
ASSETS = ROOT / "overlays" / "assets"

# Official PiGreco palette (pigreco-restyle.css)
GREEN = HexColor("#00C400")
BLUE = HexColor("#009FE5")
BG = HexColor("#080A0C")
PANEL = HexColor("#11161A")
PANEL_SOFT = HexColor("#171D22")
TEXT = HexColor("#F7FAFC")
MUTED = HexColor("#A7B1BA")
LINE = HexColor("#283039")


class AccentBar(Flowable):
    def __init__(self, width: float, height: float = 4):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.saveState()
        # green -> blue gradient approximation with strips
        n = 24
        w = self.width / n
        for i in range(n):
            t = i / max(n - 1, 1)
            r = 0.0 * (1 - t) + 0.0 * t
            g = 0.77 * (1 - t) + 0.62 * t
            b = 0.0 * (1 - t) + 0.90 * t
            # blend #00C400 -> #009FE5
            r = 0x00 / 255 * (1 - t) + 0x00 / 255 * t
            g = 0xC4 / 255 * (1 - t) + 0x9F / 255 * t
            b = 0x00 / 255 * (1 - t) + 0xE5 / 255 * t
            c.setFillColorRGB(r, g, b)
            c.rect(i * w, 0, w + 0.5, self.height, stroke=0, fill=1)
        c.restoreState()


class StepCard(Flowable):
    """Dark panel with green left accent for a numbered step."""

    def __init__(self, number: int, title: str, body_paras: list[Paragraph], width: float):
        super().__init__()
        self.number = number
        self.title = title
        self.body_paras = body_paras
        self.card_width = width
        self._inner_height = 0

    def wrap(self, availWidth, availHeight):
        w = min(self.card_width, availWidth)
        y = 0
        title_style = ParagraphStyle(
            "cardTitle",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=TEXT,
            leading=14,
        )
        self._title_p = Paragraph(f"PASSO {self.number}  ·  {self.title.upper()}", title_style)
        tw, th = self._title_p.wrap(w - 28, availHeight)
        y += th + 8
        self._wrapped = []
        for p in self.body_paras:
            pw, ph = p.wrap(w - 28, availHeight)
            self._wrapped.append((p, ph))
            y += ph + 4
        self.width = w
        self.height = y + 22
        self._inner_height = self.height
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(PANEL)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.8)
        c.roundRect(0, 0, self.width, self.height, 2, stroke=1, fill=1)
        c.setFillColor(GREEN)
        c.rect(0, 0, 4, self.height, stroke=0, fill=1)
        # number badge
        c.setFillColor(HexColor("#0C1013"))
        c.circle(18, self.height - 16, 9, stroke=0, fill=1)
        c.setFillColor(GREEN)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(18, self.height - 19, str(self.number))
        y = self.height - 12
        tw, th = self._title_p.wrap(self.width - 36, self.height)
        self._title_p.drawOn(c, 32, y - th)
        y = y - th - 10
        for p, ph in self._wrapped:
            p.drawOn(c, 14, y - ph)
            y -= ph + 4
        c.restoreState()


def prepare_logos() -> tuple[Path, Path]:
    SHOWCASE.mkdir(parents=True, exist_ok=True)
    pi_out = SHOWCASE / "_logo_pi_pdf.png"
    word_out = SHOWCASE / "_logo_word_pdf.png"
    pi = PILImage.open(ASSETS / "logo-pi-official.png").convert("RGBA")
    pi.thumbnail((280, 280), PILImage.Resampling.LANCZOS)
    pi.save(pi_out)
    word = PILImage.open(ASSETS / "logo-wordmark-official.png").convert("RGBA")
    word.thumbnail((560, 180), PILImage.Resampling.LANCZOS)
    word.save(word_out)
    return pi_out, word_out


def compress_showcase(name: str, max_w: int = 1400) -> Path:
    src = SHOWCASE / name
    dst = SHOWCASE / f"_pdf_{name}"
    im = PILImage.open(src).convert("RGB")
    im.thumbnail((max_w, int(max_w * 9 / 16)), PILImage.Resampling.LANCZOS)
    im.save(dst, "JPEG", quality=82, optimize=True)
    return dst


def make_styles():
    base = getSampleStyleSheet()
    return {
        "cover_tag": ParagraphStyle(
            "cover_tag",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=GREEN,
            alignment=TA_CENTER,
            letterSpacing=2,
            spaceAfter=8,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            fontName="Helvetica-Bold",
            fontSize=26,
            textColor=TEXT,
            alignment=TA_CENTER,
            leading=30,
            spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            fontName="Helvetica",
            fontSize=11,
            textColor=MUTED,
            alignment=TA_CENTER,
            leading=15,
            spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "h1",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=BLUE,
            spaceBefore=4,
            spaceAfter=8,
            leading=16,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=10,
            textColor=TEXT,
            leading=14.5,
            spaceAfter=6,
        ),
        "muted": ParagraphStyle(
            "muted",
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=MUTED,
            leading=12.5,
            spaceAfter=8,
        ),
        "code": ParagraphStyle(
            "code",
            fontName="Courier",
            fontSize=8.2,
            textColor=GREEN,
            leading=11.5,
            backColor=PANEL_SOFT,
            borderPadding=6,
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "caption",
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "li": ParagraphStyle(
            "li",
            fontName="Helvetica",
            fontSize=10,
            textColor=TEXT,
            leading=14,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def draw_page_chrome(canvas, doc, *, cover: bool = False):
    canvas.saveState()
    w, h = A4
    # background
    canvas.setFillColor(BG)
    canvas.rect(0, 0, w, h, stroke=0, fill=1)

    # subtle top/bottom accent stripes
    canvas.setFillColor(GREEN)
    canvas.rect(0, h - 5, w, 5, stroke=0, fill=1)
    canvas.setFillColor(BLUE)
    canvas.rect(0, 0, w, 5, stroke=0, fill=1)

    # corner brackets
    canvas.setStrokeColor(GREEN)
    canvas.setLineWidth(1.6)
    m = 14
    L = 22
    for x0, y0, dx, dy in (
        (m, h - m, 1, -1),
        (w - m, h - m, -1, -1),
        (m, m, 1, 1),
        (w - m, m, -1, 1),
    ):
        canvas.line(x0, y0, x0 + dx * L, y0)
        canvas.line(x0, y0, x0, y0 + dy * L)

    if not cover:
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(1.8 * cm, 0.85 * cm, "PiGreco Racing")
        canvas.drawRightString(w - 1.8 * cm, 0.85 * cm, f"Pagina {doc.page}")
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(1.8 * cm, 1.15 * cm, w - 1.8 * cm, 1.15 * cm)

    canvas.restoreState()


def build() -> Path:
    started = time.perf_counter()
    log.info("start branded PDF guide")
    pi_logo, word_logo = prepare_logos()
    s = make_styles()

    page_w, page_h = A4
    margin = 1.7 * cm
    frame = Frame(
        margin,
        1.5 * cm,
        page_w - 2 * margin,
        page_h - 2.6 * cm,
        id="normal",
    )
    cover_frame = Frame(
        margin,
        1.5 * cm,
        page_w - 2 * margin,
        page_h - 2.6 * cm,
        id="cover",
    )

    doc = BaseDocTemplate(
        str(OUT),
        pagesize=A4,
        title="Guida PiGreco Racing — OBS",
        author="PiGreco Racing",
    )
    doc.addPageTemplates(
        [
            PageTemplate(
                id="Cover",
                frames=[cover_frame],
                onPage=lambda c, d: draw_page_chrome(c, d, cover=True),
            ),
            PageTemplate(
                id="Body",
                frames=[frame],
                onPage=lambda c, d: draw_page_chrome(c, d, cover=False),
            ),
        ]
    )

    content_w = page_w - 2 * margin
    story: list = []

    # ----- COVER -----
    story.append(NextPageTemplate("Body"))
    story.append(Spacer(1, 1.2 * cm))
    story.append(Image(str(pi_logo), width=2.6 * cm, height=2.6 * cm, hAlign="CENTER"))
    story.append(Spacer(1, 0.35 * cm))
    story.append(Image(str(word_logo), width=9.5 * cm, height=2.5 * cm, hAlign="CENTER"))
    story.append(Spacer(1, 0.45 * cm))
    story.append(AccentBar(content_w * 0.55))
    story.append(Spacer(1, 0.55 * cm))
    story.append(Paragraph("GUIDA STREAMING OBS", s["cover_tag"]))
    story.append(Paragraph("Configura le scene<br/>in pochi passi", s["cover_title"]))
    story.append(
        Paragraph(
            "Istruzioni semplificate per i piloti del team.<br/>"
            "Non serve essere esperti di informatica.",
            s["cover_sub"],
        )
    )
    story.append(Spacer(1, 0.6 * cm))
    story.append(
        Paragraph(
            "Competizione · Rispetto · Ironia",
            ParagraphStyle(
                "motto",
                fontName="Helvetica-Bold",
                fontSize=10,
                textColor=BLUE,
                alignment=TA_CENTER,
                spaceAfter=10,
            ),
        )
    )

    # hero preview strip
    hero = compress_showcase("01-starting-soon.png", 1200)
    story.append(Image(str(hero), width=content_w, height=content_w * 9 / 16 * 0.72, hAlign="CENTER"))
    story.append(Paragraph("Anteprima scena «In arrivo»", s["caption"]))
    story.append(PageBreak())

    # ----- BODY -----
    story.append(Paragraph("COSA C’È NEL PACCHETTO", s["h1"]))
    story.append(AccentBar(4.5 * cm, 3))
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        ListFlowable(
            [
                ListItem(Paragraph("Scene OBS già pronte (In arrivo, Gara, Pausa, Fine…)", s["li"])),
                ListItem(Paragraph("Grafiche ufficiali <b>PiGreco Racing</b>", s["li"])),
                ListItem(Paragraph("Uno script che mette il <b>tuo nick</b> automaticamente", s["li"])),
                ListItem(Paragraph("Questa guida", s["li"])),
            ],
            bulletColor=GREEN,
            leftIndent=10,
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("PRIMA DI INIZIARE", s["h1"]))
    story.append(AccentBar(4.5 * cm, 3))
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        Paragraph(
            "1. Un PC Windows<br/>"
            "2. <b>OBS Studio</b> installato (gratis su <font color='#009FE5'>obsproject.com</font>)<br/>"
            "3. Questa cartella del pacchetto, messa in un posto fisso "
            "(es. Documenti → obs-pigreco-racing)<br/>"
            "4. Se non sai usare il computer oltre al doppio clic: usa <b>Setup.bat</b> "
            "oppure manda il tuo nick al referente tech",
            s["body"],
        )
    )

    story.append(Paragraph("INSTALLAZIONE IN 5 PASSI", s["h1"]))
    story.append(AccentBar(4.5 * cm, 3))
    story.append(Spacer(1, 0.35 * cm))

    def card(n: int, title: str, lines: list[str]) -> StepCard:
        paras = [Paragraph(line, s["body"]) for line in lines]
        return StepCard(n, title, paras, content_w)

    story.append(
        card(
            1,
            "Metti la cartella in un posto fisso",
            [
                "Esempio: <b>Documenti → obs-pigreco-racing</b>.",
                "Non rinominare i file dentro. Non spostare la cartella dopo aver configurato OBS.",
            ],
        )
    )
    story.append(Spacer(1, 0.35 * cm))
    story.append(
        card(
            2,
            "Avvia il setup (consigliato)",
            [
                "Fai <b>doppio clic</b> su <b>Setup.bat</b> (nella cartella del pacchetto).",
                "Ti chiede il <b>nick Twitch</b> e il nome da mostrare in diretta.",
                "Se sul PC <b>non c’è Python</b>, lo script lo installa da solo: "
                "appare la richiesta di amministratore Windows → scegli <b>Sì</b>.",
                "Alla fine dice «SETUP COMPLETATO».",
            ],
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        Paragraph(
            "Alternativa tecnica (solo se sai usare PowerShell): "
            r".\Setup.ps1 -Username TUO_NICK -PilotName \"Il Tuo Nome\"",
            s["muted"],
        )
    )

    story.append(
        card(
            3,
            "Apri OBS e scegli le scene",
            [
                "Apri <b>OBS Studio</b>.",
                "Menu in alto: <b>Collezione di scene</b> → seleziona <b>PiGreco Racing</b>.",
                "Se non la vedi: chiudi OBS, rilancia <b>Setup.bat</b>, poi riapri.",
            ],
        )
    )
    story.append(Spacer(1, 0.35 * cm))
    story.append(
        card(
            4,
            "Collega schermo e webcam",
            [
                "Scena <b>Live Race</b> → sorgente <b>Monitor Centro</b> → Proprietà → "
                "scegli il monitor centrale del triplo.",
                "Scena <b>Live Singolo</b> → <b>Monitor Singolo</b> → il monitor che usi "
                "quando il triplo è spento.",
                "Controlla che la webcam <b>StreamCam</b> sia quella giusta.",
            ],
        )
    )
    story.append(Spacer(1, 0.35 * cm))
    story.append(
        card(
            5,
            "Prova le scene",
            [
                "Clicca a sinistra: Starting Soon, Live Race, Live Singolo, BRB, Ending.",
                "Le grafiche devono riempire tutto lo schermo (non un riquadro piccolo).",
                "Nick non aggiornato? Tasto destro sulla sorgente Browser → "
                "<b>Aggiorna cache della pagina corrente</b>.",
            ],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("ANTEPRIMA DELLE SCENE", s["h1"]))
    story.append(AccentBar(4.5 * cm, 3))
    story.append(Spacer(1, 0.3 * cm))

    for fname, label in [
        ("01-starting-soon.png", "Starting Soon — prima della diretta"),
        ("02-live-chrome.png", "Live — grafiche sopra il gameplay"),
        ("03-brb.png", "BRB — torno subito"),
        ("04-ending.png", "Ending — chiusura stream"),
    ]:
        img = compress_showcase(fname, 1300)
        story.append(Image(str(img), width=content_w, height=content_w * 9 / 16 * 0.78, hAlign="CENTER"))
        story.append(Paragraph(label, s["caption"]))

    story.append(Paragraph("TASTI CONSIGLIATI (OPZIONALE)", s["h1"]))
    story.append(AccentBar(4.5 * cm, 3))
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        Paragraph(
            "OBS → Impostazioni → Tasti di scelta rapida:",
            s["body"],
        )
    )
    data = [
        [Paragraph("<b>TASTO</b>", s["body"]), Paragraph("<b>SCENA</b>", s["body"])],
        ["F1", "Starting Soon"],
        ["F2", "Live Race"],
        ["F3", "Live Singolo"],
        ["F4", "BRB"],
        ["F5", "Ending"],
    ]
    t = Table(data, colWidths=[3.2 * cm, content_w - 3.2 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PANEL_SOFT),
                ("BACKGROUND", (0, 1), (-1, -1), PANEL),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 1), (0, -1), GREEN),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("LINEABOVE", (0, 0), (-1, 0), 2, GREEN),
                ("PADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 0.45 * cm))

    story.append(Paragraph("PROBLEMI FREQUENTI", s["h1"]))
    story.append(AccentBar(4.5 * cm, 3))
    story.append(Spacer(1, 0.25 * cm))
    faqs = [
        (
            "Vedo solo un pezzetto in un angolo",
            "Chiudi OBS, rifai il Passo 2, riapri e seleziona di nuovo «PiGreco Racing».",
        ),
        (
            "Non trovo «PiGreco Racing» nel menu",
            "Il Passo 2 non ha copiato il file. Verifica --install-obs oppure chiedi al referente tech.",
        ),
        (
            "Il mio nick non cambia",
            "Rilancia Setup.bat, poi in OBS: Aggiorna cache sulla sorgente Browser.",
        ),
        (
            "Non so usare PowerShell / Python",
            "Usa solo Setup.bat con doppio clic. Se chiede l’amministratore, accetta. "
            "In alternativa manda il nick al referente tech.",
        ),
        (
            "Windows blocca lo script",
            "Tasto destro su Setup.ps1 → Proprietà → spunta «Sblocca» se presente, "
            "oppure usa Setup.bat. Se SmartScreen avvisa: Altre info → Esegui comunque.",
        ),
    ]
    for title, ans in faqs:
        story.append(
            KeepTogether(
                [
                    Paragraph(f"<font color='#00C400'><b>▸ {title}</b></font>", s["body"]),
                    Paragraph(ans, s["muted"]),
                ]
            )
        )

    story.append(Paragraph("PROMEMORIA", s["h1"]))
    story.append(AccentBar(4.5 * cm, 3))
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        Paragraph(
            "• Chiudi OBS prima di rilanciare lo script di setup.<br/>"
            "• Non spostare la cartella del pacchetto dopo la configurazione.<br/>"
            "• In OBS usa risoluzione <b>1920×1080</b> (canvas e uscita).",
            s["body"],
        )
    )
    story.append(Spacer(1, 0.6 * cm))
    story.append(AccentBar(content_w * 0.4, 3))
    story.append(Spacer(1, 0.35 * cm))
    story.append(
        Paragraph(
            "PiGreco Racing — Competizione · Rispetto · Ironia",
            s["footer"],
        )
    )

    doc.build(story)
    size_kb = OUT.stat().st_size // 1024
    log.info(
        "PDF written %s (%d KB) in %.0f ms",
        OUT.name,
        size_kb,
        (time.perf_counter() - started) * 1000,
    )
    return OUT


if __name__ == "__main__":
    build()
