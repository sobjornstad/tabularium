# if true, display a warning that you're editing your actual data file rather
# than a programming test file
IS_PRODUCTION = True

# where the database file is
if IS_PRODUCTION:
    DATABASE_FILENAME = "/home/soren/cabinet/records.db"
else:
    DATABASE_FILENAME = "test.db"

# how many columns to optimize the display for
SCREEN_WIDTH = 80

# the title displayed at the top of the screen
if not IS_PRODUCTION:
    TITLE = "TEST -- "
else:
    TITLE = "  "
TITLE += "Records Project Paper Augmentation Software"

# the password needed to access the software
PASSWORD = ''

# the years between which you could reasonably be alive and have records to search
VALID_YEAR_RANGE = (1990, 2100)

# notebook setup
NOTEBOOK_TYPES = ['CB', 'TB', 'DB']
NOTEBOOK_SIZES = {'CB': 80, 'TB': 240, 'DB': 240} # in pages
