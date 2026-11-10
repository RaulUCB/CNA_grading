from getpass import getpass
import json
import os
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse
import re

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
    prompt_candidates = [
        text for text in headings
        if text and text.lower() not in {"resposta do aluno", "student answer"}
    ]
    prompt = max(prompt_candidates, key=len, default="")
    if not answer.strip() or not prompt:
        raise RuntimeError("Could not read the assignment prompt and student response.")
    return prompt, answer


def suggest_grade(prompt, answer):
    instructions = (
        "Review an English learner's answer to the assignment. Decide whether the answer "
        "is understandable and coherent, and whether it is relevant to the assignment. "
        "Grammar mistakes do not make an otherwise understandable, relevant answer wrong. "
        "If the answer is not understandable or is irrelevant, briefly say why in feedback. "
        "If it makes sense but has grammar mistakes, give brief corrections in feedback. "
        "If there are no grammar mistakes, feedback may be an empty string. "
        "Return JSON only with boolean fields understandable and relevant, and string field "
        "feedback. Do not assign a grade."
    )
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": (
            f"{instructions}\n\nAssignment:\n{prompt}\n\n"
            f"Student response:\n{answer}"
        ),
        "format": "json",
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0,
            "num_ctx": 2048,
            "num_predict": 128,
        },
    }
    request = Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=600) as response:
            result = json.loads(response.read().decode("utf-8"))
        suggestion = json.loads(result["response"])
    except Exception as error:
        raise RuntimeError(
            f"Could not get a grading suggestion from Ollama ({OLLAMA_MODEL}). "
            "Make sure Ollama is running and the model is installed."
        ) from error

    understandable = suggestion.get("understandable")
    relevant = suggestion.get("relevant")
    if not isinstance(understandable, bool) or not isinstance(relevant, bool):
        raise RuntimeError("The local model returned invalid assessment fields.")

    grade = decide_grade(understandable, relevant)
    feedback = suggestion.get("feedback", "")
    if not isinstance(feedback, str):
        raise RuntimeError("The local model returned invalid feedback.")
    feedback = feedback.strip()
    if not feedback:
        feedback = (
            "Your answer is clear and relevant. Well done."
            if grade == "Correct"
            else "Please write a clear answer that is relevant to the assignment."
        )
    return grade, feedback


def decide_grade(understandable, relevant):
    return "Correct" if understandable and relevant else "Incorrect"


def apply_and_submit_suggestion(page, grade, feedback):
    radio_name = "Correto" if grade == "Correct" else "Incorreto"
    page.get_by_role("radio", name=radio_name).check()
    page.locator('textarea[placeholder="Adicione o texto aqui"]').fill(feedback)
    page.locator('button:has-text("Finalizar")').click()
    page.wait_for_timeout(1500)


def grade_all_pending_for_student(page, student_url, totals):
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
        totals["suggestions"] += 1
        print(f"\nHomework: {activity_url}\nAssignment: {prompt}\nStudent response: {answer}")
        print(f"Suggested grade: {grade}\nSuggested feedback: {feedback}")
        approval = input("Submit this suggested grade? [y]es / [n]o, edit manually / [s]kip: ").strip().lower()
        if approval == "y":
            apply_and_submit_suggestion(page, grade, feedback)
            totals["submitted"] += 1
            print("Grade submitted.")
        elif approval == "n":
            print("Edit the grade and feedback manually in the browser, then submit it.")
            input("Press Enter when done to continue... ")
            totals["manual"] += 1
        else:
            print("Skipped without submitting.")
            totals["skipped"] += 1


def iterate_classes(page, totals):
    class_links = []
    page.goto(CLASSES_URL)

    while True:
        for href in page.locator('a[href*="/learning/teacher/classes/"]').evaluate_all("(els) => els.map(el => el.href)"):
            path = urlparse(href).path
            if not re.fullmatch(r"/learning/teacher/classes/\d+", path):
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
            grade_all_pending_for_student(page, student_url, totals)


def main():
    totals = {"suggestions": 0, "submitted": 0, "manual": 0, "skipped": 0}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})

        try:
            login(page)
            iterate_classes(page, totals)
            print(
                "\nGrading run complete: "
                f"{totals['suggestions']} AI suggestions, "
                f"{totals['submitted']} AI-suggested grades submitted, "
                f"{totals['manual']} manually graded, "
                f"{totals['skipped']} skipped."
            )
            input("Press Enter to close the browser... ")
        except Exception as error:
            print(f"The run stopped: {error}")
            input("The browser will stay open for inspection. Press Enter to close it... ")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
