"""Generate a simplified Italian PDF guide for teammates."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pdf_guide")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Guida_PiGreco_OBS.pdf"
SHOWCASE = ROOT / "showcase"

GREEN = HexColor("#00C400")
BLUE = HexColor("#009FE5")
BLACK = HexColor("#050505")
PANEL = HexColor("#11161A")
MUTED = HexColor("#5A6570")
TEXT = HexColor("#1A1A1A")


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleIT",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=BLACK,
            spaceAfter=6,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "SubIT",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "h1": ParagraphStyle(
            "H1IT",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=BLACK,
            spaceBefore=14,
            spaceAfter=8,
            borderPadding=3,
        ),
        "h2": ParagraphStyle(
            "H2IT",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=HexColor("#0B6E00"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "BodyIT",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=TEXT,
            spaceAfter=6,
        ),
        "step": ParagraphStyle(
            "StepIT",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=TEXT,
            leftIndent=4,
            spaceAfter=4,
        ),
        "note": ParagraphStyle(
            "NoteIT",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=13,
            textColor=MUTED,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "warn": ParagraphStyle(
            "WarnIT",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=HexColor("#8A1C1C"),
            spaceBefore=6,
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "CapIT",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "footer": ParagraphStyle(
            "FootIT",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def bullet(text: str, style) -> ListItem:
    return ListItem(Paragraph(text, style), leftIndent=12, value="•")


def step_block(number: int, title: str, lines: list[str], s) -> KeepTogether:
    parts = [Paragraph(f"<b>Passo {number} — {title}</b>", s["h2"])]
    for line in lines:
        parts.append(Paragraph(line, s["step"]))
    parts.append(Spacer(1, 4))
    return KeepTogether(parts)


def maybe_image(name: str, width: float = 15.5 * cm) -> list:
    path = SHOWCASE / name
    if not path.exists():
        log.warning("missing showcase image %s", path)
        return []
    img = Image(str(path), width=width, height=width * 9 / 16)
    img.hAlign = "CENTER"
    return [img, Spacer(1, 2)]


def build() -> Path:
    started = time.perf_counter()
    s = styles()
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title="Guida PiGreco Racing — OBS",
        author="PiGreco Racing",
    )

    story: list = []
    story.append(Paragraph("PiGreco Racing", s["title"]))
    story.append(Paragraph("Guida semplice per lo streaming su OBS", s["subtitle"]))
    story.append(
        Paragraph(
            "Questa guida è pensata per chi vuole usare il pacchetto scene "
            "<b>senza dover essere un esperto di computer</b>. Segui i passi in ordine.",
            s["body"],
        )
    )

    story.append(Paragraph("Cosa trovi in questo pacchetto", s["h1"]))
    story.append(
        ListFlowable(
            [
                bullet("Le <b>scene OBS</b> già pronte (In arrivo, Gara, Pausa, Fine…)", s["body"]),
                bullet("Le <b>grafiche</b> del team PiGreco Racing", s["body"]),
                bullet("Uno <b>script</b> che personalizza il tuo nome/nick", s["body"]),
                bullet("Questa guida in PDF", s["body"]),
            ],
            bulletType="bullet",
            start="•",
        )
    )

    story.append(Paragraph("Cosa ti serve prima", s["h1"]))
    story.append(
        Paragraph(
            "1. Un PC Windows<br/>"
            "2. <b>OBS Studio</b> installato "
            "(dal sito ufficiale: obsproject.com — versione gratuita)<br/>"
            "3. La cartella di questo pacchetto (quella che ti hanno condiviso)<br/>"
            "4. (Consigliato) <b>Python</b> installato — se non ce l’hai, chiedi a chi ti ha "
            "passato il pacchetto di prepararti il file già col tuo nick",
            s["body"],
        )
    )

    story.append(Paragraph("Installazione in 5 passi", s["h1"]))

    story.append(
        step_block(
            1,
            "Metti la cartella in un posto fisso",
            [
                "Esempio: Documenti → Projects → <b>obs-pigreco-racing</b>",
                "Non rinominare i file dentro la cartella. Non spostarla dopo aver configurato OBS, "
                "oppure dovrai rifare il Passo 2.",
            ],
            s,
        )
    )
    story.append(
        step_block(
            2,
            "Scrivi il tuo nick (personalizzazione)",
            [
                "Apri il menu Start di Windows e cerca <b>PowerShell</b> (o “Terminale”).",
                "Copia queste due righe, cambia solo <b>TUO_NICK</b> e il nome, poi premi Invio:",
            ],
            s,
        )
    )
    story.append(
        Paragraph(
            "<font face='Courier' size='9'>"
            "cd percorso\\della\\cartella\\obs-pigreco-racing<br/>"
            "python tools\\setup_streamer.py --username TUO_NICK "
            "--pilot-name \"Il Tuo Nome\" --install-obs"
            "</font>",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "Esempio: --username marco92 --pilot-name \"Marco Rossi\"",
            s["note"],
        )
    )
    story.append(
        Paragraph(
            "Se compare un errore su “python”, chiedi aiuto a un compagno più tecnico: "
            "può fare lui questo passo per te.",
            s["note"],
        )
    )

    story.append(
        step_block(
            3,
            "Apri OBS e scegli la collezione scene",
            [
                "Apri <b>OBS Studio</b>.",
                "In alto: menu <b>Collezione di scene</b> (o Scene Collection).",
                "Seleziona <b>PiGreco Racing</b>.",
                "Se non la vedi: chiudi OBS, rifai il Passo 2 con --install-obs, poi riapri OBS.",
            ],
            s,
        )
    )

    story.append(
        step_block(
            4,
            "Collega lo schermo di gioco e la webcam",
            [
                "Nella scena <b>Live Race</b> clicca la sorgente <b>Monitor Centro</b> → "
                "ingranaggio / Proprietà → scegli il monitor centrale del triplo.",
                "Nella scena <b>Live Singolo</b> fai lo stesso con <b>Monitor Singolo</b> "
                "(il monitor che usi quando il triplo è spento).",
                "Controlla che <b>StreamCam</b> (o la tua webcam) sia selezionata correttamente.",
            ],
            s,
        )
    )

    story.append(
        step_block(
            5,
            "Prova le scene",
            [
                "Clicca le scene a sinistra una per una: Starting Soon, Live Race, Live Singolo, BRB, Ending.",
                "Devi vedere le grafiche PiGreco a schermo intero (non un riquadro piccolo in un angolo).",
                "Se hai cambiato il nick e non si aggiorna: tasto destro sulla sorgente Browser → "
                "<b>Aggiorna cache della pagina corrente</b>.",
            ],
            s,
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("Come si presentano le scene", s["h1"]))
    story.append(Paragraph("Starting Soon — prima di andare in diretta", s["body"]))
    story.extend(maybe_image("01-starting-soon.png", 14.5 * cm))
    story.append(Paragraph("Anteprima scena «In arrivo»", s["caption"]))

    story.append(Paragraph("Live — durante la gara (grafiche sopra il gioco)", s["body"]))
    story.extend(maybe_image("02-live-chrome.png", 14.5 * cm))
    story.append(Paragraph("Anteprima chrome live (logo, webcam, nome pilota)", s["caption"]))

    story.append(Paragraph("BRB e Ending", s["body"]))
    story.extend(maybe_image("03-brb.png", 7.2 * cm))
    story.append(Paragraph("«Torno subito»", s["caption"]))
    story.extend(maybe_image("04-ending.png", 7.2 * cm))
    story.append(Paragraph("«Grazie per aver seguito»", s["caption"]))

    story.append(Paragraph("Scorciatoie consigliate (opzionale)", s["h1"]))
    story.append(
        Paragraph(
            "In OBS: Impostazioni → Tasti di scelta rapida. Assegna ad esempio:",
            s["body"],
        )
    )
    table = Table(
        [
            ["Tasto", "Scena"],
            ["F1", "Starting Soon (In arrivo)"],
            ["F2", "Live Race (gara triplo)"],
            ["F3", "Live Singolo"],
            ["F4", "BRB (pausa)"],
            ["F5", "Ending (chiusura)"],
        ],
        colWidths=[3.5 * cm, 11 * cm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#E8F8E8")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#CCCCCC")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)

    story.append(Paragraph("Problemi frequenti", s["h1"]))
    story.append(
        Paragraph(
            "<b>Vedo solo un pezzetto di immagine in un angolo</b><br/>"
            "La collezione non è quella giusta oppure il file è vecchio. "
            "Chiudi OBS, rifai il Passo 2, riapri OBS e seleziona di nuovo «PiGreco Racing».",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Non trovo «PiGreco Racing» nel menu</b><br/>"
            "Il Passo 2 non ha copiato il file. Verifica di aver scritto --install-obs "
            "oppure chiedi a un compagno di copiare obs\\PiGreco_Racing.json nella cartella "
            "scene di OBS.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Il mio nick non cambia</b><br/>"
            "Controlla overlays\\config.js oppure riesegui setup_streamer. "
            "Poi in OBS: Aggiorna cache sulla sorgente Browser.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Non so usare PowerShell</b><br/>"
            "Nessun problema: manda il tuo nick a chi gestisce il pacchetto (es. il CTO / referente tech) "
            "e ti preparerà la cartella già configurata.",
            s["body"],
        )
    )

    story.append(Paragraph("Promemoria importanti", s["h1"]))
    story.append(
        Paragraph(
            "• Chiudi OBS prima di rilanciare setup_streamer o di sostituire i file della collezione.<br/>"
            "• Non spostare la cartella del pacchetto dopo la configurazione.<br/>"
            "• Risoluzione consigliata in OBS: <b>1920×1080</b> (sia canvas sia uscita).",
            s["body"],
        )
    )

    story.append(Spacer(1, 16))
    story.append(
        Paragraph(
            "PiGreco Racing — Competizione · Rispetto · Ironia<br/>"
            "Per dettagli tecnici vedi anche README.md nella stessa cartella.",
            s["footer"],
        )
    )

    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(GREEN)
        canvas.setLineWidth(2)
        canvas.line(1.8 * cm, A4[1] - 1.1 * cm, A4[0] - 1.8 * cm, A4[1] - 1.1 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(A4[0] / 2, 1.0 * cm, f"Pagina {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    log.info(
        "PDF written %s (%d KB) in %.0f ms",
        OUT,
        OUT.stat().st_size // 1024,
        (time.perf_counter() - started) * 1000,
    )
    return OUT


if __name__ == "__main__":
    build()
