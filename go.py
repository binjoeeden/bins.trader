from ticker_service import *
from bins_runner import *
from db_serv import *


db_service = get_db_serv("bithumb.db")


bins_trader_BTC = BINS_RUNNER("BTC", db_service)
bins_trader_BTC.daemon=True
bins_trader_BTC.start()

tick_btc_bithumb = Bithumb_Price_Service("BTC", db_service, bins_trader_BTC)
# tick_xrp_bithumb = Bithumb_Price_Service("BTC")
tick_btc_bithumb.daemon=True
tick_btc_bithumb.start()

bins_trader_XRP = BINS_RUNNER("XRP", db_service)
bins_trader_XRP.daemon=True
bins_trader_XRP.start()


tick_xrp_bithumb = Bithumb_Price_Service("XRP", db_service, bins_trader_XRP)
# tick_xrp_bithumb = Bithumb_Price_Service("BTC")
tick_xrp_bithumb.daemon=True
tick_xrp_bithumb.start()


i=1
while i>0:
    sleep(1000)
