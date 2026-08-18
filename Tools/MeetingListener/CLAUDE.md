# Kontekst: MeetingListener

U ovom folderu teče transkripcija sastanka uživo. `listen.py` dopisuje replike
u `transcript.md` u formatu `[HH:MM:SS] tekst`.

## Kako čitati transkript

Koristi skriptu, ne čitaj cijeli fajl:

```bash
python tail_new.py        # samo nepročitani dio (pomjera zapamćenu poziciju)
python tail_new.py --peek # isto, ali bez pomjeranja pozicije
python tail_new.py --all  # cijeli transkript, kad treba širi kontekst
```

Fajl raste tokom sastanka, pa `--all` koristi samo kad pitanje traži cijeli
tok razgovora.

## Kako odgovarati

- Odgovaraj kratko — korisnik je usred sastanka i čita u prolazu.
- Transkript je mašinski i sadrži greške; imena, brojeve i pojmove tumači po
  kontekstu, a ako je nešto nečitko, reci to umjesto da nagađaš.
- Govornici nisu označeni. Nemoj pripisivati izjave konkretnim osobama osim
  ako se iz sadržaja jasno vidi ko govori.
- Kad se pitanje odnosi na sam HTAP projekat, odgovor traži u repozitoriju
  (`README.md`, `Analysis/`, `Paper/`), ne samo u transkriptu.
