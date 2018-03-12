import sys, datetime
from xcoin_api_client import *
from time import sleep
import threading
from common_util import *
import sqlite3
from db_serv import *
# from bins_runner import *
from settings import *


# result = api.xcoinApiCall("/public/ticker/XRP", rgParams);

# use db, table:BINS_CORE, insert tokens
class Bithumb_Price_Service(threading.Thread):
    market = "bithumb"
    interval = 0.3

    def __init__(self, crcy, db_serv = None, bins_trade_runner=None):
        threading.Thread.__init__(self)
        self.api = XCoinAPI()
        self.buy_prc = 0
        self.sell_prc = 0
        self.crcy = crcy
        # self.db_service = get_db_serv("bithumb.db")
        if db_serv is None:
            self.db_service = get_db_serv("bithumb_"+currency.lower()+".db")
        else:
            self.db_service = db_serv

        self.bins_trade_runner = bins_trade_runner
        self.is_terminated = False
        self.rgParams = {"currency" : crcy,"payment_currency" : "KRW"};
        settings = getSettings()
        self.is_sep_by_month = settings['system']['is_sep_table_by_month']
        self.trading_mode = settings['system']['trading_mode']


    def parse_datetime_to_fields(self, dtime, fields):
        if type(dtime) is not datetime.datetime or type(fields) is not dict:
            # print("ERROR:TS0002")
            return

        fields['date'] = dtime.year*10000+dtime.month*100+dtime.day
        fields['dayweek'] = get_weekday_string(dtime.weekday())
        fields['hh'] = dtime.hour
        fields['mm'] = dtime.minute
        fields['ss'] = dtime.second
        fields['datetime'] = dtime
        fields['timestamp'] = fields['date']*1000000 \
                                +dtime.hour*10000 \
                                +dtime.minute*100 \
                                +dtime.second

        return

    def change_to_db_token_from(self, result):
        timestamp = int(result["data"]["date"])/1000
        time_tick = datetime.datetime.fromtimestamp(timestamp)
        fields={}
        dt = datetime.datetime

        # parsing date time fields
        self.parse_datetime_to_fields(time_tick, fields)

        #parsing price fields
        prc = int(float(result['data']['closing_price']))
        fields['prc'] = prc
        fields['bid_prc'] = int(float(result['data']['buy_price']))
        fields['ask_prc'] = int(float(result['data']['sell_price']))

        # fields_vol = {}
        # try:
        #     for each_tr in result2['data']:
        #         try:
        #             ts_vol = dt.strptime(each_tr['transaction_date']
        #                                     , '%Y-%m-%d %H:%M:%S')
        #         except:
        #             print('ERROR:TS0001')
        #             continue
        #
        #         # parsing date time fields
        #         self.parse_datetime_to_fields(ts_vol, fields_vol)
        #         each_tr['timestamp'] = fields_vol['timestamp']
        #
        #     fields['vol_data'] = result2['data']
        # except:
        #     pass

        return fields

    def get_query(self, query_type):
        tablename = "TICK_"+self.crcy
        if self.is_sep_by_month==1:
            tablename += '_'+datetime.datetime.now().strftime('%y%m') # ex. TICK_XRP_1803
        if query_type == 'normal':
            return "insert into "+tablename+"""(timestamp, date, dayweek, hh, mm, ss,
                                    prc, bid_prc, ask_prc)
                                    values (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        else:   # 'interpolated'
            return "insert into "+tablename+"""(timestamp, date, dayweek, hh, mm, ss,
                                    prc, bid_prc, ask_prc, interpolated)
                                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    def run(self):
        prev_token = None
        post_tick = "/public/ticker/"
        purl_vol = '/public/recent_transactions/'
        total_sleep=0
        is_terminated = self.is_terminated
        tablename = self.crcy

        DELTA_1SEC = datetime.timedelta(seconds=1)

        while is_terminated is False:
            start_time = datetime.datetime.now()
            pc_timestamp = start_time.timestamp()

            # call rest api
            result = self.api.xcoinApiCall(post_tick+self.crcy
                                            , self.rgParams);
            if result['status']!='0000':
                #print("ticker error ")
                sleep(1)  # DO NOT REMOVE this delay
                # insert table to TICK_XRP_ERROR
                is_terminated = self.is_terminated
                continue
            try:
                timestamp = int(result["data"]["date"])/1000
            except:
                print("timestamp parsing error. "+str(result))
                sleep(1)
                continue

            db_token = self.change_to_db_token_from(result)
            if prev_token is not None and \
                prev_token['timestamp'] > db_token['timestamp']:
                #print(start_time)
                #print(datetime.datetime.fromtimestamp(timestamp))
                print("time stamp error")   # api의 d 결과 time stamp가 \
                                            # 역방향으로 오는 경우가 있음 \
                                            # API 요청 전 PC의 timestamp와 \
                                            # 비교하여 이보다 과거 timestamp로 \
                                            # 결과가 오는 경우에는 버리도록 한다
                print("prev ts:"+str(prev_token['timestamp'])+", curr ts:"+str(db_token['timestamp']))
                sleep(1)  # DO NOT REMOVE this delay
                is_terminated = self.is_terminated
                continue

            # try_num_for_vol = 0
            # get volume
            # for j in range(5): # try max 10 times for each tick
            #     try:
            #         result2 = self.api.xcoinApiCall(purl_vol+self.currency
            #                                         , rgParams);
            #     except:
            #         print("get volume tick error ")
            #         sleep(0.1)
            #         continue
            # initial condition, but volume is not available yet
            if prev_token is None:
                #print('first init condition')
                prev_token = db_token
                sleep(1)
                is_terminated = self.is_terminated
                continue

            if prev_token['timestamp']>=db_token['timestamp']:
                sleep(0.1)
                # previos token과 timestamp가 동일하면 버린다 (ex. x.0초 > x.9초)
                is_terminated = self.is_terminated
                continue

            while prev_token['timestamp']+1<db_token['timestamp']:
                # insert same with previous token for interpolation
                prev_token['datetime'] = prev_token['datetime']+DELTA_1SEC
                self.parse_datetime_to_fields(prev_token['datetime'],
                                                prev_token)
                self.db_service.addqueue((self.get_query("interpolated"), (prev_token['timestamp'],
                                    prev_token['date'], prev_token['dayweek'],
                                    prev_token['hh'], prev_token['mm'],
                                    prev_token['ss'], prev_token['prc'],
                                    prev_token['bid_prc'],
                                    prev_token['ask_prc'], 1)))

                #if self.bins_trade_runner is not None:
                if self.trading_mode==REAL_TRADE and \
                    self.bins_trade_runner is not None:
                    token={}
                    token['timestamp'] = prev_token['timestamp']
                    token['prc'] = prev_token['prc']
                    token['bid_prc'] = prev_token['bid_prc']
                    token['ask_prc'] = prev_token['ask_prc']
                    self.bins_trade_runner.setTickInfo(token)


            del result, prev_token
            prev_token = db_token

            if self.bins_trade_runner is not None:
                token={}
                token['timestamp'] = db_token['timestamp']
                token['prc'] = db_token['prc']
                token['bid_prc'] = db_token['bid_prc']
                token['ask_prc'] = db_token['ask_prc']
                self.bins_trade_runner.setTickInfo(token)
                del token

            # insert current tick to DB
            self.db_service.addqueue((self.get_query("normal"), (db_token['timestamp'],
                                    db_token['date'], db_token['dayweek'],
                                    db_token['hh'], db_token['mm'],
                                    db_token['ss'], db_token['prc'],
                                    db_token['bid_prc'],
                                    db_token['ask_prc'])))

            end_time = datetime.datetime.now()
            delta = end_time - start_time

            if delta < DELTA_1SEC:
                delay_time = DELTA_1SEC - delta
                delay_seconds = delay_time.microseconds/1000000
                sleep(delay_seconds)
            is_terminated = self.is_terminated
