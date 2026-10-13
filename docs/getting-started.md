# Try JobFlow

[Dansk](getting-started.da.md) · [Back to the project](../README.md)

## Just looking? Start here

You can explore the example directly on GitHub. No installation, account or AI subscription is needed.

1. Open the [overview](../AKTUEL_STATUS.md) to see the case and its next action.
2. Follow the [job package](../Ansoegninger_Aktive/demo-ai-workflow/AFLEVERING.md) to the documents.
3. Compare the [example CV](../Ansoegninger_Aktive/demo-ai-workflow/cv.md) with the [source mapping](../Ansoegninger_Aktive/demo-ai-workflow/match.md).
4. Look at the [Joblog fields](../Ansoegninger_Aktive/demo-ai-workflow/JOBLOG.md), ready to copy into a separate job log.

The example applicant, employer, project and vacancy are fictional. This particular vacancy asks for a CV only, so its package has no application letter. The tools also support letters and short motivation documents when a real posting requires them.

## Run the demo on your computer

You need **Python 3.10 or newer**. The demo uses only Python's standard library: there is nothing to install with `pip`, and no API key, AI account or employer login is needed.

Get the files in either of these ways:

- On the [GitHub repository](https://github.com/Fostercare5988/jobflow), choose **Code → Download ZIP**, extract the ZIP and open the extracted project folder.
- If you use Git, run `git clone https://github.com/Fostercare5988/jobflow.git`, then open the `jobflow` folder.

Open a terminal in that folder, where `demo.py` is located. Run these two commands:

```text
python demo.py reset
python tools/jobflow.py validate demo-ai-workflow
```

If your Python command is `python3` or `py`, use that instead of `python` in both commands.

The first command recreates the fictional package with dates relative to today. The second should print a line beginning with **`PASS:`**. That result means the demo's files, source references and synthetic review are consistent. It does not mean a real application has been reviewed or sent.

Open the local `AKTUEL_STATUS.md` to see the result. Its links lead to the package, CV and Joblog.

The guides are available in English and Danish. File names, some generated text and command-line messages retain Danish from the original working project.

## Use it in Obsidian

In Obsidian's vault switcher, choose **Open folder as vault**, then select the downloaded project folder. Start from `AKTUEL_STATUS.md`; follow its link to the job package rather than opening every file separately. No Obsidian plugins are required for this demo.

GitHub and Obsidian both display Markdown. The Python commands regenerate the local views when the underlying records change.

## See a check catch a change

Change one sentence in `Ansoegninger_Aktive/demo-ai-workflow/cv.md` and save it. Run the validation command again:

```text
python tools/jobflow.py validate demo-ai-workflow
```

This time the check should fail: the saved review belongs to the previous version of the CV. Restore the fictional example with `python demo.py reset`.

Only use reset in this disposable demo. It replaces the demo package and its source records. Its passing review is deliberately generated test data, not a shortcut for reviewing real applications.

## Who does the actual job search?

An AI assistant with suitable tools does the research and writing in a separate working environment. The Python tools keep track of records and check files; they do not browse, call an AI model or submit anything. To adapt the approach to your own private workspace, see the [technical guide](technical-guide.md).
