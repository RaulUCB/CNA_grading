# CNA Grader Setup for Windows

The grader visits classes, students, and pending writing activities. A local Ollama model suggests `Correto` when an answer is understandable and relevant, even if it has grammar mistakes; grammar corrections go in feedback. It suggests `Incorreto` when the response is not understandable or is irrelevant. The script asks for your CNA login at runtime and waits for your review and confirmation before submission.

## Install prerequisites

1. Install Python 3.11 or newer from python.org and enable the option to add Python to PATH.
2. Install Ollama for Windows and open the Ollama app.
3. In PowerShell, download the model used by the script:

```powershell
ollama pull qwen2.5:3b
```

4. Extract this ZIP to a folder, then open PowerShell in that folder.

## Set up and run

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python grade_cna.py
```

If PowerShell blocks environment activation, run this once in that PowerShell window and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Keep Ollama running while the script runs. Log in when prompted. For each AI suggestion, review the assignment, response, grade, and feedback in the terminal. Press `y` then Enter to fill and submit the suggested grade in CNA. Press `n` to edit and submit manually, or `s` to skip without submitting. At the end, the program reports suggestions, submitted grades, manually graded activities, and skips.

## Notes

- The model runs locally through Ollama. Model speed and grading quality depend on the computer and model. The Kali test machine was too slow to finish a sample inference, so test the model on this Windows computer with sample answers before relying on suggestions.
- The script does not copy the `.venv` or Ollama model; install them on the Windows computer using these steps.
- Do not use the script unattended: AI suggestions can be wrong. Review each suggested grade and feedback before confirming submission.
