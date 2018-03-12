import sys
from setting_io import *

def getSettings():
    settings = Settings()
    settings.loadSettings()
    setting = settings.getSettings()
    # print("setting : "+str(setting))
    return setting
