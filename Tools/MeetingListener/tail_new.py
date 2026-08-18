"""
MeetingListener: tail_new.py
Ispisuje samo dio transkripta koji još nije pročitan i pamti poziciju,
kako bi Claude Code pri svakom pitanju dobio isključivo nove replike.

Pozicija se čuva u .<naziv>.offset pored samog transkripta.

  python tail_new.py            # novo od zadnjeg čitanja
  python tail_new.py --all      # cijeli transkript (bez pomjeranja pozicije)
  python tail_new.py --reset    # vrati poziciju na početak
  python tail_new.py --peek     # novo, ali bez pamćenja pozicije
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")

import argparse
from pathlib import Path


def offset_path(transcript):
    return transcript.parent / f".{transcript.name}.offset"


def read_offset(transcript):
    marker = offset_path(transcript)
    if not marker.exists():
        return 0
    try:
        return int(marker.read_text(encoding="utf-8").strip())
    except ValueError:
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ispis nepročitanog dijela transkripta.")
    parser.add_argument("--file", default="transcript.md", help="putanja do transkripta")
    parser.add_argument("--all", action="store_true", help="ispiši sve, ne pomjeraj poziciju")
    parser.add_argument("--peek", action="store_true", help="ispiši novo, ne pomjeraj poziciju")
    parser.add_argument("--reset", action="store_true", help="vrati poziciju na početak i izađi")
    args = parser.parse_args(argv)

    transcript = Path(args.file).expanduser().resolve()
    if not transcript.exists():
        print(f"Transkript ne postoji: {transcript}", file=sys.stderr)
        return 1

    if args.reset:
        offset_path(transcript).write_text("0", encoding="utf-8")
        print(f"Pozicija resetovana: {transcript}")
        return 0

    size = transcript.stat().st_size

    if args.all:
        sys.stdout.write(transcript.read_text(encoding="utf-8"))
        return 0

    start = read_offset(transcript)
    if start > size:
        # Fajl je skraćen ili zamijenjen — čita se od početka
        start = 0

    with transcript.open("r", encoding="utf-8") as fh:
        fh.seek(start)
        new_text = fh.read()
        end = fh.tell()

    if not args.peek:
        offset_path(transcript).write_text(str(end), encoding="utf-8")

    if new_text.strip():
        sys.stdout.write(new_text)
    else:
        print("(nema novog teksta)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
