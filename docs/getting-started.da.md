# Prøv JobFlow

[English](getting-started.md) · [Tilbage til projektet](../README.da.md)

## Vil du bare se, hvad det er?

Du kan åbne eksemplet direkte på GitHub. Det kræver hverken installation, konto eller AI-abonnement.

1. Åbn [overblikket](../AKTUEL_STATUS.md), og se sagen og dens næste handling.
2. Følg linket til [jobpakken](../Ansoegninger_Aktive/demo-ai-workflow/AFLEVERING.md), som samler dokumenterne.
3. Sammenlign [eksemplets CV](../Ansoegninger_Aktive/demo-ai-workflow/cv.md) med [koblingen til kilderne](../Ansoegninger_Aktive/demo-ai-workflow/match.md).
4. Se [Joblog-felterne](../Ansoegninger_Aktive/demo-ai-workflow/JOBLOG.md), der kan kopieres til en særskilt joblog.

Ansøger, virksomhed, projekt og stilling i demoen er opdigtede. Netop dette opslag beder kun om et CV, så pakken har ikke et ansøgningsbrev. Værktøjerne understøtter også ansøgninger og korte motivationstekster, når et rigtigt opslag kræver det.

## Kør demoen på din computer

Du skal bruge **Python 3.10 eller nyere**. Demoen bruger kun Pythons standardbibliotek. Du skal ikke installere pakker med `pip`, oprette en AI-konto eller angive API-nøgler eller arbejdsgiverlogin.

Hent filerne på en af disse måder:

- Gå til [projektet på GitHub](https://github.com/Fostercare5988/jobflow), vælg **Code → Download ZIP**, pak ZIP-filen ud, og åbn projektmappen.
- Bruger du Git, så kør `git clone https://github.com/Fostercare5988/jobflow.git`, og åbn derefter mappen `jobflow`.

Åbn en terminal i projektmappen, hvor `demo.py` ligger. Kør disse to kommandoer:

```text
python demo.py reset
python tools/jobflow.py validate demo-ai-workflow
```

Hedder Python-kommandoen `python3` eller `py` på din computer, bruger du det navn i begge kommandoer.

Den første kommando genskaber den fiktive jobpakke med datoer regnet fra i dag. Den anden bør vise en linje, der begynder med **`PASS:`**. Det betyder, at demoens filer, kildehenvisninger og syntetiske gennemgang passer sammen. Det betyder ikke, at en rigtig ansøgning er gennemgået eller sendt.

Åbn den lokale `AKTUEL_STATUS.md` for at se resultatet. Herfra kan du gå videre til pakken, CV'et og Joblog.

Vejledningerne findes på dansk og engelsk. Filnavne, nogle genererede tekster og beskeder fra kommandolinjen er fortsat på dansk fra det oprindelige arbejdsprojekt.

## Brug den i Obsidian

Åbn Obsidian-menuen til valg af boks/vault, vælg **Open folder as vault**, og vælg den hentede projektmappe. Start i `AKTUEL_STATUS.md`, og følg linket til jobpakken. Så behøver du ikke åbne alle filerne hver for sig. Demoen kræver ingen Obsidian-plugins.

Både GitHub og Obsidian viser Markdown. Python-kommandoerne gendanner de lokale overblik, når registrene ændres.

## Se kontrollen opdage en ændring

Ret en sætning i `Ansoegninger_Aktive/demo-ai-workflow/cv.md`, og gem filen. Kør kontrollen igen:

```text
python tools/jobflow.py validate demo-ai-workflow
```

Nu bør den fejle: den gemte gennemgang hører til den tidligere version af CV'et. Gendan det fiktive eksempel med `python demo.py reset`.

Brug kun reset i denne demo. Kommandoen erstatter demopakken og dens kilderegistre. Den beståede gennemgang er bevidst genereret testdata og må ikke bruges som genvej til at godkende rigtige ansøgninger.

## Hvem udfører den rigtige jobsøgning?

En AI-assistent med de nødvendige værktøjer researcher og skriver i et særskilt arbejdsmiljø. Python-værktøjerne holder styr på registre og kontrollerer filer. De browser ikke, kalder ingen AI-model og indsender intet. Vil du tilpasse tilgangen til din egen private mappe, så læs [den tekniske vejledning](technical-guide.da.md).
