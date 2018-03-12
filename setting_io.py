import sys
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, dump, ElementTree
from common_util import *

settings_file_name = 'config.xml'

class Settings:
    global settings_file_name
    def __init__(self):
        self.settings={}
        self.db={}
        self.loadSettings()
    def getSettings(self):
        self.loadSettings()
        return self.settings

    def loadSettings(self):
        try:
            tree = ET.parse(settings_file_name)
        except FileNotFoundError:
            print(settings_file_name+' load failed')
            return
        root = tree.getroot()
        for parent in root.getchildren():
            data = {}
            for item in parent.iter():
                try:
                    if item.tag.find("api_")>=0 or (item.tag in ("kko_id", "kko_passwd", "kko_alive_periodic_crcy")):
                        data[item.tag] = item.text
                    else:
                        data[item.tag] = float(item.text)
                except:
                    continue
            self.settings[parent.tag] = data
        # system = self.root.find('system')
