import requests
from settings import *

# 네이티브 앱 키
# 41ccf822abf1529a8d3a5c1fbf243596
# REST API 키
# 3dc77622f14a27069d862a3f971a185b
# JavaScript 키
# 77a341867a7f3e7bd3d541361fc67cb1
# Admin 키
# 010642ee456feddbd71a3bbf6511a316

# temp 8450 매수 등록 ${crcy}, ${amount}, ${prc}, ${drop_rt}, bid_rt
## 매수 등록
## ${crcy}  ${amount}개를  ${prc}원 가격에 매수 신청하였습니다.
## - ${drop_rt}%하락 후 ${bid_rt}%상승

# temp 8451 손절 등록, ${crcy}, ${amount}, ${prc}, loss, loss_rt
## 손절 등록
## ${crcy}  ${amount}개를  ${prc}원 가격에 손절 신청하였습니다.
## 예상 손실금액 :  ${loss}원, 예상 손해율 : ${loss_rt}%

# temp 8452 익절 등록 ${crcy}, ${amount}, ${prc}, profit, profit_rt
## 익절 등록
## ${crcy}  ${amount}개를  ${prc}원 가격에 익절 신청하였습니다.
## 예상 수익금액  : ${profit}원, 예상 수익률 : ${profit_rt}%

# temp 8453 매수 체결 ${crcy}, ${amount}, ${prc}
## 매수 체결
## ${crcy}  ${amount}개가  ${prc}원 가격에 매수 체결 완료되었습니다.

# temp 8454 손절 체결 ${crcy}, ${amount}, ${prc}
## 손절 체결
## ${crcy}  ${amount}개가  ${prc}원 가격에 손절 체결 완료되었습니다.

# temp 8455 익절 체결 ${crcy}, ${amount}, ${prc}
## 익절 체결
## ${crcy}  ${amount} 개가  ${prc}원 가격에 익절 체결 완료되었습니다.


class KKO_Sender:
    API_HOST = 'https://kapi.kakao.com'
    APP_KEY = 'Bearer eIuuV7TPuDps8nNSbnsDYY39VljmTRYTVidSGQopdeIAAAFiGYZHiQ'
    headers = {'Authorization': APP_KEY}
    data = {}

    def __init__(self, crcy):
        self.crcy = crcy
        self.res = self.req('/v1/user/me', '', 'GET')

    # def refresh_token(self, path,   ):
    #     url = "kauth.kakao.com/oauth/token"
    #     data = {"grant_type":"refresh_token",
    #             "client_id":"3dc77622f14a27069d862a3f971a185b",
    #             }

    def req(self, path, query, method, data={}):
        url = KKO_Sender.API_HOST + path
        if 'GET' == method:
            return requests.get(url, headers=KKO_Sender.headers)
        elif 'POST' == method:
            return requests.post(url, headers=KKO_Sender.headers, data=data)

    def send_msg(self, msg_type, amount, prc, arg1=0, arg2=0):
        if msg_type=="bid_try":
            # args = {"crcy":self.crcy, "prc":prc, "amount":amount}
            params = {"template_id":8450}#, "templates_args":args}
            return
        elif msg_type=="i_am_ok":
            params = {"template_id":8480}
        elif msg_type=="bad_ask_try":
            # args = {"crcy":self.crcy, "prc":prc, "amount":amount}
            params = {"template_id":8451}#, "templates_args":args}
            return
        elif msg_type=="good_ask_try":
            # args = {"crcy":self.crcy, "prc":prc, "amount":amount}
            params = {"template_id":8452}#, "templates_args":args}
            return
        elif msg_type == "bid_complete":
            # drop = round(arg1*100, 2)
            # bid = round(arg2*100, 2)
            # args = {"crcy":self.crcy, "prc":prc, "amount":amount, "drop_rt":drop, "bid_rt":bid}
            params = {"template_id":{8453}} #, "templates_args":args}
            return
        elif msg_type=="bad_ask_complete":
            # loss = arg1
            # loss_rt = round(arg2*100, 2)
            # args = {"crcy":self.crcy, "prc":prc, "amount":amount, "loss":loss, "loss_rt":loss_rt}
            params = {"template_id":{8454}}#, "templates_args":args}
        elif msg_type=="good_ask_complete":
            # profit = arg1
            # profit_rt = round(arg2*100, 2)
            # args = {"crcy":self.crcy, "prc":prc,"amount":amount, "profit":profit, "profit_rt":profit_rt}
            params = {"template_id":{8455}} #, "templates_args":args}
        else:
            print("msg_type error : "+msg_type)
            return
        return self.req('/v2/api/talk/memo/send',  '', 'POST', params)
