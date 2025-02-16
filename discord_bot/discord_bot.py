import asyncio
import os
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime, time
from zoneinfo import ZoneInfo

import discord
import requests
import uvicorn
from discord.ext import tasks
from dotenv import load_dotenv
from fastapi import FastAPI
from Model import ErrorModel, JobResponse

load_dotenv()
JOBS_CHANNEL_ID = int(os.getenv('JOBS_CHANNEL_ID'))
COMMANDS_CHANNEL_ID = int(os.getenv('COMMANDS_CHANNEL_ID'))
ERROR_CHANNEL_ID = int(os.getenv('ERROR_CHANNEL_ID'))

app = FastAPI()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(client.start(os.getenv('BOT_TOKEN')))

@app.on_event("shutdown")
async def shutdown_event():
    await client.close()

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    await run_parser_task.start()
    await client.get_channel(COMMANDS_CHANNEL_ID).send("I'm online :thumbsup:")

@client.event
async def on_message(message):
    if (message.author == client.user
        or message.channel.name != "bot-commands"):
        return

    if message.content.startswith('/ping'):
        await pong()
    elif message.content.startswith('/exclude'):
        await exclude_word(message)
    elif message.content.startswith('/run'):
        await run_parser()
    elif message.content.startswith('/shutdown'):
        await shutdown()

async def exclude_word(message):
    invalid_message = "Invalid command: /exclude [company|title] ['word']"

    if client.status == discord.Status.do_not_disturb:
        await message.channel.send("Parser is currently running. Try again later.")
    
    msg_split = message.content.split(" ")
    if len(msg_split) != 3:
        await message.channel.send(invalid_message)
        return
    
    word = msg_split[2]
    try:
        response = None
        if msg_split[1] == "company":
            response = requests.put(f"{os.getenv('PARSER_URL')}/exclude-company", json={"word": word})
        elif msg_split[1] == "title":
            response = requests.put(f"{os.getenv('PARSER_URL')}/exclude-title", json={"word": word})
        else:
            await message.channel.send(invalid_message)
        
        if response:
            response.raise_for_status()
            await message.channel.send(f"Success: {response.text}")
    except requests.HTTPError as e:
        await message.channel.send(f"Error: received http status {e.response.status_code}")
    except requests.ConnectionError:
        await message.channel.send(f"Error: unable to connect to parser")

async def run_parser():
    channel = client.get_channel(COMMANDS_CHANNEL_ID)
    await channel.send("Calling parse API...")
    try:
        response = requests.get(f"{os.getenv('PARSER_URL')}/run", timeout=10)
        if response.status_code in (202, 200):
            await channel.send("Success: parser starting")
            await change_status(is_busy=True)
        else:
            await channel.send(f"Error: received http status {response.status_code}")
    except TimeoutError:
        await channel.send("Error: parse request timed out")
    except requests.ConnectionError:
        await channel.send(f"Error: unable to connect to parser")

async def change_status(is_busy: bool=False, is_sleep: bool=False):
    if is_busy is True and is_sleep is True:
        return
     
    if is_busy is True:
        status = discord.Status.do_not_disturb
        activity = discord.Game(name="LinkedIn")
    elif is_sleep is True:
        status = discord.Status.idle
        activity = discord.Game(name="Sleep")
    else:
        status = discord.Status.online
        activity = None
    await client.change_presence(status=status, activity=activity)

async def send_jobs_message(model: JobResponse):
    found_job = False
    message = "### Jobs Found\n"

    searches = model.searches
    for search_term, locations in searches.items():
        for location, job_postings in locations.items():
            if len(job_postings.items()) > 0:
                found_job = True
            message += f"__\"{search_term}\" in {location}: {len(job_postings.items())} result(s)__\n"
            if len(job_postings.items()) > 0:
                for id, job in job_postings.items():
                    title = job.title
                    company = job.company
                    url = job.url
                    message += f"{company} - {title}: <{url}>\n"
            else:
                message += "\n"
                continue
    
    try:
        if found_job is True:
            await client.get_channel(JOBS_CHANNEL_ID).send(message)
        else:
            await client.get_channel(JOBS_CHANNEL_ID).send("No matching jobs found")
    except Exception as e:
        print(f"Unable to send jobs message: {str(e)}")

async def send_error_message(error: str):
    message = "Received error message:\n"
    message += f"```{error}```"

    message_chunks = []
    max_message_len = 1900

    start = 0
    while start < len(message):
        end = start + max_message_len
        chunk = message[start:end]
        start = end

    try:
        for chunk in message_chunks:
            await client.get_channel(ERROR_CHANNEL_ID).send(chunk)
        await change_status(is_busy=False)
    except Exception as e:
        print(f"Unable to send error message: {str(e)}")

async def pong():
    channel = client.get_channel(COMMANDS_CHANNEL_ID)
    await channel.send("pong")
    try:
        response = requests.get(f"{os.getenv('PARSER_URL')}/ping")
        response.raise_for_status()
        await channel.send(f":green_circle: Parser up")
    except requests.HTTPError or requests.exceptions.ReadTimeout or requests.exceptions.ConnectTimeout:
        await channel.send(":red_circle: Parser error")
    except requests.ConnectionError:
        await channel.send(":red_circle: Parser down")

async def shutdown():
    await client.get_channel(COMMANDS_CHANNEL_ID).send("Sending shutdown signal...")
    try:
        requests.get(f"{os.getenv('PARSER_URL')}/shutdown")
    except requests.exceptions.RequestException:
        pass


# --- Repeating Task ---

pacific_tz = ZoneInfo('America/Los_Angeles')
times = [
    time(hour=0, tzinfo=pacific_tz),
    time(hour=8, tzinfo=pacific_tz),
    time(hour=9, tzinfo=pacific_tz),
    time(hour=10, tzinfo=pacific_tz),
    time(hour=11, tzinfo=pacific_tz),
    time(hour=12, tzinfo=pacific_tz),
    time(hour=13, tzinfo=pacific_tz),
    time(hour=14, tzinfo=pacific_tz),
    time(hour=15, tzinfo=pacific_tz),
    time(hour=16, tzinfo=pacific_tz),
    time(hour=17, tzinfo=pacific_tz),
    time(hour=18, tzinfo=pacific_tz),
    time(hour=19, tzinfo=pacific_tz),
    time(hour=20, tzinfo=pacific_tz),
    time(hour=21, tzinfo=pacific_tz),
    time(hour=22, tzinfo=pacific_tz),
    time(hour=23, tzinfo=pacific_tz),
    time(hour=23, tzinfo=pacific_tz),
]

@tasks.loop(time=times)
async def run_parser_task():
    pacific_time = datetime.now(ZoneInfo('America/Los_Angeles'))
    if pacific_time.hour == 0:
        await shutdown()
        await change_status(is_sleep=True)
    else:
        await run_parser()

# --- Fast API ---

@app.post("/receive")
async def receive_json(model: JobResponse):
    print("Received data!")
    await send_jobs_message(model)
    await change_status(is_busy=False)

@app.post("/error")
async def receive_error(model: ErrorModel):
    print("Received error!")
    await send_error_message(model.error)

@app.get("/test")
async def test_error():
    await send_error_message("Test error message")
    return "test error message"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)

signal.signal(signal.SIGTERM, sys.exit(0))
signal.signal(signal.SIGINT, sys.exit(0))