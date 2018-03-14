
# constant 1. index
IDX_TIMESTAMP=0
IDX_PRC=1
IDX_CRCY=2
IDX_STATE=3

# deprecated
# IDX_TIMESTAMP=0
# IDX_PRC=1
IDX_BID_PRC = 2
IDX_ASK_PRC = 3

# constant 2. db table names used
TRADING_TABLE = "BINS_TRADING_BID"
TRADED_TABLE = "BINS_TRADED_ASK"
CORE_TABLE = "BINS_CORE"

# constant 3. direction
D_UP = 0
D_DOWN = 1

# constant 4. return value
OK = 0
ERROR = 1

# constant 5. stages of bids
PHASE_BID_WAIT = -1
PHASE_1    = 0 # before r_max satisfied >=bid_rt
PHASE_2    = 1 # after r_max which is satisfied >=bid_rt
PHASE_BAD_ASK_WAIT = 2 # waiting for ask
PHASE_GOOD_ASK_WAIT = 3
PHASE_END  = 4 # complete ask

# constant 6. bid-ask
BID = 0
ASK = 1

#constant 7. db field type
INT = 0
TEXT = 1
REAL = 2

# event
DEBUG = 0
RELEASE = 1
event_type = DEBUG

# settings.system.trading_mode
SIMULATION = 0
REAL_TRADE = 1

# ASK Type
ASK_BAD = 0
ASK_GOOD = 1

# wating order
COUNT = 0
FIRST_ITEM = 1

HOUR_1 = 3600
MIN_30 = 1800


def cout(*args):
    global event_type
    if event_type==RELEASE:
        pass
    else:
        print(args)

# XML indent function
def indent(elem, level=0):
    i = "\n" + level*"  "
    j = "\n" + (level-1)*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = j
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = j
    return elem

def get_weekday_string(weekday):
    if weekday==0:
        return "Mon"
    elif weekday==1:
        return "Tue"
    elif weekday==2:
        return "Wed"
    elif weekday==3:
        return "Thu"
    elif weekday==4:
        return "Fri"
    elif weekday==5:
        return "Sat"
    elif weekday==6:
        return "Sun"
    return "week:"+str(weekday)

def ceil(a, b):
    d = int((a* (10**b)))/(10**b)
    return d
