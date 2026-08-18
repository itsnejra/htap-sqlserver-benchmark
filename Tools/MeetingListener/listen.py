"""
MeetingListener: listen.py
Hvata sistemski zvuk (loopback), transkribuje ga lokalno preko faster-whisper
modela i dopisuje tekst u transcript.md.

Ništa ne napušta mašinu — model se izvršava lokalno na CPU-u ili GPU-u.

Tipična upotreba:
  python listen.py --list-devices          # pregled ulaznih uređaja
  python listen.py --calibrate 10          # mjerenje razine šutnje
  python listen.py --language bs           # snimanje sastanka

Prekid sa Ctrl+C — zadnji nedovršeni segment se transkribuje prije izlaza.
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")

import argparse
import queue
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd

# ----------------------------------------------------------------
# Konstante
# ----------------------------------------------------------------
TARGET_SR = 16_000          # faster-whisper očekuje 16 kHz mono
BLOCK_SECONDS = 0.1         # granularnost detekcije šutnje

# Nazivi po kojima se prepoznaje loopback/monitor uređaj
LOOPBACK_HINTS = (
    "monitor",              # PulseAudio / PipeWire
    "loopback",
    "stereo mix",           # Windows (Realtek)
    "what u hear",          # Windows (Creative)
    "blackhole",            # macOS
    "soundflower",          # macOS (legacy)
    "cable output",         # VB-Audio Virtual Cable
)

# Whisper na tišini povremeno halucinira fraze iz titlova — te se odbacuju
HALLUCINATION_PATTERNS = (
    "titlovi",
    "subtitles by",
    "amara.org",
    "hvala na gledanju",
    "thanks for watching",
    "prijevod i obrada",
    "podnapisi",
)


# ----------------------------------------------------------------
# Odabir uređaja
# ----------------------------------------------------------------
def list_devices():
    """Ispisuje ulazne uređaje i označava vjerovatne loopback kandidate."""
    hostapis = sd.query_hostapis()
    print(f"{'idx':>4}  {'ch':>3}  {'Hz':>7}  {'host API':<22}  naziv")
    print("-" * 100)
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] < 1:
            continue
        host = hostapis[dev["hostapi"]]["name"]
        mark = " ← loopback?" if _is_loopback_name(dev["name"]) else ""
        print(
            f"{idx:>4}  {dev['max_input_channels']:>3}  "
            f"{int(dev['default_samplerate']):>7}  {host:<22}  {dev['name']}{mark}"
        )
    print()
    print("Na Windowsu loopback ne mora biti na listi — WASAPI loopback nad")
    print("zadanim izlazom se koristi automatski ako nijedan kandidat ne postoji.")


def _is_loopback_name(name):
    lowered = name.lower()
    return any(hint in lowered for hint in LOOPBACK_HINTS)


def _wasapi_loopback_settings():
    """Vraća WasapiSettings(loopback=True) ako ga instalirani sounddevice podržava."""
    settings_cls = getattr(sd, "WasapiSettings", None)
    if settings_cls is None:
        return None
    try:
        return settings_cls(loopback=True)
    except TypeError:
        # Starije verzije sounddevice-a nemaju loopback parametar
        return None


def resolve_source(requested):
    """
    Određuje (device_index, channels, extra_settings) za snimanje.

    Redoslijed: eksplicitan uređaj → prepoznat monitor/loopback ulaz →
    WASAPI loopback nad zadanim izlazom (Windows).
    """
    devices = sd.query_devices()

    if requested is not None:
        idx = requested if isinstance(requested, int) else sd.query_devices(requested)["index"]
        dev = devices[idx]
        if dev["max_input_channels"] > 0:
            return idx, min(2, dev["max_input_channels"]), None
        # Izlazni uređaj je zadan eksplicitno → jedini smislen način je loopback
        extra = _wasapi_loopback_settings()
        if extra is None:
            raise RuntimeError(
                f"Uređaj {idx} nema ulaznih kanala, a WASAPI loopback nije dostupan."
            )
        return idx, min(2, dev["max_output_channels"]), extra

    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0 and _is_loopback_name(dev["name"]):
            return idx, min(2, dev["max_input_channels"]), None

    extra = _wasapi_loopback_settings()
    if extra is not None:
        for api in sd.query_hostapis():
            if "wasapi" in api["name"].lower() and api["default_output_device"] >= 0:
                idx = api["default_output_device"]
                return idx, min(2, devices[idx]["max_output_channels"]), extra

    raise RuntimeError(
        "Nije pronađen loopback uređaj. Pokreni --list-devices i zadaj ga preko "
        "--device, ili pogledaj README za postavljanje (BlackHole / VB-Cable / "
        "PulseAudio monitor)."
    )


def open_stream(device, channels, extra_settings, callback):
    """
    Otvara ulazni stream, po mogućnosti odmah na 16 kHz.
    Ako uređaj to ne prihvata, koristi svoju nativnu frekvenciju.
    """
    for samplerate in (TARGET_SR, int(sd.query_devices(device)["default_samplerate"])):
        try:
            stream = sd.InputStream(
                device=device,
                channels=channels,
                samplerate=samplerate,
                blocksize=int(samplerate * BLOCK_SECONDS),
                dtype="float32",
                extra_settings=extra_settings,
                callback=callback,
            )
            return stream, samplerate
        except (sd.PortAudioError, ValueError):
            continue
    raise RuntimeError("Uređaj nije prihvatio ni 16 kHz ni vlastitu frekvenciju.")


# ----------------------------------------------------------------
# Obrada zvuka
# ----------------------------------------------------------------
def to_mono(block):
    return block[:, 0] if block.shape[1] == 1 else block.mean(axis=1)


def resample_to_16k(samples, samplerate):
    """
    Spušta signal na 16 kHz. Za cjelobrojne omjere (48k, 32k) koristi se
    usrednjavanje susjednih uzoraka, što ujedno djeluje kao gruba
    anti-aliasing filtracija; inače linearna interpolacija.
    """
    if samplerate == TARGET_SR:
        return samples.astype(np.float32)

    if samplerate % TARGET_SR == 0:
        factor = samplerate // TARGET_SR
        usable = (len(samples) // factor) * factor
        return samples[:usable].reshape(-1, factor).mean(axis=1).astype(np.float32)

    n_out = int(round(len(samples) * TARGET_SR / samplerate))
    return np.interp(
        np.linspace(0, len(samples) - 1, n_out),
        np.arange(len(samples)),
        samples,
    ).astype(np.float32)


def is_hallucination(text):
    lowered = text.lower()
    return any(pattern in lowered for pattern in HALLUCINATION_PATTERNS)


# ----------------------------------------------------------------
# Kalibracija
# ----------------------------------------------------------------
def calibrate(seconds, device, channels, extra_settings):
    """Mjeri RMS razinu kroz zadani period kao pomoć pri izboru --silence-threshold."""
    levels = []
    blocks = queue.Queue()

    def callback(indata, frames, time_info, status):
        blocks.put(to_mono(indata.copy()))

    stream, samplerate = open_stream(device, channels, extra_settings, callback)
    print(f"Kalibracija {seconds} s na uređaju {device} @ {samplerate} Hz — pusti zvuk...")
    with stream:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                block = blocks.get(timeout=0.5)
            except queue.Empty:
                continue
            rms = float(np.sqrt(np.mean(block**2)))
            levels.append(rms)
            bar = "█" * min(40, int(rms * 400))
            print(f"  RMS {rms:.5f} {bar}")

    if not levels:
        print("Nijedan blok nije stigao — uređaj vjerovatno ne isporučuje zvuk.")
        return

    arr = np.array(levels)
    print()
    print(f"  min      {arr.min():.5f}")
    print(f"  medijan  {np.median(arr):.5f}")
    print(f"  max      {arr.max():.5f}")
    print()
    print(f"Prijedlog: --silence-threshold {max(arr.min() * 3, 0.0005):.4f}")


# ----------------------------------------------------------------
# Glavna petlja
# ----------------------------------------------------------------
def run(args):
    device, channels, extra_settings = resolve_source(args.device)

    if args.calibrate:
        calibrate(args.calibrate, device, channels, extra_settings)
        return 0

    from faster_whisper import WhisperModel  # uvozi se tek kad zaista treba

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Učitavanje modela '{args.model}' ({args.device_type}/{args.compute_type})...")
    model = WhisperModel(args.model, device=args.device_type, compute_type=args.compute_type)

    blocks = queue.Queue()
    chunks = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[audio] {status}", file=sys.stderr)
        blocks.put(to_mono(indata.copy()))

    stream, samplerate = open_stream(device, channels, extra_settings, callback)
    dev_name = sd.query_devices(device)["name"]

    # ── Transkripcija (odvojena nit, da snimanje nikad ne čeka model) ────
    def transcriber():
        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## Sesija {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
            fh.flush()
            while True:
                chunk = chunks.get()
                if chunk is None:
                    break
                audio = resample_to_16k(chunk, samplerate)
                segments, _ = model.transcribe(
                    audio,
                    language=args.language,
                    beam_size=args.beam_size,
                    vad_filter=True,
                    # Bez uslovljavanja prethodnim tekstom — sprječava lančane halucinacije
                    condition_on_previous_text=False,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
                if not text or is_hallucination(text):
                    continue
                line = f"[{datetime.now():%H:%M:%S}] {text}"
                fh.write(line + "\n")
                fh.flush()
                print(line)

    worker = threading.Thread(target=transcriber, daemon=True)
    worker.start()

    # ── Segmentacija: rez na šutnji, uz tvrdi limit dužine ───────────────
    # Tišina prije prve riječi se ne bafera — inače bi pauza između replika
    # trošila dužinu segmenta i tjerala tvrdi rez usred rečenice. Zadržava se
    # samo kratak pre-roll da početak riječi ne bude odsječen.
    preroll = deque(maxlen=max(1, int(args.preroll / BLOCK_SECONDS)))
    buffer = []
    buffered_frames = 0
    silence_run = 0.0
    speech_seen = False

    def flush_segment():
        nonlocal buffer, buffered_frames, silence_run, speech_seen
        if speech_seen and buffered_frames:
            chunks.put(np.concatenate(buffer))
        buffer = []
        buffered_frames = 0
        silence_run = 0.0
        speech_seen = False

    print(f"Slušam: {dev_name} @ {samplerate} Hz → {out_path}")
    print("Ctrl+C za prekid.\n")

    try:
        with stream:
            while True:
                try:
                    block = blocks.get(timeout=0.5)
                except queue.Empty:
                    continue

                block_seconds = len(block) / samplerate
                is_silent = float(np.sqrt(np.mean(block**2))) < args.silence_threshold

                if not speech_seen:
                    if is_silent:
                        preroll.append(block)
                        continue
                    buffer.extend(preroll)
                    buffered_frames += sum(len(b) for b in preroll)
                    preroll.clear()
                    speech_seen = True

                buffer.append(block)
                buffered_frames += len(block)
                duration = buffered_frames / samplerate
                silence_run = silence_run + block_seconds if is_silent else 0.0

                cut_on_pause = duration >= args.min_chunk and silence_run >= args.silence_hold
                if cut_on_pause or duration >= args.max_chunk:
                    flush_segment()
    except KeyboardInterrupt:
        print("\nPrekid — obrada zadnjeg segmenta...")

    flush_segment()
    chunks.put(None)
    worker.join()
    print(f"Transkript: {out_path}")
    return 0


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Lokalna transkripcija sistemskog zvuka u Markdown fajl.",
    )
    parser.add_argument("--list-devices", action="store_true", help="ispiši ulazne uređaje i izađi")
    parser.add_argument("--calibrate", type=float, metavar="SEK",
                        help="izmjeri RMS razinu kroz N sekundi i predloži prag šutnje")
    parser.add_argument("--device", help="indeks ili naziv uređaja (zadano: automatski loopback)")
    parser.add_argument("--out", default="transcript.md", help="izlazni fajl (zadano: transcript.md)")

    parser.add_argument("--model", default="small",
                        help="whisper model: tiny/base/small/medium/large-v3 (zadano: small)")
    parser.add_argument("--device-type", default="cpu", choices=["cpu", "cuda", "auto"],
                        help="gdje se model izvršava (zadano: cpu)")
    parser.add_argument("--compute-type", default="int8",
                        help="int8 za CPU, float16 za CUDA (zadano: int8)")
    parser.add_argument("--language", default=None,
                        help="npr. bs, hr, sr, en; zadano automatska detekcija")
    parser.add_argument("--beam-size", type=int, default=1,
                        help="veći = tačnije i sporije (zadano: 1)")

    parser.add_argument("--min-chunk", type=float, default=8.0,
                        help="minimalna dužina segmenta u sekundama (zadano: 8)")
    parser.add_argument("--max-chunk", type=float, default=20.0,
                        help="tvrdi rez ako pauze nema (zadano: 20)")
    parser.add_argument("--silence-hold", type=float, default=0.6,
                        help="koliko šutnje zatvara segment (zadano: 0.6)")
    parser.add_argument("--silence-threshold", type=float, default=0.004,
                        help="RMS prag ispod kojeg je blok šutnja (zadano: 0.004)")
    parser.add_argument("--preroll", type=float, default=0.3,
                        help="koliko tišine se zadržava ispred prve riječi (zadano: 0.3)")

    args = parser.parse_args(argv)
    if args.device is not None and args.device.isdigit():
        args.device = int(args.device)
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.list_devices:
        list_devices()
        return 0
    try:
        return run(args)
    except RuntimeError as exc:
        print(f"Greška: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
