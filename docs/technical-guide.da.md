# JobFlow: teknisk vejledning

[English](technical-guide.md) · [Prøv demoen først](getting-started.da.md) · [Projektet](../README.da.md)

## Delene i projektet

| Fil eller værktøj | Ansvar |
| --- | --- |
| `Data/jobs.json` | Det eneste register over sagernes aktuelle jobstatus. |
| `Profil/fakta.json` og `Profil/projekter.json` | Fakta og projektdokumentation med kilde-id'er. |
| `Ansoegninger_Aktive/<id>/` | Opslagsnoter, kobling til kilder, udkast og gennemgang for én sag. |
| `tools/jobflow.py` | Registerændringer, filkontrol, fingeraftryk af gennemgået materiale og Markdown-overblik. |
| `tools/jobrun.py` | Bestilling, faktisk udført arbejde og næste handling for et arbejdsforløb. |
| `AGENTS.md` og `FRAMEWORK.md` | Instruktioner til assistenten, der arbejder med filerne. |

Én ansvarlig assistent vedligeholder jobregisteret. Andre agenter kan få afgrænsede research- eller reviewopgaver i særskilte filer. Forløbsloggen henviser til sagerne og vedligeholder ikke et ekstra sæt jobstatusser.

Python-værktøjerne bruger standardbiblioteket og arbejder lokalt. De kalder ingen model-API, browser ikke hjemmesider, sender ikke ansøgninger eller beskeder, opdaterer ikke eksterne jobportaler og kører ikke i baggrunden. Assistentens tilgængelige værktøjer afgør, hvilken research og skrivning den kan udføre.

## Nyttige kommandoer

Kør kommandoerne fra projektets rodmappe. [Kom i gang-vejledningen](getting-started.da.md) viser, hvordan du opretter det fiktive eksempel.

```text
python tools/jobflow.py check
python tools/jobflow.py next demo-ai-workflow
python tools/jobflow.py fingerprints demo-ai-workflow
python tools/jobflow.py validate demo-ai-workflow
python tools/jobflow.py render
python -m unittest discover -s tests -v
```

`check` skriver en registerrapport. `next` læser den aktuelle sag og beskriver næste handling. `fingerprints` beregner fingeraftryk af relevante dokumenter, kilderegistre, skrivevejledning og sagens grundlag. `validate` sammenholder den gemte gennemgang med det aktuelle materiale. `render` gendanner overblik, afleveringssider og projektbank. Ret grundregistrene frem for disse genererede visninger.

Kilderne skal læses, og en reel gennemgang skal udføres, før fingeraftrykkene opdateres. Et matchende fingeraftryk viser, at de registrerede bytes ikke har ændret sig. Det beviser ikke, at indholdet er sandt. Demoen er kun en undtagelse, fordi dens gennemgang udtrykkeligt er syntetisk testdata.

[Kontrolnotatet](../VALIDATION.md) skelner mellem dokumenterede kørsler og testkode, der blot findes. CI-workflowet kører tests og demokontroller på de Python-versioner og operativsystemer, der fremgår af workflowet.

## Gem og genoptag et arbejdsforløb

Efter reset af demoen kan disse kommandoer oprette og genoptage en lokal eksempellog:

```text
python tools/jobrun.py start demo-run --request "Undersøg det fiktive eksempel" --job-id demo-ai-workflow --next-action "Læs kilderne og kør kontroller"
python tools/jobrun.py note demo-run --phase review --evidence "Har læst den fiktive kildekobling og den aktuelle kontrolrapport" --next-action "Beskriv eventuelle resterende mangler"
python tools/jobrun.py resume demo-run
```

Kør kun `note`, når det beskrevne arbejde faktisk er udført. `resume` henter sagernes aktuelle status fra `Data/jobs.json`. En lognote er hverken en godkendelse eller bevis for, at kontrollen bestod. Lokalt oprettede forløbslogs er ikke med i listen over tilladte offentlige filer. Brug et nyt forløbs-id, hvis `demo-run` allerede findes.

## Tilpas til din egen jobsøgning

Dette repository er en demonstration. Det er ikke en færdig tjeneste, der finder og søger job efter installation. En rigtig opsætning kræver en privat arbejdsmappe, faktiske kandidatoplysninger, skrivepræferencer og en AI-assistent med de nødvendige researchværktøjer.

1. Lav en særskilt privat arbejdskopi. Behold den offentlige demo til afprøvning, og læg ikke rigtige kandidatoplysninger i det offentlige repository.
2. Erstat det fiktive jobregister i den private kopi med et tomt: `{"schema_version": 1, "jobs": []}`. Start fakta- og projektregistrene med `{"facts": []}` og `{"projects": []}`. Fjern de fiktive sagsfiler, og erstat det syntetiske kildegrundlag med egne dokumenterede kilder.
3. Registrér, hvor dine faktiske oplysninger kommer fra. Inventarfilen `Profil/Kilder/github_inventory.json` skal have en faktisk kontroldato i `checked_at`. Kopiér ikke en demodato, og fremstil den som en udført GitHub-kontrol.
4. Tilpas `AGENTS.md`, `FRAMEWORK.md` og `System/SKRIVESTIL.md` til dine behov og din stemme. Filnavne og genererede tekster er delvist danske; tilpas dem efter behov i din egen kopi.
5. Brug den tomme [jobskabelon](../templates/job.json) til rigtige sager og [reviewskabelonen](../templates/review.json) til en reel gennemgang. Tjekpunkterne begynder bevidst som falske. Udfyld opslag, kobling til kilder, et fuldt målrettet CV og den krævede motivationstekst, før pakken registreres som klar.
6. Lad assistenten udføre research og dokumentarbejde, og gennemlæs leverancen. Giv kun den adgang, arbejdet kræver. Python-værktøjerne er fortsat lokale register- og kontrolværktøjer.

Brug ikke `demo.py reset` i den private arbejdskopi. Kommandoen erstatter syntetiske registre og er ikke beregnet til at vedligeholde personlige data. Gennemgang, PDF-eksport, brugeraccept, indsendelse og ekstern Joblog-registrering er særskilte handlinger. Registrér kun en ansøgning som sendt på grundlag af en faktisk kvittering eller ansøgerens udtrykkelige besked.

## Grænser

- Et gyldigt kilde-id beviser ikke, at kilden understøtter en sætning. Kilden og teksten skal læses.
- Ændringer i dokumenter, kilderegistre eller jobkrav kan forælde gennemgangen. Genlæs materialet frem for blot at erstatte fingeraftrykkene.
- Dubletkontrollen er forsigtig. Lignende job kan stadig kræve en konkret sammenligning.
- Den lokale fillås forhindrer overlappende skrivninger gennem værktøjerne. Det er ikke en tjeneste til flere samtidige brugere eller et manipulationssikkert revisionsspor.
- En afsendelsesdato og en evidenstekst kan ikke verificere en ekstern indsendelse eller assistentens tilladelse til at foretage den.
- Stop efter tre konkrete rettelsesrunder, hvis der stadig er en mangel, og beskriv den. Markér ikke ufærdigt arbejde som klart for at fjerne en advarsel.

## Oprindelse og publicering

Niko sætter retningen for den oprindelige arbejdsgang. Udvikling og klargøring af demoen er udført med AI-assistance. Den offentlige demo er adskilt fra det private arbejdsprojekt. [PROVENANCE.json](../PROVENANCE.json) registrerer oprindelsen af kopieret kode, mens [PUBLICATION_MANIFEST.json](../PUBLICATION_MANIFEST.json) oplister de gennemgåede offentlige filer og deres fingeraftryk.

Kontrollér en uændret publiceret version med:

```text
python tools/verify_manifest.py
```

Reset af demodatoer og filændringer ændrer med vilje de registrerede fingeraftryk. Manifestet beskriver den publicerede version og er ikke en løbende sikkerheds- eller integritetstjeneste. `.gitignore` afviser som udgangspunkt nye filer og giver en ekstra publiceringsgrænse. Det erstatter ikke en gennemgang af de præcise filer, der skal lægges på GitHub.

Der er ikke valgt en licens i denne version. Se repositoryets aktuelle licensoplysninger, før du videredistribuerer koden eller indarbejder den i andre projekter.
