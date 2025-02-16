import json
import logging
import os
import time
import traceback

import inference
import requests
from Database import Database
from dotenv import load_dotenv
from Job import Job
from JobDB import JobDB
from JobResponse import JobPosting, JobResponse
from selenium import webdriver
from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException,
                                        TimeoutException)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import \
    expected_conditions as ExpectedConditions
from selenium.webdriver.support.relative_locator import locate_with
from selenium.webdriver.support.wait import WebDriverWait

logger = logging.getLogger(__name__)
log_handler = logging.basicConfig(level='INFO')
logger.info("parse.py starting.")

options = Options()
options.add_argument("--disable-gpu")
options.add_argument("--log-level=3")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, timeout=10, poll_frequency=0.5)

STAGE_PARSE = "parse"
STAGE_KEYWD = "keyword"
STAGE_QUALF = "qualification"
STAGE_MATCH = "match"
STAGE_PREP_SEND = "prep_send"
STAGE_CMPLT = "completed"

load_dotenv()

def main():
    json_response = JobResponse(searches={})
    completed_ids = []

    filters: dict = load_filters()

    try:
        navigate_jobs()
        login()
        wait.until(ExpectedConditions.url_changes)
        if "Security Verification" in driver.title:
            logger.warning("Redirected to security verification")

        db = Database()
        for title, location in filters['search_params'].items():
            if title not in json_response.searches:
                json_response.searches[title] = {}
            if location not in json_response.searches[title]:
                json_response.searches[title][location] = {}

            id_update_list = []

            search(title, location)
            filter_recent_24hr()
            wait_for_jobs_list_update()
            
            jobs_list = parse_jobs(db=db, filters=filters)
            jobs_list_keyword_match = match_keywords(jobs_list=jobs_list, db=db, filters=filters)
            jobs_list_full_match = match_qualifications(
                jobs_list=jobs_list_keyword_match, 
                db=db,
                education=filters['user']['education'],
                years_exp=filters['user']['years_exp'].get(title)
            )

            # populate response object with data
            for job in jobs_list_full_match:
                completed_ids.append(job.id)
                id_update_list.append(job.id)
                
                json_response.searches[title][location][f"{job.id}"] = JobPosting(
                    title=truncate(job.title, max_len=42),
                    company=truncate(job.company, max_len=20),
                    url=job.get_url()
                )
            
            # prepare jobs for send stage
            for id in id_update_list:
                db.update(id, stage=STAGE_PREP_SEND)

            navigate_jobs()
        logout()
        driver.close()
        send_jobs(db, json_response, completed_ids)
        db.update_last_run()
    except Exception as e:
        logger.error(e, exc_info=True)
        stack: str = traceback.format_exc()
        if stack:
            send_error(stack)
        else:
            send_error(str(e))
    finally:
        driver.quit()
        db.close_connection()
        exit()

# --- Helper Functions ---

def login():
    wait.until(lambda d: driver.execute_script("return document.readyState") == "complete")
    session_key = driver.find_element(By.ID, "session_key")
    session_password = driver.find_element(By.ID, "session_password")
    submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")

    wait.until(ExpectedConditions.element_to_be_clickable(session_key))
    session_key.send_keys(os.getenv("SESSION_KEY"))
    session_password.send_keys(os.getenv("SESSION_PASSWORD"))
    wait.until(ExpectedConditions.element_to_be_clickable(submit_button))
    submit_button.click()

    # Wait for 2FA
    wait.until(ExpectedConditions.title_contains("Jobs"))
    time.sleep(1)

def logout():
    profile_img = driver.find_element(By.XPATH, "//img[@width='24']")
    profile_img.click()
    time.sleep(0.5)
    logout_button = driver.find_element(By.XPATH, "//a[@href='/m/logout/']")
    logout_button.click()
    time.sleep(3)

def navigate_jobs():
    driver.get("https://www.linkedin.com/jobs")
    wait.until(ExpectedConditions.title_contains("Jobs"))
    time.sleep(1)

def search(title: str, location: str):
    logger.info(f"Search: \"{title}\" in {location}")
    recent_searches = driver.find_element(By.XPATH, "//ul[@aria-label='Recent job searches']")
    recent_searches_list = recent_searches.find_elements(By.TAG_NAME, "li")

    try:
        for li in recent_searches_list:
            text = li.text
            if title in text and location in text:
                logger.info("Search: using recent search")
                li.click()
                return
        
        # new search
        search_box_title = driver.find_element(By.XPATH, "//input[@aria-label='Search by title, skill, or company']")
        search_box_title.clear()
        search_box_title.send_keys(title)

        search_box_location = driver.find_element(By.XPATH, "//input[@aria-label='City, state, or zip code']")
        search_box_location.clear()
        search_box_location.send_keys(location + Keys.ENTER)
    except StaleElementReferenceException:
        pass
    finally:
        wait.until(ExpectedConditions.title_contains(title))

def filter_recent_24hr():
    time.sleep(1.5)
    try:
        # filter by most recent, past 24 hours
        all_filters_button = driver.find_element(By.CLASS_NAME, "search-reusables__all-filters-pill-button")
        wait.until(ExpectedConditions.element_to_be_clickable(all_filters_button))
        all_filters_button.click()
    except StaleElementReferenceException:
        pass

    try:
        filters_panel = driver.find_element(By.XPATH, "//div[@aria-labelledby='reusable-search-advanced-filters-right-panel']")
    except StaleElementReferenceException:
        pass
    time.sleep(1.5)

    attempts = 0
    while attempts < 3:
        try:
            most_recent = filters_panel.find_element(By.XPATH, ".//label[@for='advanced-filter-sortBy-DD']")
            wait.until(ExpectedConditions.element_to_be_clickable(most_recent))
            most_recent.click()

            past_24hr = filters_panel.find_element(By.XPATH, ".//label[@for='advanced-filter-timePostedRange-r86400']")
            wait.until(ExpectedConditions.element_to_be_clickable(past_24hr))
            past_24hr.click()

            show_results_button = filters_panel.find_element(By.XPATH, ".//button[@data-test-reusables-filters-modal-show-results-button]")
            wait.until(ExpectedConditions.element_to_be_clickable(show_results_button))
            show_results_button.click()
            return
        except StaleElementReferenceException:
            attempts += 1

def wait_for_jobs_list_update():
    list_locator = locate_with(By.TAG_NAME, "div").below({By.CLASS_NAME: "jobs-search-results-list__header"})
    list_div = driver.find_element(list_locator)
    initial_val = list_div.get_attribute("class")
    try:
        # wait until list element class value changes, singnifies DOM updated with new result
        wait.until_not(lambda driver: list_div.get_attribute("class") == initial_val)
    except StaleElementReferenceException:
        logger.debug("StaleElementReferenceException")

def parse_jobs(db: Database, filters: dict, parse_viewed = False) -> list[Job]:
    logger.info("Parsing Jobs...")
    parsed_jobs: list[Job] = []
    repeat_counter = 0
    stop_parsing = False

    parsed_jobs = append_interrupted_jobs(db, parsed_jobs, STAGE_PARSE)

    # # maybe make this a feature flag in future
    # # skip viewed jobs by default

    for page_i in range(1, 40):
        logger.info(f"page {page_i}")
        time.sleep(1)

        attempts = 0
        while attempts < 2:
            if len(driver.find_elements(By.CLASS_NAME, "jobs-search-no-results-banner")) > 0:
                driver.refresh()
                time.sleep(0.1)
                wait.until_not(ExpectedConditions.title_is("LinkedIn"))
                attempts += 1
            else:
                break
        
        # get filters
        excluded_titles_set = set(filters['excluded_title_words'])
        excluded_companies_set = set(filters['excluded_companies'])
        excluded_locations_set = set(filters['excluded_expanded_locations'])

        attempts = 0
        while attempts < 2:
            try:
                list_element = driver.find_element(By.XPATH, "//div[@data-results-list-top-scroll-sentinel]/following-sibling::ul")
                job_list = list_element.find_elements(By.TAG_NAME, "li")
                break
            except StaleElementReferenceException:
                pass
            attempts += 1

        # scroll to preload all jobs in list
        scroll_origin = ScrollOrigin.from_element(job_list[0])
        delta_y = 660   # 132 * 5
        ActionChains(driver)\
            .scroll_from_origin(scroll_origin, 0, 0)\
            .pause(0.1)\
            .scroll_from_origin(scroll_origin, 0, delta_y * 1)\
            .pause(0.1)\
            .scroll_from_origin(scroll_origin, 0, delta_y * 2)\
            .pause(0.1)\
            .scroll_from_origin(scroll_origin, 0, delta_y * 3)\
            .pause(0.1)\
            .scroll_from_origin(scroll_origin, 0, delta_y * 4)\
            .pause(0.1)\
            .scroll_from_origin(scroll_origin, 0, delta_y * 5)\
            .pause(0.1)\
            .scroll_from_origin(scroll_origin, 0, delta_y * 5)\
            .pause(0.1)\
            .scroll_from_origin(scroll_origin, 0, delta_y * 6)\
            .perform()

        # parse each job
        for job in job_list:
            # check id exists
            id = job.get_attribute("data-occludable-job-id")
            if not id:
                continue

            # check database if id has been parsed already
            if db.id_exists(id) is True:
                repeat_counter += 1
                # Stop parsing if encountered multiple viewed jobs in a row
                if (repeat_counter > 4):
                    logger.info("Stopping parse.")
                    stop_parsing = True
                    break
                continue
            
            try:
                title = job.find_element(By.TAG_NAME, "strong").text
                company = job.find_element(By.CLASS_NAME, "artdeco-entity-lockup__subtitle").text
                location = job.find_element(By.CLASS_NAME, "artdeco-entity-lockup__caption").text

                # if (excluded titles) or (excluded companies) or (excluded location)
                if (
                    any(substr in title for substr in excluded_titles_set)
                    or any(company in excluded_company for excluded_company in excluded_companies_set)
                    or any(location in excluded_location for excluded_location in excluded_locations_set)
                ):
                    db.create(JobDB(Job(id, title, company, location), stage=STAGE_PARSE, discarded=True))
                    continue

            except NoSuchElementException:
                continue
            
            db.create(JobDB(Job(id, title, company, location), stage=STAGE_PARSE, discarded=False))
            parsed_jobs.append(Job(id, title, company, location))
        
        # reset counter on each page
        repeat_counter = 0
        if stop_parsing:
            break

        # go to next page
        try:
            pages_end = driver.find_element(By.CLASS_NAME, "query-expansion-suggestions")
        except NoSuchElementException:
            # while not end of pages
            current_url = driver.current_url
            next_page = f"{current_url}&start={25 * page_i}"
            driver.get(next_page)
            wait.until(ExpectedConditions.title_contains("Jobs"))
        else:
            logger.info("Parse Job: Reached last page")
            break

    logger.info(f"Total: {len(parsed_jobs)} jobs")
    return parsed_jobs

def match_keywords(jobs_list: list[Job], db: Database, filters: dict, threshold = 2) -> list[Job]:
    logger.info("Matching Keywords...")
    match_keywords_set = set(filters['match_keywords'])

    new_jobs_list = append_interrupted_jobs(db, jobs_list, STAGE_KEYWD)
    
    for job in jobs_list:
        marked_error = False
        
        # go to job url
        driver.get(f"https://www.linkedin.com/jobs/view/{job.id}")
        time.sleep(3.2) # will get http 429 error without this (too many requests)

        attempts = 0
        while attempts < 4:
            try:
                wait.until(ExpectedConditions.presence_of_element_located((By.TAG_NAME, "Article")))
                description = driver.find_element(By.ID, "job-details")
            except NoSuchElementException:
                print("keyword stage exception.")
                if attempts >= 3:
                    marked_error = True
                    break
                driver.refresh()
                time.sleep(1 + attempts)
            attempts += 1
        
        desc_lower = description.text.lower()

        if marked_error or not desc_lower:
            db.update(job.id, stage=STAGE_KEYWD, discarded=True, keywords="ERROR")
            print(f"marked invalid: {job.id}")
            continue

        # check description and add to list if it meets/exceeds threshold
        # threshold should be adjustable through parameter
        count = 0
        matched_keywords = []
        for keyword in match_keywords_set:
            if keyword.lower() in desc_lower:
                count += 1
                matched_keywords.append(keyword)

        if count >= threshold:
            job.description = description.text.strip()
            job.matching_keywords = matched_keywords
            keywords_str = json.dumps(matched_keywords)
            db.update(job.id, description=job.description, keywords=keywords_str, stage=STAGE_KEYWD)
            new_jobs_list.append(job)
        else:
            db.update(job.id, stage=STAGE_KEYWD, discarded=True)
    
    logger.info(f"{len(new_jobs_list)} matches out of {len(jobs_list)}")
    return new_jobs_list

def match_qualifications(jobs_list: list[Job], db: Database, education, years_exp) -> list[Job]:
    logger.info("Matching Qualifications...")
    new_jobs_list = append_interrupted_jobs(db, jobs_list, STAGE_QUALF)

    for job in jobs_list:
        is_match = inference.job_desc_match_qualifications(job.description, education, years_exp)
        if is_match is True:
            db.update(job.id, stage=STAGE_QUALF)
            new_jobs_list.append(job)
        else:
            # remove description to save space on DB
            db.update(job.id, description='', stage=STAGE_QUALF, discarded=True)
        time.sleep(1)
    
    logger.info(f"{len(new_jobs_list)} matches out of {len(jobs_list)}")
    return new_jobs_list

def append_interrupted_jobs(db: Database, jobs_list: list[Job], stage: str) -> list[Job]:
    job_ids = [job.id for job in jobs_list]
    counter = 0

    # get all cached jobs that haven't been discarded (resume processing)
    cached_list: list[JobDB] = db.get_all_stage(stage=stage, discarded=False)
    for job_db in cached_list:
        cached_id = job_db.info.id
        if cached_id not in job_ids:
            jobs_list.append(job_db.info)
            counter += 1
    
    if counter > 0:
        logger.info(f"Including {counter} interrupted job(s) found in database...")

    return jobs_list

def send_jobs(db: Database, json_response: JobResponse, completed_ids):
    logger.info("Sending jobs...")
    response = requests.post(f"{os.getenv('BOT_URL')}/receive", json=json_response.model_dump())
    response.raise_for_status()
    
    for id in completed_ids:
        db.update(id, stage=STAGE_CMPLT)

def send_error(error):
    logger.info("Sending error message...")
    requests.post(f"{os.getenv('BOT_URL')}/error", json={"error": error})

def load_filters():
    with open('filters.json', 'r') as f:
        return json.load(f)

def truncate(str, max_len):
    if len(str) > max_len:
        return str[:max_len] + "..."
    else:
        return str

if __name__ == "__main__":
    main()