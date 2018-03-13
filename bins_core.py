import sqlite3 as db
import threading
from time import sleep
import sys
from common_util import *
from db_serv import *
from datetime import datetime
from kko_serv import *
from settings import *

is_terminated=False

class BINS_TRADER_CORE(threading.Thread):
    prc_list =[]
    dyn_core = []
    trading_list = []
    traded_list = []

    # max, min과 같은 것들을 list 내에서만 유지할 것이 아니라 list 생성후
    # 계속 유지될 수 있도록 확장할 것 (list 내에서만 / 삭제 token 합쳐서 ..)
    def __init__(self, db_serv, crcy, order_book=None):
        self.prc_list =[]
        self.dyn_core = []
        self.trading_list = []
        self.traded_list = []

        self.db = db_serv
        self.curr_direction=["", ""]
        self.crcy = crcy
        self.order = order_book
        self.resumed_trading_completed = False
        self.last_handle_ts = 0
        self.last_cand_r_max = None
        self.last_cand_r_min = None
        self.ask_hist = []

        self.set_alias_cfg()
        self.added_prc_list = 0
        self.skipped_prc_list = 0
        self.is_trying_bid = False
        self.handle_next_tick= False
        self.total_bid_cnt = 0
        self.total_good_cnt = 0
        self.total_bad_cnt = 0
        self.ask_result=[]
        self.last_order_ts = 0
        self.first_bid_ts = 0
        self.first_r_min_ts = 0

        self.update_cfg_cnt = 0
        # self.drop_adjusted = False
        # try_cnt_resume=5
        # get trading list to resume
        # self.get_trading_bid()
        #while self.resumed_trading_completed is False and try_cnt_resume>0:
        #    sleep(0.5)
        #    try_cnt_resume-=1
        self.settings = getSettings()
        alive_msg_crcy = self.settings['system']['kko_alive_periodic_crcy']
        self.is_alive_msg = (self.crcy==alive_msg_crcy)
        self.kko_alive_interval = int(self.settings['system']['kko_alive_interval'])

        self.kko_msg = self.settings['system']['kko_msg']
        if self.kko_msg==1:
            try:
                self.kko_sender = KKO_Sender(self.crcy)
                print("kakao init "+str(self.kko_sender.res))
                if self.kko_sender.res.status_code != 200:
                    print("kko init failed:"+str(self.kko_sender.res))
                    self.kko_sender = None
            except:
                self.kko_sender = None
        else:
            self.kko_sender = None

    def get_dbfield(self, token, idx_field, field_type=INT):
        if len(token)<=idx_field or token[idx_field] is None:
            if field_type==TEXT:
                return ""
            elif field_type==REAL:
                return 0.0
            else: # INT
                return 0
        return token[idx_field]

    def push(self, token):
        size = len(self.prc_list)
        self.update_cfg_cnt = (self.update_cfg_cnt+1)%(self.kko_alive_interval)
        if self.update_cfg_cnt%60==0:
            self.set_alias_cfg()
            if self.update_cfg_cnt==0 and self.is_alive_msg:
                if self.kko_sender is not None:
                    self.kko_sender.send_msg('i_am_ok', None, None, None)

        if size>0 and self.prc_list[size-1][IDX_PRC]==token[IDX_PRC] and self.handle_next_tick is False:
            # print("skip push!")
            self.prc_list.pop()
            self.prc_list.append(token)
            # self.skipped_prc_list += 1
            return "skipped"



        if self.handle_next_tick is True:
            self.handle_next_tick  = False


        if len(self.prc_list)==self.size: # overflow of PRC list queue
            self.pop()
        self.prc_list.append(token)
        # self.added_prc_list +=1

        # print("added cnt : "+str(self.added_prc_list)+", skipped : "+str(self.skipped_prc_list))
        return "added"

    def pop(self, pop_index=0):
        if len(self.prc_list)<=pop_index:
            # print("ERROR:BO0001")
            return
        deleted_token = self.prc_list[pop_index]

        self.prc_list.remove(self.prc_list[pop_index])

        for token in self.dyn_core:
            if token[IDX_TIMESTAMP]<=deleted_token[IDX_TIMESTAMP]:
                self.dyn_core.remove(token)
                break

        return deleted_token

    def get_time_period_sec(self):
        if len(self.prc_list)<2:
            return 0
        last_ts = self.prc_list[-1][IDX_TIMESTAMP]
        first_ts = self.prc_list[0][IDX_TIMESTAMP]
        return last_ts-first_ts

    def get_maxgap_in_secs(self, gap_ts):
        if len(self.dyn_core)<2:
            return 0
        curr_ts = self.prc_list[-1][IDX_TIMESTAMP]
        r_max = 0
        r_min = 0
        for r_val in self.dyn_core:
            if curr_ts - r_val[IDX_TIMESTAMP] > gap_ts:
                continue
            if r_val[IDX_PRC]<r_min:
                r_min = r_val[IDX_PRC]
            if r_val[IDX_PRC]>r_max:
                r_max = r_val[IDX_PRC]
        return r_max-r_min

    def get_clone_list(self):
        return self.prc_list.copy()

    def set_alias_cfg(self):
        self.settings = getSettings()
        bins_core_tag = 'bins_core_'+self.crcy.lower()
        bins_core_cfg = self.settings[bins_core_tag]
        self.size = bins_core_cfg['prc_list_size']

        self.max_num_trade = bins_core_cfg['max_num_trade']
        self.drop_rt = bins_core_cfg['drop_rt']
        self.drop_rt_org = self.drop_rt
        # self.bid_drop_rt_adj_unit = bins_core_cfg['bid_drop_rt_adj_unit']

        self.bid_rt = bins_core_cfg['bid_rt']
        self.rise_rt = bins_core_cfg['rise_rt']
        self.ask_rt = bins_core_cfg['ask_rt']
        self.giveup_rt = bins_core_cfg['giveup_rt']
        self.bid_amount = bins_core_cfg['bid_amount']
        try:
            self.round_num = int(bins_core_cfg['round_num'])
        except:
            self.round_num = 0
        self.fee_rate = bins_core_cfg['fee_rate']
        self.worst_mkt_ask = bins_core_cfg['worst_mkt_ask']
        self.best_mkt_ask = bins_core_cfg['best_mkt_ask']
        self.drop_mkt_bid = bins_core_cfg['drop_mkt_bid']
        self.bid_max_rt = bins_core_cfg['bid_max_rt']
        self.bid_wait_max_sec = int(bins_core_cfg['bid_wait_max_sec'])
        self.adj_drop_rt = bins_core_cfg['adj_drop_rt']

    def check_direction(self):
        len_prc_list = len(self.prc_list)
        # print("check direction : "+str(len_prc_list)+", "+str(self.prc_list))

        if len_prc_list==0:
            return "empty"
        if self.last_handle_ts == self.prc_list[-1][IDX_TIMESTAMP]:
            return "already_checked"
        self.last_handle_ts = self.prc_list[-1][IDX_TIMESTAMP]
        if len_prc_list>2:
            p1 = self.prc_list[len_prc_list-3][IDX_PRC]
            p2 = self.prc_list[len_prc_list-2][IDX_PRC]
            p3 = self.prc_list[len_prc_list-1][IDX_PRC]

            if p1<p2 and p2>p3:
                return "r_max"
            if p1>p2 and p2<p3:
                return "r_min"
            if p2<p3:
                return "up"
            if p2>p3:
                return "down"
            else:
                return "same"
        elif len_prc_list==2:
            p1 = self.prc_list[0][IDX_PRC]
            p2 = self.prc_list[1][IDX_PRC]
            if p1>p2:
                return "down"
            else:
                return "up"
        else:
            return "empty"

    def get_last_r_max(self):
        last_r_max = None

        for core_token in self.dyn_core[::-1]:
            if core_token[IDX_STATE]=="r_max":
                last_r_max = core_token
                break
        return last_r_max

    def insert_db(self, query_type, token):
        if query_type=="I_ORDER_FAIL_HISTORY":
            db_token = token
        elif query_type=="I_ORDER_HISTORY":
            db_token = token
        elif query_type=="I_BINS_TRADE_LIST":
            if token['stage']==PHASE_BID_WAIT:
                stage = 'BID_WAIT'
            elif token['stage']==PHASE_1:
                stage = 'PHASE_1'
            elif token['stage']==PHASE_2:
                stage = 'PHASE_2'
            elif token['stage']==PHASE_BAD_ASK_WAIT:
                stage = 'BAD_ASK_WAIT'
            elif token['stage']==PHASE_GOOD_ASK_WAIT:
                stage = 'GOOD_ASK_WAIT'
            elif token['stage']==PHASE_END:
                stage = 'PHASE_END'
            else:
                print("stage error, stage : "+str(token['stage']))
            db_token = (token['crcy'],
                        stage,
                        token['ask_result_amount'],
                        token['bid_result_amount'],
                        token['bid_amount'],
                        token['ts_bid'],
                        token['bid_prc'],
                        token['bid_order_id'],
                        token['ts_ask'],
                        token['ask_prc'],
                        token['ask_order_id'],
                        token['r1_max_ts'],
                        token['r1_max_prc'],
                        token['r_min_ts'],
                        token['r_min_prc'],
                        token['r2_max_ts'],
                        token['r2_max_prc'],
                        token['giveup_rt_cfg'],
                        token['giveup_rt'],
                        token['drop_rt_cfg'],
                        token['drop_rt'],
                        token['bid_rt_cfg'],
                        token['bid_rt'],
                        token['rise_rt_cfg'],
                        token['rise_rt'],
                        token['ask_rt_cfg'],
                        token['ask_rt'],
                        token['profit_loss'],
                        token['profit_loss_rt'])
        else:
            return
        self.db.request_db(query_type, db_token)

    def bid_new_item(self, curr_ts, curr_prc, is_market_bid=False):
        max_val = self.last_cand_r_max
        min_val = self.last_cand_r_min
        deviation = max_val[IDX_PRC] - min_val[IDX_PRC]
        drop_rt = deviation/max_val[IDX_PRC]
        bid_rt = drop_rt*self.bid_rt    # self.bid_rt means bid_rt_cfg

        # buy condition
        new_token = {'crcy':self.crcy, 'stage':PHASE_BID_WAIT,
                    'ask_result_amount':0.0, 'bid_result_amount':0.0,
                    'bid_order_it':'', 'ts_ask':0, 'ask_prc':0,
                    'ask_order_id':'', 'r2_max_ts':0, 'r2_max_prc':0,
                    'giveup_rt':0.0, 'rise_rt':0.0, 'ask_rt':0.0,
                    'profit_loss':0, 'profit_loss_rt':0.0, 'ask_krw':0,
                    'bid_fee':0, 'ask_fee':0}
        new_token['bid_amount'] = self.bid_amount
        new_token['ts_bid'] = curr_ts
        new_token['bid_prc'] = curr_prc
        new_token['fee_rate'] = self.fee_rate
        new_token['r1_max_ts'] = max_val[IDX_TIMESTAMP]
        new_token['r1_max_prc'] = max_val[IDX_PRC]
        new_token['r_min_ts'] = min_val[IDX_TIMESTAMP]
        new_token['r_min_prc'] = min_val[IDX_PRC]
        new_token['giveup_rt_cfg'] = self.giveup_rt
        new_token['drop_rt_cfg'] = self.drop_rt
        new_token['drop_rt'] = drop_rt
        new_token['bid_rt_cfg'] = self.bid_rt
        new_token['bid_rt'] = (curr_prc/new_token['r_min_prc'] -1)/drop_rt # TBD : curr_prc대신 실제 bid 주문체결된 가격 기준으로 변경 필요
        new_token['rise_rt_cfg'] = self.rise_rt
        new_token['ask_rt_cfg'] = self.ask_rt
        if self.order is not None :
            print("request bid order !!!"+str(self.bid_amount)+", prc:"+str(curr_prc))
            result = self.order.req_order(BID, self.bid_amount,
                                          curr_prc, is_market_bid)
            if result['status']!='0000': # 미체결
                print("bid failed!!! "+str(new_token))
                db_token = (curr_ts, 'BID_FAIL', self.crcy, curr_prc,
                            self.bid_amount, 'r1_max_ts:'+str(new_token['r1_max_ts'])+
                            ', r1_max_prc:'+str(new_token['r1_max_prc'])+
                            ', r_min_ts:'+str(new_token['r_min_ts'])+
                            ', r_min_prc:'+str(new_token['r_min_prc'])+
                            ', drop_rt_cfg:'+str(new_token['drop_rt_cfg'])+
                            ', drop_rt:'+str(drop_rt)+
                            ', bid_rt_cfg:'+str(self.bid_rt)+
                            ', bid_rt:'+str(new_token['bid_rt']),
                            str(result))
                self.insert_db('I_ORDER_FAIL_HISTORY', db_token)
                self.handle_next_tick = True
                return
            else:
                print("bid request success!")
                if self.kko_sender is not None:
                    self.kko_sender.send_msg('bid_try', self.bid_amount, format(curr_prc, ','))
                new_token['bid_order_id'] = result['order_id']
                new_token['stage'] = PHASE_BID_WAIT
                self.is_trying_bid = True
                # if self.last_cand_r_max != self.get_last_r_max():
                #     self.last_cand_r_max = self.get_last_r_max()
                # else:
                #     self.last_cand_r_max = None
                self.last_cand_r_max = self.get_next_cand_r_max()
                self.last_cand_r_min = None
        else:
            print("order is None!!!!")
            new_token['bid_order_id'] = 'SIMULATION'
            new_token['stage'] = PHASE_1
            new_token['bid_krw'] = curr_prc*self.bid_amount
            new_token['bid_fee'] = self.bid_amount*self.fee_rate
            remain = self.bid_amount - new_token['bid_fee']
            (new_token['amount_1'], new_token['amount_2']) \
            = remain.as_integer_ratio()
        # new_token['bid_krw'] = curr_prc * self.bid_amount

        # TBD : need to check whether order succeed & update DB
        self.insert_db("TRADE_BID_ADD", new_token)
        self.trading_list.append(new_token)

        return

    def get_trading_cnt_with_stage(self, o_type):
        count = 0
        first_bid = None
        for i in self.trading_list:
            if i['stage'] == o_type:
                if first_bid is None:
                    first_bid = i
                count+=1
        return (count, first_bid)
    def get_current_trading_count(self):
        cnt = 0
        for e in self.trading_list:
            if e['stage']!=PHASE_END:
                cnt+=1
        return cnt
    def handle_waiting_order(self, curr_ts, curr_prc):
        return_value = False
        exist_close_order = False
        for each_bid in self.trading_list:
            if each_bid['stage'] in (PHASE_BID_WAIT, PHASE_BAD_ASK_WAIT, PHASE_GOOD_ASK_WAIT) \
               and exist_close_order:
               return True
            if each_bid['stage'] ==PHASE_BID_WAIT:
                order_id = each_bid['bid_order_id']
                bidask = BID
                bidask_str = "BID"
                stage = 'PHASE_BID_WAIT'
                amount = each_bid['bid_amount']
                print("checking order bid waiting (o_id, bid ts, bid prc): "+str(order_id)+","+str(each_bid['ts_bid'])+", "+str(each_bid['bid_prc']))
            elif each_bid['stage']==PHASE_BAD_ASK_WAIT:
                order_id = each_bid['ask_order_id']
                bidask = ASK
                bidask_str = "ASK"
                stage = 'PHASE_BAD_ASK_WAIT'
                result_stage = 'BAD_ASK_END'
                amount = each_bid['bid_result_amount']
                print("checking order bad ask waiting (o_id, ask ts, ask prc): "+str(order_id)+str(each_bid['ts_ask'])+", "+str(each_bid['ask_prc']))
            elif each_bid['stage']==PHASE_GOOD_ASK_WAIT:
                order_id = each_bid['ask_order_id']
                bidask = ASK
                bidask_str = "ASK"
                stage = 'PHASE_GOOD_ASK_WAIT'
                result_stage = 'GOOD_ASK_END'
                amount = each_bid['bid_result_amount']
                print("checking order good ask waiting (o_id, ask ts, ask prc): "+str(order_id)+str(each_bid['ts_ask'])+", "+str(each_bid['ask_prc']))
            else:
                continue

            order = self.order.check_is_complete_order(order_id, bidask, amount)
            amount=0
            krw = 0
            profit_loss =0
            profit_loss_rt = 0

            if bidask==BID:
                each_bid['bid_krw'] = order['complete_krw']
                each_bid['bid_fee'] = order['complete_fee']
                bid_result = float(order['complete_amount']-order['complete_fee'])
                each_bid['bid_result_amount'] = bid_result
                if bid_result!=0:
                    (each_bid['amount_1'], each_bid['amount_2']) \
                    = bid_result.as_integer_ratio()
                amount = each_bid['bid_result_amount']
                krw = each_bid['bid_krw']
                each_bid['bid_fee'] = krw*self.fee_rate
                total_amount = each_bid['bid_amount']
                if order['result'] is True:
                    each_bid['stage'] = PHASE_1
                    self.total_bid_cnt +=1

                    self.is_trying_bid = False
                    print("bid complete!")
                    if self.kko_sender is not None:
                        self.kko_sender.send_msg('bid_complete', self.bid_amount, format(curr_prc, ','), each_bid['drop_rt'], each_bid['bid_rt'])
                # last_r_max = self.get_last_r_max()
                #if self.last_cand_r_max[IDX_TIMESTAMP]== last_r_max[IDX_TIMESTAMP]:


                # last_r_max = self.get_last_r_max()
                # if last_r_max != self.last_cand_r_max:
                #     print("change cand r max : "+str(self.last_cand_r_max)+" -> "+str(last_r_max))
                #     self.last_cand_r_max = last_r_max
                    # self.last_cand_r_max = None
                    # self.last_cand_r_min = None
                print("current trade list "+str(len(self.trading_list)))
            elif bidask==ASK:
                is_bad_market_sell_end = False
                if result_stage=='BAD_ASK_END' and order['result'] is False:
                    next_giveup_prc = (1-self.worst_mkt_ask)*each_bid['bid_prc']
                    if curr_prc < next_giveup_prc:
                        each_bid['ask_result_amount'] = order['complete_amount']
                        each_bid['bid_result_amount'] -= order['complete_amount']
                        each_bid['ask_fee'] = order['complete_fee']
                        each_bid['ask_krw'] = order['complete_krw']

                        cancel_result = self.order.cancel_order(each_bid['ask_order_id'], ASK)
                        if cancel_result['status']=='0000':
                            # if only cancel previous order success,
                            ## reorder market_sell
                            ask_amount = ceil(each_bid['bid_result_amount'], self.round_num)
                            each_bid['bid_result_amount'] = ask_amount
                            res_resell = self.order.req_order(ASK,
                                                            ask_amount,
                                                            curr_prc, True)
                            if res_resell['status']!='0000':
                                db_token = (curr_ts,
                                            "BAD_REASK_FAIL",
                                            each_bid['crcy'],
                                            curr_prc,
                                            each_bid['bid_result_amount'],
                                            'ts_bid:'+str(each_bid['ts_bid'])+
                                            ', bid_prc:'+str(each_bid['bid_prc'])+
                                            ', bid_krw:'+str(each_bid['bid_krw'])+
                                            ', drop_rt_cfg:'+str(each_bid['drop_rt_cfg'])+
                                            ', drop_rt:'+str(each_bid['drop_rt']),
                                            str(res_resell))
                                self.insert_db("I_ORDER_FAIL_HISTORY", db_token)
                                # lets try again next time
                                exist_close_order = True
                                continue
                            else:
                                each_bid['ask_order_id'] = res_resell['order_id']
                                conts = res_resell['data']
                                complete_amount = 0
                                complete_krw = 0
                                complete_fee = 0
                                tr_ts_max = 0
                                for each_cont in conts:
                                    complete_amount += float(res_resell['units'])
                                    complete_fee += float(res_resell['fee'])
                                    complete_krw += int(res_resell['total'])
                                each_bid['ask_result_amount'] += complete_amount
                                each_bid['bid_result_amount'] -= complete_amount
                                each_bid['ask_fee'] += order['complete_fee']
                                each_bid['ask_krw'] += complete_krw
                                ask_prc = each_bid['ask_krw']/each_bid['ask_result_amount']
                                drop = each_bid['bid_prc']-ask_prc
                                each_bid['drop_rt'] = drop / each_bid['bid_prc']
                                each_bid['ask_prc'] = ask_prc
                                each_bid['ts_ask'] = curr_ts
                                order['result'] = True
                                is_bad_market_sell_end = True
                    # Delete! : This case impossible
                    # elif curr_prc > (1-self.giveup_rt)*each_bid['bid_prc']:
                    #     # return to phase 1
                    #     each_bid['stage'] = PHASE_1
                    #     continue
                elif result_stage=='GOOD_ASK_END' and order['result'] is False:   # GOOD_ASK
                    phase2_rise_threshold = each_bid['bid_prc']*(1+each_bid['rise_rt_cfg'])
                    if curr_prc<phase2_rise_threshold:
                        cancel_result = self.order.cancel_order(each_bid['ask_order_id'], ASK)
                        if cancel_result['status']=='0000':
                            # if only cancel previous order success,
                            ## reorder market_sell
                            print("go back to phase_1 T_T")
                            # back to Phase 1
                            each_bid['stage'] = PHASE_1
                            each_bid['ask_result_amount'] = order['complete_amount']
                            each_bid['bid_result_amount'] -= order['complete_amount']
                            each_bid['ask_fee'] = order['complete_fee']
                            each_bid['ask_krw'] = order['complete_krw']
                            order['result'] = True
                            continue

                if  order['result'] is True:
                    if is_bad_market_sell_end is False:
                        each_bid['ask_krw'] += order['complete_krw']
                        each_bid['ask_result_amount'] += order['complete_amount']
                        each_bid['ask_fee'] += order['complete_fee']
                    total_amount = each_bid['bid_result_amount']
                    amount = each_bid['ask_result_amount']
                    krw = each_bid['ask_krw'] - each_bid['ask_fee']
                    each_bid['profit_loss'] = krw - each_bid['bid_krw']
                    profit_loss = each_bid['profit_loss']
                    each_bid['profit_loss_rt'] = each_bid['profit_loss']/each_bid['bid_krw']
                    profit_loss_rt = each_bid['profit_loss_rt']
                    each_bid['stage'] = PHASE_END
                    print("ask complete! profit : "+str(profit_loss))

                    if result_stage=='BAD_ASK_END':
                        msg_type = 'bad_ask_complete'
                        self.total_bad_cnt += 1
                        self.ask_result.append(ASK_BAD)
                        # profit_rt = each_bid['giveup_rt']
                    else:
                        msg_type = 'good_ask_complete'
                        self.total_good_cnt += 1
                        self.ask_result.append(ASK_GOOD)
                        # profit_rt = each_bid['rise_rt'] * (1-each_bid['ask_rt'])

                    # rs = self.ask_result
                    # if len(rs)>=3:
                    #     if rs[-1]==ASK_BAD and rs[-2]==ASK_BAD and rs[-3]==ASK_BAD:
                    #         if self.bid_rt>self.bid_rt_min+self.fee_rate:
                    #             self.bid_rt -= self.bid_rt_adj_unit
                    #             self.giveup_rt += self.giveup_rt_adj_unit
                    #             for ee in self.trading_list:
                    #                 if ee['stage'] == PHASE_1:
                    #                     ee['bid_rt_cfg'] = self.bid_rt
                    #                     ee['giveup_rt_cfg'] = self.giveup_rt
                    #             print("BAD BAD BAD. cfg of (bid_rt, giveup_rt) are adjusted to ()"+ str(self.bid_rt)+", "+str(self.giveup_rt))



                    if self.kko_sender is not None:
                        self.kko_sender.send_msg(msg_type, amount, format(each_bid['ask_prc'], ','), each_bid['profit_loss'], each_bid['profit_loss_rt'])


            if order['result'] is False:
                continue

            exist_close_order = True
            self.insert_db("I_BINS_TRADE_LIST", each_bid)

            good = self.total_good_cnt
            bad = self.total_bad_cnt
            bid = self.total_bid_cnt

            print("total bid : "+str(bid))
            print("total good : "+str(good))
            print("total bad : "+str(bad))
            if bad!=0:
                print("good/bad cnt        : "+str(ceil((good/bad)*100,1))+" %")

            if order['result']!='0000':
                err_msg = 'status:'+order['status']+', '+str(order['complete_fee'])
            else:
                err_msg = ''

            db_token = (order_id, curr_ts, self.crcy, bidask_str, stage,
                        total_amount, amount, krw, profit_loss, profit_loss_rt,
                        order['complete_fee'],
                        err_msg, self.total_bid_cnt, self.total_good_cnt, self.total_bad_cnt)
            self.insert_db("I_ORDER_HISTORY", db_token)
            if bidask==ASK:
                self.trading_list.remove(each_bid)
            #     self.drop_rt = self.drop_rt_org
            #     self.drop_adjusted = False

            self.last_order_ts = curr_ts

    # def save_list(self):
    #     if self.trading_list is None:
    #         return
    #     if len(self.trading_list)==0:
    #         return
    #     with open('trading_list'+'_'+self.crcy.lower()+ '.pkl', 'wb+') as f:
    #         pickle.dump(self.trading_list, f, pickle.PROTO)
    #         print("saved trading list.")
    #         print(str(self.trading_list))
    #
    # def load_list(self):
    #     try:
    #         with open('trading_list'+'_'+self.crcy.lower()+ '.pkl', 'rb') as f:
    #             self.trading_list=pickle.load(f)
    #             if len(self.trading_list)>0:
    #                 print("trading list loaded.")
    #                 print(str(self.trading_list))
    #     except:
    #         print("nothing to load")
    #         self.trading_list = []


    def conv_ts_to_sec(self, ts):
        ss = ts%100
        ts -= ss
        mm = int((ts%10000) /100)
        ts -= (mm*100)
        hh = int((ts%1000000) / 10000)
        ts -= (hh*10000)
        dd = int((ts%100000000) / 1000000)
        print(str(dd)+"  "+str(hh)+":"+str(mm)+":"+str(ss))
        sec = ss+mm*60+hh*60*60+dd*24*60*60
        return sec

    def get_next_cand_r_max(self):
        select_first= False
        if self.last_cand_r_max is None:
            if len(self.dyn_core)>0:
                select_first = True
            else:
                return None
        max_val =(0, 0, 0, 0)
        for r_val in self.dyn_core:
            if r_val[IDX_STATE]!='r_max':
                continue
            if select_first:
                return r_val
            if self.last_cand_r_max[IDX_TIMESTAMP]<=r_val[IDX_TIMESTAMP]:
                continue
            if max_val[IDX_PRC]<r_val[IDX_PRC]:
                max_val = r_val

        if max_val[IDX_TIMESTAMP]!=0:
            return max_val
        else:
            return None


    def handle_bins_order(self):
        # set current direction
        self.curr_direction = self.check_direction()

        # alias
        state = self.curr_direction
        # print("curr direction : " +state)

        if state == "empty":
            return
        curr_token = self.prc_list[-1]
        curr_ts = curr_token[IDX_TIMESTAMP]
        curr_prc = curr_token[IDX_PRC]

        if state in ("already_checked", "same"):
            self.handle_waiting_order(curr_ts, curr_prc)
            return
        print(str(curr_ts)+"] current state : "+state)

        r2_max_val = 0
        # update dynamic core values : r_max, r_min cases
        if state=="r_max" or state=="r_min":
            core_token  = (self.prc_list[-2][IDX_TIMESTAMP],
                           self.prc_list[-2][IDX_PRC],
                           self.crcy, state)

            self.dyn_core.append(core_token)
            self.db.request_db("BINS_DYNAMIC_CORE", core_token)
            # update maximum and minimum r_values(r_max, r_min)
            is_update_r_value = False
            if state=="r_max":
                if self.last_cand_r_max is None or \
                    self.last_cand_r_max[IDX_PRC] < core_token[IDX_PRC]:
                    self.last_cand_r_max = core_token
                    self.last_cand_r_min = None
                    self.dyn_core.append(core_token)
                    self.last_cand_r_min = None
                    # print("append r_values after : "+str(self.dyn_core))


                for token in self.trading_list:
                    bid_prc = token['bid_prc']
                    rise_thres = bid_prc*(1+token['rise_rt_cfg'])
                    if (token['stage']== PHASE_1) and core_token[IDX_PRC] >=rise_thres:
                        r2_max_val = core_token[IDX_PRC]
                        break

            else:  # state=="r_min"
                if self.last_cand_r_max is None:
                    print("skip this r_min : cand r_max not exist "+str(core_token))
                    return
                if self.last_cand_r_min is not None and \
                    self.last_cand_r_min[IDX_PRC] < core_token[IDX_PRC]:
                    print("skip r-min :"+str(core_token)+", cur_r_min:"+str(self.last_cand_r_min))
                    return

                last_max = self.last_cand_r_max

                deviation = last_max[IDX_PRC] - core_token[IDX_PRC]
                drop_rt = deviation/last_max[IDX_PRC]
                (t_cnt, b) = self.get_trading_cnt_with_stage(PHASE_1)
                adj_drop_rt = self.drop_rt+(self.adj_drop_rt*t_cnt)
                if drop_rt>=adj_drop_rt:
                    print("insert r_min : "+str(core_token))
                    self.last_cand_r_min=core_token
                else:
                    print("skip r-min : "+str(core_token[IDX_PRC])+", r-max:"+str(last_max[IDX_PRC])+", drop_rt : "+str(drop_rt)+", cfg : "+str(adj_drop_rt))
                    return

        #exist_waiting_order = self.handle_waiting_order()
        self.handle_waiting_order(curr_ts, curr_prc)

        # update trading_list
        for each_bid in self.trading_list:
            bid_prc = each_bid['bid_prc']
            if each_bid['stage']>=PHASE_1:
                each_bid['bid_result_amount'] = each_bid['amount_1']/each_bid['amount_2']
                print("check update bid start - bid_ts:"+str(each_bid['ts_bid'])+", stage : "+str(each_bid['stage']))

            if each_bid['stage']==PHASE_1:

                # check giveup(손절)
                giveup_prc = (1-self.giveup_rt)*each_bid['bid_prc']
                if (state=='down') and curr_prc<=giveup_prc:
                    print("bad ask condition! (curr, giveup_thres, bid_prc) :"+str(curr_prc)+", "+str(giveup_prc)+", "+str(bid_prc))
                    drop = bid_prc-curr_prc
                    each_bid['giveup_rt'] = drop / bid_prc
                    each_bid['ask_prc'] = curr_prc
                    each_bid['ts_ask'] = curr_ts

                    if self.order is not None:
                        ask_amount = ceil(each_bid['bid_result_amount'], self.round_num)
                        result = self.order.req_order(ASK,
                                                        ask_amount,
                                                        curr_prc)
                        if result['status']!='0000': # 미체결
                            db_token = (curr_ts,
                                        "BAD_ASK_FAIL",
                                        each_bid['crcy'],
                                        curr_prc,
                                        each_bid['bid_result_amount'],
                                        'ts_bid:'+str(each_bid['ts_bid'])+
                                        ', bid_prc:'+str(each_bid['bid_prc'])+
                                        ', bid_krw:'+str(each_bid['bid_krw'])+
                                        ', drop_rt_cfg:'+str(each_bid['drop_rt_cfg'])+
                                        ', drop_rt:'+str(each_bid['drop_rt']),
                                        str(result))
                            self.insert_db("I_ORDER_FAIL_HISTORY", db_token)
                            continue
                        else:
                            each_bid['ask_order_id'] = result['order_id']
                            each_bid['stage']=PHASE_BAD_ASK_WAIT
                            self.insert_db("I_BINS_TRADE_LIST", each_bid)
                            if self.kko_sender is not None:
                                self.kko_sender.send_msg('bad_ask_try', each_bid['bid_result_amount'], format(curr_prc, ',') )
                            print("wait to sell loss !!!! drop_rt : "+str(each_bid['drop_rt']))
                            continue
                    else:
                        each_bid['ask_order_id'] = 'SIMULATION'
                        self.insert_db("UPDATE_TRADE_LIST_BAD_ASK_END", each_bid)
                        each_bid['ask_fee'] = curr_ps*self.fee_rate
                        print("sell loss !!!! : "+str(each_bid['profit_loss']))

                        continue

                if state == "r_max" and r2_max_val>0:
                    rise_threshold = bid_prc*(1+each_bid['rise_rt_cfg'])
                    print("[r_max] phase 1->2 check (curr rmax, rise_thres):"+str(core_token[IDX_PRC])+", "+str(rise_threshold))
                    if r2_max_val>=rise_threshold:
                        print(" turn into Phase 2 !!")
                        each_bid['stage']=PHASE_2
                        each_bid['r2_max_ts'] = core_token[IDX_TIMESTAMP]
                        each_bid['r2_max_prc'] = core_token[IDX_PRC]
                        r_max_prc = each_bid['r2_max_prc']
                        deviation = r_max_prc-bid_prc
                        each_bid['rise_rt'] = deviation / bid_prc
                        drop_thres = deviation*each_bid['ask_rt_cfg']
                        ask_thres_prc = r_max_prc -drop_thres
                        if curr_prc <= ask_thres_prc:
                            each_bid['ask_rt'] = (r_max_prc-curr_prc)/(bid_prc*each_bid['rise_rt'])
                    continue

            elif each_bid['stage']==PHASE_2:
                # 익절 good ask case
                print("phase 2 check state : "+state)
                if state=='down':
                    deviation = each_bid['r2_max_prc']-bid_prc
                    each_bid['ask_rt_cfg'] = self.ask_rt
                    drop_thres = deviation*each_bid['ask_rt_cfg']
                    ask_thres_prc = each_bid['r2_max_prc'] - drop_thres
                    print("[down] good ask check !! curr:"+str(curr_prc)+", ask thres:"+str(ask_thres_prc))

                    if curr_prc <= ask_thres_prc:
                        r_max_prc = each_bid['r2_max_prc']
                        each_bid['ask_rt'] = (r_max_prc-curr_prc)/(bid_prc*each_bid['rise_rt'])
                        if self.round_num<0:
                            kk=0
                        else:
                            kk= self.round_num
                        each_bid['ask_prc'] = curr_prc-(10*kk)
                        each_bid['ts_ask'] = curr_ts
                        ask_amount = ceil(each_bid['bid_result_amount'], self.round_num)
                        print("버린다 : "+str(each_bid['ask_prc']-ask_amount))
                        each_bid['bid_result_amount'] = ask_amount
                        if self.order is not None:
                            if each_bid['rise_rt']>=self.best_mkt_ask:
                                # 호가 매도 (즉 체결)
                                result = self.order.req_order(ASK,
                                                    each_bid['bid_result_amount'],
                                                    curr_prc, True)
                            else:
                                result = self.order.req_order(ASK,
                                                    each_bid['bid_result_amount'],
                                                    curr_prc)
                            if result['status']!='0000': # 미체결
                                each_bid['ask_krw'] = curr_prc*each_bid['bid_result_amount']
                                each_bid['profit_loss'] = each_bid['ask_krw']-each_bid['bid_krw']
                                each_bid['profit_loss_rt'] = each_bid['profit_loss'] / each_bid['bid_krw']

                                db_token = (curr_ts,
                                            "GOOD_ASK_FAIL",
                                            each_bid['crcy'],
                                            curr_prc,
                                            each_bid['bid_result_amount'],
                                            'ts_bid:'+str(each_bid['ts_bid'])+
                                            ', bid_prc:'+str(each_bid['bid_prc'])+
                                            ', profit_loss:'+str(each_bid['profit_loss'])+
                                            ', profit_loss_rt:'+str(each_bid['drop_rt_cfg']),
                                            str(result))
                                self.insert_db("I_ORDER_FAIL_HISTORY", db_token)
                            else:   # 주문등록 성공
                                each_bid['ask_order_id'] = result['order_id']
                                each_bid['stage']=PHASE_GOOD_ASK_WAIT
                                self.insert_db("I_BINS_TRADE_LIST", each_bid)
                                if self.kko_sender is not None:
                                    self.kko_sender.send_msg('good_ask_try', each_bid['bid_result_amount'], format(curr_prc, ',') )

                                print("wait to sell profit!", "bid prc:"+str(bid_prc)+", sell prc : "+str(curr_prc))
                                continue
                        else: #simulation condition
                            each_bid['stage']=PHASE_END
                            self.insert_db("I_BINS_TRADE_LIST", each_bid)
                            self.prc_list.remove(each_bid)
                            print("wait to sell profit !!!! profit krw : "+str(each_bid['profit_loss']))
                            break

                # return to PHASE 1 case : 극대점 이후 익절 전 상승 전환
                if (state=="r_min" or state=='up') and each_bid['r2_max_prc']<curr_prc:
                    print("Phase2 -> Phase1 T_T (bidts, bid_prc) : "+str(curr_ts)+", "+str(curr_prc))
                    each_bid['stage']=PHASE_1
                    each_bid['r2_max_ts'] = 0
                    each_bid['r2_max_prc'] = 0
                    each_bid['rise_rt'] = 0
                    continue

        t_cnt = self.get_current_trading_count()
        if t_cnt>=self.max_num_trade:
            return

        # newly bid case
        #if len(self.trading_list)<self.settings['bins_core']['max_units_bid'] and \
        if (state == "up" or state=="r_min") and \
            self.last_cand_r_max is not None and \
            self.last_cand_r_min is not None:
                print(str(self.last_cand_r_max)+',,,'+str(self.last_cand_r_min))

                max_val = self.last_cand_r_max
                min_val = self.last_cand_r_min
                deviation = max_val[IDX_PRC] - min_val[IDX_PRC]
                drop_rt = deviation/max_val[IDX_PRC]

                bid_rt = drop_rt*self.bid_rt    # self.bid_rt means bid_rt_cfg
                max_bid_rt = drop_rt*self.bid_max_rt
                print("drop rt : "+str(drop_rt)+", cur prc:"+str(curr_prc)+", min_thres : "+str(min_val[IDX_PRC] * (1+bid_rt)))

                if self.is_trying_bid and curr_prc >= min_val[IDX_PRC] * (1+max_bid_rt):
                    # 이미 너무 많이 올라왔으므로 마지막 r_max로 candidate를 변경
                    last_r_max = self.get_last_r_max()
                    if last_r_max != self.last_cand_r_max:
                        print("change cand r max : "+str(self.last_cand_r_max)+" -> "+str(last_r_max))
                        self.last_cand_r_max = last_r_max
                    self.last_cand_r_min = None
                    return

                if curr_prc >= min_val[IDX_PRC] * (1+bid_rt):
                    print("try bid condition! "+str(curr_ts)+", "+str(curr_ts))
                    # self.drop_adjusted = False
                    if self.first_bid_ts==0:
                        self.first_bid_ts=curr_ts
                    is_market_bid = False
                    if drop_rt>self.drop_mkt_bid:
                        print("market bid condition")
                        is_market_bid=True
                    self.bid_new_item(curr_ts, curr_prc, is_market_bid)
                    print("waiting order ")
                else:
                    print("not new-bid condition")

                # cancel order
                w_ret = self.get_trading_cnt_with_stage(PHASE_BID_WAIT)
                if w_ret[COUNT]>0:
                    wait_bid = w_ret[FIRST_ITEM]
                    if wait_bid is None:
                        return
                    print("check cancel bid condition. (waitingtime, max_wait_cfg) : "+str(wait_bid['ts_bid']-curr_ts)+", "+str(self.bid_wait_max_sec))
                    if wait_bid['ts_bid']-curr_ts<self.bid_wait_max_sec:
                        return
                    bid_cancel = w_ret[FIRST_ITEM]
                    order_id_to_cancel = bid_cancel['bid_order_id']
                    res_cc = self.order.cancel_order(order_id_to_cancel, BID)
                    if res_cc['status']=='0000':
                        print("cancel waiting bid order : prc "+str(bid_cancel['bid_prc']))
                        self.trading_list.remove(bid_cancel)
                        # self.save_list()
                        if w_ret[COUNT] ==1 and self.is_trying_bid:
                            self.is_trying_bid = False
                    elif res_cc['status']=='5600' and res_cc['message'].find('거래 체결내역이 존재하지')>0:
                        print("delete cancelled order")
                        self.trading_list.remove(bid_cancel)
                        # self.save_list()
                        if w_ret[COUNT] ==1 and self.is_trying_bid:
                            self.is_trying_bid = False
                    else:
                        print("order cancel failed !!!!!!")
