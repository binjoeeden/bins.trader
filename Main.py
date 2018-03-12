from ticker_service import *
from db_serv import *
from bins_runner import *
from bins_simulator import *

# db_service = DB_Worker("bithumb.db")
# db_service.start()

# print("tick thread start")
# # db file 내에 TICK_(CURRENCY) table이 존재해야 한다
# tick_xrp_bithumb = Bithumb_Price_Service("XRP")
# tick_xrp_bithumb.start()
# print("thread call end")

bins_trader = BINS_RUNNER("XRP")
bins_trader.start()

simulator = BINS_SIMULATOR("XRP", bins_trader)
simulator.go()

for i in range(15):
    sleep(1)

bins_trader.stop()
db_service.stop()

bins_trader.join()
db_service.join()

print("end main")
