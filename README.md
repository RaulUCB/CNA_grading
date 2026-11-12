# CNA Writing Grader 1.1.0

A Windows app that visits CNA writing activities and uses a local Ollama model to
suggest a grade and short feedback. It requires an English response; answers in
another language are suggested as `Incorrect`. English grammar mistakes alone do
not make an otherwise understandable, relevant answer incorrect.
This is a tool for teachers.

## Run the standalone Windows app

Download and extract `CNAWritingGrader-win-x64.zip`, then run
`CNAWritingGrader.exe` from the extracted folder. The app includes Python and
Playwright's Chromium browser. It still requires Ollama for Windows to be installed
and running, with the `qwen2.5:3b` model available by default.

On launch, you can enter additional AI instructions. They are saved locally and
used on future runs, as extra guidance that cannot override the grader's core rules.
Use **Check for updates** to check GitHub for a newer published release. Updates
are downloaded manually from the releases page; the app does not replace itself.

See [WINDOWS_SETUP.md](./WINDOWS_SETUP.md) for setup, building, and update
instructions, and [CHANGELOG.md](./CHANGELOG.md) for release history.

## Run from source

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python .\grade_cna.py
```

To select a different installed Ollama model for that PowerShell session:

```powershell
$env:CNA_GRADING_MODEL = "llama3.2:3b"
python .\grade_cna.py
```

The app prompts for CNA credentials in the terminal. It scans classes for pending
writing activities, displays each assignment, student response, proposed grade,
and feedback, then waits for your choice:

- `y`: submit this suggestion
- `a`: submit this suggestion and automatically submit every remaining suggestion
  during this run
- `n`: grade manually in the browser
- `s`: skip without submitting

## Review and safety

AI suggestions can be wrong. Check the assignment, response, grade, and feedback
before submitting. `a` disables per-activity confirmation for the rest of the run;
use it only when you are comfortable allowing automatic submission. Credentials
are requested at runtime and should not be added to source files.
