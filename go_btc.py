from ticker_service import *
from bins_runner import *
from db_serv import *

db_service = get_db_serv("bithumb.db")

bins_trader = BINS_RUNNER("BTC", db_service)
bins_trader.daemon=True
bins_trader.start()


tick_btc_bithumb = Bithumb_Price_Service("BTC", db_service, bins_trader)
# tick_xrp_bithumb = Bithumb_Price_Service("BTC")
tick_btc_bithumb.daemon=True
tick_btc_bithumb.start()

i=1
while i>0:
    sleep(1000)
