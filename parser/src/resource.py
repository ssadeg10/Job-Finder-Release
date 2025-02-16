import json
import os
import subprocess
import sys
import traceback
import uuid

from fastapi import Body, FastAPI
from fastapi.responses import Response

app = FastAPI()
filters_file = 'filters.json'

@app.get("/run")
def run():
    response = Response(status_code=202)
    try:
        subprocess.Popen([sys.executable, "parse.py"])
    except Exception:
        response = {
            "message": "Parser execution failed", 
            "error": traceback.format_exc()
        }
    return response

@app.put("/exclude-company", status_code=200)
def exclude_company(body: dict = Body(...)):
    word = body['word']
    add_excluded_word(key='excluded_companies', value=word)
    return word

@app.put("/exclude-title", status_code=200)
def exclude_title(body: dict = Body(...)):
    word = body['word']
    add_excluded_word(key='excluded_title_words', value=word)
    return word

@app.get("/ping")
def pong():
    return "pong"

@app.get("/shutdown")
def shutdown():
    subprocess.run(["shutdown", "-s"])
    sys.exit(0)

def add_excluded_word(key, value):
    with open(filters_file, 'r') as f:
        data = json.load(f)
        data[key].append(value)
    
    # create randomly named temporary file to avoid 
    # interference with other thread/asynchronous request (thanks stackoverflow)
    temp_file = os.path.join(os.path.dirname(filters_file), str(uuid.uuid4()))

    with open(temp_file, 'w') as f:
        json.dump(data, f, indent=4)
    
    os.replace(temp_file, filters_file)