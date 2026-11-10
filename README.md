# CNA Writing Grader 1.0

A Windows-friendly Python tool that visits CNA writing activities and uses a local
Ollama model to suggest a grade and short feedback. It requires an English response;
answers in another language are suggested as `Incorrect`. English grammar mistakes
alone do not make an otherwise understandable, relevant answer incorrect. THIS IS A TOOL FOR TEACHERS!

## Requirements

- Python 3.11 or newer
- Ollama for Windows, running locally
- The `qwen2.5:3b` model (the default), or another Ollama model selected with
  `CNA_GRADING_MODEL`
- Playwright and its Chromium browser

See [WINDOWS_SETUP.md](./WINDOWS_SETUP.md) for installation instructions.

## Run

From PowerShell in the project folder:

```powershell
.\.venv\Scripts\python.exe .\grade_cna.py
```

To select a different installed Ollama model for that PowerShell session:

```powershell
$env:CNA_GRADING_MODEL = "llama3.2:3b"
.\.venv\Scripts\python.exe .\grade_cna.py
```

Enter your CNA credentials when prompted. The script scans classes for pending
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
