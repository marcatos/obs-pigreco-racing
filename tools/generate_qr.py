"""Generate Discord (or custom URL) QR code PNG for ending scene."""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("generate_qr")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "overlays" / "assets" / "qr-discord.png"
DEFAULT_URL = "https://discord.com/invite/wZ4ZfK9DYy"


def main() -> None:
    t0 = time.perf_counter()
    p = argparse.ArgumentParser(description="Generate PiGreco ending QR PNG")
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M
    except ImportError as e:
        raise SystemExit("Install dependency: pip install \"qrcode[pil]\"") from e

    log.info("start generate_qr url=%s", args.url)
    qr = qrcode.QRCode(box_size=8, border=2, error_correction=ERROR_CORRECT_M)
    qr.add_data(args.url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#00C400", back_color="#080A0C")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    img.save(args.out)
    log.info(
        "wrote %s (%d bytes) in %.0f ms",
        args.out,
        args.out.stat().st_size,
        (time.perf_counter() - t0) * 1000,
    )


if __name__ == "__main__":
    main()
