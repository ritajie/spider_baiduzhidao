import requests
from bs4 import BeautifulSoup
import threading
import json
import time
import os
import re


def BetterTime(timestr):
    "将各种格式的时间字符串规范化"
    if '今天' in timestr or '前' in timestr:
        localtime = time.localtime()
        year = str(localtime.tm_year)
        month = str(localtime.tm_mon)
        day = str(localtime.tm_mday)
        if len(month) == 1:
            month = ('0'+month)
        if len(day) == 1:
            day = ('0'+month)
        return year+'-'+month+'-'+day
    thetime = re.findall('\d{4}-\d{1,2}-\d{1,2}', timestr)
    if thetime:
        return thetime[0]

    return timestr


def AllZhidaoUrls(moviename):
    "get all urls of zhidao about 'moviename'"
    url = 'http://zhidao.baidu.com/search'
    data = {
        'lm': '0',
        'rn': '10',
        'pn': '0',
        'fr': 'search',
        'ie': 'gbk',
        'word': moviename
    }
    # 1.解析搜索结果第一页 获取最大页码 顺便把第一页百度知道url给yield出来
    res = requests.get(url,  params=data)
    res.encoding = 'gbk'
    soup = BeautifulSoup(res.text, 'html.parser')

    # 先把第一页的百度知道yield出来
    arr = soup.select('#wgt-list')
    print('url:%s' % (url))
    print('data:', data)
    print('arr:', arr)
    for eachtip in arr[0].select('dl'):
        titleurl = eachtip.select('.ti')[0].attrs.get('href')
        yield {'last_pn': 0, 'url': titleurl}

    # 获取最大页码：pn
    endurl = soup.select('.pager')[0].select('a')[-1].attrs.get('href')
    maxpn = int(endurl.split('=')[-1])
    # maxpn = 10
    # 开始get每一页搜索结果
    for pn in range(10, maxpn+1, 10):
        data['pn'] = pn
        res = requests.get(url, params=data)
        res.encoding = 'gbk'
        soup = BeautifulSoup(res.text, 'html.parser')
        # 先把每一页的百度知道yield出来
        arr = soup.select('#wgt-list')
        if len(arr) > 0:
            for eachtip in arr[0].select('dl'):
                titleurl = eachtip.select('.ti')[0].attrs.get('href')
                yield {'last_pn': maxpn-pn, 'url': titleurl}


def ParserSingleZhidao(zhidaourl):
    "解析一个百度知道的页面 提取重要信息：时间、点赞数、反对数、标题和回答内容"
    res = requests.get(zhidaourl)
    res.encoding = 'gbk'
    soup = BeautifulSoup(res.text, 'html.parser')
    try:
        title = soup.select('.ask-title ')[0].text
    except IndexError as e:
        return
    # 1.解析最佳答案
    bestans = soup.select('.wgt-best')
    if bestans:
        bestans = bestans[0]
        # 获取点赞数和讨厌数
        nums = bestans.select('.evaluate')
        agree = nums[0].attrs.get('data-evaluate')
        disagree = nums[1].attrs.get('data-evaluate')
        # 获取回答内容
        mainContent = bestans.select('[accuse="aContent"]')[0]
        content = mainContent.text.strip()
        # 获取时间
        timestr = bestans.select('.pos-time')[0].text.strip()
        thetime = BetterTime(timestr)
        yield {'title': title, 'agree': agree, 'disagree': disagree, 'content': content, 'zhidaourl': zhidaourl, 'time': thetime}

    # 2.解析普通答案
    nomal_anses = soup.select('.wgt-answers')
    for eachans in nomal_anses:
        # 获取点赞数和讨厌数
        nums = eachans.select('.evaluate')
        agree = nums[0].attrs.get('data-evaluate')
        disagree = nums[1].attrs.get('data-evaluate')
        # 获取回答内容
        mainContent = eachans.select('[accuse="aContent"]')[0]
        content = mainContent.text.strip()
        # 获取时间
        timestr = eachans.select('.pos-time')[0].text.strip()
        thetime = BetterTime(timestr)

        yield {'title': title, 'agree': agree, 'disagree': disagree, 'content': content, 'zhidaourl': zhidaourl, 'time': thetime}

    # 如果有“下一页”，递归之
    pager_next = soup.select('.pager-next')
    if pager_next:
        nexturl = 'http://zhidao.baidu.com'+pager_next[0].attrs.get('href')
        for ans in ParserSingleZhidao(nexturl):
            yield ans


# 存放爬去的所有最终信息
bigarr = list()


def aThread(last_pn, zhidaourl):
    for ans in ParserSingleZhidao(zhidaourl):
        print(last_pn, time.ctime(), ans['time'])
        bigarr.append(ans)


def Main(moviename):
    # 0. 新建文件夹
    localtime = time.localtime()
    year = str(localtime.tm_year)
    month = str(localtime.tm_mon)
    day = str(localtime.tm_mday)
    dirname = year+'_'+month+'_'+day+'_'+moviename
    # 如果这个电影在一天内已经检索过了 就不再检索了
    if os.path.exists(dirname):
        return dirname

    threads = list()
    # 1. 获取百度知道url 对每个url进行解析 解析结果装进bigarr数组里
    for ans1 in AllZhidaoUrls(moviename):
        each_thread = threading.Thread(
            target=aThread, args=[ans1.get('last_pn'), ans1.get('url')])
        each_thread.start()
        threads.append(each_thread)
    for each_thread in threads:
        each_thread.join()
    # 2. bigarr去重 排序 结果newarr
    arr = list()
    # 存放已经存在的答案：时间，点赞，反对，标题，回答内容（不用url，因为多页的回答里都存在最佳答案）
    oldarr = list()
    for i in bigarr:
        temparr = [i.get('time'), i.get('agree'), i.get(
            'disagree'), i.get('title'), i.get('content')]
        if temparr not in oldarr:
            arr.append(i)
            oldarr.append(temparr)
    # 排序 按照agree-disagree
    newarr = sorted(arr, key=lambda a: a.get('time'), reverse=True)
    # 3. 将结果存储进文件
    file = open(dirname, 'w')
    file.write(json.dumps(newarr))
    file.close()
    return dirname


if __name__ == '__main__':
    Main('钢铁侠')
