# -*- coding:utf-8 -*-

import base64
import datetime
import xlrd
import hashlib
import json
import os
import random
import re
import string
import time
from urllib import parse
from lxml import etree
import io
import pandas as pd
from functools import reduce

from io import BytesIO
import cv2
import numpy as np
import requests
from PIL import Image, ImageFont, ImageDraw
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from biz_cv.key_account.fdfs import download_path
from biz_cv.key_account.decorators import *
from biz_cv.key_account.fdfs import ftp_test
from biz_cv.key_account.ka_spider import Spider
from selenium.webdriver.common.keys import Keys


class YonghuiSpider(Spider):
    def __init__(self, req_params):
        super().__init__(req_params)
        if 'kms_all_store' in self.req_params.keys():
            if self.req_params['kms_all_store'] == 'true':
                if self.doc != '库存数据':
                    self.sold_to_party =[]
                else:
                    self.sold_to_party = [{"code": ""}]
        # self.stp = self.get_stp()
        # self.data_stp = self.get_data_stp()
        self.sign_token = ''
        self.session_code = ''
        self.vender_code = ''
        self.login_token = ''
        self.sign = ''
        self.source_cookies = {}
        self.page_size = 200
        self.delay = 1
        self.ka_url = 'http://glzx.yonghui.cn/newvssportal/login.html'
        # self.path = r'订货通知单明细打印.pdf'


    @login_check
    def login(self):
        option = webdriver.ChromeOptions()
        # option.add_argument("--headless")
        option.add_argument('--no-sandbox')
        option.add_experimental_option('excludeSwitches', ['enable-automation'])
        with webdriver.Chrome(options=option) as driver:
            driver.maximize_window()
            driver.get(self.ka_url)
            time.sleep(1)
            WebDriverWait(driver, 15, 0.5).until(ec.presence_of_element_located((By.XPATH, '//*[@id="app_substrate"]/section/div/div/section/main/div/section/div[3]/div[1]/div/div[2]/div[1]/input')))
            driver.find_element_by_xpath('//*[@id="app_substrate"]/section/div/div/section/main/div/section/div[3]/div[1]/div/div[2]/div[1]/input').send_keys(self.username)
            driver.find_element_by_xpath('//*[@id="app_substrate"]/section/div/div/section/main/div/section/div[3]/div[1]/div/div[2]/div[2]/input').send_keys(self.password)
            driver.find_element_by_xpath('//*[@id="app_substrate"]/section/div/div/section/main/div/section/div[3]/div[1]/div/button').click()
            time.sleep(5)
            try:
                driver.find_element_by_class_name("bg-img")
            except Exception:
                self.result['login'] = 0
                self.result['errors'].append("验证码方式更改")
            else:
                # 滑块验证码
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.leftClick(x=300, y=300)
                time.sleep(5)
                pyautogui.press('F11')
                time.sleep(5)
                location = driver.find_element_by_xpath('//*[@id="captcha"]/div[2]/div/div[2]/div[2]/div[2]/div[2]/div/i').location
                try_num = 0
                while try_num < 10:
                    try_num += 1
                    # 获取原始图片
                    bg_img = driver.find_element_by_class_name("bg-img").get_attribute("src").split(";")[-1].split(',')[
                        -1]
                    bg_img_base64 = base64.b64decode(bg_img)
                    bg_img_np = np.frombuffer(bg_img_base64, dtype=np.uint8)
                    bg_img_gray = cv2.imdecode(bg_img_np, 0)
                    slice_img = \
                        driver.find_element_by_class_name('slice-img').get_attribute('src').split(";")[-1].split(',')[
                            -1]
                    slice_img_base64 = base64.b64decode(slice_img)
                    slice_img_np = np.frombuffer(slice_img_base64, dtype=np.uint8)
                    slice_img_gray = cv2.imdecode(slice_img_np, 0)
                    result = cv2.matchTemplate(bg_img_gray, slice_img_gray, cv2.TM_CCOEFF_NORMED)
                    y, x = np.unravel_index(result.argmax(), result.shape)

                    time.sleep(0.2)
                    # 拖动起点

                    # linux
                    pyautogui.moveTo(x=location['x'], y=location['y'], duration=1, tween=pyautogui.linear)
                    time.sleep(0.2)
                    pyautogui.dragRel(xOffset=x, yOffset=random.randint(-5, 5), duration=2,
                                      button='left',
                                      tween=pyautogui.easeInElastic)
                    time.sleep(self.delay * 2)

                    if "再试一次" in driver.page_source and try_num == 10:
                        self.result['login'] = 0
                        self.result['errors'].append("滑动验证码错误")
                        return
                    if "用户中心" in driver.page_source:
                        break
            time.sleep(5)

            # 获取cookies
            if "用户中心" in driver.page_source:
                if self.doc == '库存数据':
                    driver.get('http://glzx.yonghui.cn/glzs/index.html#/Supplier/homePage')
                    time.sleep(5)
                cookies = driver.get_cookies()
                for i in range(len(cookies)):
                    self.cookie += cookies[i]['name'] + '=' + cookies[i]['value']
                    self.source_cookies[cookies[i]['name']] = cookies[i]['value']
                    if i != len(cookies) - 1:
                        self.cookie += '; '
                    if cookies[i]['name'] == 'signToken':
                        self.sign_token = cookies[i]['value']
                    elif cookies[i]['name'] == 'sessionCode':
                        self.session_code = cookies[i]['value']
                    elif cookies[i]['name'] == 'venderCode':
                        self.vender_code = cookies[i]['value']
            else:
                self.result['login'] = 0
                self.result['errors'].append("未能正确滑动验证码")
                return

    # 促销数据2
    @request_check
    def get_sales_data_header3(self):
        option = webdriver.ChromeOptions()
        # option.add_argument("--headless")
        option.add_argument('--no-sandbox')
        option.add_experimental_option('excludeSwitches', ['enable-automation'])
        with webdriver.Chrome(options=option) as driver:
            driver.maximize_window()
            driver.get(self.ka_url)
            time.sleep(1)
            WebDriverWait(driver, 15, 0.5).until(ec.presence_of_element_located((By.XPATH,
                                                                                 '//*[@id="app_substrate"]/section/div/div/section/main/div/section/div[3]/div[1]/div/div[2]/div[1]/input')))
            driver.find_element_by_xpath(
                '//*[@id="app_substrate"]/section/div/div/section/main/div/section/div[3]/div[1]/div/div[2]/div[1]/input').send_keys(
                self.username)
            driver.find_element_by_xpath(
                '//*[@id="app_substrate"]/section/div/div/section/main/div/section/div[3]/div[1]/div/div[2]/div[2]/input').send_keys(
                self.password)
            driver.find_element_by_xpath(
                '//*[@id="app_substrate"]/section/div/div/section/main/div/section/div[3]/div[1]/div/button').click()
            time.sleep(5)
            try:
                driver.find_element_by_class_name("bg-img")
            except Exception:
                self.result['login'] = 0
                self.result['errors'].append("验证码方式更改")
            else:
                # 滑块验证码
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.leftClick(x=300, y=300)
                time.sleep(5)
                pyautogui.press('F11')
                time.sleep(5)
                location = driver.find_element_by_xpath(
                    '//*[@id="captcha"]/div[2]/div/div[2]/div[2]/div[2]/div[2]/div/i').location
                try_num = 0
                while try_num < 10:
                    try_num += 1
                    # 获取原始图片
                    bg_img = driver.find_element_by_class_name("bg-img").get_attribute("src").split(";")[-1].split(',')[
                        -1]
                    bg_img_base64 = base64.b64decode(bg_img)
                    bg_img_np = np.frombuffer(bg_img_base64, dtype=np.uint8)
                    bg_img_gray = cv2.imdecode(bg_img_np, 0)
                    slice_img = \
                        driver.find_element_by_class_name('slice-img').get_attribute('src').split(";")[-1].split(',')[
                            -1]
                    slice_img_base64 = base64.b64decode(slice_img)
                    slice_img_np = np.frombuffer(slice_img_base64, dtype=np.uint8)
                    slice_img_gray = cv2.imdecode(slice_img_np, 0)
                    result = cv2.matchTemplate(bg_img_gray, slice_img_gray, cv2.TM_CCOEFF_NORMED)
                    y, x = np.unravel_index(result.argmax(), result.shape)

                    time.sleep(0.2)
                    # 拖动起点

                    # linux
                    pyautogui.moveTo(x=location['x'], y=location['y'], duration=1, tween=pyautogui.linear)
                    time.sleep(0.2)
                    pyautogui.dragRel(xOffset=x + random.randint(1, 2), yOffset=random.randint(-5, 5), duration=2,
                                      button='left',
                                      tween=pyautogui.easeInElastic)
                    time.sleep(self.delay * 2)

                    if "再试一次" in driver.page_source and try_num == 10:
                        self.result['login'] = 0
                        self.result['errors'].append("滑动验证码错误")
                        return
                    if "用户中心" in driver.page_source:
                        break
            time.sleep(5)
            # 选择供应商
            try:
                driver.find_element_by_xpath('/html/body/div[4]/div/div[2]/div/div[2]/button/span/span').click()
                time.sleep(3)
            except:
                pass
            try:
                driver.find_element_by_xpath(
                    '/html/body/div[1]/section/div/div/section/main/div/div[3]/div/div[2]/div/div[2]/button/span/span').click()
                time.sleep(3)
            except:
                pass
            try:
                driver.find_element_by_xpath('/html/body/div[1]/section/header/div/div[3]/div[1]').click()
                time.sleep(3)
                driver.find_element_by_xpath('//*[@value="{}"]'.format(self.req_params['venders1'])).click()
            except:
                pass
            time.sleep(6)

            # 获取cookies
            if "用户中心" in driver.page_source:
                time_stamp1 = str(int(time.time() * 1000))
                driver.get('http://glzx.yonghui.cn/glzs/index.html#/Supplier/homePage')
                time.sleep(5)
                cookies = driver.get_cookies()
                for i in range(len(cookies)):
                    self.cookie += cookies[i]['name'] + '=' + cookies[i]['value']
                    self.source_cookies[cookies[i]['name']] = cookies[i]['value']
                    if i != len(cookies) - 1:
                        self.cookie += '; '
                    if cookies[i]['name'] == 'signToken':
                        self.sign_token = cookies[i]['value']
                    elif cookies[i]['name'] == 'sessionCode':
                        self.session_code = cookies[i]['value']
                    elif cookies[i]['name'] == 'venderCode':
                        self.vender_code = cookies[i]['value']
                self.sign = driver.execute_script('return localStorage.getItem("SIGN");')[1:-1]
                self.login_token = driver.execute_script('return localStorage.getItem("login-token");')[1:-1]

                driver.find_element_by_xpath(
                    '/html/body/div/section/div/div/section/main/section/div/div/section/header/ul/li[2]').click()
                time.sleep(5)
                driver.find_element_by_xpath(
                    '/html/body/div/section/div/div/section/main/section/div/div/section/section/aside/div/ul/li[1]/ul/li[5]/span').click()
                time.sleep(3)
                driver.find_element_by_xpath(
                    '/html/body/div/section/div/div/section/main/section/div/div/section/section/main/div/div[2]/button[2]/span').click()
                time.sleep(3)
                driver.find_element_by_xpath(
                    '/html/body/div[1]/section/div/div/section/main/section/div/div/section/section/main/div/div[3]/div/div[2]/div/form/div[1]/div/div/input').send_keys(
                    self.req_params['ordertimestart'].replace('-', '/'))
                driver.find_element_by_xpath(
                    '/html/body/div[1]/section/div/div/section/main/section/div/div/section/section/main/div/div[3]/div/div[2]/div/form/div[2]/div/div/input').send_keys(
                    self.req_params['ordertimeend'].replace('-', '/'))
                time.sleep(3)
                driver.find_element_by_xpath(
                    '/html/body/div[1]/section/div/div/section/main/section/div/div/section/section/main/div/div[3]/div/div[2]/div/form/div[1]/label').click()
                time.sleep(3)
                driver.find_element_by_xpath(
                    '/html/body/div[1]/section/div/div/section/main/section/div/div/section/section/main/div/div[3]/div/div[3]/span/button[2]').click()
                time.sleep(3)

                driver.find_element_by_xpath('//*[@placeholder="请输入"]').clear()
                time.sleep(3)
                driver.find_element_by_xpath('//*[@placeholder="请输入"]').send_keys(time_stamp1)
                time.sleep(3)

                driver.find_element_by_xpath('//*[@class="tips-text no-indent"]').click()
                time.sleep(3)
                driver.find_element_by_xpath(
                    '//*[@class="el-button el-button--primary"]/span[text()="确认查询稍后到离线中心查看"]').click()
                time.sleep(3)

                driver.find_element_by_xpath('//*[@class="iconfont icon-xiazai mr10 f14"]').click()
                ActionChains(driver).key_down(Keys.CONTROL).send_keys("t").key_up(Keys.CONTROL).perform()
                time.sleep(3)
                for i in range(5):
                    time.sleep(30)
                    downloadPath = ''
                    headers = {
                        'Connection': 'keep-alive',
                        'login-id': 'Flag=N',
                        'signStr': 'fflineQuery%2Flist{}'.format(self.sign),
                        'login-token': self.login_token,
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36',
                        'Content-Type': 'application/json; charset=UTF-8',
                        'Accept': 'application/json, text/plain, */*',
                        'timestamp': '1639448610579',
                        'sign': 'afb0a2642b32480db1c8a08b506853d2',
                        'Origin': 'http://glzx.yonghui.cn',
                        'Referer': 'http://glzx.yonghui.cn/',
                        'Accept-Language': 'zh-CN,zh;q=0.9',
                        'Cookie': self.cookie
                    }
                    data = '{}'
                    response = requests.post('http://glmh.yonghui.cn/vender/report/center/offlineQuery/list',
                                             headers=headers,
                                             data=data, verify=False)
                    response.encoding = 'utf-8'
                    req = json.loads(response.text)
                    for j in req["data"]:
                        if j["name"] == time_stamp1 and str(j["status"]) == '2':
                            downloadPath = j['downloadPath']
                            break
                        else:
                            continue
                    if downloadPath != '':
                        driver.quit()
                        break
            else:
                self.result['login'] = 0
                self.result['errors'].append("未能正确滑动验证码")
        return downloadPath

    @request_check
    def get_sales_data_header4(self, url=''):
        headers = {
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Referer': 'http://glzx.yonghui.cn/',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cookie': self.cookie
        }

        response = requests.get(url, headers=headers, verify=False)
        # print(response.text)
        sales_line_data = list()
        res = io.BytesIO(response.content)
        ss = pd.read_csv(res, encoding='gbk', )
        ss = ss.where(ss.notnull(), '')
        dd = ss.groupby(['日期', '门店编码', '门店名称'])
        field_list = ['日期', '全国', '大区编码', '大区名称', '城市编码', '城市名称', '门店编码', '门店名称', '课组编码', '课组名称', '部类编码', '部类名称',
                      '大类编码', '大类名称', '中类编码', '中类名称', '小类编码', '小类名称', '商品条码',
                      '商品编码', '商品名称', '供应商编码', '供应商名称', '品牌编码', '品牌名称', '渠道编码', '渠道名称', '销售金额', '销售数量',
                      '促销扣款', '优惠券金额']
        head_field_list = ['日期', '全国', '大区编码', '大区名称', '城市编码', '城市名称', '门店编码', '门店名称', '课组编码', '课组名称', '部类编码', '部类名称',
                           '大类编码', '大类名称', '中类编码', '中类名称', '小类编码', '小类名称']
        detail_field_list = ['商品条码', '商品编码', '商品名称', '供应商编码', '供应商名称', '品牌编码', '品牌名称', '渠道编码', '渠道名称', '销售金额', '销售数量', '促销扣款', '优惠券金额']
        count = 0

        for group_index, group in dd:
            # count = len(dd)
            group_list = group.values.tolist()
            return_date = dict(head={}, data={}, code=1, errors='')
            return_date['data']['商品详情'] = list()
            for index, single in enumerate(group_list):
                detail_dict = dict()
                for head in head_field_list:
                    return_date['head'][head] = str(single[field_list.index(head)])
                for detail in detail_field_list:
                    detail_dict[detail] = str(single[field_list.index(detail)])
                if detail_dict['供应商编码'] == self.req_params['venders1']:
                    return_date['data']['商品详情'].append(detail_dict)
                    shopid_md5 = self.get_other_md5(return_date)
                    return_date['kms_md5'] = shopid_md5
            if len(return_date['data']['商品详情']) != 0:
                sales_line_data.append(return_date)
                count += 1
        # print(count)
        # with open('test.txt', 'a', encoding='utf-8') as f:
        #     f.write(str(sales_line_data))
        return sales_line_data, count

    def crawling_promotion_data(self):
        if self.req_params['ordertimestart'].isdigit():
            self.req_params['ordertimestart'] = time.strftime('%Y-%m-%d',
                                                              time.localtime(
                                                                  int(self.req_params['ordertimestart']) / 1000))
        if self.req_params['ordertimeend'].isdigit():
            self.req_params['ordertimeend'] = time.strftime('%Y-%m-%d',
                                                            time.localtime(int(self.req_params['ordertimeend']) / 1000))
        try:
            path = self.get_sales_data_header3()
        except LoginError:
            self.result['login'] = 0
            self.result['errors'].append('登陆失败')
        flag = True
        for i in range(1):
            # url = download_path
            current_page = 1
            total_page = -1
            warning = 0
            total_num_vds = 0
            try:
                shopid_header, count = self.get_sales_data_header4(url=path)
                total_num_vds += 1
                self.result['info']['crawling_num'] = count
                for data_detail in shopid_header:
                    self.result['form'].append(data_detail)
                    # print(shopid_header)
                time.sleep(self.delay)
            finally:
                if warning == 2:
                    flag = False
                    self.result['errors'].append('前三页抓取失败，自动退出')
                if total_page <= 0 or current_page > total_page:
                    warning += 1
                if current_page >= total_page != -1:
                    pass
                current_page += 1
        self.result['info']['succeed'] = self.result['info']['crawling_num']
        self.result['info']['failed'] = self.result['info']['crawling_num'] - self.result['info']['succeed']
        if flag:
            if self.result['info']['lose_max'] == 0:
                self.result['info']['total_num'] = self.result['info']['crawling_num']
            self.result['info']['total_min'] = self.result['info']['crawling_num'] + self.result['info']['lose_min']
            self.result['info']['total_max'] = self.result['info']['crawling_num'] + self.result['info']['lose_max']
        else:
            self.result['info']['lose_max'] = -1
            self.result['info']['total_min'] = self.result['info']['crawling_num']

    # 库存数据
    @request_check
    def get_inventory_data_header(self, stp='', venders=''):

        parm_random = self.create_random()
        headers = {
            'Connection': 'keep-alive',
            'login-id': 'Flag=N',
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36',
            'Content-Type': 'application/json; charset=UTF-8',
            'Origin': 'http://glzx.yonghui.cn',
            'Referer': 'http://glzx.yonghui.cn/glzs/index.html',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cookie': self.cookie
        }

        # 处理格式
        if self.req_params["brand"] == '':
            brand = []
        else:
            if len(self.req_params["brand"]) == 1:
                brand = self.req_params["brand"]
            else:
                brand = self.req_params["brand"].split(',')

        if self.req_params["goodsFlag"] == '':
            goodsFlag = []
        else:
            if len(self.req_params["goodsFlag"]) == 1:
                goodsFlag = self.req_params["goodsFlag"]
            else:
                goodsFlag = self.req_params["goodsFlag"].split(',')

        if self.req_params["goodsStatus"] == '':
            goodsStatus = []
        else:
            if len(self.req_params["goodsStatus"]) == 1:
                goodsStatus = self.req_params["goodsStatus"]
            else:
                goodsStatus = self.req_params["goodsStatus"].split(',')

        if self.req_params["middleClass"] == '':
            middleClass = []
        else:
            if len(self.req_params["middleClass"]) == 1:
                middleClass= self.req_params["middleClass"]
            else:
                middleClass = self.req_params["middleClass"].split(',')

        #  获取头页面
        data_in = {"param":{"aggs":["goodsid","bar_code","goodsname","brand","brand_name","catg_s_id","catg_s_name","standard","unit_name","pkg_pcs_s"],
                    "shopId":[stp] if stp else [],  # 门店
                    "brand": brand,  # 品牌
                    "metrics":["inv_qty","inv_amt","in_transit_inv_qty","in_transit_inv_amt"],
                    "middleClass":middleClass,  # 类别
                    "goodsFlag": goodsFlag,  # 商品标识
                    "goodsStatus":goodsStatus,  # 商品状态
                    "venderChildId":[venders],  # 供应商
                    "stockType":[self.req_params["stockType"]],  # 库存类型
                    "isAgg": "1",
                    "orderField":"", "orderType":""},
                    "random": parm_random,
                    "signCode": hashlib.md5(('GLZX_03' + parm_random[2:5] + self.sign_token).encode('utf-8')).hexdigest() }
        data_on = json.dumps(data_in, ensure_ascii=False)
        data = "{}".format(data_on).replace(' ', '')
        response = requests.post('http://glzx.yonghui.cn/vender/report/reportes/dynamic/invRealtimeServiceImpl/queryApi', headers=headers, data=data.encode('utf-8'), verify=False)
        return response.text

    @analyze_check
    def analyze_inventory_data_header(self, inventory_data_header):
        inventory_data_header = json.loads(inventory_data_header)
        inventory_header_data = list()
        inventory_data_headers = inventory_data_header['data']
        if inventory_data_headers:
            for row in inventory_data_headers:
                detail = dict()
                detail['商品编码'] = str(row['goodsid'])
                detail['商品条码'] = str(row['bar_code'])
                detail['商品名称'] = str(row['goodsname'])
                detail['品牌编码'] = str(row['brand'])
                detail['品牌名称'] = str(row['brand_name'])
                detail['小类编码'] = str(row['catg_s_id'])
                detail['小类名称'] = str(row['catg_s_name'])
                detail['规格'] = str(row['standard'])
                detail['单位'] = str(row['unit_name'])
                inventory_header_data.append(detail)
        message = dict()
        message['total_page'] = -(-inventory_data_header['total'] // 10)
        message['total_num'] = inventory_data_header['total']
        message['current_num'] = len(inventory_header_data)
        return inventory_header_data, message

    @request_check
    def get_inventory_data_line(self, goodsid=''):
        parm_random = self.create_random()
        data_in = {"param": {
            "barCode": goodsid,
            "shopId": [],  # 门店
            "brand": [],  # 品牌
            "fields": ["shop_id","shop_name","goodsid","bar_code","goodsname","brand","brand_name","standard","unit_name","pkg_pcs_s","inv_qty","inv_amt","in_transit_inv_qty","in_transit_inv_amt"],
            "middleClass": [],  # 类别
            "goodsFlag": [],  # 商品标识
            "goodsStatus": [],  # 商品状态
            "venderChildId": [],  # 供应商
            "stockType": [self.req_params["stockType"]],  # 库存类型
            "isAgg": "0",
            "orderField": "", "orderType": ""},
            "random": parm_random,
            "signCode": hashlib.md5(('GLZX_03' + parm_random[2:5] + self.sign_token).encode('utf-8')).hexdigest()}
        data_on = json.dumps(data_in, ensure_ascii=False)
        data = "{}".format(data_on).replace(' ', '')

        headers = {
            'Connection': 'keep-alive',
            'login-id': 'Flag=N',
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36',
            'Content-Type': 'application/json; charset=UTF-8',
            'Origin': 'http://glzx.yonghui.cn',
            'Referer': 'http://glzx.yonghui.cn/glzs/index.html',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cookie': self.cookie
        }

        req = requests.post('http://glzx.yonghui.cn/vender/report/reportes/dynamic/invRealtimeServiceImpl/queryApi', data=data, headers=headers)
        return req.text

    @analyze_check
    def analyze_inventory_data_line(self, inventory_data_line):
        inventory_data_line = json.loads(inventory_data_line)
        inventory_line_data = dict()
        rows = inventory_data_line['data']
        inventory_line_data['商品详情'] = []
        if inventory_data_line:
            for row in rows:
                detail = dict()
                detail['门店编码'] = str(row['shop_id'])
                detail['门店名称'] = str(row['shop_name'])
                detail['件装数'] = str(row['pkg_pcs_s'])
                detail['库存数量'] = str(row['inv_qty'])
                detail['库存金额'] = str(row['inv_amt'])
                detail['在库存数量'] = str(row['in_transit_inv_qty'])
                detail['在库存金额'] = str(row['in_transit_inv_amt'])
                inventory_line_data['商品详情'].append(detail)
            return inventory_line_data

    def crawling_inventory_data(self):
        try:
            self.login()
            # self.cookie = 'sessionTimeOut=604800000; signToken=f4189633-1972-4fda-8d54-5e8d55954d40; tokenTime=2021-09-28%2002%3A59%3A59; sa_jssdk_2015_glzx_yonghui_cn=%7B%22distinct_id%22%3A%2213983875338%22%2C%22first_id%22%3A%2217c2b34de7516-0f939dda7321e4-b7a1a38-1327104-17c2b34de76759%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%7D; id=201704181421253648; idStatus=1; mainId=; idType=1; venderRank=2; venderCode=126334CQ; isAssetVender=false; isParper=1; clearFlag=0; password=; level=0; registerChannel=GLZX_03; isVirtual=0; guideFlag=N; glysBindFlag=0; venderUsingGlzxDzjsFlag=1; glysVenderCode=126334CQ; glysBindId=; glysVenderName=%u91CD%u5E86%u5E02%u5929%u53CB%u4E73%u4E1A%u80A1%u4EFD%u6709%u9650%u516C%u53F8%u9500%u552E%u5206%u516C%u53F8; phone=13983875338; nickname=%u5929%u53CB; createBy=13220300878; createTime=2017-04-18T14%3A21%3A23; updateTime=2021-06-02T14%3A38%3A37; tokenid=374DC54F985845E8B04CB711FADA11C5; tokentime=2021-06-02T14%3A38%3A37; isTobaccoVender=0; mobilePhone=13983875338; sessionCode=F9F7406692AC4EB2AA47D551F09CF3A1; accountName=%u91CD%u5E86%u5E02%u5929%u53CB%u4E73%u4E1A%u80A1%u4EFD%u6709%u9650%u516C%u53F8%u9500%u552E%u5206%u516C%u53F8; venderName=%u91CD%u5E86%u5E02%u5929%u53CB%u4E73%u4E1A%u80A1%u4EFD%u6709%u9650%u516C%u53F8%u9500%u552E%u5206%u516C%u53F8; virtualVenderCode=; taxId=91500112739827719F; lastTime=2018-03-07T18%3A49%3A05; uid=201704181421253648; refuseWarnFlag=0; refuseReason=; ssqConfirmFlag=0; ssqConfirmMenuFlag=0; f4189633-1972-4fda-8d54-5e8d55954d40=; venderFlag=undefined; verifyFlag=0; verifyFailReason=; bankCode=102653001387; bankName=%u4E2D%u56FD%u5DE5%u5546%u94F6%u884C%u80A1%u4EFD%u6709%u9650%u516C%u53F8%u91CD%u5E86%u5317%u90E8%u65B0%u533A%u652F%u884C; sensorsdata2015jssdkcross=%7B%22%24device_id%22%3A%2217c2bb1b319659-08ed57a11bad55-b7a1a38-1327104-17c2bb1b31a4bc%22%7D; yhTraceUid=201704181421253648; UM_distinctid=17c2bb2209b339-093d5c31a65af2-b7a1a38-144000-17c2bb2209d414; CNZZDATA1271236333=590526686-1632813369-http%253A%252F%252Fglzx.yonghui.cn%252F%7C1632813369; yhTraceSid=1009e9b1-e616-890e-21e1-6d03f413df1a; yhTraceId=5bd7eba6-99bb-04d0-968c-b8966ab453a5'
        except LoginError:
            self.result['login'] = 0
            self.result['errors'].append('登录失败')

        if self.result['login'] == 1:
            if len(self.venders) == 0:
                try:
                    self.get_vender_list()
                except RequestError:
                    self.result['errors'].append('获取供应商列表失败')
            if self.vender_code in self.venders:
                self.venders.remove(self.vender_code)
                self.venders.insert(0, self.vender_code)
            flag = True
            total_num = 0
            for i in range(len(self.venders)):
                if i != 0 and self.venders[i] != '':
                    vender_code = self.venders[i]
                    try:
                        self.change_login_vender(vender_code)
                    except RequestError:
                        self.result['errors'].append('切换至{}供应商失败'.format(vender_code))
                        continue
                if self.venders[i] != '':
                    current_page = 1
                    total_page = -1
                    total_num_vds = 0
                    warning = 0
                    for stp in self.sold_to_party:
                        stp= stp["code"]
                        for fuuu in range(1):
                            try:
                                inventory_data_header = self.get_inventory_data_header(stp=stp, venders=self.venders[i])
                                inventory_data_header_data, message = self.analyze_inventory_data_header(inventory_data_header)
                                time.sleep(self.delay)
                            except RequestError:
                                if current_page == total_page:
                                    self.result['errors'].append(
                                        '供应商{}第{}页抓取失败，丢失1-{}条单据数据'.format(stp, current_page, self.page_size))
                                    self.result['info']['lose_min'] += 1
                                else:
                                    self.result['errors'].append(
                                        '供应商{}第{}页抓取失败，丢失{}条单据数据'.format(stp, current_page, self.page_size))
                                    self.result['info']['lose_min'] += self.page_size
                                self.result['info']['lose_max'] += self.page_size
                            except AnalyzeError:
                                if current_page == total_page:
                                    self.result['errors'].append(
                                        '供应商{}第{}页解析失败，丢失1-{}条单据数据'.format(stp, current_page, self.page_size))
                                    self.result['info']['lose_min'] += 1
                                else:
                                    self.result['errors'].append(
                                        '供应商{}第{}页解析失败，丢失{}条单据数据'.format(stp, current_page, self.page_size))
                                    self.result['info']['lose_min'] += self.page_size
                                self.result['info']['lose_max'] += self.page_size
                            else:
                                total_page = max(message['total_page'], total_page)
                                total_num_vds = max(message['total_num'], total_num_vds)
                                self.result['info']['crawling_num'] += message['current_num']
                                for head in inventory_data_header_data:
                                    inventory_data = dict(head={}, data={}, code=1, errors='')
                                    inventory_data['head'] = head
                                    goodsid = head['商品条码']
                                    try:
                                        inventory_data_line = self.get_inventory_data_line(goodsid=goodsid)
                                        inventory_data_line_data = self.analyze_inventory_data_line(inventory_data_line)
                                        time.sleep(self.delay)
                                    except RequestError:
                                        inventory_data['code'] = 0
                                        inventory_data['errors'] = '单据行抓取错误'
                                    except AnalyzeError:
                                        inventory_data['code'] = 0
                                        inventory_data['errors'] = '单据行解析错误'
                                    else:
                                        inventory_data['data'] =inventory_data_line_data
                                        self.result['info']['succeed'] += 1
                                    finally:
                                        order_md5 = self.get_md5(inventory_data)
                                        inventory_data['kms_md5'] = order_md5
                                        self.result['form'].append(inventory_data)
                            finally:
                                if warning == 2:
                                    flag = False
                                    self.result['info']['lose_min'] -= (warning + 1) * self.page_size
                                    self.result['errors'].append('供应商{}前三页抓取失败，自动切换'.format(stp))
                                    break
                                if total_page <= 0 or current_page > total_page:
                                    warning += 1
                                if current_page >= total_page != -1:
                                    break
                                current_page += 1
                        total_num += total_num_vds
                    self.result['info']['failed'] = self.result['info']['crawling_num'] - self.result['info']['succeed']
                    if flag:
                        self.result['info']['total_num'] = total_num
                        self.result['info']['total_min'] = self.result['info']['crawling_num'] + self.result['info']['lose_min']
                        self.result['info']['total_max'] = self.result['info']['crawling_num'] + self.result['info']['lose_max']
                    else:
                        self.result['info']['lose_max'] = -1
                        self.result['info']['total_min'] = self.result['info']['crawling_num']


if __name__ == '__main__':

    yonghui = {"deadlinestart": "",
               "flag": "2",
               "ordertimeend": "2022-03-24",
               "sold_to_party": [{"name": "", "code": ""}],
               "KMS_path_type": "DEV环境",
               "password": "577cb9378aa978e1df7ac3c337d00b06",
               "venders": "A00025",
               "ordertimestart": "2022-03-24",
               "sheetid": "",
               "kms_ip": "",
               "force": "0",
               "ka_name": "永辉",
               "tenantry_id": "46cf3c61e30658e302a30bba71a1c156",
               "deadlineend": "",
               "status": "",
               "username": "18155198037"}

    aa = YonghuiSpider(req_params=yonghui)
    aa.crawling_inventory_data()

    res1 = aa.result
    res1 = json.dumps(res1, ensure_ascii=False)
    print(res1)
