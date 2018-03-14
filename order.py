
from xcoin_api_client import *
import sys, datetime
import sqlite3
from common_util import *
from settings import *
import threading
from time import sleep

# class Bithumb_Order_Helper(threading.Thread):
#
#     def __init__(self, crcy, order_id, ):
#         threading.Thread.__init__(self)
#         self.api = XCoinAPI()

min_units = {"BTC": 0.001, "ETH": 0.001, "DASH": 0.001, "LTC": 0.01,
        "ETC": 0.1, "XRP": 10, "BCH": 0.001, "XMR": 0.01, "ZEC": 0.01,
        "QTUM": 0.1, "BTG": 0.01, "EOS": 0.1}

class Bithumb_Order:
    global min_units
    def __init__(self, crcy):
        self.crcy = crcy
        self.rgParams = {"currency":crcy, "Payment_currency":"KRW",};
        settings = getSettings()
        self.trading_mode = settings['system']['trading_mode']

        self.api = XCoinAPI()
        # result_check_interval = settings['bins_core']['order_chck_interval']
        # self.tick_post = "/public/ticker/"

    def req_order(self, bidask, amount, prc, market_bidask=False):
        try_num = 0
        if self.trading_mode==SIMULATION or \
            amount<min_units[self.crcy]:
            return
        self.rgParams['units'] = amount

        if market_bidask is True:   # 호가 체결
            if bidask==BID:
                # 구입해야 하면 ask 가격으로 산다 (호가 체결 위해)
                order_post = "/trade/market_buy"
            else:
                # ask case
                order_post = "/trade/market_sell"

            print(self.rgParams)
            sleep(0.1)
            result = self.api.xcoinApiCall(order_post
                                            , self.rgParams);
        else: # 일반 주문
            order_post = '/trade/place'
            self.rgParams['order_currency'] = self.crcy
            self.rgParams['price'] = prc
            print(self.rgParams)
            if bidask==BID:
                self.rgParams['type']='bid'
            else:
                # ask case
                self.rgParams['type']='ask'
            result = self.api.xcoinApiCall(order_post
                                            , self.rgParams);
        print("order result:"+str(result))
        return result
    def cancel_order(self, order_id, bidask):
        if bidask == BID:
            bs_type = "bid"
        else:
            bs_type = "ask"
        rgParams = {"order_id":order_id, "type":bs_type,
                    "currency":self.crcy}
        sleep(0.1)
        result = self.api.xcoinApiCall("/trade/cancel",
                                        rgParams);
        return result
    def check_is_complete_order(self, order_id, bidask, total_amount):
        if bidask == BID:
            bs_type = "bid"
        else:
            bs_type = "ask"
        rgParams = {"order_id":order_id, "type":bs_type,
                    "currency":self.crcy}
        sleep(0.1)
        result = self.api.xcoinApiCall("/info/order_detail",
                                        rgParams);
        chck_item={'result':False,
                    'status':'0000',
                    'complete_krw':0,
                    'complete_fee':0,
                    'complete_amount':0}
        if result['status']=='0000':
            # check order completed
            print(result)
            try:
                conts = result['data']
                complete_amount = 0
                complete_krw = 0
                complete_fee = 0
                tr_ts_max = 0
                for each_cont in conts:
                    complete_amount += float(each_cont['units_traded'])
                    complete_fee += float(each_cont['fee'])
                    complete_krw += int(each_cont['total'])
                    tr_ts = int(each_cont['transaction_date'])/1000
                    if tr_ts_max<tr_ts:
                        tr_ts_max = tr_ts
            except:
                print("check order parsing error : "+str(result))
                return {'result':False}
            chck_item={'result':False,
                        'status':result['status'],
                        'complete_amount':complete_amount,
                        'complete_krw':complete_krw,
                        'complete_fee':complete_fee,
                        'ts_cont':tr_ts_max}
            diff = abs(total_amount-complete_amount)
            if diff/total_amount < 0.02:  # fee 0.015 + 오차범위
                chck_item['result']=True
        elif result['status']=='9999':
            chck_item['status']='9999'
            chck_item['msg'] = result['msg']

        elif result['status']=='5600':
            print("check order info result error : "+str(result))
            chck_item['status']= result['status']
            chck_item['msg'] = result['message']
        else:
            chck_item['status']= result['status']
            chck_item['msg'] = 'Unknown'
        return chck_item


if __name__ == "__main__":
    order = Bithumb_Order("BTC")
    order.req_order(BID, 0.001, 12780000)
