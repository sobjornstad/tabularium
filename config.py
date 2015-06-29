# if true, display a warning that you're editing your actual data file rather
# than a programming test file
IS_PRODUCTION = False

# where the database file is
if IS_PRODUCTION:
    DATABASE_FILENAME = "/home/soren/cabinet/records.db"
else:
    DATABASE_FILENAME = "records.db"
    #DATABASE_FILENAME = "test.db"

# the password needed to access the software
PASSWORD = ''

# the years between which you could reasonably be alive and have records to search
VALID_YEAR_RANGE = (1990, 2100)

# notebook setup
NOTEBOOK_TYPES = ['CB', 'TB', 'DB']
NOTEBOOK_SIZES = {'CB': 80, 'TB': 240, 'DB': 240} # in pages
