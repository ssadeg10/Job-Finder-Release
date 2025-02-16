from Job import Job


class JobDB:
    def __init__(self, job: Job, stage: str, discarded: bool):
        self.info = job
        self.stage = stage
        self.discarded = discarded