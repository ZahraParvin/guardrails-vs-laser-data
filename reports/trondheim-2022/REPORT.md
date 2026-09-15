# FV6650 i Trondheim: NVDB mot laserdata fra 2022

## Resultat

**Ingen NVDB-avvik er bekreftet.** Analysen av 26 rekkverksobjekter, totalt 1 022,14 m, ga ett ustøttet intervall på 7 m og 16 mulige uregistrerte objekter. Etter oppfølging med vegbilder, laserprofiler og vårflyfoto er 12 kandidater og intervallet avvist i screening. Fire kandidater er fortsatt usikre. [Oppfølgingsrapporten](FOLLOWUP.md) forklarer de seks nye avgjørelsene og begrensningene.

Dette er en reell datapipeline og en dokumentert utprøving av en enkel detektor. Bygninger, kjøretøy og vegetasjon kan forveksles med rekkverk. Vurderingene er gjort med Codex og er **ikke uavhengig fagkontroll eller feltverifiserte fasitsvar**.

| Kontroll | Antall |
|---|---:|
| Ustøttede intervaller ≥ 5 m | 1, lengde 7 m |
| Kandidater utenfor nærliggende registrerte linjer | 16 |
| Kandidater avvist ved gjennomgang | 12 |
| Ustøttede intervaller avvist som mangel | 1 |
| Usikre kandidater | 4 |
| Usikre ustøttede intervaller | 0 |
| Bekreftede registeravvik | 0 |

![Oversikt over det virkelige studieområdet](overview.png)

## Datavalg

- **Strekning:** FV6650-objektene i NVDB-eksempeluttrekket. Cirka 1,45 km nord–sør, med 1,02 km registrert rekkverk; dette er ikke 1,02 km sammenhengende veg. Urbant område med boliger og jernbane, valgt før resultattolkning fordi tett lasersurvey og samtidige flyfoto var tilgjengelige.
- **Laser:** NDH Trondheim 30pkt 2022, prosjekt 5765, Terratec for Kartverket. Nominell tetthet 30 punkter/m². [Prosjektrapporten](https://hoydedata.no/LaserServices/REST/DownloadPDF.ashx?projectId=5765) oppgir flyging **29.–30. juli 2022**. Metadatafeltet «siste flydato» oppgir 29. juli; rapporten gir den mer fullstendige perioden.
- **NVDB:** type 5, hentet 15. september 2026. Studieutvalg: 26 objekter. Separat referanseuttrekk: alle 48 rekkverksobjekter rundt korridoren, inkludert naboveger.
- **Flyfoto:** «Trondheim kommune 2022», prosjekt 3999, prosjektdato **24. august 2022**, pikselstørrelse 0,10 m, eier Trondheim kommune. Datoen kommer fra prosjektmetadata; enkeltbildenes datofelt er ikke utfylt i rasterkatalogen. Kilde: [Norge i bilder](https://norgeibilder.no/), [API-dokumentasjon](https://backend-api.klienter-prod-k8s2.norgeibilder.no/swagger/index.html).

### Uttrekk og kvalitetskontroll

Kilden er Kartverkets offentlige **Potree 1.7-visningsdatasett**, med LAZ-noder. Alle lenkede hierarkinivåer som overlapper 25 m rundt linjene er lest. Det ble ikke valgt en grov visningsoppløsning. Uttrekket omfatter 94 hierarkifiler og 1 363 LAZ-filer, cirka 58,7 MB komprimert punktdata.

- 11 876 117 LAZ-poster lest fra kildefilene.
- 6 753 709 punkter beholdt innenfor 25 m-korridoren.
- 3 761 844 punkter analysert innenfor 15 m-korridoren.
- 920 208 klasse-2-punkter i 25 m-uttrekket.
- 1 729 ekstra poster med identiske XYZ i 25 m-uttrekket, cirka 0,026 %. Ingen deduplisering er utført; identiske koordinater kan også tilhøre ulike returer.

**Visningsdatasettet er ikke sammenlignet med originalleveransen.** Hierarkiets punktantall avviker fra faktiske LAZ-poster i 1 019 noder: indeksen angir totalt 4 857 892 punkter, mens filene inneholder 11 876 117. Årsaken er ikke fastslått. Analysen bruker faktiske LAZ-poster. Alle tilgjengelige lenker er fulgt, men dette beviser ikke at datasettet er identisk med originalsurveyet.

Kilden er UTM32 / NN2000 ifølge prosjektmetadata og rapport. LAZ-nodene mangler CRS-angivelse. Skriptet dokumenterer derfor CRS fra kilden og transformerer XY fra EPSG:25832 til EPSG:25833. Z beholdes i NN2000. Faktiske XY-koordinater er kontrollert mot octree-nodenes grenser. URL, SHA-256 og punktantall per node er lagret lokalt i `data/trondheim_2022/provenance.json`.

## Metode og vurderinger

Standardparametrene er beholdt: 0,3–1,5 m over nærmeste klasse-2-punkt, søkeradius 1,5 m, minst fem punkter for støtte og minst 5 m sammenhengende manglende støtte. DBSCAN-kandidater skal ligge mer enn 5 m fra registrerte linjer, være minst 8 m lange og ha lengde/bredde-forhold minst fire. Dette er en heuristikk, ikke en trent rekkverksmodell.

### G01 – 7 m uten laserstøtte, avvist som mangel

Objekt **671258022**, vegreferanse **FV6650 S2D1 m842–856**. Flagget gjelder 0–7 m langs geometridelen; dette er ikke beregnet offisiell vegmeter. Vegbildet fra **20. juli 2022** viser stålskinne med nettingpanel ved den aktuelle fasaden under trekronen, i samsvar med NVDB-beskrivelsen. Flagget avvises som påstand om manglende rekkverk. Laserprofilen viser mange høye returer og få i søkebåndet; skjerming er en plausibel, men ikke isolert årsak. Vegbildet er tatt 9–10 dager før lasersurveyet og beviser ikke tilstanden på selve flydagen. Se [bilde og kilde](FOLLOWUP.md#g01-barrier-present-despite-low-laser-support).

![Laserprofil for det ustøttede intervallet](gap_diagnostic.png)

### C01, C09 og C12 – bygningsrelaterte kandidater

Polygonene følger eller krysser bygningsflater og hage-/terrasseområder. Avvist i bildegjennomgangen. En lang, smal klynge er ikke tilstrekkelig til å identifisere rekkverk; den presise mekanismen i bakkeestimatet er ikke isolert.

### C06 og C13–C15 – kandidater i kjørefelt

Disse ligger inne i kjørebanen, ikke langs en fast vegkant. Avvist som faste rekkverk ut fra bildet og vegutformingen. Kjøretøy i lasersurveyet er en plausibel forklaring, men ulike opptaksdatoer gjør at dette ikke er verifisert.

### Vegetasjons- og grenseobjekter

Oppfølgingen avviser C02, C04, C08, C10 og C16 som vegetasjons-/terrengkandidater med middels sikkerhet i screening. Laserprofilene fra 2022 og vårflyfoto fra 2024/2026 støtter denne tolkningen. Senere bilder er støttegrunnlag, ikke fasit for 2022. C03, C05, C07 og C11 står som `uncertain`; de krever nærbilder og datert dokumentasjon av grenseobjektet.

Alle 17 vurderinger finnes i [review.csv](review.csv), med koordinater, dato, kilde og begrunnelse. [Første gjennomgang](review_first_pass.csv) er bevart. [Kildemanifestet](evidence_manifest.json) dokumenterer oppfølgingens vegbilder, raster-ID-er, datoer og filhashverdier. Fotoark ligger lokalt i `outputs/real/review/`; flyfotoene er ikke kopiert inn i den publiserbare rapportmappen.

### Rettelse under validering

Den første kjøringen brukte bare FV6650 som registerreferanse og ga 18 kandidater. Bildekontrollen avdekket et grenseobjekt som allerede var registrert på en annen veg. Referansesettet ble utvidet til alle 48 nærliggende rekkverksobjekter; ny kjøring ga 16 kandidater. En regresjonstest dekker dette. Tersklene ble ikke justert etter etikettene.

## Følsomhet

| Søkeradius | Min. punkter | Flagg ≥ 5 m | Flagget lengde |
|---|---:|---:|---:|
| 1,0 m | 5 | 4 | 31 m |
| 1,0 m | 20 | 13 | 99 m |
| **1,5 m** | **5** | **1** | **7 m** |
| 1,5 m | 10 | 2 | 15 m |
| 1,5 m | 20 | 7 | 53 m |
| 2,0 m | 5 | 1 | 6 m |

Alle ni kombinasjoner ligger i [sensitivity.csv](sensitivity.csv). Resultatene er parameteravhengige. Stor radius kan gi støtte fra andre objekter. Et uavhengig fasitutvalg trengs før tersklene kan kalles kalibrerte. Presisjon og recall er ikke målt; støttede og uflaggete kontrollsteder er ikke systematisk vurdert.

## Kjøretid og minne

Korrigert lokal kjede: **6,39 sekunder**, inkludert LAZ-lesing, utsnitt, bakkeestimat, støtte, DBSCAN, eksport og figur. Målt topp-RSS **618,8 MiB**, avlest hvert 50 ms; ikke en garantert øvre grense. Importer og nettverksnedlasting er utenfor målingen. Resultatet avhenger av maskin og hurtigbuffer.

## Gjenta forsøket

Installer prosjektet med `.[dev]`. Fra rotmappen med miljøets Python:

```powershell
python -m guardrails fetch --bbox "269000,7040000,271000,7042000" --output data/nvdb
python scripts/download_study.py
python -m guardrails fetch --bbox "268915,7040315,269280,7041840" --output data/trondheim_2022/reference_nvdb
python scripts/run_real.py
python scripts/analyse_study.py
python scripts/review_study.py outputs/real
python scripts/report_study.py
```

Nye NVDB-uttrekk kan endre resultatene. LAZ-noder mellomlagres. `report_study.py` gjengir eksplisitte vurderinger fra denne gjennomgangen; den utfører **ikke automatisk visuell validering**. Nytt datagrunnlag må vurderes på nytt før etikettene brukes.

## Videre validering

Fire steder gjenstår i [field_checks.csv](field_checks.csv): C03, C05, C07 og C11. Tilgjengelige vegbilder fra 2022 er kontrollert; de viser ikke disse grenseobjektene godt nok. Nærbilder fra adkomstvegene og historisk dokumentasjon trengs. Sammenlign også med original LAZ-eksport og vurder et representativt utvalg av støttede og ustøttede steder. NVDB fra 2026 kan ikke uten videre være fasit for laser fra 2022.

## Kilder og attribusjon

- Laser: **© Kartverket**, NDH Trondheim 30pkt 2022, Terratec. [Høydedata](https://hoydedata.no/LaserInnsyn2/) og [vilkår](https://www.kartverket.no/api-og-data/vilkar-for-bruk).
- NVDB: Inneholder data under norsk lisens for offentlige data (NLOD) tilgjengeliggjort av **Statens vegvesen**.
- Lokalt foto-kontrollgrunnlag: **© norgeibilder.no / Trondheim kommune**, prosjekt 3999. Flyfoto er lisensierte produkter med egne vilkår; de er ikke en generell CC BY-punktsky.
- Oppfølging: [Vegbilder, Statens vegvesen, NLOD](https://dataut.vegvesen.no/nb/dataset/vegbilder), opptak 8. juni og 20. juli 2022; vårflyfoto fra Norge i bilder, prosjektene 4629 og 5077. Se [oppfølgingsrapport](FOLLOWUP.md).
