#!/usr/bin/env python3
"""Auto-discover new hot sectors at pre-market/noon/post-market.
Also flags uncovered hot sectors (->_hot_uncovered for Claude to review)."""
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

# All 60 sectors we track (used to detect uncovered hot boards)
OUR_60 = {'锂矿/盐湖提锂','锂电池/电解液','光伏/太阳能','风电','储能','新能源汽车',
    '煤炭','黄金/贵金属','铜铝有色','化工','钢铁','银行','券商','保险','房地产开发',
    '白酒','食品饮料','医药/CRO','医疗器械','算电协同','算力租赁/GPU云','Token工厂/模型推理',
    '稀土永磁','钼/小金属','电子特气/工业气体','半导体靶材',
    'AI智能体/应用','核电/核能','量子计算/量子科技','卫星互联网/北斗',
    'AI芯片','CPO/硅光','光模块','光纤光缆','连接器/铜连接',
    'PCB/覆铜板','MLCC电容','电子树脂/PPE','电子铜箔','HBM/存储芯片',
    'AI服务器/超节点','液冷散热','交换机/网络','电源/DrMOS','数据中心/AIDC',
    '半导体设备','光刻胶','先进封装CoWoS','半导体硅片',
    '六氟化钨WF₆','玻璃基板TGV','培育钻石/散热','超导/核聚变','碳纤维',
    '人形机器人','商业航天','6G/通信','固态电池','低空经济eVTOL','空间计算/物理AI','钨稀土'}

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

    # ── NEW: Flag uncovered hot sectors (Claude reads _hot_uncovered next session) ──
    hot_uncovered = []
    for h in items[:30]:
        pct = h.get('f3', 0) or 0
        if pct < 1.5: continue
        name = h.get('f14', '')
        if any(our in name or name in our for our in OUR_60): continue
        if any(ex in name or name in ex for ex in EXCLUDE): continue
        hot_uncovered.append({'n': name, 'pct': round(pct, 1)})

    # Load and update data.json
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['_hot_uncovered'] = hot_uncovered[:15]

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

    if discovered:
        old_dyn = data.get('dynamicSectors', [])
        merged = discovered + old_dyn
        seen, dedup = set(), []
        for ds in merged:
            k = ds['id']
            if k not in seen: seen.add(k); dedup.append(ds)
        data['dynamicSectors'] = dedup[:8]
        names = ', '.join(d['n'] for d in discovered)
        print('OK: %d new sectors: %s' % (len(discovered), names))

    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if hot_uncovered:
        print('Uncovered hot (%d): %s' % (len(hot_uncovered), ', '.join(h['n'] for h in hot_uncovered[:8])))
    else:
        print('All hot sectors covered ✅')

if __name__ == '__main__':
    discover()
