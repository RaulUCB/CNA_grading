from getpass import getpass
import json
import os
from urllib.request import Request, urlopen
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

BASE_URL = "https://app.cna.com.br"
CLASSES_URL = f"{BASE_URL}/learning/teacher/classes"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = os.getenv("CNA_GRADING_MODEL", "qwen2.5:3b")


def normalize_url(href):
    if not href:
        return None
    if href.startswith("http"):
        return href
    return urljoin(BASE_URL, href)


def collect_unique_links(page, selector):
    values = []
    for element in page.locator(selector).all():
        href = element.get_attribute("href")
        url = normalize_url(href)
        if url and url not in values:
            values.append(url)
    return values


def login(page):
    username = input("CNA username: ")
    password = getpass("CNA password: ")
    page.goto(f"{BASE_URL}/login")
    page.fill('input[placeholder="Digite seu usuário"]', username)
    page.fill('input[placeholder="Digite sua senha"]', password)
    page.click('button:has-text("Acessar")')
    page.wait_for_load_state("networkidle")


def get_activity_content(page):
    answer = page.locator('textarea[disabled], textarea[readonly]').first.input_value()
    headings = [text.strip() for text in page.locator("h5").all_inner_texts()]
    prompt = next(
        (text for text in headings if text and text != "Resposta do aluno"),
        "",
    )
    if not answer.strip() or not prompt:
        raise RuntimeError("Could not read the assignment prompt and student response.")
    return prompt, answer


def suggest_grade(prompt, answer):
    instructions = (
        "You are assisting a teacher reviewing an English learner's writing. "
        "Judge only whether the response is understandable and coherent as an answer. "
        "Ignore grammar mistakes when deciding the grade: if it makes sense, use Correct. "
        "If it does not make sense, is incoherent, or does not answer the task, use Incorrect. "
        "Put any grammar mistakes and brief corrections in feedback. Do not use Partial. "
        "Return only a JSON object with keys grade (Correct or Incorrect) and feedback (string). "
        "Write feedback in simple, encouraging English."
    )
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": (
            f"{instructions}\n\nAssignment:\n{prompt}\n\n"
            f"Student response:\n{answer}"
        ),
        "format": "json",
        "stream": False,
    }
    request = Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
        suggestion = json.loads(result["response"])
    except Exception as error:
        raise RuntimeError(
            f"Could not get a grading suggestion from Ollama ({OLLAMA_MODEL}). "
            "Make sure Ollama is running and the model is installed."
        ) from error

    grade = suggestion.get("grade")
    if grade not in {"Correct", "Incorrect"}:
        raise RuntimeError("The local model returned an invalid grade suggestion.")
    feedback = suggestion.get("feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        raise RuntimeError("The local model returned empty feedback.")
    return grade, feedback.strip()


def apply_and_submit_suggestion(page, grade, feedback):
    radio_name = "Correto" if grade == "Correct" else "Incorreto"
    page.get_by_role("radio", name=radio_name).check()
    page.locator('textarea[placeholder="Adicione o texto aqui"]').fill(feedback)
    input("Review the filled grade and feedback in the browser. Press Enter to submit, or Ctrl+C to stop... ")
    page.locator('button:has-text("Finalizar")').click()
    page.wait_for_timeout(1500)


def grade_all_pending_for_student(page, student_url):
    page.goto(student_url)
    activity_links = []

    for link in page.locator('a[href*="/activity/"]').all():
        href = link.get_attribute("href")
        text = (link.text_content() or "").strip()
        if href and "A corrigir" in text:
            activity_links.append(normalize_url(href))

    for activity_url in activity_links:
        page.goto(activity_url)
        prompt, answer = get_activity_content(page)
        grade, feedback = suggest_grade(prompt, answer)
        print(f"\nHomework: {activity_url}\nAssignment: {prompt}\nStudent response: {answer}")
        print(f"Suggested grade: {grade}\nSuggested feedback: {feedback}")
        approval = input("Accept this suggestion? [y]es / [n]o / [s]kip: ").strip().lower()
        if approval == "y":
            apply_and_submit_suggestion(page, grade, feedback)
        elif approval == "n":
            print("Edit the grade and feedback manually in the browser, then submit it.")
            input("Press Enter when done to continue... ")
        else:
            print("Skipped without submitting.")


def iterate_classes(page):
    class_links = []
    page.goto(CLASSES_URL)

    while True:
        for href in page.locator('a[href*="/learning/teacher/classes/"]').evaluate_all("(els) => els.map(el => el.href)"):
            if "/learning/teacher/classes/" not in href:
                continue
            if href not in class_links:
                class_links.append(href)

        next_button = page.locator('button:has-text("Próxima")').first
        if next_button.count() == 0:
            break

        if next_button.is_disabled():
            break

        next_button.click()
        page.wait_for_load_state("networkidle")

    for class_url in class_links:
        students_url = class_url.rstrip("/") + "/writing/students"
        print(f"Opening class students: {students_url}")
        page.goto(students_url)
        student_links = collect_unique_links(page, 'a[href*="/writing/students/"]')
        if not student_links:
            print(f"No student links found at {students_url}")
        for student_url in student_links:
            grade_all_pending_for_student(page, student_url)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1440, "height": 1200})

    try:
        login(page)
        iterate_classes(page)
        input("Review pass finished. Press Enter to close the browser... ")
    except Exception as error:
        print(f"The run stopped: {error}")
        input("The browser will stay open for inspection. Press Enter to close it... ")
    finally:
        browser.close()
