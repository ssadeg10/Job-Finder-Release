import json
import sqlite3
from datetime import date, datetime, timedelta

import pytz

from Job import Job
from JobDB import JobDB

DB_PATH = "db/jobs.db"
DAYS_CACHED = 29

class Database:
    init_run: bool = True

    def __init__(self, db_file = None):
        if db_file:
            self.connection = sqlite3.connect(db_file)
        else:
            self.connection = sqlite3.connect(DB_PATH)
        self.cursor = self.connection.cursor()
        
        if Database.init_run is True:
            self.create_table()
            Database.init_run = False

        day = date.today().day
        if day in (15, 28):
            self.delete_expired()

    def create_table(self):
        # discarded is a boolean value (0/1)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS linkedin (
                id INTEGER NOT NULL PRIMARY KEY,
                title TEXT DEFAULT '',
                company TEXT DEFAULT '',
                location TEXT DEFAULT '',
                description TEXT DEFAULT '',
                keywords TEXT DEFAULT '',
                stage TEXT DEFAULT '',
                discarded INTEGER DEFAULT 0,
                expiration TEXT DEFAULT ''
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS parameters (
                last_run TEXT DEFAULT ''
            )
        ''')
        self.cursor.execute('''
            INSERT INTO parameters (last_run)
            SELECT ''
            WHERE NOT EXISTS (SELECT 1 FROM parameters)
        ''')
        self.connection.commit()

    def create(self, job: JobDB):
        best_by = date.today() + timedelta(days=DAYS_CACHED)
        info = job.info
        self.cursor.execute('''
            INSERT INTO linkedin 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (info.id, info.title, info.company, \
            info.location, info.description, None, \
                job.stage, job.discarded, best_by,))
        self.connection.commit()
        return self.cursor.lastrowid

    def read(self, id: int):
        self.cursor.execute('''
            SELECT * FROM linkedin
            WHERE id = ?
        ''', (id,))
        return self.cursor.fetchone()

    def update(self, id: int, description: str = None, 
            keywords: str = None, stage: str = None, discarded: bool = None):
        if description is not None:
            self.cursor.execute('''
                UPDATE linkedin
                SET description = ?
                WHERE id = ?
            ''', (description, id,))
        if keywords is not None:
            self.cursor.execute('''
                UPDATE linkedin
                SET keywords = ?
                WHERE id = ?
            ''', (keywords, id,))
        if stage is not None:
            self.cursor.execute('''
                UPDATE linkedin
                SET stage = ?
                WHERE id = ?
            ''', (stage, id,))
        if discarded is not None:
            self.cursor.execute('''
                UPDATE linkedin
                SET discarded = ?
                WHERE id = ?
            ''', (discarded, id,))
        self.connection.commit()

    def delete(self, id: int):
        self.cursor.execute('''
            DELETE FROM linkedin
            WHERE id = ?
        ''', (id,))
        self.connection.commit()
    
    def delete_expired(self):
        self.cursor.execute('''
            DELETE FROM linkedin
            WHERE expiration < ?
        ''', (date.today(),))
        self.connection.commit()
    
    def get_all_stage(self, stage, discarded) -> list[JobDB]:
        self.cursor.execute('''
            SELECT * FROM linkedin
            WHERE stage = ?
            AND discarded = ?
        ''', (stage, discarded,))
        fetch_list = self.cursor.fetchall()
        jobs_list = []
        for entry in fetch_list:
            jobs_list.append(
                JobDB(Job(
                    id=entry[0],
                    title=entry[1],
                    company=entry[2],
                    location=entry[3],
                    description=entry[4],
                    matching_keywords=json.loads(entry[5] or '{}')
                ), stage=entry[6], discarded=entry[7])
            )
        return jobs_list


    def id_exists(self, id: int) -> bool:
        return self.read(id) is not None
    
    def get_last_run(self):
        self.cursor.execute("SELECT last_run FROM parameters LIMIT 1")
        last_run = self.cursor.fetchone()
        return last_run[0]

    def update_last_run(self):
        pacific = pytz.timezone('US/Pacific')
        now = datetime.now(pacific).strftime("%Y-%m-%d %H:%M")
        self.cursor.execute('''
            UPDATE parameters
            SET last_run = ?
            WHERE rowid = ?
        ''', (now, 1,))
        self.connection.commit()
    
    def close_connection(self):
        self.connection.close()

db = Database()
db.get_all_stage("parse", False)