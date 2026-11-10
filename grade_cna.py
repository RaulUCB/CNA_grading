from getpass import getpass
import json
import os
import re
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

BASE_URL = "https://app.cna.com.br"
CLASSES_URL = f"{BASE_URL}/learning/teacher/classes"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = os.getenv("CNA_GRADING_MODEL", "qwen2.5:3b")
ENGLISH_MARKERS = {
    "a", "about", "after", "all", "am", "an", "and", "are", "as", "at", "be",
    "because", "been", "before", "but", "by", "can", "did", "do", "for", "from",
    "get", "go", "had", "has", "have", "he", "her", "him", "his", "i", "if", "in",
    "into", "is", "it", "its", "like", "me", "my", "of", "on", "or", "our", "she",
    "so", "than", "that", "the", "their", "them", "they", "this", "to", "was", "we",
    "were", "what", "when", "where", "which", "who", "will", "with", "would", "you",
    "your",
}
PORTUGUESE_MARKERS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos", "e",
    "ela", "elas", "ele", "eles", "em", "era", "essa", "esse", "esta", "este", "eu",
    "foi", "foram", "isso", "isto", "mais", "mas", "meu", "minha", "na", "nas",
    "nem", "no", "nos", "nossa", "o", "os", "ou", "para", "pela", "pelas", "pelo",
    "pelos", "por", "qual", "que", "se", "sem", "ser", "seu", "sua", "tambem", "um",
    "uma", "voce",
}


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


def is_pending_activity(text):
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = " ".join(normalized.casefold().split())
    return any(
        status in normalized
        for status in (
            "a corrigir",
            "por corrigir",
            "pendente",
            "pending",
            "to grade",
            "to be graded",
            "awaiting correction",
            "awaiting grading",
        )
    )


def is_pending_activity_link(link, link_text):
    if is_pending_activity(link_text):
        return True

    parent = link.locator("xpath=..")
    for _ in range(4):
        if parent.count() == 0:
            break
        if is_pending_activity(parent.inner_text()):
            return True
        parent = parent.locator("xpath=..")
    return False


def is_english_response(answer, model_assessment):
    normalized = unicodedata.normalize("NFKD", answer.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    words = set(re.findall(r"[a-z]+", normalized))
    english_score = len(words & ENGLISH_MARKERS)
    portuguese_score = len(words & PORTUGUESE_MARKERS)

    if english_score >= 2 and english_score > portuguese_score:
        return True
    if portuguese_score >= 2 and portuguese_score > english_score:
        return False
    return model_assessment


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
        "This is an English-language test, so the student's answer must be written in English. "
        "Assess whether the answer is in English, understandable and coherent, and relevant "
        "to the assignment. Judge the language of the student's actual sentence, not the "
        "assignment, names, places, or isolated foreign words. English responses may contain "
        "grammar, spelling, or punctuation errors and are still English. The words 'I', "
        "'went', 'with', 'we', 'the', 'to', and 'afterward' are English; a sentence using "
        "ordinary English words is not Portuguese just because it mentions a Portuguese "
        "place or has spelling errors. A response written in Portuguese or another language "
        "is not acceptable even if understandable and relevant; do not correct its grammar "
        "or vocabulary. For a non-English response, set in_english to false and use the exact "
        "feedback 'Please answer in English.' For an English response, grammar mistakes do "
        "not make an otherwise understandable, relevant answer wrong. Give at most one brief "
        "grammar correction in feedback, or use an empty string. Never rewrite the student's "
        "response or add examples. Keep feedback under 15 words. Return only one complete "
        "JSON object with boolean fields in_english, understandable, relevant and string "
        "field feedback. Do not assign a grade."
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
            "num_predict": 256,
        },
    }
    request = Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    result = None
    for attempt in range(2):
        try:
            with urlopen(request, timeout=600) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace").strip()
            if error.code >= 500 and attempt == 0:
                time.sleep(2)
                continue
            raise RuntimeError(
                f"Ollama returned HTTP {error.code} for model {OLLAMA_MODEL}: "
                f"{details[:500] or error.reason}"
            ) from error
        except (URLError, TimeoutError) as error:
            if attempt == 0:
                time.sleep(2)
                continue
            raise RuntimeError(
                f"Could not connect to Ollama at {OLLAMA_URL} for model "
                f"{OLLAMA_MODEL}: {error}"
            ) from error

    if not isinstance(result, dict) or not isinstance(result.get("response"), str):
        raise RuntimeError("Ollama returned a response without a generated result.")
    try:
        suggestion = json.loads(result["response"])
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Ollama returned invalid JSON for model {OLLAMA_MODEL}: "
            f"{result['response'][:500]}"
        ) from error

    in_english = suggestion.get("in_english")
    understandable = suggestion.get("understandable")
    relevant = suggestion.get("relevant")
    if (
        not isinstance(in_english, bool)
        or not isinstance(understandable, bool)
        or not isinstance(relevant, bool)
    ):
        raise RuntimeError("The local model returned invalid assessment fields.")

    model_says_english = in_english
    in_english = is_english_response(answer, model_says_english)
    grade = decide_grade(in_english, understandable, relevant)
    if not in_english:
        return grade, "Please answer in English. Your response must be written in English."
    if not model_says_english:
        feedback = (
            "Your answer is in English and addresses the assignment. Well done."
            if grade == "Correct"
            else "Your answer is in English. Please make sure it clearly answers the assignment."
        )
        return grade, feedback

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


def decide_grade(in_english, understandable, relevant):
    return "Correct" if in_english and understandable and relevant else "Incorrect"


def activity_editability_issue(page):
    for radio_name in ("Correto", "Incorreto"):
        radio = page.get_by_role("radio", name=radio_name, exact=True)
        if radio.count() != 1 or not radio.is_enabled():
            return f"The {radio_name} grade option is missing or disabled."
    return None


def apply_and_submit_suggestion(page, grade, feedback):
    radio_name = "Correto" if grade == "Correct" else "Incorreto"
    radio = page.get_by_role("radio", name=radio_name, exact=True)
    issue = activity_editability_issue(page)
    if issue:
        raise RuntimeError(f"{issue} Nothing was submitted.")

    radio.evaluate(
        "(element) => {"
        " const label = element.labels && element.labels[0];"
        " if (!label) throw new Error('Grade option has no visible label.');"
        " label.click();"
        "}"
    )
    if not radio.is_checked():
        raise RuntimeError(f"The {radio_name} grade option could not be selected.")

    feedback_field = page.locator('textarea[placeholder="Adicione o texto aqui"]')
    feedback_field.wait_for(state="visible")
    if not feedback_field.is_enabled():
        raise RuntimeError("The feedback field is disabled; nothing was submitted.")
    feedback_field.fill(feedback)

    submit_button = page.locator('button:has-text("Finalizar")')
    submit_button.wait_for(state="visible")
    if not submit_button.is_enabled():
        raise RuntimeError("The Finalizar button is disabled; nothing was submitted.")
    submit_button.click()
    page.wait_for_timeout(1500)


def grade_all_pending_for_student(page, student_url, totals):
    page.goto(student_url)
    page.wait_for_load_state("networkidle")
    seen_activity_links = set()
    activity_elements = page.locator('a[href*="/activity/"]').all()

    pending_links = []
    for link in activity_elements:
        href = link.get_attribute("href")
        text = (link.text_content() or "").strip()
        if not href or not is_pending_activity_link(link, text):
            continue
        activity_url = normalize_url(href)
        if activity_url not in seen_activity_links:
            seen_activity_links.add(activity_url)
            pending_links.append(activity_url)

    totals["activity_links"] += len(activity_elements)
    totals["pending_activities"] += len(pending_links)

    for activity_url in pending_links:
        page.goto(activity_url)
        page.wait_for_load_state("networkidle")
        issue = activity_editability_issue(page)
        if issue:
            totals["uneditable"] += 1
            print(f"\nSkipping non-editable activity {activity_url}: {issue}")
            continue

        prompt, answer = get_activity_content(page)
        grade, feedback = suggest_grade(prompt, answer)
        totals["suggestions"] += 1
        print(f"\nHomework: {activity_url}\nAssignment: {prompt}\nStudent response: {answer}")
        print(f"Suggested grade: {grade}\nSuggested feedback: {feedback}")
        if totals["auto_approve"]:
            print("Auto-yes is enabled; submitting this suggestion.")
            approval = "y"
        else:
            approval = input(
                "Submit this suggested grade? [y]es / [a]uto-yes from now on / "
                "[n]o, edit manually / [s]kip: "
            ).strip().lower()
            if approval == "a":
                totals["auto_approve"] = True
                print("Auto-yes enabled for the rest of this run.")
                approval = "y"

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
    page.wait_for_load_state("networkidle")

    while True:
        for href in page.locator('a[href*="/learning/teacher/classes/"]').evaluate_all("(els) => els.map(el => el.href)"):
            path = urlparse(href).path
            if not re.fullmatch(r"/learning/teacher/classes/[^/]+/?", path):
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

    if not class_links:
        raise RuntimeError(
            "No class links were found. Confirm that login succeeded and that "
            "the classes page lists at least one class."
        )

    print(f"Found {len(class_links)} class(es).")
    for class_url in class_links:
        students_url = class_url.rstrip("/") + "/writing/students"
        print(f"Opening class students: {students_url}")
        page.goto(students_url)
        page.wait_for_load_state("networkidle")
        student_links = collect_unique_links(page, 'a[href*="/writing/students/"]')
        if not student_links:
            print(f"No student links found at {students_url}")
        before_activity_links = totals["activity_links"]
        before_pending_activities = totals["pending_activities"]
        for student_url in student_links:
            grade_all_pending_for_student(page, student_url, totals)
        class_activity_links = totals["activity_links"] - before_activity_links
        class_pending_activities = totals["pending_activities"] - before_pending_activities
        print(
            f"Class scan: {len(student_links)} student link(s), "
            f"{class_activity_links} activity link(s), "
            f"{class_pending_activities} pending activity/activities."
        )
        if class_activity_links and not class_pending_activities:
            print(
                "Activity links were found, but none had a recognized pending "
                "status; no grades were changed for this class."
            )


def main():
    totals = {
        "suggestions": 0,
        "submitted": 0,
        "manual": 0,
        "skipped": 0,
        "activity_links": 0,
        "pending_activities": 0,
        "uneditable": 0,
        "auto_approve": False,
    }
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
                f"{totals['skipped']} skipped, "
                f"{totals['uneditable']} non-editable/already graded, "
                f"{totals['activity_links']} activity links checked, "
                f"{totals['pending_activities']} marked pending."
            )
            input("Press Enter to close the browser... ")
        except Exception as error:
            print(f"The run stopped: {error}")
            input("The browser will stay open for inspection. Press Enter to close it... ")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
