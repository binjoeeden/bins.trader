import sqlite3 as db
import threading
import sys, datetime
from time import sleep
from common_util import *


class DB_Worker(threading.Thread):
    queue = []

    def __init__(self, dbname):
        threading.Thread.__init__(self)
        self.dbname = dbname
        self.mutex = threading.Lock()
        self.is_terminated=False

    def addqueue(self, job):
        self.mutex.acquire()
        self.queue.append(job)
        self.mutex.release()

    def stop(self):
        self.is_terminated=True

    def run(self):
        print_tick =0
        is_terminate = self.is_terminated
        while is_terminate is False:
            sleep(1)
            self.mutex.acquire()
            size_queue = len(self.queue)
            self.mutex.release()

            print_tick=(print_tick+1)%100
            if print_tick%50==0:
                print("db queue size : "+str(size_queue))
            if size_queue==0:
                is_terminate = self.is_terminated
                continue
            conn = db.connect(self.dbname)
            with conn:
                cur = conn.cursor()
                while size_queue>0:
                    self.mutex.acquire()
                    job = self.queue[0]
                    self.queue.remove(self.queue[0])
                    self.mutex.release()

                    is_select=False
                    if job[0].lower().find("select")>=0:
                        is_select=True

                    if len(job)<2:
                        self.mutex.acquire()
                        size_queue = len(self.queue)
                        self.mutex.release()
                        is_terminate = self.is_terminated
                        continue
                    try:
                        if type(job[1]) is tuple:
                            cur.execute(job[0], job[1])
                        else:
                            # print("execute query without param")
                            cur.execute(job[0])

                        if is_select is False:
                            conn.commit()
                        else:
                            # print("callback check")
                            callback=None
                            if callable(job[1]):
                                callback=job[1]
                            elif len(job)==3 and callable(job[2]):
                                callback=job[2]
                            if callback is not None:
                                #print("?? "+str(callable(callback)))
                                result=cur.fetchall()
                                #print(result)
                                # execute callback to pass result
                                callback(result)
                        # if print_tick%10==0:
                        #     print("db query OK : ", str(job[1]))
                    except:
                        # print("ERROR_DS0001",str(job[1]))
                        # print("qeury : "+job[0])
                        # if type(job[1]) is tuple:
                            # print("params : "+str(job[1]))
                        pass
                    del job
                    sleep(0.03)
                    self.mutex.acquire()
                    size_queue = len(self.queue)
                    self.mutex.release()
                else:
                    # print("no db request")
                    pass
                cur.close()
            conn.close()

        is_terminate = self.is_terminated

    def request_db(self, query_type,  values, callback=None):
        sql = "INSERT INTO "+query_type
        if query_type=="I_ORDER_FAIL_HISTORY":
            sql = """INSERT INTO ORDER_FAIL_HISTORY(ts, stage, crcy, prc,
                                                    amount, other_info,
                                                    err_return)
                                                    values(?, ?, ?, ?, ?, ?, ?)"""
        elif query_type=="I_ORDER_HISTORY":
            sql = """INSERT INTO ORDER_HISTORY(order_id, ts_cont, crcy, bidask,
                                            stage, total_amount, complete_amount,
                                            krw, profit_loss, profit_loss_rt,
                                            fee, err_msg,
                                            total_bid_cnt, total_good_ask_cnt, total_bad_ask_cnt)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        elif query_type=="BINS_DYNAMIC_CORE":
            sql = """INSERT INTO BINS_DYNAMIC_CORE(ts, prc, crcy, type)
                    values(?, ?, ?, ?)"""
        elif query_type=="I_BINS_TRADE_LIST":
            sql = """INSERT INTO BINS_TRADE_LIST(crcy,
                                                stage,
                                                ask_result_amount,
                                                bid_result_amount,
                                                bid_amount,
                                                ts_bid,
                                                bid_prc,
                                                bid_order_id,
                                                ts_ask,
                                                ask_prc,
                                                ask_order_id,
                                                r1_max_ts,
                                                r1_max_prc,
                                                r_min_ts,
                                                r_min_prc,
                                                r2_max_ts,
                                                r2_max_prc,
                                                giveup_rt_cfg,
                                                giveup_rt,
                                                drop_rt_cfg,
                                                drop_rt,
                                                bid_rt_cfg,
                                                bid_rt,
                                                rise_rt_cfg,
                                                rise_rt,
                                                ask_rt_cfg,
                                                ask_rt,
                                                profit_loss,
                                                profit_loss_rt)
                    values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        elif query_type=="DELETE_TRADING_BID":
            sql = "UPDATE BINS_TRADING_BID FROM BINS_TRADING_BID WHERE ts=? AND crcy=?"
        else:
            # print("ERROR:BO0003 "+table_name)
            return

        self.addqueue((sql, values, callback))
        return

class DB_Service:
    service = {}
    def __init__(self, dbname):
        if dbname not in self.service:
            DB_Service.service[dbname] = DB_Worker(dbname)
            DB_Service.service[dbname].daemon = True
            DB_Service.service[dbname].start()
        self.worker = DB_Service.service[dbname]

    def get_worker(self):
        return self.worker

def get_db_serv(dbname):
    db_serv = DB_Service(dbname)

    return db_serv.get_worker()
