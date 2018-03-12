
import sqlite3 as db


class BINS_SIMULATOR:
    def __init__(self, crcy, runner):
        self.crcy = crcy
        self.runner = runner
        self.data = []

    def get_result_callback(self, result):
        # cout("[BINS_SUMULATOR] callback start.")
        self.data = result
        # print(len(result))

    def go(self):
        sql = """select timestamp, prc, bid_prc, ask_prc from tick_xrp where
                    timestamp<20180224143000"""
        conn = db.connect("bithumb.db")
        with conn:
            cs = conn.cursor()
            cs.execute((sql))
            result = cs.fetchall()
            # print("result len : "+str(len(result)))

            for tok in result:
                token={}
                token['timestamp'] = tok[0]
                token['prc'] = tok[1]
                token['bid_prc'] = tok[2]
                token['ask_prc'] = tok[3]
                self.runner.setTickInfo(token)
