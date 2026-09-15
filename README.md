# Rekkverk: NVDB mot laserdata

Et lite Python-prosjekt som sammenligner registrerte rekkverkslinjer med laserpunkter i rekkverkshøyde. Resultatene er kandidater for kontroll, ikke bevis på feil i NVDB.

## Status og resultat

**Virkelig forsøk utført på FV6650 i Trondheim:** 26 rekkverksobjekter, 1 022 m registrert geometri og 3,76 millioner analyserte laserpunkter fra NDH Trondheim 30pkt 2022. Resultat: ett ustøttet intervall på 7 m og 16 kandidater. Etter kontroll mot vegbilder fra 2022, laserprofiler og vårflyfoto fra 2024/2026 er 12 kandidater og intervallet avvist i screening. Fire kandidater er fortsatt usikre. **Ingen NVDB-avvik er bekreftet.** Se [oppfølging og dokumentasjon](reports/trondheim-2022/FOLLOWUP.md). Vurderingene er ikke feltverifiserte.

Se [rapport med datakilder og følsomhetsanalyse](reports/trondheim-2022/REPORT.md), [kart](reports/trondheim-2022/overview.png) og [vurderingstabell](reports/trondheim-2022/review.csv). Dette er AI-assistert bildegjennomgang, ikke uavhengig feltvalidering. Kartverkets visningsdatasett er heller ikke sammenlignet med original LAZ-leveranse.

| Gjennomgang av 17 flagg | Resultat |
|---|---:|
| Kandidater avvist i screening | 12 |
| Ustøttet intervall avvist som manglende rekkverk | 1 |
| Usikre kandidater | 4 |
| Bekreftede NVDB-avvik | 0 |

Oppfølgingen avklarte seks av de ti tidligere usikre flaggene med middels sikkerhet: G01 viser et eksisterende rekkverk i vegbildet, mens C02, C04, C08, C10 og C16 vurderes som vegetasjon/terreng. **C03, C05, C07 og C11 gjenstår** i [kontrollisten](reports/trondheim-2022/field_checks.csv). Senere flyfoto er støttegrunnlag, ikke fasit for tilstanden i 2022. [Kildemanifestet](reports/trondheim-2022/evidence_manifest.json) dokumenterer bilder, datoer og filhashverdier; [første vurdering](reports/trondheim-2022/review_first_pass.csv) er bevart.

En deterministisk **syntetisk demo** følger også med: ett flagg på 18 m og én kandidat. Demoresultatene skal ikke blandes med det virkelige forsøket. Teststatus: 14 tester bestått.

## Kjøring

Python 3.11 eller nyere. Fra prosjektmappen på Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m guardrails demo
```

På Linux/macOS brukes `.venv/bin/python` i stedet. Tester: `python -m pytest` med prosjektmiljøet aktivert.

Se `outputs/demo/overview.png` og `outputs/demo/summary.json` etter kjøring.

## Gjenta Trondheim-forsøket

Bruk prosjektmiljøets Python i kommandoene nedenfor, for eksempel `.\.venv\Scripts\python` på Windows. Nedlasting krever nettverkstilgang. Skriptene mellomlagrer rådata lokalt.

```powershell
python -m guardrails fetch --bbox "269000,7040000,271000,7042000" --output data/nvdb
python scripts/download_study.py
python -m guardrails fetch --bbox "268915,7040315,269280,7041840" --output data/trondheim_2022/reference_nvdb
python scripts/run_real.py
python scripts/analyse_study.py
python scripts/review_study.py outputs/real
python scripts/report_study.py
```

Studien bruker **NDH Trondheim 30pkt 2022**, prosjekt 5765, med flyging 29.–30. juli 2022. Skriptet laster ned alle lenkede, overlappende hierarkinivåer fra Kartverkets Potree-visningsdatasett og transformerer XY fra UTM32 til UTM33. NVDB-uttrekket fra september 2026 inneholdt 84 objekter; studieutvalget omfatter 26 på FV6650. Alle 48 nærliggende rekkverksobjekter brukes som referanse ved kandidatsøket.

Den lokale analyseprosessen tok **6,39 sekunder**, med målt toppminne **618,8 MiB**. Nettverksnedlasting og importer er ikke med i målingen. Se [rapporten](reports/trondheim-2022/REPORT.md) for datakvalitet, kildeavvik og målemetode, og [oppfølgingen](reports/trondheim-2022/FOLLOWUP.md#reproduce-this-follow-up) for kommandoene som henter vegbilder og vårflyfoto og pakker evidensen.

Nye NVDB-uttrekk kan endre resultatene. `report_study.py` gjengir dokumenterte vurderinger og kontrollerer geometrienes hashverdier; skriptet utfører ikke automatisk visuell validering. Endret datagrunnlag må vurderes på nytt før etikettene gjenbrukes.

## Analyser et annet område

1. Velg omtrent 2 × 2 km med rekkverk i [Vegkart](https://vegkart.no). Kontroller dekning, opptaksår og tetthet på [Høydedata](https://hoydedata.no/LaserInnsyn2). Velg punktsky, LAS/LAZ og UTM33; last ned til `data/tile.laz`.
2. Noter faktisk vegnummer, kommune, bbox, laserprosjekt, år, punkttetthet, nedlastingsdato og produktvilkår i en lokal proveniensfil.
3. Hent rekkverk og kjør analysen. Erstatt Trondheim-bboxen nedenfor med ditt område, og bruk en egen resultatmappe:

```powershell
python -m guardrails fetch --bbox "269000,7040000,271000,7042000"
python -m guardrails inspect data/tile.laz
python -m guardrails run --guardrails data/nvdb/guardrails.gpkg --tile data/tile.laz --config config.example.json --output outputs/custom
```

Bruk miljøets Python. `fetch` bruker [NVDB API Les V4](https://nvdb-docs.atlas.vegvesen.no/nvdbapil/v4/Vegobjekter/), følger sidelenker og lagrer rårespons, egenskaper og vegreferanse. Både punktsky og linjer må oppgi EPSG:25833. Andre soner må reprojiseres først. NVDB-objekter kan strekke seg utenfor bbox; manglende laserobservasjon markeres som ukjent.

API-et krever `srid=UTM_33` og returnerer EPSG:5973 (UTM33 + NN2000); eksporten beholder den horisontale geometrien som EPSG:25833. LAS/LAZ med samme sammensatte koordinatsystem godtas også.

## Metode

- Les LAS/LAZ i blokker. Filtrer først med bbox, deretter en vektorisert polygontest. Skriv utsnittet til disk uten å samle alle blokker i minnet.
- Bruk en 15 m søkekorridor. Oppgavens 3 m buffer ville gjort kandidater mer enn 5 m fra registrerte linjer umulige å finne. Analysen finner fortsatt bare kandidater innenfor søkekorridoren.
- Estimer høyde over nærmeste klasse-2-punkt. Avstander over 5 m gir ukjent høyde. Uten klasse 2 brukes 5-persentilen i 2 × 2 m celler, med lavere tillit.
- Del hver linjedel i intervaller på høyst 1 m; tell punkter 0,3–1,5 m over bakken innenfor 1,5 m. Under fem punkter gir manglende støtte når andre gyldige laserpunkter finnes lokalt. Ingen observasjon gir `unknown`.
- Slå sammen sammenhengende intervaller uten støtte, minst 5 m. Behold kurvene og skill separate linjedeler. Søk også etter DBSCAN-klynger mer enn 5 m fra linjene; bruk roterte hovedakser for lengde og bredde.

## Utdata

| Fil | Innhold |
|---|---|
| `flagged_gaps.gpkg` | Flaggede linjestrekninger, sortert etter lengde |
| `unregistered_candidates.gpkg` | Lange, smale klynger utenfor registrerte linjer |
| `support_per_object.csv` | Støttet, ustøttet og ukjent lengde per objekt og vegreferanse |
| `samples.csv` | Punktantall og status for hvert intervall |
| `corridor_cloud.npy` | Utsnitt, kolonner x, y, z, klasse |
| `overview.png` | Oversiktskart uten bakgrunnsbilder |
| `summary.json` | Parametre, datastier, tidspunkt og resultattall |
| `review_template.csv` | De 20 lengste flaggene til manuell kontroll |

`from_m` og `to_m` er avstand langs den enkelte geometridelen, **ikke** offisiell vegmeter. Vegreferansen beholdes som kildeopplysning. Overlappende NVDB-objekter kan gi dobbel lengde i summer.

## Kalibrering og feilkilder

Åpne GeoPackage-filene i QGIS med datert flyfoto fra Norge i bilder. Kopier `review_template.csv` til `review.csv` før utfylling; malen overskrives ved ny kjøring. Fyll `verdict` med `confirmed`, `false_positive` eller `uncertain`, og noter bildekilde, dato og forklaring. Kjør `python -m guardrails review outputs/real/review.csv` for opptelling. Rapporter N bekreftede avvik av K vurderte, med usikre og falske positive separat.

Bildegjennomgang og oppfølging er utført for Trondheim-forsøket; tersklene er ikke kalibrert mot uavhengig fasit. Skygge, glissen punktsky, vegetasjon, terrenghelning, feilklassifisering, sideforskyvning og ulike opptaksår påvirker resultatet. Nærmeste bakkepunkt er en tilnærming, ikke en eksakt terrengmodell. Lokal observasjon garanterer ikke at laserstrålen traff rekkverket. Hekker, gjerder og biler kan gi støtte eller feil kandidater. Bruk `--reference-guardrails` med alle nærliggende registrerte linjer når studieutvalget er begrenset til én veg. Test flere parametre med separate `--output`-mapper, og behold et eget kontrollutvalg ved evaluering.

## Hva ligger i GitHub-prosjektet?

- `guardrails/`: innlesing, analyse, kommandolinje og syntetisk demo.
- `scripts/`: nedlasting, kjøring, diagnostikk og dokumentert oppfølging av Trondheim-forsøket.
- `tests/`: regresjonstester for datapipeline og datainnhenting.
- `reports/trondheim-2022/`: rapporter, vurderinger, kildemanifest, kart og utvalgt evidens som kan deles.

`.gitignore` utelater rådata i `data/`, kjøringsresultater og lokale flyfoto i `outputs/`, Python-miljøer, midlertidige filer, lokale hemmeligheter og personlige søknadsdokumenter. Rapportmappen beholdes slik at resultatene kan leses uten å laste ned punktskyen. Ignoreringsregler fjerner ikke filer som allerede er sporet av Git.

## Hva måtte endres i full skala?

La vegnettet styre flisleggingen og bruk overlapp mellom fliser. Bruk lineær vegreferanse som koblingsnøkkel og en kvalitetssikret DTM som bakkegrunnlag. PDAL er et naturlig alternativ for produksjonsflyt. Selve lesingen og utsnittet er blokkbasert; KD-trær og analyse bruker minne proporsjonalt med utsnittet. Kjøringen stopper ved fem millioner utsnittspunkter eller 200 000 kandidatpunkter for å begrense risikoen for minneproblemer, særlig i DBSCAN. Dette er ikke en landsdekkende produksjonsløsning.

## Data og lisenser

- NVDB: «Inneholder data under norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Statens vegvesen.» Se [NVDBs dokumentasjon](https://nvdb.atlas.vegvesen.no/docs/produkter/nvdbapil/v4/introduksjon/Oversikt/) og [vilkår for uttrekk](https://www.vegvesen.no/fag/teknologi/nasjonal-vegdatabank/hente-ut-og-se-pa-data-i-nasjonal-vegdatabank/).
- Kartverkets gratisprodukter: [CC BY 4.0 og vilkår](https://www.kartverket.no/api-og-data/vilkar-for-bruk), kilde © Kartverket. Kontroller særvilkår for det konkrete laserprosjektet og oppgi øvrige rettighetshavere i produktmetadata. Ingen virkelig punktsky distribueres her.
- Vegbilder: Statens vegvesen, [NLOD og datasettbeskrivelse](https://dataut.vegvesen.no/nb/dataset/vegbilder). Rapporten inkluderer ett anonymisert vegbilde med kilde og dato.
- Flyfoto: Norge i bilder og rettighetshavere angitt i kildemanifestet. Bildene brukes til lokal kontroll og inngår ikke i rapportmappen som deles.
- Demoen er generert lokalt og inneholder ingen NVDB- eller Kartverket-data. Kildekode: MIT, se `LICENSE`.

Oppgavebeskrivelsen er bevart i `guardrails-vs-laser-data.md`.
