import httplib2
import json

url = 'https://api.coinrail.co.kr/public/orderbook'
currency = 'xrp-krw'
if __name__ == "__main__":
	http = httplib2.Http()
	response, content = http.request(url+'?'+'currency='+currency, 'GET')
	c = str(content, 'utf-8')

	print(c)

	data = json.loads(c)
	# print data["ask_orderbook"]
	# print data["bid_orderbook"]
	print(data)
