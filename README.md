# Job Finder

A fully automated system that finds relevant job posts from LinkedIn based on search preferences and sends job matches as a Discord message.

https://github.com/user-attachments/assets/98088623-f950-4b3c-9a5c-27ee7e7b04af

## Description

The system is made up of two machines in an sort-of asynchronous master-slave configuration: one running the discord bot that acts as an interface and scheduler, and the other which does the job parsing.

This diagram is a working setup configured on a Raspberry Pi 1B and a mini NUC PC:
![System diagram](/assets/Diagram%201.png)
When the Parser script is started, Selenium starts up, logs into LinkedIn using the user's credentials, and goes page-by-page emulating clicks and scrolls. There are three stages in which jobs are narrowed down unil they meet all criteria:

1. <u>Filtering:</u> keep jobs that do not contain certain words in either the title, company, or location.
2. <u>Keyword Matching:</u> keeps jobs that meet the threshold of keywords found in a job's description.
3. <u>Qualification Matching:</u> keeps jobs that match the education and years experience requirements found in a job's description.

Throughout the process, each job is tracked in a SQLite database based on the stage running. This lets the script pick-up valid jobs left incomplete due to power outages or system errors.

This is a high-level overview of the Parser script, where each stage passes a list of valid jobs:
![Parser overview](/assets/Diagram%202.png)

## Getting Started

This is a monorepo that contains both `discord_bot` and `parser`, each of which should be installed on separate machines.

### Dependencies

A requirements file is provided in each project, which can be installed using pip package installer:
`pip install -U -r requirements.txt`

### Setup

A template `.env` file is provided in each project that should be populated with respecive values.

In the parser project, the file `filters.json` should be populated with respective values used for filtering jobs. Also, `inference.py` has a list called `degree_variations` that should be modified if you aren't using a Bachelor's degree as the education filter.

Both projects contain a startup script that should be configured to execute on startup/boot for each respective machine.

The Discord bot (`discord_bot.py`) uses times to automatically call the parser. The timezone should be changed if not 'America/Los_Angeles'.

For full automation, in Windows, you should use Microsoft's Autologon tool so that the login prompt doesn't block the script executing. Additionally, the PC should be set to turn on automatically at a set time before the first run time of the discord bot task by configuring the BIOS (see System diagram above).

### Executing program

The system should run automatically after rebooting each machine. The `/run` discord command can be used to manually call the Parser.
