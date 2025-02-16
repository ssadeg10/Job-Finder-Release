class Job:
    def __init__(self, id: int, title, company, location, description="", logo=None, matching_keywords: list[str]=None, years_exp=None):
        self.id = id
        self.title = title
        self.company = company
        self.location = location
        self.description = description
        self.logo = logo
        self.matching_keywords = matching_keywords
        self.years_exp = years_exp
    
    def __str__(self):
        return "\nid: %s\ntitle: %s\ncompany: %s\nlocation: %s\n" % (self.id, self.title, self.company, self.location)
    
    def get_url(self):
        return f"https://www.linkedin.com/jobs/view/{self.id}"