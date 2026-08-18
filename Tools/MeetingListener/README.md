# MeetingListener

Lokalni „slušač" sastanka: hvata sistemski zvuk (Teams, Zoom, Meet — svejedno),
transkribuje ga na tvojoj mašini i dopisuje u `transcript.md`. Claude Code
zatim čita taj fajl i odgovara na pitanja iz razgovora.

**Ništa ne ide na internet.** Whisper model se preuzme jednom i dalje se
izvršava lokalno.

```
sistemski zvuk (loopback)  →  listen.py  →  transcript.md  →  Claude Code
```

Latencija je otprilike `--min-chunk` + vrijeme transkripcije, realno 10–20 s
sa `small` modelom na CPU-u.

> **Pristanak:** loopback hvata sve što ide kroz zvučnike, dakle i druge
> učesnike. Snimanje tuđeg govora u većini slučajeva traži njihovu saglasnost —
> reci im, isto kao što Teams prikaže banner kad krene vlastito snimanje.

---

## 1. Instalacija

```bash
cd Tools/MeetingListener
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

Prvo pokretanje preuzima Whisper model (`small` ≈ 500 MB) u lokalni cache.

---

## 2. Postavljanje loopback zvuka

Mikrofon snima samo tebe. Za ostale učesnike treba **loopback** — uređaj koji
vraća izlazni zvuk nazad kao ulaz.

### Windows

Ništa se ne instalira: skripta automatski koristi **WASAPI loopback** nad
zadanim izlaznim uređajem. Ako verzija `sounddevice`-a to ne podržava,
uključi *Stereo Mix* (Sound → Recording → desni klik → Show Disabled Devices)
ili instaliraj [VB-Audio Virtual Cable](https://vb-audio.com/Cable/).

### macOS

macOS ne dozvoljava snimanje sistemskog zvuka bez virtuelnog uređaja:

1. Instaliraj [BlackHole](https://existential.audio/blackhole/):
   `brew install blackhole-2ch`
2. Otvori *Audio MIDI Setup* → **Multi-Output Device** → označi svoje
   zvučnike **i** BlackHole 2ch.
3. Postavi taj Multi-Output kao sistemski izlaz (inače nećeš ništa čuti).
4. `python listen.py --device "BlackHole 2ch"`

### Linux (PulseAudio / PipeWire)

Monitor izvor već postoji — skripta ga sama nađe po nazivu `Monitor of ...`.

---

## 3. Provjera prije sastanka

```bash
python listen.py --list-devices      # koji uređaji postoje
python listen.py --calibrate 10      # pusti zvuk i gledaj RMS razine
```

`--list-devices` ispisuje i ulazne i izlazne uređaje; za WASAPI loopback se
zadaje indeks **izlaznog** uređaja (zvučnika).

`--calibrate` ispisuje razinu signala i predlaže `--silence-threshold`.
Ako su sve vrijednosti ~0.00000, loopback ne radi — vrati se na korak 2.

---

## 4. Snimanje

```bash
python listen.py --language bs
```

Korisne opcije:

| Opcija | Zadano | Čemu služi |
|--------|--------|------------|
| `--language` | auto | `bs`, `hr`, `sr`, `en` — fiksiranje jezika smanjuje greške |
| `--model` | `small` | `medium` / `large-v3` su tačniji i sporiji, `base` brži |
| `--device-type cuda --compute-type float16` | cpu/int8 | ako imaš NVIDIA GPU |
| `--min-chunk` | 8 | manje = brži odgovor, lošija tačnost |
| `--max-chunk` | 20 | tvrdi rez kad govornik ne pravi pauze |
| `--silence-threshold` | 0.004 | prag tišine iz `--calibrate` |
| `--out` | `transcript.md` | putanja transkripta |

Prekid je `Ctrl+C` — zadnji segment se transkribuje prije izlaza.

---

## 5. Pitanja Claudeu tokom sastanka

U **drugom terminalu**, u istom folderu:

```bash
claude
```

Pa pitaj normalno, npr. *„šta su rekli o rokovima?"*. Claude čita transkript
preko:

```bash
python tail_new.py       # samo ono što još nije pročitano
python tail_new.py --all # cijeli transkript
```

`tail_new.py` pamti dokle je stiglo u `.transcript.md.offset`, pa se stari
dio razgovora ne čita iznova pri svakom pitanju.

Za automatsko praćenje bez pitanja koristi `/loop`:

```
/loop 2m pročitaj novi dio transkripta preko `python tail_new.py` i javi mi
samo ako je neko postavio pitanje meni ili spomenuo rok
```

---

## 6. Kad transkript nije dobar

| Simptom | Uzrok i rješenje |
|---------|------------------|
| `Nijedan ulaz se nije dao otvoriti` | Greška nabraja sve pokušaje; uzmi indeks iz `--list-devices` i zadaj `--device <idx>` |
| Prazan transkript | Loopback ne radi → `--calibrate`, pa korak 2 |
| Sve na engleskom | Zadaj `--language bs` |
| Ponavljanje fraza tipa „Titlovi…" | Halucinacija na tišini; podigni `--silence-threshold` |
| Presporo | `--model base`, ili GPU: `--device-type cuda --compute-type float16` |
| Netačno kod stručnih pojmova | `--model medium` ili `large-v3` |
| Odsječeni počeci riječi | Povećaj `--preroll` (npr. `0.6`) |
