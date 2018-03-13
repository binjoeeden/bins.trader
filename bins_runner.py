import sys, datetime
from settings import *
import threading
import sqlite3
from common_util import *
from bins_core import *
from db_serv import *
from order import *

# use db, table:BINS_CORE, insert tokens
class BINS_RUNNER(threading.Thread):

    def __init__(self, currency, db_serv=None):
        threading.Thread.__init__(self)
        if db_serv is None:
            self.db_serv = get_db_serv("bithumb_"+currency.lower()+".db")
        else:
            self.db_serv = db_serv
        self.crcy = currency
        self.settings = getSettings()
        self.bins_trader = None
        self.tick_list = []
        bins_core_tag = 'bins_core_'+self.crcy.lower()
        self.tick_time = self.settings[bins_core_tag]['tick_time']
        if self.tick_time is None or self.tick_time<1:
            self.tick_time=1
        self.mutex = threading.Lock()
        self.is_terminated=False

    def stop(self):
        self.is_terminated=True

    def run(self):
        order = None
        if self.settings['system']['trading_mode']==REAL_TRADE:
            order = Bithumb_Order(self.crcy)
        self.bins_trader = BINS_TRADER_CORE(self.db_serv, self.crcy, order)

        # print_tick =0
        while self.is_terminated is False:
            sleep(self.tick_time)
            # update configures at a interval of 10 seconds
            # setting_tick = (settings_tick+1)%10
            # if settings_tick==0:
            #     self.settings = getSettings()
            self.mutex.acquire()
            size_queue = len(self.tick_list)
            self.mutex.release()
            # print_tick=(# print_tick+1)%100
            # if print_tick%10==0:
                # print("runner queue size : "+str(size_queue))

            if size_queue==0:
                continue

            while size_queue>0:
                tick=self.tick_list[0]
                curr_ts     = tick['timestamp']
                if self.tick_time>1 and curr_ts%self.tick_time>0:
                    # print("discard input ts : "+str(curr_ts))
                    continue

                curr_prc    = tick['prc']
                curr_bid_prc = tick['bid_prc']
                curr_ask_prc = tick['ask_prc']
                token = (curr_ts, curr_prc, curr_bid_prc, curr_ask_prc)
                # cout("start push & update with "+str(token))
                result=self.bins_trader.push(token)
                if result=="added":
                    self.bins_trader.handle_bins_order()

                self.mutex.acquire()
                self.tick_list.remove(self.tick_list[0])

                size_queue = len(self.tick_list)
                self.mutex.release()

                # cout("end push & update with "+str(token), "remain tick : "+str(size_queue))
                # print("")
        # print("thread stopped")
        pass

    def setTickInfo(self, tick_token):
        # cout("set tick : "+str(tick_token))
        self.mutex.acquire()
        self.tick_list.append(tick_token)
        self.mutex.release()
