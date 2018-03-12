#
# XCoin API-call related functions
#
# @author	btckorea
# @date	2017-04-12
#
# Compatible with python3 version.

import sys
import time
import math
import base64
import hmac, hashlib
import urllib.parse
import pycurl
import json
from time import sleep
from settings import *

class XCoinAPI:
	api_url = "https://api.bithumb.com";

	def __init__(self):
		settings = getSettings()
		self.api_key = settings['system']['api_key']
		self.api_secret = settings['system']['api_secret']
		self.max_wait_cnt = 10
		self.num_of_remain_open_brace = 0
		self.complete_req = False
		self.contents = ""

	def init_result_config(self):
		self.start_ts = 0
		self.end_ts = 0
		self.complete_req = False
		self.num_of_remain_open_brace = 0
		self.contents = ""

	def body_callback(self, buf):
		result = str(buf, 'utf-8')
		self.contents += result
		self.num_of_remain_open_brace += result.count('{')- result.count('}')
		if self.num_of_remain_open_brace==0:
			self.complete_req = True


	def microtime(self, get_as_float = False):
		if get_as_float:
			return time.time()
		else:
			return '%f %d' % math.modf(time.time())

	def usecTime(self) :
		mt = self.microtime(False)
		mt_array = mt.split(" ")[:2];
		return mt_array[1] + mt_array[0][2:5];

	def xcoinApiCall(self, endpoint, rgParams):
		# 1. Api-Sign and Api-Nonce information generation.
		# 2. Request related information from the Bithumb API server.
		#
		# - nonce: it is an arbitrary number that may only be used once.
		# - api_sign: API signature information created in various combinations values.
		endpoint_item_array = {
			"endpoint" : endpoint
		};

		uri_array = dict(endpoint_item_array, **rgParams); # Concatenate the two arrays.

		str_data = urllib.parse.urlencode(uri_array);

		nonce = self.usecTime();

		data = endpoint + chr(0) + str_data + chr(0) + nonce;

		utf8_data = data.encode('utf-8');

		key = self.api_secret;
		utf8_key = key.encode('utf-8');

		h = hmac.new(bytes(utf8_key), utf8_data, hashlib.sha512);
		hex_output = h.hexdigest();
		utf8_hex_output = hex_output.encode('utf-8');

		api_sign = base64.b64encode(utf8_hex_output);
		utf8_api_sign = api_sign.decode('utf-8');


		self.curl_handle = pycurl.Curl();
		self.curl_handle.setopt(pycurl.POST, 1);
		#self.curl_handle.setopt(pycurl.VERBOSE, 1); # vervose mode :: 1 => True, 0 => False
		self.curl_handle.setopt(pycurl.POSTFIELDS, str_data);

		url = self.api_url + endpoint;
		self.curl_handle.setopt(self.curl_handle.URL, url);
		self.curl_handle.setopt(self.curl_handle.HTTPHEADER, ['Api-Key: ' + self.api_key, 'Api-Sign: ' + utf8_api_sign, 'Api-Nonce: ' + nonce]);
		self.curl_handle.setopt(self.curl_handle.WRITEFUNCTION, self.body_callback);
		#response_code = self.curl_handle.getinfo(pycurl.RESPONSE_CODE); # Get http response status code.

		# content = str(self.contents, 'utf-8')

		wait = 0
		result = {'status':'9999', 'msg':'exception error'}
		try:
			self.curl_handle.perform();
			while wait < self.max_wait_cnt:
				if self.complete_req:
					break
				else:
					wait+=1
					sleep(0.01)
			self.curl_handle.close();

			result_str = self.contents
			comleted_ret = self.complete_req
			self.init_result_config()
			if comleted_ret:
				return json.loads(result_str)
			else:
				result['msg'] = 'not response from server'
				return result
		except:
			return result
