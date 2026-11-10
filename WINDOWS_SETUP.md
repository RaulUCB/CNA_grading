# CNA Grader Setup for Windows

This bundle contains the grader script, not the Python environment or AI model. The script asks for your CNA login at runtime; do not put credentials in the file. It proposes grades and feedback, but waits for your review and confirmation before submission.

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

Keep Ollama running while the script runs. Log in when prompted. For each AI suggestion, review the grade and feedback in the terminal and browser; only accept it when you agree. Press `y` then Enter to fill in and submit, `n` to edit and submit manually, or `s` to skip.

## Notes

- The model runs locally through Ollama. A larger model or slower computer can make each suggestion take longer.
- The script does not copy the `.venv` or Ollama model; install them on the Windows computer using these steps.
- Do not use the script unattended: review each suggested grade before confirming submission.
