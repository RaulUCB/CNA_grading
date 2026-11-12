# CNA Writing Grader 1.1.0 — Windows Setup

The grader visits classes, students, and pending writing activities. A local Ollama model suggests `Correto` when an answer is in English, understandable, and relevant, even if it has grammar mistakes; it suggests `Incorreto` for non-English, incomprehensible, or irrelevant responses. The app asks for your CNA login at runtime. Review each suggestion before submitting; the optional `a` choice enables automatic submission for the remainder of that run.

## Use the standalone app

1. Install Ollama for Windows and open the Ollama app.
2. In PowerShell, download the default model:

```powershell
ollama pull qwen2.5:3b
```

3. Download and extract `CNAWritingGrader-win-x64.zip`.
4. Run `CNAWritingGrader.exe` from the extracted `CNAWritingGrader` folder. Keep the
   whole folder together; it contains the app runtime and Chromium browser.

At startup, enter optional additional instructions for the AI. They are saved in
`%APPDATA%\CNA Writing Grader\settings.json` and used in future runs. These
instructions supplement, and do not replace, the grader's core rules.

Use **Check for updates** to compare the app version with the latest published
GitHub release. If a newer release is available, open its page, download the new
ZIP, close the app, and replace the old extracted folder. Updates are not installed
automatically. No release will be reported until one has been published on GitHub.

## Build the standalone app from source

Install Python 3.11 or newer, then open PowerShell in the source folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
.\build_windows.ps1
```

The script installs build dependencies, downloads Chromium, and creates:

- `dist\CNAWritingGrader\CNAWritingGrader.exe` and its required app files
- `dist\CNAWritingGrader-win-x64.zip`, ready to distribute or attach to a GitHub release

The app runs grading interactions in a console, so keep the console window open.
To publish an update, create a GitHub release with a version tag such as `v1.2.0`
and attach the generated ZIP. Update `APP_VERSION` in `grade_cna.py` before making
the next release. See [CHANGELOG.md](./CHANGELOG.md) for the published feature
history.

If PowerShell blocks environment activation, run this once in that PowerShell window and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Keep Ollama running while the app runs. Log in when prompted. For each AI suggestion, review the assignment, response, grade, and feedback in the terminal. Press `y` then Enter to submit the suggested grade in CNA. Press `a` to submit the current suggestion and automatically submit the remaining suggestions in that run, `n` to edit and submit manually, or `s` to skip without submitting. At the end, the program reports suggestions, submitted grades, manually graded activities, skipped activities, and non-editable activities.

## Notes

- The model runs locally through Ollama; it is not included in the app. Model speed
  and grading quality depend on the computer and model.
- Do not use the app unattended: AI suggestions can be wrong. Review each suggested
  grade and feedback before confirming submission.
