#!/usr/bin/env python3
"""Auto-discover new hot sectors at pre-market/noon/post-market. Injects into data.json."""
import json, os, time
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(DIR, 'data.json')

KNOWN = {'AI芯片','CPO','光模块','光纤光缆','连接器','PCB','MLCC','电容','电子树脂','PPE','电子铜箔',
    'HBM','存储芯片','AI服务器','超节点','液冷','交换机','DrMOS','数据中心','AIDC',
    '半导体设备','光刻胶','CoWoS','硅片','六氟化钨','玻璃基板','TGV','培育钻石','超导','碳纤维',
    '人形机器人','商业航天','6G','固态电池','低空经济','eVTOL','空间计算','物理AI','钨稀土',
    '芯片','半导体','光通信','存储','航天','军工','通用航空','低空','有色','稀土','钨','钼',
    '通信','电源','散热','AI','光纤','电子','硅片','封装','光刻','钻石','小金属','稀缺'}
EXCLUDE = {'昨日打板','科创板做市','融资融券','大盘股','HS300','上证180',
    '标准普尔','周期股','行业龙头','MSCI中国','GDR','参股期货','首发经济',
    '金融地产','DRG/DIP','CAR-T','共享经济','可燃冰','低碳冶金','草甘膦',
    '动力电池回收','托育服务','刀片电池','病毒防治','CRO','锂矿概念'}

def fetch(url, retries=2):
    for _ in range(retries):
        try:
            r = urlopen(Request(url, headers={'User-Agent': UA, 'Accept': '*/*'}), timeout=15)
            return r.read().decode('utf-8', errors='replace')
        except: time.sleep(2)
    return None

def discover():
    cst = datetime.now(timezone.utc) + timedelta(hours=8)
    today = cst.strftime('%m/%d')
    text = fetch('http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=60&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:3&fields=f2,f3,f12,f14')
    if not text: return
    try: items = json.loads(text).get('data',{}).get('diff',[])
    except: return

    new_hot = []
    for h in items:
        pct = h.get('f3',0) or 0
        if pct < 2.0: continue
        name = h.get('f14','')
        skip = False
        for ex in EXCLUDE:
            if ex in name or name in ex: skip = True; break
        if skip: continue
        for kw in KNOWN:
            if kw in name or name in kw: skip = True; break
        if not skip:
            new_hot.append((h, pct))

    if not new_hot:
        print('No new sectors')
        return

    discovered = []
    for h, pct in new_hot[:5]:
        bcode, name = h.get('f12',''), h.get('f14','')
        stocks = []
        for _ in range(2):
            try:
                t = fetch('http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=12&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:%s&fields=f2,f3,f12,f14' % bcode)
                if t:
                    for s in json.loads(t).get('data',{}).get('diff',[]):
                        stocks.append({'c': s.get('f12',''), 'n': s.get('f14',''), 'chg': s.get('f3',0)})
                    break
            except: pass
        if not stocks: continue

        icons = {'航天':'🚀','航空':'✈️','军工':'🛡️','黄金':'🥇','金融':'💰','银行':'🏦',
                 '医药':'💊','医疗':'🏥','消费':'🛒','食品':'🍜','白酒':'🍶','汽车':'🚗',
                 '新能源':'🔋','光伏':'☀️','风电':'🌬️','煤炭':'⛏️','石油':'🛢️',
                 '化工':'🧪','钢铁':'🏗️','电力':'⚡','环保':'♻️','游戏':'🎮','传媒':'📺','锂':'🔋'}
        icon = next((ic for kw,ic in icons.items() if kw in name), '🔥')
        sig = 'major' if pct >= 4 else 'good'
        pct_s = '%+.1f' % pct

        discovered.append({
            'id': 'dyn_%s' % bcode, 'n': name, 'icon': icon, 'sig': sig,
            'tag': '%s%%|%s' % (pct_s.lstrip('+'), today),
            'd': '%s板块%s%%,当日新晋热门。共%d只标的。' % (name, pct_s, len(stocks)),
            'st': stocks,
            'ch': {'up': '---', 'mid': '<em>板块%s%%</em>' % pct_s, 'down': '---'},
            'ev': '%s自动发现' % today, 'stars': 3
        })

    if not discovered:
        print('No valid stocks')
        return

    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    old_dyn = data.get('dynamicSectors', [])
    merged = discovered + old_dyn
    seen, dedup = set(), []
    for ds in merged:
        k = ds['id']
        if k not in seen: seen.add(k); dedup.append(ds)
    data['dynamicSectors'] = dedup[:8]
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    names = ', '.join(d['n'] for d in discovered)
    print('OK: %d new sectors: %s' % (len(discovered), names))

if __name__ == '__main__':
    discover()
