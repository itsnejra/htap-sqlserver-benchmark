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
import warnings
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
    """Ispisuje uređaje i označava kandidate za snimanje sistemskog zvuka."""
    hostapis = sd.query_hostapis()
    loopback_ready = _wasapi_loopback_settings() is not None
    print(f"{'idx':>4}  {'ul':>3}  {'iz':>3}  {'Hz':>7}  {'host API':<22}  naziv")
    print("-" * 104)
    for idx, dev in enumerate(sd.query_devices()):
        host = hostapis[dev["hostapi"]]["name"]
        mark = ""
        if dev["max_input_channels"] > 0 and _is_loopback_name(dev["name"]):
            mark = "  ← loopback ulaz"
        elif dev["max_output_channels"] > 0 and loopback_ready and "wasapi" in host.lower():
            mark = "  ← WASAPI loopback kandidat"
        print(
            f"{idx:>4}  {dev['max_input_channels']:>3}  {dev['max_output_channels']:>3}  "
            f"{int(dev['default_samplerate']):>7}  {host:<22}  {dev['name']}{mark}"
        )
    print()
    print(f"sounddevice {sd.__version__}; WASAPI loopback kroz sounddevice "
          f"{'dostupan' if loopback_ready else 'NIJE dostupan'}")
    print("Uređaj se bira sa --device <idx>. Za WASAPI loopback zadaje se")
    print("indeks IZLAZNOG uređaja (zvučnika), ne ulaznog.")

    _list_soundcard_speakers()


def _list_soundcard_speakers():
    """Ispisuje zvučnike vidljive rezervnom backendu (bira se nazivom)."""
    soundcard = _soundcard_module()
    if soundcard is None:
        print()
        print("soundcard backend: nije instaliran → pip install soundcard")
        return
    try:
        speakers = soundcard.all_speakers()
        default = soundcard.default_speaker()
    except Exception as exc:
        print(f"\nsoundcard backend: greška pri nabrajanju ({exc})")
        return
    print()
    print("soundcard backend (--backend soundcard, --device \"<naziv>\"):")
    for speaker in speakers:
        mark = "  ← zadani" if default is not None and speaker.name == default.name else ""
        print(f"   {speaker.name}{mark}")


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
        # sounddevice < 0.5.0 nema loopback parametar
        return None


def candidate_sources(requested):
    """
    Gradi listu kandidata [(opis, indeks, extra_settings)] po prioritetu.

    Vraća se lista, a ne jedan uređaj, jer se na Windowsu uređaji poput
    onemogućenog Stereo Mixa uredno enumerišu ali se ne daju otvoriti —
    tada se prelazi na sljedećeg kandidata.
    """
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    loopback = _wasapi_loopback_settings()
    found = []

    def add(idx, extra, label):
        if not any(idx == i and (extra is None) == (e is None) for _, i, e in found):
            found.append((label, idx, extra))

    if requested is not None:
        idx = requested if isinstance(requested, int) else sd.query_devices(requested)["index"]
        dev = devices[idx]
        if dev["max_input_channels"] > 0:
            add(idx, None, f"ulaz «{dev['name']}»")
        if dev["max_output_channels"] > 0 and loopback is not None:
            add(idx, loopback, f"WASAPI loopback «{dev['name']}»")
        if not found:
            raise RuntimeError(
                f"Uređaj {idx} nema ulaznih kanala, a WASAPI loopback nije dostupan "
                f"(sounddevice {sd.__version__}; potrebna verzija >= 0.5.0)."
            )
        return found

    # 1) Ulazi koji su po nazivu monitor/loopback (PulseAudio, Stereo Mix, BlackHole…)
    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0 and _is_loopback_name(dev["name"]):
            add(idx, None, f"ulaz «{dev['name']}»")

    # 2) WASAPI loopback: prvo zadani izlaz, pa ostali izlazni uređaji
    if loopback is not None:
        for api in hostapis:
            if "wasapi" not in api["name"].lower():
                continue
            default_out = api.get("default_output_device", -1)
            if default_out is not None and default_out >= 0:
                add(default_out, loopback,
                    f"WASAPI loopback «{devices[default_out]['name']}» (zadani izlaz)")
            for idx in api.get("devices", ()):
                if devices[idx]["max_output_channels"] > 0:
                    add(idx, loopback, f"WASAPI loopback «{devices[idx]['name']}»")

    if not found:
        raise RuntimeError(
            "Nije pronađen nijedan kandidat za snimanje sistemskog zvuka.\n"
            "Pokreni --list-devices, pa zadaj uređaj sa --device <idx>.\n"
            "Windows: uključi Stereo Mix ili instaliraj VB-Audio Virtual Cable.\n"
            "macOS: instaliraj BlackHole i napravi Multi-Output Device."
        )
    return found


def _channel_options(dev, extra_settings):
    """Kanali koje vrijedi probati; WASAPI loopback traži tačan broj kanala miksa."""
    limit = dev["max_output_channels"] if extra_settings is not None else dev["max_input_channels"]
    order = (limit, 2, 1) if extra_settings is not None else (min(2, limit), 1, limit)
    options = []
    for channels in order:
        if 0 < channels <= limit and channels not in options:
            options.append(channels)
    return options


def _rate_options(dev):
    """Frekvencije po prioritetu — nativna prva, jer je WASAPI ne konvertuje."""
    options = []
    for rate in (int(dev["default_samplerate"]), 48_000, 44_100, TARGET_SR):
        if rate > 0 and rate not in options:
            options.append(rate)
    return options


def open_stream(sources, callback):
    """
    Otvara prvi ulaz koji uspije, probajući kombinacije kanala i frekvencija.
    Vraća (stream, samplerate, opis). Ako sve padne, greška nabraja pokušaje.
    """
    attempts = []
    for label, idx, extra in sources:
        dev = sd.query_devices(idx)
        for channels in _channel_options(dev, extra):
            for samplerate in _rate_options(dev):
                try:
                    stream = sd.InputStream(
                        device=idx,
                        channels=channels,
                        samplerate=samplerate,
                        blocksize=int(samplerate * BLOCK_SECONDS),
                        dtype="float32",
                        extra_settings=extra,
                        callback=callback,
                    )
                    return stream, samplerate, f"{label}, {channels} kan. @ {samplerate} Hz"
                except Exception as exc:
                    attempts.append(f"{label}: {channels} kan. @ {samplerate} Hz → {exc}")

    listing = "\n  ".join(attempts[:15])
    raise RuntimeError(
        f"Nijedan ulaz se nije dao otvoriti (sounddevice {sd.__version__}).\n"
        f"Pokušano:\n  {listing}\n\n"
        "Sljedeći korak: pokreni --list-devices i zadaj uređaj ručno sa --device <idx>.\n"
        "Windows: Postavke zvuka → Snimanje → desni klik → Prikaži onemogućene uređaje →\n"
        "uključi Stereo Mix; ako ga nema, instaliraj VB-Audio Virtual Cable."
    )


# ----------------------------------------------------------------
# Rezervni backend: soundcard
# ----------------------------------------------------------------
# sounddevice do 0.5.6 ne izlaže WASAPI loopback, pa na Windowsu ostaje samo
# Stereo Mix — koji je na većini mašina onemogućen ili ga uopšte nema.
# Biblioteka soundcard otvara loopback nad zvučnicima direktno.
def _soundcard_module():
    try:
        import soundcard
    except ImportError:
        return None
    return soundcard


class SoundCardCapture:
    """
    Snima izlazni uređaj preko soundcard-a i prosljeđuje blokove istom
    callbacku kao sounddevice, da ostatak skripte ne zna za razliku.
    """

    def __init__(self, recorder, callback, block_frames, samplerate, label):
        self._recorder = recorder
        self._callback = callback
        self._block_frames = block_frames
        self._active = None
        self._thread = None
        self._stop = threading.Event()
        self.samplerate = samplerate
        self.label = label

    def _pump(self):
        while not self._stop.is_set():
            try:
                data = self._active.record(numframes=self._block_frames)
            except Exception as exc:                     # uređaj nestao usred snimanja
                print(f"[audio] snimanje prekinuto: {exc}", file=sys.stderr)
                return
            if data is not None and len(data):
                self._callback(np.asarray(data, dtype=np.float32), len(data), None, None)

    def __enter__(self):
        self._active = self._recorder.__enter__()
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc_info):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        return self._recorder.__exit__(*exc_info)


def open_soundcard(requested, callback):
    """Otvara loopback nad zvučnicima preko soundcard biblioteke."""
    soundcard = _soundcard_module()
    if soundcard is None:
        raise RuntimeError("biblioteka nije instalirana → pip install soundcard")

    # WASAPI loopback ne isporučuje uzorke dok se ništa ne pušta, pa soundcard
    # svaku tišinu prijavi kao prekid u snimanju. Bezopasno, ali zatrpava ispis.
    warnings.filterwarnings("ignore", message="data discontinuity in recording")

    if isinstance(requested, str):
        speaker = soundcard.get_speaker(requested)
    else:
        # Indeksi se razlikuju među backendima, pa se za soundcard uzima
        # zadani izlaz; drugi zvučnik se bira nazivom (--device "Realtek").
        speaker = soundcard.default_speaker()
    if speaker is None:
        raise RuntimeError("zvučnik nije pronađen")

    mic = soundcard.get_microphone(id=str(speaker.name), include_loopback=True)
    if mic is None:
        raise RuntimeError(f"loopback nad «{speaker.name}» nije dostupan")

    samplerate = 48_000
    block_frames = int(samplerate * BLOCK_SECONDS)
    channels = 2 if getattr(mic, "channels", 2) and mic.channels >= 2 else 1
    recorder = mic.recorder(samplerate=samplerate, channels=channels, blocksize=block_frames)
    label = f"soundcard loopback «{speaker.name}», {channels} kan. @ {samplerate} Hz"
    return SoundCardCapture(recorder, callback, block_frames, samplerate, label)


def open_capture(requested, backend, callback):
    """
    Otvara snimanje prvim backendom koji uspije.
    Vraća (kontekst menadžer, samplerate, opis).
    """
    problems = []

    if backend in ("auto", "sounddevice"):
        try:
            return open_stream(candidate_sources(requested), callback)
        except RuntimeError as exc:
            if backend == "sounddevice":
                raise
            problems.append(str(exc))

    if backend in ("auto", "soundcard"):
        try:
            capture = open_soundcard(requested, callback)
            return capture, capture.samplerate, capture.label
        except Exception as exc:
            problems.append(f"soundcard backend: {exc}")
            if backend == "soundcard":
                raise RuntimeError(f"soundcard backend: {exc}")

    raise RuntimeError(
        "\n\n".join(problems)
        + "\n\nAko ni soundcard ne uspije: uključi Stereo Mix (Postavke zvuka →\n"
        "Snimanje → desni klik → Prikaži onemogućene uređaje) ili instaliraj\n"
        "VB-Audio Virtual Cable."
    )


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
def calibrate(seconds, requested, backend):
    """Mjeri RMS razinu kroz zadani period kao pomoć pri izboru --silence-threshold."""
    levels = []
    blocks = queue.Queue()

    def callback(indata, frames, time_info, status):
        blocks.put(to_mono(indata.copy()))

    stream, samplerate, label = open_capture(requested, backend, callback)
    print(f"Kalibracija {seconds} s — {label}")
    print("Pusti zvuk (video, muziku, poziv)...")
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
    if args.calibrate:
        calibrate(args.calibrate, args.device, args.backend)
        return 0

    from faster_whisper import WhisperModel  # uvozi se tek kad zaista treba

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Učitavanje modela '{args.model}' ({args.device_type}/{args.compute_type})...")
    model = WhisperModel(args.model, device=args.device_type, compute_type=args.compute_type)

    blocks = queue.Queue()
    chunks = queue.Queue()
    stats = {"blokova": 0, "segmenata": 0, "transkribovano": 0, "razina": 0.0}

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[audio] {status}", file=sys.stderr)
        blocks.put(to_mono(indata.copy()))

    stream, samplerate, source_label = open_capture(args.device, args.backend, callback)

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
                started = time.monotonic()
                segments, _ = model.transcribe(
                    audio,
                    language=args.language,
                    beam_size=args.beam_size,
                    vad_filter=True,
                    # Bez uslovljavanja prethodnim tekstom — sprječava lančane halucinacije
                    condition_on_previous_text=False,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
                stats["transkribovano"] += 1
                if args.meter:
                    print(f"[mjerac] segment {len(audio) / TARGET_SR:.1f} s obradjen "
                          f"za {time.monotonic() - started:.1f} s")
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
            stats["segmenata"] += 1
        buffer = []
        buffered_frames = 0
        silence_run = 0.0
        speech_seen = False

    print(f"Slušam: {source_label} → {out_path}")
    print("Ctrl+C za prekid.\n")

    last_meter = time.monotonic()

    def show_meter():
        print(f"[mjerac] razina {stats['razina']:.4f} | blokova {stats['blokova']} | "
              f"segmenata {stats['segmenata']} | obradjeno {stats['transkribovano']} | "
              f"ceka {chunks.qsize()}")

    try:
        with stream:
            while True:
                if args.meter and time.monotonic() - last_meter >= args.meter:
                    show_meter()
                    last_meter = time.monotonic()

                try:
                    block = blocks.get(timeout=0.5)
                except queue.Empty:
                    continue

                stats["blokova"] += 1
                block_seconds = len(block) / samplerate
                level = float(np.sqrt(np.mean(block**2)))
                stats["razina"] = level
                is_silent = level < args.silence_threshold

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
    parser.add_argument("--backend", default="auto", choices=["auto", "sounddevice", "soundcard"],
                        help="način snimanja; auto prvo probava sounddevice pa soundcard")
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
    parser.add_argument("--meter", type=float, default=0.0, metavar="SEK",
                        help="svakih N sekundi ispisi razinu i brojace (0 = iskljuceno)")
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
