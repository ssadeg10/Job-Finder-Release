import os
import re

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# Note: Rate limit of 1,000 requests per day
# CHAT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
QA_MODEL = "deepset/roberta-base-squad2"
load_dotenv()

client = InferenceClient(
    api_key=os.getenv("API_TOKEN"), 
    headers={"x-wait-for-model": "true", "x-use-cache": "false"}
)

#! change variations based on education in .env
degree_variations = {
    "bachelor",
    "bachelor's",
    "bs ",
    "b.s ",
    " bs",
    " b.s",
}
questions = [
    "What is the degree required?",
    "How many years of experience?"
]
alt_question_1 = [
    "What is the educational degree required?",
    "What is the minimum degree required?"
]
alt_question_2 = [
    "How many years of work experience?",
    f"How many years of {degree_variations[0]} experience?",
]

def job_desc_match_qualifications(job_desc: str, education: str, years_exp) -> bool:
    attempts = 0
    while attempts < 3:
        if attempts > 0:
            questions[0] = alt_question_1[attempts - 1]
            questions[1] = alt_question_2[attempts - 1]
        qa_pairs: dict = question_answer(questions, job_desc)
        answer_string = " ".join(qa_pairs.values()).strip().lower().replace(".", "")
        numbers = re.findall(r'\d+', answer_string)
        le = len(numbers)
        if le > 0:
            break
        attempts += 1

    years = int(years_exp)

    if any(value in answer_string for value in degree_variations) \
    or any(value in job_desc.strip().lower() for value in degree_variations):
        if le == 0:
            return True
        elif le == 1:
            return years in (le - 1, le, le + 1)
        else:
            min_val = int(min(numbers))
            max_val = int(max(numbers))
            return min_val <= years <= max_val
    else:
        return False
    
def question_answer(questions: list, description):
    answers = {}
    for q in questions:
        result = client.question_answering(
            model=QA_MODEL,
            question=q,
            context=description
        )
        answers[q] = result.answer
    return answers

# def status():
#     status = client.get_model_status(QA_MODEL)
#     return status.loaded, status.state
