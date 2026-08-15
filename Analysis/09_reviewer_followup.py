"""
09_reviewer_followup.py — analize koje traze primjedbe na rad.

Svaka sekcija odgovara jednoj primjedbi:

  1. VELICINA EFEKTA. Rad je koristio Cohenov d uz Mann-Whitney, a d je
     parametrijska mjera preko sredina i pooled devijacije. Uz odbacenu
     normalnost to je nekonzistentno. Ovdje se racuna Cliffova delta, koja
     pripada istoj neparametrijskoj porodici kao Mann-Whitney, uz rank-biserial
     korelaciju kao ekvivalentnu mjeru.

  2. CXSYNC_PORT. Rad tvrdi da je MAXDOP 1 nuzan da se izbjegnu zastoji na
     memorijsko-optimiziranim tabelama, a istovremeno pokazuje da MAXDOP 2 na
     tim istim tabelama radi bolje. Ovdje se mjeri koliko tih cekanja zaista
     ima pri DOP = 2, cime se tvrdnja ili potvrdjuje ili opovrgava.

  3. KAUZALNI RACUN. Tvrdnja "upiti zavrse prije pa oslobode procesor" ne
     objasnjava sama po sebi dobitak: dvostruko vise niti kroz upola krace
     vrijeme daje istu trenutnu zauzetost. Ovdje se racuna procesorsko vrijeme
     po ZAVRSENOM analitickom upitu i broj zavrsenih upita po runu, cime se
     razlikuju dva objasnjenja:
       (a) paralelni plan radi MANJE ukupnog posla  -> "paralelizam smanjuje rad"
       (b) isti posao, ali se upiti pri DOP 1 gomilaju -> "paralelizam rastereti red"

  4. NEMONOTONOST. Propusnost u row-mode rukama pada od C=16 ka C=32. To ide u
     prilog tezi, ali znaci da dio dobitka nije "vise propusnosti" nego
     "izbjegnut kolaps" — sto rad treba imenovati.

  5. VELICINA UZORKA. Nisu sve celije imale 30 runova nakon iskljucenja.

  6. SMJER EFEKTA PO OMJERIMA. Rad prikazuje samo 80/20.

POKRETANJE
----------
  python Analysis/09_reviewer_followup.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "Results"
OUT = RESULTS / "reviewer_followup.txt"

RATIO = "80_20"
CONCS = [4, 16, 32]

lines: list[str] = []


def emit(text: str = "") -> None:
    print(text)
    lines.append(text)


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> tuple[float, str]:
    """
    Cliffova delta: P(a > b) - P(a < b), u rasponu [-1, 1].

    Racuna se preko Mann-Whitney U statistike, sto je egzaktno i izbjegava
    kvadratno poredjenje svih parova: delta = 2U / (n1 n2) - 1.
    """
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return float("nan"), "n/a"
    u = stats.mannwhitneyu(a, b, alternative="two-sided").statistic
    delta = 2.0 * u / (n1 * n2) - 1.0

    ad = abs(delta)
    if ad < 0.147:
        label = "zanemariv"
    elif ad < 0.33:
        label = "mali"
    elif ad < 0.474:
        label = "srednji"
    else:
        label = "veliki"
    return delta, label


def load() -> pd.DataFrame:
    frames = [pd.read_csv(RESULTS / "summary.csv")]
    for arm in sorted(RESULTS.glob("summary_arm_*.csv")):
        frames.append(pd.read_csv(arm))
    df = pd.concat(frames, ignore_index=True)
    df["Configuration"] = df["Configuration"].str.strip().str.lower()
    return df[df["OltpSuccessRate"] >= 0.90]


def im_baseline(present: set[str]) -> tuple[str, str]:
    """
    Koja se ruka koristi kao MAXDOP 1 osnova za polugu paralelizma.

    im@d1base je izmjeren u istoj sesiji kao im@d2, pod istim brojacima i nad
    istim stanjem baze, pa usporedba protiv njega mjeri iskljucivo MAXDOP.
    Glavni `im` set potice iz ranije kampanje, prije instrumentacije, pa
    usporedba protiv njega mijesa efekt paralelizma s razlikom medju sesijama.
    """
    if "im@d1base" in present:
        return "im@d1base", "ista sesija — mjeri iskljucivo MAXDOP"
    return "im", "RAZLICITA SESIJA — efekt paralelizma nije odvojen od efekta sesije"


def off_arm(present: set[str]) -> tuple[str, str]:
    """
    Koja se ruka koristi kao preusmjerena (OFF) konfiguracija.

    htap@d1base je HTAP mjeren u istoj sesiji kao im@d1base i im@d2. Glavni
    `htap` set potice iz ranije kampanje, pa usporedba protiv njega nosi isti
    problem kao i poluga paralelizma: efekt smjestaja se ne moze odvojiti od
    razlike medju mjernim sesijama.
    """
    if "htap@d1base" in present:
        return "htap@d1base", "ista sesija"
    return "htap", "RAZLICITA SESIJA — efekt smjestaja nije odvojen od efekta sesije"


def cell(df: pd.DataFrame, cfg: str, col: str, conc: int,
         ratio: str | None = RATIO) -> np.ndarray:
    sel = (df.Configuration == cfg) & (df.ConcurrencyLevel == conc)
    if ratio is not None:
        sel &= df.OltpOlapRatio == ratio
    return df.loc[sel, col].dropna().to_numpy()


def med(df: pd.DataFrame, cfg: str, col: str, conc: int,
        ratio: str | None = RATIO) -> float:
    v = cell(df, cfg, col, conc, ratio)
    return float(np.median(v)) if len(v) else float("nan")


def section_effect_size(df: pd.DataFrame, present: set[str]) -> None:
    emit("1. VELICINA EFEKTA — Cliffova delta umjesto Cohenovog d")
    emit("-" * 74)
    emit("   Delta = P(A > B) - P(A < B). Vrijednost 1,00 znaci potpunu separaciju:")
    emit("   svaki run jedne ruke nadmasuje svaki run druge.")
    emit("")

    base, note = im_baseline(present)
    off, offnote = off_arm(present)
    pairs = [(off, "im@d2", f"smjestaj ({off.upper()} vs IM-P) — {offnote}"),
             ("im@d2", base, f"paralelizam (IM-P vs {base.upper()}) — {note}"),
             ("htap", "im", "nekontrolirano (OFF vs IM)")]

    for a_cfg, b_cfg, label in pairs:
        if a_cfg not in present or b_cfg not in present:
            emit(f"   {label}: ruka nije izmjerena — preskacem")
            continue
        emit(f"   {label}")
        for c in CONCS:
            a, b = cell(df, a_cfg, "OltpThroughput", c), cell(df, b_cfg, "OltpThroughput", c)
            if len(a) < 3 or len(b) < 3:
                continue
            delta, lab = cliffs_delta(a, b)
            rb = delta  # rank-biserial korelacija je jednaka Cliffovoj delti
            _, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            emit(f"     C={c:>2}: delta = {delta:+.3f} ({lab})   "
                 f"rank-biserial = {rb:+.3f}   p = {p:.2e}   "
                 f"N = {len(a)}/{len(b)}")
        emit("")


def section_cxsync(df: pd.DataFrame, present: set[str]) -> None:
    emit("2. CXSYNC_PORT PRI MAXDOP 2 NA HEKATON TABELAMA")
    emit("-" * 74)
    if "im@d2" not in present or "CxSyncPortMs" not in df.columns:
        emit("   Ruka im@d2 ili kolona brojaca nije dostupna — preskacem.\n")
        return

    emit("   Rad tvrdi da je MAXDOP 1 nuzan zbog ovih cekanja. Ako su pri DOP 2")
    emit("   zanemariva, tvrdnju treba oslabiti; ako su znatna, treba objasniti")
    emit("   zasto ruka svejedno radi bolje.")
    emit("")
    emit(f"   {'C':>3}  {'CXSYNC_PORT':>14}  {'CXPACKET+CONSUMER':>20}  {'udio u mjernoj fazi':>21}")
    for c in CONCS:
        cx = med(df, "im@d2", "CxSyncPortMs", c)
        par = med(df, "im@d2", "ParallelismWaitMs", c)
        if not np.isfinite(cx):
            continue
        emit(f"   {c:>3}  {cx / 1000:>11.2f} s  {par / 1000:>17.2f} s  "
             f"{cx / 60000 * 100:>20.2f} %")
    emit("")


def section_causal(df: pd.DataFrame, present: set[str]) -> None:
    emit("3. KAUZALNI RACUN — gdje odlazi procesorsko vrijeme")
    emit("-" * 74)

    emit("   (a) Zavrseni analiticki upiti po runu (medijan)")
    emit(f"       {'C':>3}  {'IM (DOP 1)':>12}  {'IM-P (DOP 2)':>14}  {'OFF':>10}  {'IM-P / IM':>11}")
    for c in CONCS:
        im = med(df, "im", "OlapTotalOps", c)
        imp = med(df, "im@d2", "OlapTotalOps", c) if "im@d2" in present else float("nan")
        off = med(df, "htap", "OlapTotalOps", c)
        ratio = imp / im if np.isfinite(imp) and im else float("nan")
        emit(f"       {c:>3}  {im:>12,.0f}  {imp:>14,.0f}  {off:>10,.0f}  {ratio:>11.2f}")
    emit("")

    if "OlapCpuMs" not in df.columns:
        emit("   (b) Brojaci nisu dostupni — preskacem.\n")
        return

    emit("   (b) Procesorsko vrijeme po ZAVRSENOM analitickom upitu")
    emit("       Pada li po upitu, paralelni plan radi manje ukupnog posla;")
    emit("       ostane li isti, dobitak dolazi od propusnosti a ne od ustede.")
    emit(f"       {'ruka':<10} {'C':>3}  {'OLAP CPU (s)':>13}  {'upita':>8}  {'CPU/upit (ms)':>15}"
         f"  {'OLTP CPU (s)':>13}")
    for arm in ["im@d1base", "im@d2"]:
        if arm not in present:
            emit(f"       {arm:<10} nije izmjereno")
            continue
        for c in CONCS:
            cpu = med(df, arm, "OlapCpuMs", c)
            ops = med(df, arm, "OlapTotalOps", c)
            oltp = med(df, arm, "OltpCpuMs", c)
            if not np.isfinite(cpu) or not ops:
                continue
            emit(f"       {arm:<10} {c:>3}  {cpu / 1000:>13.1f}  {ops:>8,.0f}  "
                 f"{cpu / ops:>15.1f}  {oltp / 1000:>13.1f}")
    emit("")

    if "im@d1base" not in present:
        emit("   NAPOMENA: ruka im@d1base nije izmjerena, pa se CPU po upitu ne moze")
        emit("   uporediti izmedju stepena paralelizma. Kauzalni racun ostaje")
        emit("   nezatvoren: pokrenite --arm d1base u istoj sesiji kao --arm d2.")
    emit("")


def section_nonmonotonic(df: pd.DataFrame) -> None:
    emit("4. NEMONOTONOST PROPUSNOSTI (omjer 80/20)")
    emit("-" * 74)
    emit(f"   {'konfiguracija':<14} {'C=4':>10} {'C=16':>10} {'C=32':>10}   C16 -> C32")
    for cfg in sorted(df.Configuration.unique()):
        v = [med(df, cfg, "OltpThroughput", c) for c in CONCS]
        if not np.isfinite(v).all():
            continue
        change = (v[2] - v[1]) / v[1] * 100
        trend = f"PAD {change:+.0f} %" if change < 0 else f"rast {change:+.0f} %"
        emit(f"   {cfg:<14} {v[0]:>10,.0f} {v[1]:>10,.0f} {v[2]:>10,.0f}   {trend}")
    emit("")
    emit("   Row-mode ruke kolabiraju pri zasicenju, dok preusmjerena raste.")
    emit("   Dio dobitka pri C=32 je stoga izbjegnut kolaps, a ne cist prirast.")
    emit("")


def section_sample_size(df: pd.DataFrame) -> None:
    emit("5. VELICINA UZORKA PO CELIJI")
    emit("-" * 74)
    n = df[df.OltpOlapRatio == RATIO].groupby(["Configuration", "ConcurrencyLevel"]).size()
    emit(f"   omjer 80/20: min N = {n.min()}, max N = {n.max()}, "
         f"celija s N < 30: {(n < 30).sum()} od {len(n)}")
    below = n[n < 30]
    for (cfg, c), val in below.items():
        emit(f"     {cfg} @ C={c}: N = {val}")
    emit("")
    emit("   Rad treba pisati 'do 30 po celiji' uz raspon, ne '30 po celiji'.")
    emit("")


def section_ratios(df: pd.DataFrame, present: set[str]) -> None:
    emit("6. SMJER EFEKTA KROZ SVE OMJERE OPTERECENJA")
    emit("-" * 74)
    for label, a_cfg, b_cfg in [("nekontrolirano (OFF / IM)", "htap", "im"),
                                ("paralelizam (IM-P / IM)", "im@d2", "im")]:
        if a_cfg not in present or b_cfg not in present:
            emit(f"   {label}: ruka nije izmjerena — preskacem")
            continue
        emit(f"   {label}")
        for r in ["80_20", "50_50", "20_80"]:
            vals = []
            for c in CONCS:
                a, b = med(df, a_cfg, "OltpThroughput", c, r), med(df, b_cfg, "OltpThroughput", c, r)
                vals.append(a / b if b else float("nan"))
            if not np.isfinite(vals).any():
                emit(f"     {r}: nije mjereno")
                continue
            emit(f"     {r}: " + "  ".join(f"{v:.2f}x" for v in vals))
        emit("")
    emit("   Smjer efekta (> 1) treba potvrditi u tekstu i za ostale omjere,")
    emit("   uz napomenu da velicina nije monotona po konkurentnosti.")
    emit("")


def section_aba(df: pd.DataFrame, present: set[str]) -> None:
    """
    ABA raspored: ista postavka izmjerena prije i poslije druge postavke.

    Postoji jer redoslijed ruku nije bio kontrolisan — d1base je isla prva,
    d2 druga. Ako se sistem mijenja kroz sesiju, ta razlika ulazi u rezultat
    isto kao i sama postavka. Ponavljanjem prve ruke na kraju dobija se mjera
    tog pomaka: ako se dva mjerenja iste postavke poklapaju, vremena nema i
    usporedba vrijedi; ako se razlikuju, razlika je velicina koju treba oduzeti.
    """
    emit("8. ABA — pomak kroz sesiju")
    emit("-" * 74)

    if "im@d1base2" not in present:
        emit("   Ponovljena ruka im@d1base2 nije izmjerena.")
        emit("   Bez nje se efekt postavke ne moze odvojiti od pomaka kroz sesiju,")
        emit("   jer je d1base isla prva a d2 druga. Pokrenite:")
        emit("     dotnet run ... -- --arm d1base2 --only IM\n")
        return

    emit("   Ista postavka (MAXDOP 1), izmjerena prije i poslije ruke d2.")
    emit("")
    emit(f"   {'C':>3}  {'prvi put':>10}  {'zadnji put':>12}  {'pomak':>8}  "
         f"{'d2 izmedju':>12}")
    for c in CONCS:
        a = med(df, "im@d1base", "OltpThroughput", c)
        b = med(df, "im@d1base2", "OltpThroughput", c)
        d2 = med(df, "im@d2", "OltpThroughput", c)
        if not (np.isfinite(a) and np.isfinite(b)):
            continue
        emit(f"   {c:>3}  {a:>10,.0f}  {b:>12,.0f}  {b / a:>8.2f}  {d2:>12,.0f}")
    emit("")
    emit("   Pomak blizu 1,00 -> sesija je stabilna, usporedba d1base vs d2 vrijedi.")
    emit("   Pomak znatno razlicit od 1,00 -> redoslijed nosi dio razlike i")
    emit("   zakljucak o MAXDOP-u se ne moze donijeti bez korekcije.")
    emit("")


def section_drift(df: pd.DataFrame) -> None:
    """
    Raste li propusnost kroz seriju ponavljanja unutar iste celije.

    Trideset runova u celiji tretiraju se kao nezavisni uzorci — to pretpostavlja
    i Mann-Whitney. Ako propusnost sistematski raste s rednim brojem runa, uzorci
    nisu razmjenjivi: medijan tada ovisi o tome koliko je serija dugacka, a ne
    samo o konfiguraciji. Mjeri se Spearmanovom korelacijom izmedju rednog broja
    runa i propusnosti, unutar svake celije zasebno.
    """
    emit("7. DRIFT UNUTAR SERIJE PONAVLJANJA")
    emit("-" * 74)
    emit("   rho = korelacija rednog broja runa i propusnosti unutar celije.")
    emit("   Blizu nule: runovi su razmjenjivi. Blizu +1: sistem se jos zagrijava.")
    emit("")
    emit(f"   {'konfiguracija':<14} {'C':>3}  {'rho':>7}  {'p':>10}  "
         f"{'prvih 5':>10}  {'zadnjih 5':>11}  {'omjer':>7}")

    flagged = 0
    for cfg in sorted(df.Configuration.unique()):
        for c in CONCS:
            sel = ((df.Configuration == cfg) & (df.ConcurrencyLevel == c)
                   & (df.OltpOlapRatio == RATIO))
            sub = df.loc[sel, ["RunNumber", "OltpThroughput"]].dropna()
            if len(sub) < 10:
                continue
            sub = sub.sort_values("RunNumber")
            rho, p = stats.spearmanr(sub.RunNumber, sub.OltpThroughput)
            first = sub.OltpThroughput.head(5).median()
            last = sub.OltpThroughput.tail(5).median()
            ratio = last / first if first else float("nan")
            mark = " <-" if (p < 0.05 and abs(rho) > 0.5) else ""
            if mark:
                flagged += 1
            emit(f"   {cfg:<14} {c:>3}  {rho:>+7.3f}  {p:>10.2e}  "
                 f"{first:>10,.0f}  {last:>11,.0f}  {ratio:>7.2f}{mark}")

    emit("")
    if flagged:
        emit(f"   {flagged} celija pokazuje jak drift (|rho| > 0,5 uz p < 0,05).")
        emit("   Tamo medijan mjeri i duzinu serije, ne samo konfiguraciju, pa")
        emit("   usporedbe treba ograniciti na jednak broj runova po ruci.")
    else:
        emit("   Nijedna celija ne pokazuje jak drift — runovi su razmjenjivi.")
    emit("")


def main() -> None:
    if not (RESULTS / "summary.csv").exists():
        raise SystemExit(f"Nedostaje {RESULTS / 'summary.csv'}.")

    df = load()
    present = set(df.Configuration.unique())

    emit("=" * 74)
    emit("ODGOVORI NA PRIMJEDBE — izracunato iz sirovih mjerenja")
    emit("=" * 74)
    emit(f"konfiguracije u podacima: {', '.join(sorted(present))}")
    emit("")

    section_effect_size(df, present)
    section_cxsync(df, present)
    section_causal(df, present)
    section_nonmonotonic(df)
    section_sample_size(df)
    section_ratios(df, present)
    section_drift(df)
    section_aba(df, present)

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Izvjestaj: {OUT}")


if __name__ == "__main__":
    main()
