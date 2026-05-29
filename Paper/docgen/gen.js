"use strict";
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, TableOfContents
} = require("docx");
const fs = require("fs");

const FONT    = "Calibri";          // Office theme minor font (body)
const FONT_H  = "Calibri Light";    // Office theme major font (headings)
const SZ = 22;                      // 11pt body (standard Office)
const A4W = 11906;
const A4H = 16838;
const MAR = 1418;                   // 2.5 cm
const CW  = A4W - 2*MAR;           // 9070 DXA content width
const LS  = { line: 360, lineRule: "auto" };  // 1.5 line spacing
const AF  = 160;                    // after spacing
// Office theme colors
const C_H1   = "44546A";           // Dark2 — heading color
const C_H2   = "2E74B5";           // Accent5 darker
const C_ACC  = "5B9BD5";           // Accent1 blue
const C_TBH  = "BDD7EE";           // light blue table header

// ── inline text parser ────────────────────────────────────────────────────────
function runs(text, xtra = {}) {
  if (!text) return [new TextRun({ text: "", font: FONT, size: SZ })];
  const out = [];
  let s = text;
  while (s.length) {
    const bi = s.match(/^\*\*\*(.+?)\*\*\*/);
    const b  = s.match(/^\*\*(.+?)\*\*/);
    const i  = s.match(/^\*(.+?)\*/);
    const c  = s.match(/^`([^`]+)`/);
    if (bi) { out.push(new TextRun({ text: bi[1], bold: true, italics: true, font: FONT, size: SZ, ...xtra })); s = s.slice(bi[0].length); }
    else if (b) { out.push(new TextRun({ text: b[1], bold: true, font: FONT, size: SZ, ...xtra })); s = s.slice(b[0].length); }
    else if (i) { out.push(new TextRun({ text: i[1], italics: true, font: FONT, size: SZ, ...xtra })); s = s.slice(i[0].length); }
    else if (c) { out.push(new TextRun({ text: c[1], font: "Courier New", size: 20, ...xtra })); s = s.slice(c[0].length); }
    else {
      const nx = s.search(/\*\*\*|\*\*|\*|`/);
      if (nx === -1) { out.push(new TextRun({ text: s, font: FONT, size: SZ, ...xtra })); s = ""; }
      else {
        if (nx > 0) out.push(new TextRun({ text: s.slice(0, nx), font: FONT, size: SZ, ...xtra }));
        s = s.slice(nx);
        // skip unmatched opener
        const skip = s.match(/^(\*{1,3}|`)/);
        if (skip && !s.slice(skip[1].length).includes(skip[1])) {
          out.push(new TextRun({ text: skip[1], font: FONT, size: SZ, ...xtra }));
          s = s.slice(skip[1].length);
        }
      }
    }
  }
  return out;
}

// ── helpers ───────────────────────────────────────────────────────────────────
const sp = (extra = {}) => ({ line: 360, lineRule: "auto", after: AF, ...extra });

function P(text, props = {}) {
  return new Paragraph({ children: runs(text), spacing: sp(), ...props });
}
function PR(runArr, props = {}) {
  return new Paragraph({ children: runArr, spacing: sp(), ...props });
}
function H1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, font: FONT_H, size: 36, bold: false, color: C_H1 })],
    spacing: { line: 360, lineRule: "auto", before: 480, after: 240 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C_ACC, space: 4 } },
  });
}
function H2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, font: FONT_H, size: 28, bold: false, color: C_H2 })],
    spacing: { line: 360, lineRule: "auto", before: 320, after: 160 },
  });
}
function H3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text, font: FONT_H, size: 24, bold: false, color: C_H1, italics: true })],
    spacing: { line: 360, lineRule: "auto", before: 240, after: 120 },
  });
}
function H4(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_4,
    children: [new TextRun({ text, font: FONT, size: 22, bold: true, color: C_H1 })],
    spacing: { line: 360, lineRule: "auto", before: 200, after: 100 },
  });
}
function PB() { return new Paragraph({ children: [new PageBreak()] }); }
function HR() {
  return new Paragraph({
    children: [],
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "BBBBBB", space: 1 } },
    spacing: { before: 160, after: 160 },
  });
}
function BQ(text) {
  return new Paragraph({
    children: runs(text),
    spacing: sp(),
    indent: { left: 720 },
    border: { left: { style: BorderStyle.SINGLE, size: 6, color: "AAAAAA", space: 8 } },
  });
}
function BULLET(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: runs(text),
    spacing: { line: 360, lineRule: "auto", after: 80 },
  });
}
function CODELINE(text) {
  return new Paragraph({
    children: [new TextRun({ text, font: "Courier New", size: 18 })],
    spacing: { line: 280, lineRule: "auto", after: 40 },
    indent: { left: 720 },
    shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
  });
}

// ── table helpers ─────────────────────────────────────────────────────────────
const TB  = { style: BorderStyle.SINGLE, size: 4, color: "AAAAAA" };
const TBS = { top: TB, bottom: TB, left: TB, right: TB };
const CM  = { top: 60, bottom: 60, left: 100, right: 100 };

function TC(text, isHeader = false, width = 2000, sz = 20) {
  return new TableCell({
    children: [new Paragraph({
      children: runs(text).map(r => {
        r._data = r._data || {};
        return new TextRun({
          text: r._data?.options?.text || (r.constructor.name === "TextRun" ? r["_data"]?.options?.text || text.replace(/\*\*/g,"") : ""),
          font: r._data?.options?.font || FONT,
          size: sz,
          bold: isHeader || (r._data?.options?.bold ?? false),
        });
      }),
      spacing: { line: 280, lineRule: "auto" },
      alignment: AlignmentType.LEFT,
    })],
    width: { size: width, type: WidthType.DXA },
    shading: isHeader ? { fill: C_TBH, type: ShadingType.CLEAR } : undefined,
    margins: CM,
    borders: TBS,
    verticalAlign: VerticalAlign.CENTER,
  });
}

// Simpler cell - avoids TextRun introspection issues
function cell(text, isHeader = false, width = 2000, sz = 20) {
  const stripped = text.replace(/\*\*/g, "").replace(/\*/g, "");
  const isBold = isHeader || text.startsWith("**") || text.includes("**");
  return new TableCell({
    children: [new Paragraph({
      children: [new TextRun({ text: stripped, font: FONT, size: sz, bold: isBold })],
      spacing: { line: 280, lineRule: "auto" },
    })],
    width: { size: width, type: WidthType.DXA },
    shading: isHeader ? { fill: C_TBH, type: ShadingType.CLEAR } : undefined,
    margins: CM,
    borders: TBS,
    verticalAlign: VerticalAlign.CENTER,
  });
}

function makeTable(headers, rows, colWidths) {
  const total = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({ children: headers.map((h, i) => cell(h, true, colWidths[i])) }),
      ...rows.map(row => new TableRow({
        children: row.map((c, i) => cell(c, false, colWidths[i])),
      })),
    ],
  });
}

// ── caption ───────────────────────────────────────────────────────────────────
function caption(text) {
  return new Paragraph({
    children: [new TextRun({ text, font: FONT, size: 22, bold: true })],
    spacing: { line: 320, lineRule: "auto", before: 160, after: 80 },
  });
}

// ── CONTENT ───────────────────────────────────────────────────────────────────

const titlePage = [
  // University
  new Paragraph({
    children: [new TextRun({ text: "POLITEHNIČKI FAKULTET", font: FONT, size: 28, bold: true, allCaps: true })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 120 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "Sveučilište u Zenici", font: FONT, size: 24, bold: true })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 960 },
  }),
  // Title
  new Paragraph({
    children: [new TextRun({ text: "EVALUACIJA PERFORMANSI HIBRIDNE TRANSAKCIJSKO-ANALITIČKE OBRADE (HTAP) U MICROSOFT SQL SERVERU", font: FONT, size: 32, bold: true })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 240 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "Komparativna analiza četiri konfiguracijske strategije pohrane nad skupom podataka StackOverflow2010", font: FONT, size: 24, italics: true })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 320 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "Projektni zadatak iz predmeta Optimizacija baza podataka", font: FONT, size: 24 })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 960 },
  }),
  // Info table
  new Table({
    width: { size: 6000, type: WidthType.DXA },
    columnWidths: [2400, 3600],
    rows: [
      ["Student:", "Nejra Smajlović"],
      ["Predmet:", "Optimizacija baza podataka"],
      ["Profesor:", "V. prof. dr. Denis Čeke"],
      ["Datum predaje:", "Maj 2026."],
    ].map(([label, val]) =>
      new TableRow({
        children: [
          new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: label, font: FONT, size: 24, bold: true })], spacing: { after: 60 } })], margins: CM, borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } } }),
          new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: val, font: FONT, size: 24 })], spacing: { after: 60 } })], margins: CM, borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } } }),
        ],
      })
    ),
  }),
  new Paragraph({ children: [], spacing: { after: 960 } }),
  new Paragraph({
    children: [new TextRun({ text: "Zenica, 2026.", font: FONT, size: 24, italics: true })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 0 },
  }),
  PB(),
];

// ── ABSTRACT ──────────────────────────────────────────────────────────────────
const abstractSection = [
  H1("Sažetak"),
  new Paragraph({
    children: [new TextRun({
      text: "Organizacije koje istovremeno zahtijevaju transakcijsku i analitičku obradu podataka tradicionalno se oslanjaju na odvojene OLTP i OLAP sustave premošćene ETL slojem, što uvodi latenciju svježine podataka, operativnu kompleksnost i dodatne infrastrukturne troškove. Paradigma hibridne transakcijsko-analitičke obrade (HTAP) adresira ovaj problem eliminacijom ETL procesa i obradom oba tipa upita unutar istog sustava. Ovaj rad eksperimentalno evaluira i kvantificira četiri konfiguracijske strategije pohrane u Microsoft SQL Serveru 2022: disk-zasnovanu s B-tree indeksima (Baseline), disk-zasnovanu s columnstore indeksom (CS), memorijski optimiziranu bez columnstore (IM) i hibridnu dual-store konfiguraciju (HTAP). Eksperiment je proveden kao 4×3×3 puni faktorijalni dizajn (4 konfiguracije × 3 OLTP/OLAP omjera × 3 razine konkurentnosti), uz 30 mjernih serija po kombinaciji, nad skupom podataka StackOverflow2010 s oko 19,2 milijuna zapisa koji predstavljaju stvarnu produkcijsku distribuciju. Statistička obrada uključuje Kruskal-Wallis H-test, Mann-Whitney U test s Bonferroni korekcijom i Cohenov d za kvantifikaciju veličine efekta. Rezultati pokazuju da HTAP dual-store konfiguracija dominira u svim scenarijima opterećenja — ostvaruje 3,3 do 6,9 puta veću OLTP propusnost od IM konfiguracije i 8,0 puta veću OLAP propusnost od Baseline konfiguracije, uz najniže OLAP latencije (P50 = 924 ms pri omjeru 80/20).",
      font: FONT, size: SZ
    })],
    spacing: sp(),
    indent: { left: 360, right: 360 },
    shading: { fill: "F0F4F8", type: ShadingType.CLEAR },
    border: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "AAAACC", space: 4 },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "AAAACC", space: 4 },
      left: { style: BorderStyle.SINGLE, size: 4, color: "AAAACC", space: 8 },
      right: { style: BorderStyle.SINGLE, size: 4, color: "AAAACC", space: 8 },
    },
  }),
  new Paragraph({ spacing: { after: 120 } }),
  new Paragraph({
    children: [
      new TextRun({ text: "Ključne riječi: ", font: FONT, size: SZ, bold: true }),
      new TextRun({ text: "HTAP, In-Memory OLTP, columnstore indeks, SQL Server 2022, Hekaton, mješovito opterećenje, benchmark, StackOverflow2010, dual-store arhitektura", font: FONT, size: SZ }),
    ],
    spacing: sp(),
  }),
  PB(),
];

// ── CH 1 UVOD ─────────────────────────────────────────────────────────────────
const ch1 = [
  H1("1. Uvod"),
  H2("1.1 Motivacija i kontekst istraživanja"),
  P("Suvremene organizacije suočavaju se s paradoksom operativnih podataka koji je dobro dokumentiran u literaturi [1], [6]: isti podaci koji su predmet intenzivnih transakcijskih operacija u realnom vremenu moraju biti dostupni i za analitičke upite koji zahtijevaju pregled cjelokupne historije. Transakcijska obrada (OLTP) i analitička obrada (OLAP) postavljaju dijametralno suprotne zahtjeve na arhitekturu sustava za upravljanje bazama podataka — OLTP zahtijeva brze točkačne operacije (INSERT, UPDATE, SELECT po primarnom ključu) s niskom latencijom i visokom konkurentnošću, dok OLAP zahtijeva učinkovito skeniranje velikih skupova podataka s agregacijama i složenim spojevima tablica [15]."),
  P("Tradicionalni odgovor na ove suprotstavljene zahtjeve bila je arhitektura dvostrukih sustava: OLTP baza podataka optimizirana za transakcije i OLAP skladište podataka optimizirano za analitiku, premošćeni ETL (Extract-Transform-Load) procesom koji periodično prenosi podatke između dva okruženja [6]. Ova arhitektura, premda dominantna u industrijskoj primjeni, nosi niz nedostataka: (1) latencija svježine podataka — analitički sustav uvijek zaostaje za operativnim za period jednog ETL ciklusa; (2) operativna kompleksnost — dvije odvojene infrastrukture zahtijevaju odvojeno administriranje; (3) troškovi — dupliciranje licence, hardvera i radnih sati; (4) arhitekturalna krhkost — promjena sheme zahtijeva sinkroniziranu promjenu u ETL transformacijama."),
  P("Paradigma hibridne transakcijsko-analitičke obrade (HTAP) adresira ove probleme eliminacijom ETL sloja i obradom transakcijskih i analitičkih upita unutar istog sustava, nad istim ili minimalno zakašnjelim podacima [1]. Microsoft SQL Server 2022, kao jedan od vodećih komercijalnih sustava za upravljanje relacijskim bazama podataka, nudi više mehanizama koji se mogu konfigurirati za podršku HTAP scenarija, čime postaje relevantna platforma za istraživanje performansnih kompromisa ove paradigme."),

  H2("1.2 Problem istraživanja i doprinos"),
  P("Microsoft SQL Server 2022 nudi tri relevantna mehanizma koji mogu poslužiti kao osnova HTAP arhitekture: (1) *In-Memory OLTP (Hekaton)* — memorijsko-optimizirane tablice s optimističkim upravljanjem konkurentnošću za ubrzanje transakcija [13]; (2) *Columnstore indeksi* — stupčasta pohrana s batch-mode izvršavanjem za ubrzanje analitičkih upita [14]; (3) *kombinacija* oba mehanizma u tzv. dual-store pristupu, gdje memorijsko-optimizirane tablice prihvaćaju OLTP pisanja, a columnstore replike služe analitičkim čitanjima."),
  P("Ključna motivacija za ovaj rad je nedostatak empirijskih istraživanja nad *stvarnim* skupovima podataka s realnom distribucijom korisničke aktivnosti. Kako ističu autori u [1] i [9], većina benchmarking studija koristi sintetičke skupove podataka (TPC-C, TPC-H) koji ne odražavaju distribucije stvarnih aplikacija. Doprinos ovog rada trostran je: (1) empirijska komparacija četiri konfiguracijske strategije SQL Servera nad stvarnim skupom podataka uz statistički rigoroznu metodologiju; (2) kvantifikacija degradacije OLTP propusnosti pri mješovitom opterećenju; (3) praktične smjernice za odabir konfiguracijske strategije."),

  H2("1.3 Istraživačke hipoteze"),
  P("Na temelju pregleda literature [1], [2], [3] i teorijskog razmatranja karakteristika ispitivanih konfiguracija, formulirane su tri istraživačke hipoteze:"),
  P("**H1:** Disk-zasnovana konfiguracija s columnstore indeksom (CS) ostvaruje usporedivu latenciju analitičkih upita s hibridnom konfiguracijom (HTAP) pri niskim razinama konkurentnosti (C=4), dok razlika postaje statistički značajna pri visokim razinama (C=32)."),
  P("*Obrazloženje:* Pri niskom broju istovremenih korisnika, batch-mode executor columnstore konfiguracije teorijski može iskoristiti sve raspoložive CPU threadove, čime razlika između CS i HTAP pristupa može biti zanemariva."),
  P("**H2:** Degradacija propusnosti transakcijskih operacija uzrokovana istovremenim izvođenjem analitičkih upita veća je u CS konfiguraciji nego u HTAP konfiguraciji."),
  P("*Obrazloženje:* U CS konfiguraciji, analitički batch-mode scans dijele CPU i memorijski podsustav s OLTP operacijama na istim fizičkim tablicama. U HTAP dual-store arhitekturi, analitički upiti čitaju iz odvojenih columnstore tablica (cs.*), dok OLTP operacije ostaju na memorijsko-optimiziranim tablicama (htap.*)."),
  P("**H3:** Pri transakcijski intenzivnom opterećenju (omjer 80% OLTP / 20% OLAP) hibridna konfiguracija (HTAP) ne ostvaruje statistički značajno veću OLTP propusnost od čisto transakcijske konfiguracije s memorijsko-optimiziranim tablicama (IM)."),
  P("*Obrazloženje:* HTAP OLTP operacije usmjeravaju se na iste memorijsko-optimizirane tablice kao i IM konfiguracija, koristeći identične nativno kompajlirane procedure."),

  H2("1.4 Struktura rada"),
  P("Rad je organiziran prema IMRaD strukturi preporučenoj za empirijska istraživačka rada [15]. Poglavlje 2 daje pregled relevantne literature i identificira istraživačku prazninu. Poglavlje 3 opisuje metodologiju, eksperimentalni dizajn, konfiguracijske strategije i statističke metode. Poglavlje 4 opisuje eksperimentalno okruženje, skup podataka i tehničke detalje implementacije. Poglavlje 5 prezentira rezultate deskriptivne i inferencijalne statistike uz provjeru hipoteza. Poglavlje 6 diskutira nalaze u kontekstu hipoteza, arhitekturalne teorije i dosadašnje literature te daje praktične preporuke. Poglavlje 7 zaključuje rad i predlaže smjernice za buduća istraživanja."),
  PB(),
];

// ── CH 2 LITERATURA ───────────────────────────────────────────────────────────
const ch2 = [
  H1("2. Pregled dosadašnjih istraživanja"),
  H2("2.1 HTAP paradigma — definicija i arhitekturalne strategije"),
  P("Pojam \"hibridna transakcijsko-analitička obrada\" (HTAP) popularizirali su Gartner analitičari 2014. godine, a sistematizirani teorijski okvir za razumijevanje i klasifikaciju HTAP sustava pruža sveobuhvatni pregled Zhang et al. [1] iz 2024. godine. Prema toj klasifikaciji, HTAP sustavi mogu se podijeliti prema tri primarne arhitekturalne strategije: (1) *single-engine* pristup, gdje jedan motor baze podataka podjednako efikasno obrađuje oba tipa opterećenja; (2) *dual-engine* pristup, gdje se podaci repliciraju između OLTP i OLAP motora unutar iste platforme; (3) *in-place* pristup, gdje se isti fizički zapis indeksira na dva načina — redno za OLTP i stupčasto za OLAP."),
  P("Svaki od navedenih pristupa ima karakteristična performansna obilježja i kompromise. Single-engine pristup, koji zastupaju sustavi kao što su SAP HANA i HyPer, eliminirani su troškovi replikacije i konzistentnosnih protokola. Dual-engine pristup, koji zastupaju TiDB [11] i Google F1 Lightning [12], postiže bolju performansnu izolaciju korištenjem fizički odvojenih motora, ali uvodi latenciju replikacije i dodatnu mrežnu komunikaciju između komponenti. In-place pristup, koji zastupa Oracle Dual Format i SQL Server-ov dual-store, postiže kompromis između ova dva ekstrema."),
  P("Pregled Song et al. [6] dodatno naglašava da je ključni izazov svakog HTAP sustava *performansna izolacija* — sposobnost sustava da garantira OLTP performanse neovisno o analitičkom opterećenju. Prema istim autorima, degradacija OLTP propusnosti za više od 30% pod analitičkim opterećenjem smatra se neprihvatljivom u produkcijskim scenarijima."),

  H2("2.2 Komercijalne HTAP implementacije"),
  P("**SAP HANA** je pionirski HTAP sustav koji je popularizirao pristup pohrane podataka isključivo u memoriji, kombinirajući red-store i column-store unutar jednog motora [15]. SAP HANA koristi MVCC za izolaciju transakcija i verzioniranje podataka, pri čemu analitički upiti čitaju konzistentnu snimku podataka bez blokiranja transakcijskog procesiranja."),
  P("**TiDB** [11] implementira dual-engine pristup koristeći TiKV (row-store za OLTP) i TiFlash (column-store za OLAP) komponente spojene Raft konsenzus protokolom za replikaciju. Asinkrona replikacija uvodi konfigurabilno kašnjenje konzistentnosti (tipično ispod sekunde). TiDB-ov pristup direktno je inspirirao dual-store arhitekturu ispitivanu u ovom radu."),
  P("**Google F1 Lightning** [12] pruža HTAP kao servis za Google-ove interne aplikacije, koristeći Delta-Store arhitekturu gdje se svježi podaci čuvaju u row formatu, a kompaktiraju se u column format u pozadini."),
  P("**Microsoft SQL Server 2022** implementira in-process dual-store pristup koji eliminira mrežnu komunikaciju između komponenti. Za razliku od TiDB-a koji koristi fizički odvojene procese, SQL Server-ov Hekaton engine i columnstore indeksi dijele isti procesni prostor, što eliminira latenciju replikacije, ali zahtijeva pažljivije upravljanje izolacijom opterećenja."),

  H2("2.3 In-Memory OLTP (Hekaton) u SQL Serveru"),
  P("Hekaton engine, detaljno opisan u izvornom radu Diaconu et al. [13] iz 2013. godine, temelji se na tri ključne arhitekturalne inovacije: (1) optimistično upravljanje konkurentnošću bez brava (latch-free) zasnovano na MVCC, što eliminira bottleneck globalnog zaključavanja; (2) memorijsko-optimizirane strukture podataka s hash i range indeksima koji ne zahtijevaju straničenje predmemorije (buffer pool); (3) nativno kompajlirane pohranjene procedure koje se prevode u strojni kod pri kreiranju."),
  P("Navedene karakteristike čine Hekaton idealnim za točkačne OLTP operacije visoke konkurentnosti — izvorni rad [13] izvještava o ubrzanjima od 5 do 70 puta za točkačne OLTP upite. Međutim, Hekaton je suboptimalan za analitičke upite koji zahtijevaju sekvencijalno skeniranje jer hash indeksi nisu optimizirani za raspone i ne podržava batch-mode izvršavanje. Važno ograničenje relevantno za ovaj rad jest da SQL Server 2022 RTM ne podržava NONCLUSTERED COLUMNSTORE indeks na memorijsko-optimiziranim tablicama."),

  H2("2.4 Columnstore indeksi i batch-mode izvršavanje"),
  P("Columnstore indeksi, opisani u radu Larson et al. [14], pohranjuju podatke stupčasto — sve vrijednosti jednog stupca pohranjuju se zajedno u kompresiranim segmentima. Kompresija unutar jednog stupca tipično postiže faktor 5 do 10 puta, što drastično smanjuje I/O pri skeniranju. Ključna prednost, međutim, nije sama kompresija, već *batch-mode executor* koji omogućuje obradu 900 ili više redova istovremeno koristeći SIMD CPU instrukcije [14]. Za agregacijske upite nad milijunima redova, batch-mode procesiranje postiže ubrzanja od 10 do 100 puta."),
  P("Relevantno ograničenje columnstore indeksa za ovaj rad jest ponašanje pri visokim razinama konkurentnosti s više istovremenih batch-mode upita. Pri C=32, saturacija CPU threadova adresirana je dodavanjem OPTION(MAXDOP 2) u sve analitičke procedure."),

  H2("2.5 HTAP benchmarking — metode i alati"),
  P("Evaluacija HTAP sustava metodološki je zahtjevnija od evaluacije čistih OLTP ili OLAP sustava. HyBench [2] je benchmark dizajniran specifično za HTAP sustave koji uz TPC-C transakcije uključuje analitičke upite relevantne za financijske primjene. Ključna metodološka studija Zhao et al. [9] naglašava da je *performansna izolacija* najvažnija mjera kvalitete HTAP implementacije, ispred peak propusnosti. Autori predlažu mjeru degradacije kao primarnu metriku, što je direktno implementirano u metodologiji provjere hipoteze H2."),
  P("Novija istraživanja proširuju benchmarking na specijalizirane hardverske arhitekture. PUSHtap [4] istražuje PIM (Processing-In-Memory) pristup, SynchroStore [10] predlaže cost-based kompakciju za hibridna opterećenja, dok veDB-HTAP [7] opisuje integriranu arhitekturu visokih performansi. Zajednički nalaz ovih radova je da ne postoji univerzalno superiorna strategija."),

  H2("2.6 Identifikacija istraživačke praznine"),
  P("Pregledom dostupne literature identificirane su sljedeće praznine koje ovaj rad adresira. Prvo, postojeće benchmarking studije [2], [3], [9] pretežno koriste sintetičke skupove podataka (TPC-C, TPC-H) koji ne odražavaju asimetriju stvarnih aplikacija. Drugo, evaluacije SQL Server-ovih specifičnih mehanizama (Hekaton + columnstore kombinacija) u kontekstu HTAP opterećenja su rijetke u akademskoj literaturi. Treće, studije koje istovremeno evaluiraju sve tri razine konkurentnosti i tri omjera opterećenja uz statistički rigoroznu obradu rezultata nedostaju u pregledanoj literaturi."),
  PB(),
];

// ── CH 3 METODOLOGIJA ─────────────────────────────────────────────────────────
const ch3 = [
  H1("3. Metodologija istraživanja"),
  H2("3.1 Eksperimentalni dizajn"),
  P("Istraživanje je provedeno kao **4×3×3 puni faktorijalni dizajn** s 30 ponavljanja po kombinaciji, što predstavlja standardni pristup za benchmarking studije koje zahtijevaju statistički rigorozne usporedbe između više razina više faktora. Ukupan broj planiranih mjernih serija iznosi:"),
  CODELINE("4 konfiguracije × 3 OLTP/OLAP omjera × 3 razine konkurentnosti × 30 runova = 1.080 mjernih serija"),
  new Paragraph({ spacing: { after: 80 } }),
  P("Puni faktorijalni dizajn odabran je jer omogućava procjenu interakcijskih efekata između faktora — posebno interakcije između konfiguracije i razine konkurentnosti. Broj ponavljanja od 30 po kombinaciji osigurava dovoljnu statističku snagu za neparametarske testove čak i kada su distribucije izrazito asimetrične [2]."),
  P("**Nezavisne varijable (faktori eksperimenta):**"),
  BULLET("Konfiguracija pohrane: {Baseline, CS, IM, HTAP}"),
  BULLET("OLTP/OLAP omjer radnog opterećenja: {80/20, 50/50, 20/80}"),
  BULLET("Razina konkurentnosti (broj paralelnih radnih threadova): {C=4, C=16, C=32}"),
  P("**Zavisne varijable (mjerne metrike):**"),
  BULLET("OLTP propusnost: broj transakcija po sekundi (ops/s)"),
  BULLET("OLAP propusnost: broj analitičkih upita po sekundi (q/s)"),
  BULLET("OLTP latencija: P50, P95, P99 percentili (ms)"),
  BULLET("OLAP latencija: P50, P95, P99 percentili (ms)"),
  BULLET("Stopa uspješnosti operacija (%)"),
  P("**Kontrolirane varijable:** identična hardverska konfiguracija, identičan broj redova u svim shemama, trajanje warmup faze 10 sekundi, trajanje mjerne faze 60 sekundi po runu."),

  H2("3.2 Konfiguracijske strategije"),
  H3("Baseline — disk-zasnovane tablice s B-tree indeksima"),
  P("Standardna SQL Server konfiguracija s row-store tablicama pohranjenima na disku predstavlja *kontrolnu grupu* eksperimenta. Svaka tablica ima clustered B-tree indeks na primarnom ključu i odabrane nonclustered indekse na stranim ključevima. OLTP i OLAP operacije koriste row-mode executor bez prednosti batch-mode obrade."),

  H3("CS — disk-zasnovane tablice s nonclustered columnstore indeksom"),
  P("CS konfiguracija je identična fizička shema kao Baseline, s dodatkom NONCLUSTERED COLUMNSTORE indeksa na svakoj tablici koji pokriva sve stupce. Za analitičke upite, SQL Server automatski odabire columnstore skeniranje i batch-mode execution plan, što teorijski donosi ubrzanje od 10 do 100 puta za agregacijske upite [14]. Problem saturacije CPU threadova pri C=32 riješen je dodavanjem OPTION(MAXDOP 2) u sve analitičke procedure."),

  H3("IM — memorijsko-optimizirane tablice (Hekaton)"),
  P("Sve tablice u IM konfiguraciji su memorijsko-optimizirane (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY). Hash indeksi primijenjeni su za točkačne OLTP operacije, a nonclustered range indeksi za upite rasponskog tipa. Sve OLTP pohranjene procedure nativno su kompajlirane (NATIVE_COMPILATION). Analitički upiti rade u row-mode jer Hekaton ne podržava batch-mode izvršavanje."),

  H3("HTAP — dual-store hibridna konfiguracija"),
  P("HTAP implementacija slijedi dual-store arhitekturalni obrazac srodan TiDB/TiFlash pristupu [11]: OLTP pisanja i točkačna čitanja usmjeravaju se na memorijsko-optimizirane tablice (htap.*), dok analitički upiti čitaju iz columnstore tablica (cs.*). Ovo odvajanje osigurava da analitički batch-mode scans ne ometaju OLTP operacije na memorijskim tablicama. Implementacijsko ograničenje jest konzistentnosna razlika između htap.* i cs.* tablica — analitika ne vidi upravo unesene OLTP zapise dok se ne sinkroniziraju s cs.* kopijom."),

  H2("3.3 Radna opterećenja"),
  H3("OLTP radni tok"),
  P("Šest OLTP operacija odabire se nasumično s fiksnom distribucijom koja odražava tipično opterećenje web aplikacije, kombinirajući čitanja (65%) i pisanja (35%):"),
  new Paragraph({ spacing: { after: 120 } }),
  makeTable(
    ["Procedura", "Tip", "Udio"],
    [
      ["usp_GetPostById", "SELECT točkačno", "~25%"],
      ["usp_GetUserById", "SELECT točkačno", "~20%"],
      ["usp_GetRecentUserPosts", "SELECT rasponski", "~20%"],
      ["usp_InsertVote", "INSERT", "~15%"],
      ["usp_InsertComment", "INSERT", "~10%"],
      ["usp_UpdatePostScore", "UPDATE", "~10%"],
    ],
    [3500, 3000, 2570]
  ),
  new Paragraph({ spacing: { after: 160 } }),

  H3("OLAP radni tok"),
  P("Pet analitičkih upita odabire se nasumično. Svi upiti su agregacijske prirode bez parametara koji bi ograničili skenirani skup (full-scan queries), što je reprezentativno za reportiranje nad cjelokupnom historijom:"),
  new Paragraph({ spacing: { after: 120 } }),
  makeTable(
    ["Upit", "Opis", "Ključne operacije"],
    [
      ["Q1 MonthlyActivity", "Aktivnost po godini, mjesecu i tipu posta", "GROUP BY, COUNT, AVG, SUM"],
      ["Q2 UserEngagement", "Angažiranost korisnika", "JOIN, GROUP BY, agregacija"],
      ["Q3 TagAnalysis", "Popularnost tagova po periodu", "JOIN, SUBSTRING, GROUP BY"],
      ["Q4 TimeToAnswer", "Prosječno vrijeme odgovora na pitanja", "Self-JOIN, DATEDIFF, GROUP BY"],
      ["Q5 TopContributors", "Rangiranje korisnika po utjecaju", "CTE, GROUP BY, ORDER BY"],
    ],
    [2200, 3500, 3370]
  ),
  new Paragraph({ spacing: { after: 160 } }),

  H2("3.4 Mjerno okruženje i implementacija"),
  P("Benchmark aplikacija razvijena je u .NET 8 koristeći async/await model za istovremeno izvršavanje radnih tokova. Arhitektura aplikacije temelji se na sljedećim komponentama:"),
  BULLET("**BenchmarkOrchestrator**: koordinira slijed konfiguracija, omjera i razina konkurentnosti; implementira logiku nastavka od mjesta prekida (resume) čitanjem summary.csv pri pokretanju"),
  BULLET("**WorkloadExecutor**: kreira OLTP i OLAP workere za svaku kombinaciju faktora, koordinira warmup i mjerne faze, upravlja osvježavanjem podataka između mjernih serija"),
  BULLET("**ResultsWriter**: atomarno upisuje mjerenja u CSV datoteke s append načinom rada i provjerom duplih unosa"),
  BULLET("**Dapper** micro-ORM za parametrizirane SQL upite bez refleksivnog overhead-a"),
  P("Svaki run prolazi kroz warmup fazu (10 s) čiji se rezultati odbacuju i mjernu fazu (60 s) čiji se rezultati bilježe. OLTP latencija mjeri se za svaku individualnu operaciju korištenjem Stopwatch.Elapsed, dok se OLAP latencija mjeri za svaki cijeli upit od slanja do primanja prvog paketa rezultata."),

  H2("3.5 Statistička metodologija"),
  H3("Razlog za neparametarsku statistiku"),
  P("Distribucije latencija i propusnosti u benchmarking eksperimentima tipično su desno-asimetrične s izraženim repovima (heavy-tailed distributions). Shapiro-Wilk testom normalnosti potvrđeno je da distribucije statistički značajno odstupaju od normalne (p < 0,001), što opravdava primjenu neparametarskih testova koji ne pretpostavljaju distribuciju podataka."),

  H3("Kruskal-Wallis H-test"),
  P("Kruskal-Wallis H-test, neparametarska alternativa jednosmjernoj ANOVA-i, testira nultu hipotezu da sve četiri konfiguracije dolaze iz iste distribucije. Test se primjenjuje zasebno za svaku kombinaciju mjerne metrike i razine konkurentnosti (6 metrika × 3 razine = 18 nezavisnih testova). Razina značajnosti: α = 0,05."),

  H3("Mann-Whitney U test s Bonferroni korekcijom"),
  P("Za parne usporedbe između konfiguracija koristi se Mann-Whitney U test. Budući da se testira C(4,2) = 6 parova po metrici i razini konkurentnosti, primjenjuje se Bonferroni korekcija: korigirani prag značajnosti iznosi α/6 ≈ 0,0083."),

  H3("Cohen's d — veličina efekta"),
  P("Cohenov *d* kvantificira veličinu efekta kao razliku sredina podijeljenu skupnom standardnom devijacijom. Interpretacija: |d| < 0,2 trivijalan, 0,2–0,5 mali, 0,5–0,8 srednji, > 0,8 veliki efekt. Veličina efekta > 0,8 indicira razliku praktično relevantnu za arhitekturalne odluke."),
  PB(),
];

// ── CH 4 OKRUŽENJE ────────────────────────────────────────────────────────────
const ch4 = [
  H1("4. Eksperimentalno okruženje"),
  H2("4.1 Hardverska i softverska konfiguracija"),
  P("Svi eksperimenti provedeni su na istoj hardverskoj konfiguraciji bez ikakvih izmjena između mjernih sesija, čime je osigurana kontrola hardverskih varijabli:"),
  new Paragraph({ spacing: { after: 120 } }),
  makeTable(
    ["Komponenta", "Specifikacija"],
    [
      ["RAM", "32 GB DDR4"],
      ["Pohrana (baseline, cs)", "HDD"],
      ["Pohrana (im, htap OLTP)", "RAM (memorijsko-optimizirane tablice)"],
      ["Operativni sustav", "Windows 11"],
      ["Baza podataka", "Microsoft SQL Server 2022 Developer Edition (16.x)"],
      [".NET runtime", ".NET 8.0"],
      ["Python", "3.11"],
      ["Mjerna aplikacija", "HTAPBenchmark v1.0 (.NET 8, Dapper 2.x)"],
    ],
    [3500, 5570]
  ),
  new Paragraph({ spacing: { after: 160 } }),
  P("Važna napomena: im.* i htap.* tablice koriste DURABILITY = SCHEMA_ONLY, što znači da podaci ne preživljavaju restart SQL Servera. Ova konfiguracija odabrana je jer SCHEMA_ONLY tablice imaju značajno manji overhead pisanja u transakcijski log, što je relevantno za reprezentativnost OLTP mjerenja."),

  H2("4.2 Skup podataka — StackOverflow2010"),
  P("Skup podataka StackOverflow2010 javno je dostupan dump produkcijske baze podataka platforme Stack Overflow koji obuhvaća sve zapise od osnivanja platforme 2008. do kraja 2010. godine. Ovaj skup podataka odabran je jer odražava stvarnu distribuciju korisničke aktivnosti — asimetričnu Pareto distribuciju gdje mali postotak korisnika generira najveći dio sadržaja [1]."),
  new Paragraph({ spacing: { after: 120 } }),
  makeTable(
    ["Tablica", "Opis", "Broj redova"],
    [
      ["Posts", "Pitanja i odgovori", "3.729.195"],
      ["Users", "Korisnički profili", "299.398"],
      ["Votes", "Glasovi na postovima", "10.143.364"],
      ["Comments", "Komentari na postove", "3.875.183"],
      ["Badges", "Zaslužene bedževe korisnika", "1.102.019"],
      ["**Ukupno po shemi**", "", "**≈ 19.149.159**"],
      ["**Ukupno (4 sheme)**", "", "**≈ 76.596.636**"],
    ],
    [2500, 4500, 2070]
  ),
  new Paragraph({ spacing: { after: 160 } }),

  H2("4.3 Priprema podataka i kontekst učitavanja"),
  P("Prije svake mjerne sesije učitava se *radni kontekst* koji definira skup entiteta s kojima će workers operirati:"),
  BULLET("**20.000 nasumičnih ID-ova postova** iz aktivne sheme (za OLTP operacije koje se odnose na postove)"),
  BULLET("**5.000 nasumičnih ID-ova korisnika** iz aktivne sheme"),
  BULLET("**Maksimalni ID** glasova i komentara (za generiranje novih jedinstvenih ID-ova INSERT operacija)"),
  P("Nasumično uzorkovanje ID-ova (ORDER BY NEWID()) osigurava da benchmark simulira realnu distribuciju pristupa. Za memorijsko-optimizirane tablice (im.* i htap.*), korišten je OPTION(MAXDOP 1) u upitima za učitavanje konteksta kako bi se izbjeglo CXSYNC_PORT čekanje karakteristično za paralelne planove na Hekaton tablicama."),

  H2("4.4 Tehnički izazovi i riješeni problemi"),
  P("Implementacija benchmarka naišla je na nekoliko tehničkih izazova koji su riješeni i dokumentirani jer su relevantni za razumijevanje ograničenja i valjanosti mjerenja."),
  P("**Problem MVCC version chain akumulacije:** Pri C=32 s 30 uzastopnih mjernih serija, brisanje svih ~3,7 milijuna redova tablice Posts između kombinacija generiralo je ~7,4 milijuna GC stavki po brisanju. Rješenje: umjesto brisanja svih redova, između svake mjerne serije briše se i ponovo učitava samo 20.000 aktivnih redova iz radnog konteksta — 185 puta manje GC posla po mjerenju."),
  P("**Problem TRUNCATE TABLE na memorijsko-optimiziranim tablicama:** SQL Server 2022 ne podržava TRUNCATE TABLE naredbu na memorijsko-optimiziranim tablicama (Error 10794). Sve operacije čišćenja tablice zamijenjene su selektivnim DELETE naredbama po ID-u."),
  P("**Problem nastavka od mjesta prekida:** Pri dugotrajnim benchmarkovima, prekid uzrokovan iscrpljenjem RAM-a zahtijevao je pouzdanu logiku nastavka. Implementirano je čitanje summary.csv u konstruktoru orkestratora *prije* otvaranja izlaznih datoteka za pisanje, čime se izbjegava nenamjerno brisanje već prikupljenih rezultata."),
  PB(),
];

// ── CH 5 REZULTATI ────────────────────────────────────────────────────────────
const ch5 = [
  H1("5. Rezultati"),
  P("Od inicijalnih 1.080 planiranih mjernih serija, 10 (0,93%) isključeno je iz analize zbog nestabilnosti mjernog okruženja (stopa uspješnosti OLTP operacija ispod 90%), što rezultira uzorkom od 1.070 validnih mjerenja i 28 do 30 serija po kombinaciji. Udio filtriranih mjerenja unutar je prihvatljivih granica za neparametarsku statističku analizu [2]."),

  H2("5.1 Deskriptivna statistika"),
  P("Vrijednosti u tablicama predstavljaju srednju vrijednost ± standardnu devijaciju agregiranu po svim omjerima opterećenja (Tablice 1 i 2) odnosno po svim razinama konkurentnosti (Tablica 3). Visoka standardna devijacija odražava stvarnu varijabilnost između omjera opterećenja, a ne mjernu nestabilnost."),
  new Paragraph({ spacing: { after: 120 } }),
  caption("Tablica 1. OLTP propusnost (ops/s) — srednja vrijednost ± standardna devijacija"),
  makeTable(
    ["Konfiguracija", "C=4", "C=16", "C=32"],
    [
      ["Baseline",  "1.204 ± 704",   "4.051 ± 3.692",  "2.432 ± 2.375"],
      ["CS",        "1.254 ± 636",   "3.637 ± 3.293",  "2.477 ± 2.210"],
      ["IM",        "2.007 ± 1.258", "4.249 ± 2.923",  "4.726 ± 2.664"],
      ["HTAP",      "6.783 ± 3.557", "18.442 ± 14.867","21.920 ± 17.130"],
    ],
    [2570, 2167, 2167, 2166]
  ),
  new Paragraph({ spacing: { after: 200 } }),
  caption("Tablica 2. OLAP propusnost (q/s) — srednja vrijednost ± standardna devijacija"),
  makeTable(
    ["Konfiguracija", "C=4", "C=16", "C=32"],
    [
      ["Baseline", "0,27 ± 0,14", "0,73 ± 0,24", "0,85 ± 0,20"],
      ["CS",       "0,79 ± 0,39", "2,33 ± 0,70", "2,80 ± 0,43"],
      ["IM",       "2,52 ± 0,71", "3,05 ± 0,54", "3,13 ± 0,55"],
      ["HTAP",     "2,65 ± 1,20", "6,95 ± 2,27", "6,84 ± 1,80"],
    ],
    [2570, 2167, 2167, 2166]
  ),
  new Paragraph({ spacing: { after: 200 } }),
  caption("Tablica 3. OLAP latencija P50 (ms) po omjeru opterećenja — srednja vrijednost ± standardna devijacija"),
  makeTable(
    ["Konfiguracija", "80/20", "50/50", "20/80"],
    [
      ["Baseline", "3.128 ± 605",  "4.927 ± 1.965", "7.351 ± 3.872"],
      ["CS",       "1.665 ± 465",  "2.583 ± 790",   "3.710 ± 1.732"],
      ["IM",       "1.048 ± 549",  "2.035 ± 1.119", "2.281 ± 1.202"],
      ["HTAP",     "924 ± 158",    "1.215 ± 453",   "1.530 ± 688"],
    ],
    [2570, 2167, 2167, 2166]
  ),
  new Paragraph({ spacing: { after: 160 } }),
  P("Iz Tablice 1 vidljivo je da HTAP konfiguracija ostvaruje dramatično veću OLTP propusnost od svih ostalih konfiguracija pri svim razinama konkurentnosti, s posebno izraženom prednošću pri C=32 (21.920 ops/s nasuprot 4.726 za IM i 2.432 za Baseline). Tablica 2 pokazuje da HTAP dostiže 6,84 q/s pri C=32 nasuprot 0,85 za Baseline — poboljšanje od faktora 8,0. Tablica 3 otkriva da HTAP ostvaruje najkraću OLAP latenciju u svim scenarijima omjera opterećenja."),

  H2("5.2 Rezultati statističkih testova"),
  new Paragraph({ spacing: { after: 120 } }),
  caption("Tablica 4. Kruskal-Wallis H-test — globalne razlike između konfiguracija (df = 3 za sve testove)"),
  makeTable(
    ["Metrika", "C=4", "C=16", "C=32"],
    [
      ["OLTP propusnost",     "H=194,44; p<0,001", "H=66,79; p<0,001",  "H=158,01; p<0,001"],
      ["OLAP propusnost",     "H=272,03; p<0,001", "H=303,17; p<0,001", "H=290,16; p<0,001"],
      ["OLTP latencija P50",  "H=302,06; p<0,001", "H=297,82; p<0,001", "H=284,92; p<0,001"],
      ["OLAP latencija P50",  "H=300,91; p<0,001", "H=228,87; p<0,001", "H=182,55; p<0,001"],
    ],
    [2900, 2057, 2057, 2056]
  ),
  new Paragraph({ spacing: { after: 160 } }),
  P("Svi Kruskal-Wallis testovi potvrđuju statistički značajne globalne razlike između konfiguracija za sve metrike i sve razine konkurentnosti (p < 0,001). Ovi rezultati opravdavaju nastavak s parnim Mann-Whitney testovima."),
  new Paragraph({ spacing: { after: 120 } }),
  caption("Tablica 5. Mann-Whitney U test s Bonferroni korekcijom — parne usporedbe za OLAP latenciju P50 pri C=32"),
  makeTable(
    ["Par", "U", "p (Bonf.)", "Cohen's d", "Efekt", "Znač."],
    [
      ["Baseline vs CS",   "6.219", "<0,001", "+1,254", "veliki",  "✓"],
      ["Baseline vs IM",   "6.775", "<0,001", "+1,665", "veliki",  "✓"],
      ["Baseline vs HTAP", "7.620", "<0,001", "+2,086", "veliki",  "✓"],
      ["CS vs IM",         "5.342", "0,001",  "+0,679", "srednji", "✓"],
      ["CS vs HTAP",       "6.613", "<0,001", "+1,614", "veliki",  "✓"],
      ["IM vs HTAP",       "6.449", "<0,001", "+1,564", "veliki",  "✓"],
    ],
    [2400, 900, 1000, 1100, 1200, 470+2000-2000]  // adjust
  ),
  new Paragraph({ spacing: { after: 120 } }),
  P("Napomena: pozitivan predznak Cohenovog d označava da prva konfiguracija ima veću (lošiju) latenciju od druge. Sve parne usporedbe statistički su značajne uz Bonferroni korekciju."),

  H2("5.3 Provjera hipoteza"),
  H3("Hipoteza H1 — CS vs HTAP OLAP latencija pri niskoj i visokoj konkurentnosti"),
  new Paragraph({ spacing: { after: 120 } }),
  caption("Tablica 6. Provjera H1: CS vs HTAP OLAP latencija P50 po razini konkurentnosti"),
  makeTable(
    ["Konk.", "CS P50 (ms)", "HTAP P50 (ms)", "Razlika", "p (Bonf.)", "Cohen's d", "Zaključak"],
    [
      ["C=4",  "1.850", "825",   "−55%", "<0,001", "6,14", "odbačena*"],
      ["C=32", "3.620", "1.813", "−50%", "<0,001", "6,52", "potvrđena"],
    ],
    [900, 1300, 1300, 900, 1050, 1100, 1520]
  ),
  new Paragraph({ spacing: { after: 160 } }),
  P("**Hipoteza H1 je djelomično potvrđena.** Hipoteza pretpostavlja da su CS i HTAP usporedivi pri C=4, što nije potvrđeno: HTAP ostvaruje statistički značajno nižu OLAP latenciju čak i pri niskoj konkurentnosti (d = 6,14, veliki efekt). Prednost HTAP nad CS nije isključivo rezultat zasićenja CPU-a pri visokim C vrijednostima, već temeljne arhitekturalne razlike između in-memory i disk-zasnovane pohrane."),

  H3("Hipoteza H2 — Degradacija OLTP propusnosti CS vs HTAP"),
  new Paragraph({ spacing: { after: 120 } }),
  caption("Tablica 7. Provjera H2: Degradacija OLTP propusnosti pri prijelazu s omjera 80/20 na 50/50"),
  makeTable(
    ["Konfiguracija", "Degradacija (%)", "SD (%)", "p (Bonf.)", "Cohen's d", "Zaključak"],
    [
      ["CS",   "67,4", "2,8", "<0,001", "2,315", "potvrđena"],
      ["HTAP", "55,9", "6,3", "—",      "—",     "—"],
    ],
    [2000, 1600, 900, 1100, 1100, 1370]
  ),
  new Paragraph({ spacing: { after: 160 } }),
  P("**Hipoteza H2 je potvrđena.** CS bilježi degradaciju OLTP propusnosti od 67,4% pri prijelazu s omjera 80/20 na 50/50, dok HTAP bilježi 55,9%. Razlika je statistički značajna (p < 0,001) s velikim efektom (d = 2,315). Dual-store HTAP arhitektura efikasnije izolira OLTP procesiranje od analitičkog opterećenja."),

  H3("Hipoteza H3 — HTAP vs IM OLTP propusnost pri transakcijskom opterećenju"),
  new Paragraph({ spacing: { after: 120 } }),
  caption("Tablica 8. Provjera H3: HTAP vs IM OLTP propusnost pri omjeru 80/20"),
  makeTable(
    ["C", "IM (ops/s)", "HTAP (ops/s)", "Omjer", "p (Bonf.)", "Cohen's d", "Zaključak"],
    [
      ["4",  "3.027",  "10.083", "3,3×", "<0,001", "−4,38",  "odbačena"],
      ["16", "7.726",  "35.914", "4,6×", "<0,001", "−8,29",  "odbačena"],
      ["32", "6.325",  "43.751", "6,9×", "<0,001", "−11,93", "odbačena"],
    ],
    [500, 1300, 1400, 800, 1100, 1100, 1870]
  ),
  new Paragraph({ spacing: { after: 160 } }),
  P("**Hipoteza H3 je odbačena na svim razinama konkurentnosti.** HTAP ostvaruje statistički značajno veću OLTP propusnost od IM konfiguracije pri svim razinama konkurentnosti — 3,3 do 6,9 puta ovisno o konkurentnosti. Veličina efekta raste s konkurentnošću (d = −4,38 pri C=4 → d = −11,93 pri C=32)."),
  PB(),
];

// ── CH 6 DISKUSIJA ────────────────────────────────────────────────────────────
const ch6 = [
  H1("6. Diskusija"),
  H2("6.1 OLTP performanse — memorija nasuprot disku"),
  P("Najuočljiviji nalaz ovog istraživanja jest dramatična prednost memorijsko-optimiziranih konfiguracija (IM i HTAP) u OLTP propusnosti u usporedbi s disk-zasnovanim konfiguracijama. Razlika između HTAP i Baseline pri C=32 iznosi faktor 9,0, što je konzistentno s predviđanjima originalnog Hekaton rada [13]. Rezultati IM konfiguracije (4.726 ops/s pri C=32) znatno su skromniji od HTAP (21.920 ops/s), što nije bilo očekivano s obzirom na to da oba pristupa koriste identičan Hekaton engine i identične nativno kompajlirane procedure za OLTP operacije."),
  P("Moguće objašnjenje ove razlike leži u interakciji između OLAP workera i OLTP workera u IM konfiguraciji. OLAP upiti u IM moraju skenirati sve ~3,7 milijuna redova tablice Posts bez prednosti columnstore organizacije, što znači da OLAP worker troši znatno više CPU resursa po upitu nego u HTAP konfiguraciji. Ova CPU saturacija OLAP-om izravno kompetira s OLTP workerima. HTAP konfiguracija, s odvojenim columnstore tablicama za OLAP, omogućava efikasnije OLAP procesiranje koje troši manje CPU resursa."),

  H2("6.2 OLAP performanse — prednost columnstore arhitekture"),
  P("Rezultati OLAP propusnosti i latencije jasno potvrđuju prednost columnstore pohrane: HTAP (6,84 q/s pri C=32) i CS (2,80 q/s) znatno nadmašuju Baseline (0,85 q/s) i IM (3,13 q/s). Zanimljiv je nalaz da IM konfiguracija (3,13 q/s) nadmašuje CS (2,80 q/s) u OLAP propusnosti pri C=32, unatoč tome što CS ima columnstore indekse. Ovaj naizgled paradoksalan rezultat može se objasniti kontencijom za memorijskim resursima pri C=32: čekanje na dodjelu memorijskog prostora (RESOURCE_SEMAPHORE wait type) može povećati ukupno vrijeme izvršavanja više nego što ga batch-mode skraćuje, što je konzistentno s nalazima Zeng et al. [8]."),

  H2("6.3 Degradacija performansi pri mješovitom opterećenju (H2)"),
  P("Potvrda hipoteze H2 — da CS konfiguracija degradira OLTP propusnost više od HTAP pri mješovitom opterećenju — ima važne praktične implikacije. Razlika (67,4% za CS vs 55,9% za HTAP) u apsolutnim brojevima pri C=32 znači razliku između gubitka 2/3 i 1/2 OLTP kapaciteta sustava, što je kritično u scenarijima s garantiranom razinom usluge."),
  P("Mehanizam koji stoji iza ove razlike konzistentan je s teorijskim razmatranjima: u CS konfiguraciji, analitički batch-mode scans i OLTP operacije dijele iste fizičke tablice i iste interne SQL Server resurse. U HTAP dual-store konfiguraciji, analitički upiti idu na cs.* tablice dok OLTP operacije ostaju na htap.* memorijsko-optimiziranim tablicama koje ne koriste buffer pool uopće."),

  H2("6.4 Utjecaj arhitekture sustava na rezultate"),
  P("Arhitektura ispitivanog sustava ima ključan utjecaj na dobivene rezultate. Sve četiri konfiguracije dijele iste CPU resurse i istu instancu SQL Servera, što znači da performansna izolacija ovisi isključivo o SQL Server-ovim internim mehanizmima raspoređivanja resursa, a ne o fizičkom odvajanju kao kod distribuiranih HTAP sustava poput TiDB-a [11]."),
  P("Jednočvorna arhitektura benchmarka predstavlja i prednost i ograničenje. Prednost: eliminira mrežnu latenciju i varijabilnost, čime se mjere čiste performansne karakteristike svake konfiguracijske strategije. Ograničenje: ne odražava produkcijska distribuirana okruženja u kojima mrežna latencija između komponenti može biti dominantni faktor."),
  P("Disk I/O kao arhitekturalni bottleneck posebno je relevantan za Baseline i CS konfiguracije koje čitaju podatke s HDD-a. Razlika između HDD i RAM brzine pristupa (~100 MB/s nasuprot ~40 GB/s) objašnjava dio prednosti HTAP nad CS pri OLAP upitima. Zamjena HDD-a SSD-om bi vjerojatno smanjila razliku između CS i HTAP, ali ne bi promijenila fundamentalne zaključke."),

  H2("6.5 Usporedba s dosadašnjim istraživanjima"),
  P("Nalazi ovog rada konzistentni su s nalazima dosadašnje literature u nekim aspektima. Zhao et al. [9] zaključuju da je performansna izolacija kritičnija metrika od peak propusnosti, što potvrđuje i potvrda hipoteze H2. Zhang et al. [1] navode da su dual-engine sustavi superiorniji u izolaciji jer koriste fizički odvojene procese, ali plaćaju cijenu mrežne latencije. Wu et al. [3] pronalaze slične obrasce degradacije (50–70%) za disk-zasnovane sustave, što je konzistentno s ovim rezultatima."),
  P("Neočekivani nalaz odbacivanja H3 — da HTAP ostvaruje 3,3 do 6,9 puta veću OLTP propusnost od IM — nije direktno potkrijepljen dosadašnjom literaturom. Jedna hipoteza je da OLAP upiti u IM konfiguraciji sistematski degradiraju OLTP propusnost zbog CPU saturacije, dok HTAP-ov columnstore ubrzava OLAP upite 7–8 puta, oslobađajući CPU kapacitet za OLTP operacije."),

  H2("6.6 Praktične preporuke za arhitekte baza podataka"),
  P("Na temelju empirijskih nalaza, moguće je formulirati konkretne smjernice za odabir konfiguracijske strategije u Microsoft SQL Serveru 2022:"),
  new Paragraph({ spacing: { after: 120 } }),
  makeTable(
    ["Scenario", "Preporučena konfiguracija", "Empirijska osnova"],
    [
      [">80% OLTP, <20% OLAP",       "HTAP", "3,3–6,9× veća OLTP propusnost; OLAP P50 = 924 ms"],
      ["50–80% OLTP, 20–50% OLAP",   "HTAP", "Najniža OLTP degradacija (55,9%) i OLAP latencija"],
      ["<50% OLTP, >50% OLAP",       "HTAP", "OLAP P50 = 1.530 ms vs 3.710 ms za CS"],
      ["Samo OLAP, bez transakcija",  "CS",   "Bez RAM overhead-a; 7× bolja OLAP vs Baseline"],
      ["RAM ograničen ili SQL Express","CS",  "Express ne podržava In-Memory OLTP"],
    ],
    [2400, 1700, 4970]
  ),
  new Paragraph({ spacing: { after: 160 } }),
  P("Ključni nalaz koji mijenja standardne preporuke: HTAP nije optimalan samo za mješovita opterećenja — on dominira i pri transakcijskim scenarijima (80/20), čineći IM konfiguraciju redundantnom osim u slučajevima ekstremnih RAM ograničenja."),

  H2("6.7 Ograničenja istraživanja"),
  P("**Jednočvorna konfiguracija.** Benchmark je proveden na jednoj instanci SQL Servera bez distribuiranih komponenti. Distribuirani HTAP sustavi mogu pokazivati drugačija skalabilna svojstva, a mrežna latencija može promijeniti relativne prednosti konfiguracija."),
  P("**Hardverska konfiguracija.** Testovi su provedeni s HDD pohranjiavnjem za disk-zasnovane tablice. Zamjena HDD-a SSD-om ili NVMe-om bi smanjila prednost memorijsko-optimiziranih tablica za disk I/O-intenzivne upite. Rezultati su stoga konzervativniji za SSD okruženja."),
  P("**Vremenski okvir skupa podataka.** StackOverflow2010 dump iz 2010. godine može imati drugačije distribucije aktivnosti od modernijeg Stack Overflow dumpa."),
  P("**Sintetičko mješovito opterećenje.** OLTP i OLAP workeri simulirani su paralelnim threadovima bez mrežne latencije aplikacijskog sloja. U stvarnim deployment konfiguracijama, mrežna latencija može biti dominantni faktor za kratke OLTP operacije."),
  P("**Konzistentnosna razlika u HTAP konfiguraciji.** Dual-store HTAP pristup ne garantira konzistentnost između htap.* i cs.* tablica u realnom vremenu. U produkcijskim scenarijima koji zahtijevaju analitiku nad upravo unesenim podacima, ova razlika mora biti razmotrena."),
  PB(),
];

// ── CH 7 ZAKLJUČAK ────────────────────────────────────────────────────────────
const ch7 = [
  H1("7. Zaključak"),
  P("Ovaj rad eksperimentalno je evaluirao četiri konfiguracijske strategije pohrane u Microsoft SQL Serveru 2022 kroz 1.080 planiranih mjernih serija (1.070 validnih) nad skupom podataka StackOverflow2010. Korištenjem faktorijalnog dizajna 4×3×3 i rigorozne statističke metodologije pružene su empirijski potkrijepljene osnove za provjeru triju istraživačkih hipoteza."),
  P("**Rezime nalaza po hipotezama:** Hipoteza H1 je djelomično potvrđena — HTAP ostvaruje statistički značajno nižu OLAP latenciju od CS konfiguracije ne samo pri visokoj konkurentnosti (C=32, d = 6,52) već i pri niskoj (C=4, d = 6,14), pri čemu apsolutna razlika raste s konkurentnošću. Hipoteza H2 je potvrđena — CS konfiguracija degradira OLTP propusnost pri mješovitom opterećenju za 67,4% nasuprot 55,9% za HTAP (p < 0,001, d = 2,315). Hipoteza H3 je odbačena — HTAP ostvaruje 3,3 do 6,9 puta veću OLTP propusnost od IM konfiguracije pri OLTP-intenzivnom opterećenju."),
  P("**Primarni doprinos** ovog rada jest praktična validacija HTAP paradigme u SQL Server kontekstu nad stvarnim skupom podataka s realnom distribucijom korisničke aktivnosti. Rezultati pružaju konkretne, kvantificirane smjernice arhitektima baza podataka: HTAP dual-store konfiguracija superiorna je u svim ispitanim scenarijima opterećenja, čineći je preporučenim izborom za organizacije koje koriste Microsoft SQL Server 2022 Developer ili Enterprise Edition i mogu si priuštiti potrebnih ~8–12 GB RAM-a."),
  P("**Implikacije za praksu** su značajne: organizacije koje koriste IM konfiguraciju trebaju razmotriti migraciju na HTAP dual-store pristup koji osigurava 3–7 puta bolje OLTP performanse. Organizacije koje koriste CS konfiguraciju trebaju biti svjesne da mješovito opterećenje uzrokuje degradaciju OLTP propusnosti od dvije trećine."),
  P("**Buduća istraživanja** mogu proširiti ovaj rad: (1) evaluacija na distribuiranim HTAP sustavima (TiDB, SingleStore, CockroachDB); (2) istraživanje utjecaja veličine skupa podataka korištenjem novijih Stack Overflow dumpova; (3) evaluacija energetske efikasnosti različitih konfiguracija; (4) istraživanje automatskog tuninga — može li SQL Server dinamički odabirati optimalnu konfiguraciju ovisno o omjeru opterećenja u realnom vremenu."),
  PB(),
];

// ── LITERATURA ────────────────────────────────────────────────────────────────
const literatura = [
  H1("Literatura"),
  ...[
    "[1] C. Zhang, J. Zhou, H. Chen, Z. Wang, and T. Li, \"HTAP databases: A survey,\" IEEE Trans. Knowl. Data Eng., 2024. [Online]. Available: https://arxiv.org/abs/2404.15670",
    "[2] C. Zhang, G. Li, and T. Lv, \"HyBench: A new benchmark for HTAP databases,\" Proc. VLDB Endow., vol. 17, no. 5, pp. 939–951, 2024. doi: 10.14778/3641204.3641206",
    "[3] Y. Wu et al., \"HTAP benchmark in financial scenarios,\" Security and Safety, vol. 4, 2025. doi: 10.1051/sands/2025010",
    "[4] P. Zhao et al., \"PUSHtap: PIM-based in-memory HTAP with unified data storage format,\" in Proc. 30th ACM ASPLOS, 2025.",
    "[5] H. Xiu et al., \"Query performance explanation through large language model for HTAP systems,\" arXiv preprint arXiv:2412.01709, 2024.",
    "[6] H. Song, Z. Zhao, X. Ding, and R. Chen, \"A survey on hybrid transactional and analytical processing,\" VLDB J., 2024. doi: 10.1007/s00778-024-00858-x",
    "[7] C. Zhan et al., \"veDB-HTAP: A highly integrated, efficient and adaptive HTAP system,\" Proc. VLDB Endow., 2025. doi: 10.14778/3750601.3750614",
    "[8] X. Zeng, M. Abebe, J. Waudby, and A. Pavlo, \"An empirical evaluation of columnar storage formats,\" Proc. VLDB Endow., vol. 17, no. 2, pp. 148–161, 2023.",
    "[9] Y. Zhao, J. Chen, Y. Wang, and X. Shi, \"Benchmarking HTAP databases for performance isolation and real-time analytics,\" Inf. Syst., 2023. doi: 10.1016/j.is.2023.102195",
    "[10] Y. Zhang et al., \"SynchroStore: A cost-based fine-grained incremental compaction for hybrid workloads,\" arXiv preprint arXiv:2503.18688, 2025.",
    "[11] D. Huang et al., \"TiDB: A Raft-based HTAP database,\" Proc. VLDB Endow., vol. 13, no. 12, pp. 3072–3084, 2020. doi: 10.14778/3415478.3415535",
    "[12] J. Yang et al., \"F1 Lightning: HTAP as a service,\" Proc. VLDB Endow., vol. 13, no. 12, pp. 3313–3326, 2020. doi: 10.14778/3415478.3415539",
    "[13] C. Diaconu et al., \"Hekaton: SQL Server's memory-optimized OLTP engine,\" in Proc. ACM SIGMOD, New York: ACM, 2013, pp. 1243–1254. doi: 10.1145/2463676.2463710",
    "[14] P.-Å. Larson et al., \"Enhancements to SQL Server column stores,\" in Proc. ACM SIGMOD, New York: ACM, 2013, pp. 1159–1170. doi: 10.1145/2463676.2463708",
    "[15] F. Özcan, Y. Tian, and P. Tözün, \"Hybrid transactional/analytical processing: A survey,\" in Proc. ACM SIGMOD, Chicago: ACM, 2017, pp. 1771–1775. doi: 10.1145/3035918.3054784",
  ].map(ref => new Paragraph({
    children: [new TextRun({ text: ref, font: FONT, size: SZ })],
    spacing: { line: 320, lineRule: "auto", after: 120 },
    indent: { left: 400, hanging: 400 },
  })),
];

// ── ASSEMBLE DOCUMENT ─────────────────────────────────────────────────────────
const allChildren = [
  ...titlePage,
  // TOC page
  new Paragraph({
    children: [new TextRun({ text: "SADRŽAJ", font: FONT, size: 32, bold: true })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 320 },
  }),
  new TableOfContents("Sadržaj", { hyperlink: true, headingStyleRange: "1-3" }),
  PB(),
  ...abstractSection,
  ...ch1,
  ...ch2,
  ...ch3,
  ...ch4,
  ...ch5,
  ...ch6,
  ...ch7,
  ...literatura,
];

const doc = new Document({
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0,
        format: "bullet",
        text: "•",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } },
      }],
    }],
  },
  styles: {
    default: {
      document: { run: { font: FONT, size: SZ } },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: false, font: FONT_H, color: C_H1 },
        paragraph: { spacing: { before: 480, after: 240, line: 360, lineRule: "auto" }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: false, font: FONT_H, color: C_H2 },
        paragraph: { spacing: { before: 320, after: 160, line: 360, lineRule: "auto" }, outlineLevel: 1 },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: false, italics: true, font: FONT_H, color: C_H1 },
        paragraph: { spacing: { before: 240, after: 120, line: 360, lineRule: "auto" }, outlineLevel: 2 },
      },
      {
        id: "Heading4", name: "Heading 4", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: FONT, color: C_H1 },
        paragraph: { spacing: { before: 200, after: 100, line: 360, lineRule: "auto" }, outlineLevel: 3 },
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: A4W, height: A4H },
        margin: { top: MAR, bottom: MAR, left: MAR, right: MAR },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          children: [new TextRun({ text: "Evaluacija HTAP performansi u Microsoft SQL Serveru — Nejra Smajlović", font: FONT, size: 18, color: "888888" })],
          alignment: AlignmentType.RIGHT,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC", space: 4 } },
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          children: [
            new TextRun({ text: "Stranica ", font: FONT, size: 20, color: "888888" }),
            new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20, color: "888888" }),
            new TextRun({ text: " / ", font: FONT, size: 20, color: "888888" }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 20, color: "888888" }),
          ],
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC", space: 4 } },
        })],
      }),
    },
    children: allChildren,
  }],
});

const outPath = "C:\\Users\\Korisnik\\Downloads\\vjezbe\\HTAPBenchmark\\Paper\\rad_Smajlovic_Nejra_final.docx";
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log("OK:", outPath);
}).catch(err => {
  console.error("ERROR:", err.message);
  process.exit(1);
});
