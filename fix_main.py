#!/usr/bin/env python3
"""Rewrite main() to cleanly add dynamic sector discovery"""
import re

with open('D:/projects/market-dashboard/.github/scripts/fetch_data.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find: def main(): → everything until the end
idx_def_main = content.find('\ndef main():')
idx_next_func = content.find('\ndef ', idx_def_main + 1)
if idx_next_func == -1:
    idx_next_func = len(content)

# Build the clean main() replacement
clean_main = '''
def main():
    now = datetime.now(timezone.utc)
    cst = now + timedelta(hours=8)
    is_trading = cst.weekday() < 5 and 9 <= cst.hour < 15

    codes = get_stock_codes()
    stock_sector = get_sector_mapping()
    indices = get_indices()
    sectors = get_sector_heat()
    live = get_live_prices(codes)
    fund = get_fund_flow_em()
    zt_ladder = get_zt_ladder(cst)

    winners, losers = compute_winners_losers(live, stock_sector, sectors)
    next_update = '今日 17:00 收盘复盘' if is_trading else '下个交易日 9:15 开盘扫描'

    # Load existing data
    preserve = {}
    preserve_keys = ['sectors', 'top3', 'picks', 'briefing', 'events', 'layout', 'bHistory', 'concepts', 'dynamicSectors']
    old_cycle = None
    old_briefing_date = ''
    old_dynamic = []
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            try:
                old = json.load(f)
                for k in preserve_keys:
                    if k in old and old[k]: preserve[k] = old[k]
                old_recap = old.get('recap', {})
                if 'cycle' in old_recap and old_recap['cycle']: old_cycle = old_recap['cycle']
                old_briefing = old.get('briefing', {})
                old_briefing_date = old_briefing.get('updated', '') if old_briefing else ''
                old_dynamic = old.get('dynamicSectors', [])
            except: pass

    # Auto-fresh sectors/briefing if stale (Claude data >12h old)
    cst_str = cst.strftime('%Y-%m-%d')
    sectors_fresh = preserve.get('sectors') and old_briefing_date.startswith(cst_str)
    if not sectors_fresh and sectors:
        preserve['sectors'] = auto_sectors(sectors, indices, preserve.get('sectors'))

    briefing_fresh = preserve.get('briefing') and old_briefing_date.startswith(cst_str)
    if not briefing_fresh and sectors:
        ai = indices[:4] if indices else []
        idx_text = ' | '.join([f"{i['n']} {i['chg']}" for i in ai])
        ai_top3 = [{'r': 1, 't': f"📊 大盘实时: {idx_text}", 'b': f"更新时间 {cst.strftime('%H:%M')}", 's': []}]
        if sectors:
            top5 = sorted(sectors, key=lambda x: float(x['s'].replace('%','').replace('+','').replace('-','-')), reverse=True)[:5]
            ai_top3.append({'r': 2, 't': f"🔥 今日最热: {', '.join([h['n'] for h in top5])}", 'b': f"领涨: {top5[0]['n']} {top5[0]['s']}", 's': [f"{h['n']} {h['s']}" for h in top5]})
        if zt_ladder and zt_ladder.get('tiers'):
            max_b = zt_ladder['tiers'][0]
            ai_top3.append({'r': 3, 't': f"🪜 连板: 最高{max_b['boardCount']}连板，共{zt_ladder['totalCount']}只涨停", 'b': f"涨停{zt_ladder['totalCount']}只", 's': [f"{s['c']} {s['n']}" for s in max_b['stocks'][:6]]})
        preserve['briefing'] = {'updated': cst.strftime('%Y-%m-%d %H:%M CST'), 'top3': ai_top3, 'picks': preserve.get('picks', [])}
        preserve['top3'] = ai_top3

    cycle = old_cycle or (auto_cycle(indices) if indices else None) or {'phase': '等待数据', 'phaseIcon': '📊', 'signals': ['行情数据加载中'], 'riskLevel': 'medium', 'riskLabel': '等待', 'suggestion': '等待开盘'}

    # Auto-discover NEW hot sectors at noon (only once per day 12:00-12:15 CST)
    our_kw = ['AI芯片','CPO','光模块','光纤光缆','连接器','PCB','覆铜板','MLCC','电容','电子树脂','PPE','电子铜箔',
              'HBM','存储芯片','AI服务器','超节点','液冷','散热','交换机','电源','DrMOS','数据中心','AIDC',
              '半导体设备','光刻胶','先进封装','CoWoS','半导体硅片','六氟化钨','WF6','玻璃基板','TGV',
              '培育钻石','超导','核聚变','碳纤维','人形机器人','商业航天','6G','固态电池','低空经济','eVTOL',
              '空间计算','物理AI','钨稀土','芯片','半导体','光通信','存储','航天','机器人','有色','稀土','钨']
    is_noon = cst.hour == 12 and 0 <= cst.minute < 15
    if is_noon and sectors:
        new_hot = []
        for h in sectors[:40]:
            name = h['n']; pct = float(h['s'].replace('%','').replace('+','').replace('-','-'))
            if pct < 2.0: continue
            if any(kw in name or name in kw for kw in our_kw): continue
            new_hot.append((h, pct))

        if new_hot:
            discovered = []
            for h, pct in new_hot[:5]:
                bcode = h.get('f12', '')
                stocks = []
                for _ in range(2):
                    try:
                        url = f'http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=12&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:{bcode}&fields=f2,f3,f12,f14'
                        t = fetch(url, encoding='utf-8')
                        if t: stocks = [{'c': i.get('f12',''), 'n': i.get('f14',''), 'chg': i.get('f3',0)} for i in json.loads(t).get('data',{}).get('diff',[])[:12]]
                        break
                    except: pass

                icons = {'航天':'🚀','航空':'✈️','军工':'🛡️','黄金':'🥇','金融':'💰','银行':'🏦',
                         '医药':'💊','医疗':'🏥','消费':'🛒','食品':'🍜','白酒':'🍶','汽车':'🚗',
                         '新能源':'🔋','光伏':'☀️','风电':'🌬️','煤炭':'⛏️','石油':'🛢️',
                         '化工':'🧪','钢铁':'🏗️','电力':'⚡','环保':'♻️','游戏':'🎮','传媒':'📺','教育':'📚'}
                icon = next((ic for kw,ic in icons.items() if kw in name), '📊')
                tag = f'🔥{h[\"s\"]}|{cst.strftime(\"%m/%d\")} 新晋'
                sig = 'major' if pct >= 4 else 'good'

                discovered.append({
                    'id': f'dyn_{bcode}', 'n': name, 'icon': icon, 'sig': sig,
                    'tag': tag, 'd': f'{name}板块{h[\"s\"]},当日新晋热门。共{len(stocks)}只标的。',
                    'st': stocks, 'ch': {'up': '—', 'mid': f'<em>板块{h[\"s\"]}</em>', 'down': '—'},
                    'ev': f'📌{cst.strftime(\"%m/%d\")}自动发现', 'stars': 3
                })

            if discovered:
                merged = discovered + old_dynamic
                seen = set(); dedup = []
                for ds in merged:
                    k = ds.get('id', ds['n'])
                    if k not in seen: seen.add(k); dedup.append(ds)
                preserve['dynamicSectors'] = dedup[:8]

    # Auto-generate fixed events
    auto_events = [
        {'d': '6月15日', 'icon': '💰', 'e': '章源钨业上半月长单报价', 's': '钨/稀土', 'big': 1, 'desc': '每半月定期催化'},
        {'d': '6月16日', 'icon': '🔋', 'e': 'AEPT固态电池产业大会(上海)', 's': '固态电池', 'big': 1, 'desc': '全球固态电池白皮书'},
        {'d': '6月16日', 'icon': '👓', 'e': '深圳首届AI眼镜展', 's': '消费电子', 'big': 0, 'desc': '雷鸟/华为/中兴联签'},
        {'d': '6月18日', 'icon': '📊', 'e': '5月半导体销售额(SIA)', 's': '半导体', 'big': 0, 'desc': '验证涨价传导'},
        {'d': '6月20日', 'icon': '🟧', 'e': '三星电机MLCC长单报价', 's': 'MLCC', 'big': 1, 'desc': '村田涨后三星是否跟进'},
        {'d': '6月24日', 'icon': '💾', 'e': '美光财报发布', 's': '存储芯片', 'big': 1, 'desc': '全球存储景气风向标'},
        {'d': '6月24日', 'icon': '🧠', 'e': '英伟达年度股东大会', 's': 'AI芯片', 'big': 0, 'desc': 'AI工厂路线图'},
        {'d': '6月30日', 'icon': '🏭', 'e': '中国智算产业生态年会', 's': 'AI算力', 'big': 0, 'desc': '国产智算基础设施'},
        {'d': '7月1日', 'icon': '🔴', 'e': '日本WF6永久停产', 's': '六氟化钨', 'big': 1, 'desc': '全球25%产能退出'},
        {'d': '7月1日', 'icon': '🟧', 'e': '村田MLCC涨价10-40%生效', 's': 'MLCC', 'big': 1, 'desc': '年内第三轮'},
        {'d': '7月1日', 'icon': '✈️', 'e': '新民航法施行', 's': '低空经济', 'big': 1, 'desc': '300m空域开放'},
        {'d': '7月2日', 'icon': '🌐', 'e': '全球数字经济大会(北京)', 's': '数字经济', 'big': 0, 'desc': ''},
        {'d': '7月2日', 'icon': '🤖', 'e': '中国AI智能体大会(杭州)', 's': 'AI应用', 'big': 0, 'desc': ''},
        {'d': '7月5日', 'icon': '⚙️', 'e': 'SEMICON West旧金山', 's': '半导体设备', 'big': 1, 'desc': '全球最大半导体展'},
        {'d': '7月8日', 'icon': '💾', 'e': '长鑫存储IPO路演启动', 's': '存储/设备', 'big': 1, 'desc': '募资295亿'},
        {'d': '7月8日', 'icon': '🤖', 'e': 'AMTS+AHTE上海', 's': '人形机器人', 'big': 1, 'desc': '850家展商'},
        {'d': '7月11日', 'icon': '🤖', 'e': '机器人+创新大会(邹城)', 's': '人形机器人', 'big': 0, 'desc': ''},
        {'d': '7月17日', 'icon': '🧠', 'e': '世界人工智能大会WAIC', 's': 'AI', 'big': 1, 'desc': '全球顶级AI盛会'},
        {'d': '7月25日', 'icon': '🟧', 'e': '风华高科/三环半年报预告', 's': 'MLCC', 'big': 0, 'desc': '验证涨价弹性'},
        {'d': '7月30日', 'icon': '💰', 'e': '章源钨业下半月长单报价', 's': '钨/稀土', 'big': 1, 'desc': '停产一月后走势'},
        {'d': '8月上旬', 'icon': '📊', 'e': 'A股半年报密集披露', 's': '全部赛道', 'big': 0, 'desc': '业绩兑现窗口'},
        {'d': '8月26日', 'icon': '🤖', 'e': 'AGIC深圳AI大会', 's': 'AI', 'big': 1, 'desc': '8.1万㎡,1000+企业'},
        {'d': '8月30日', 'icon': '📊', 'e': '中期业绩披露完毕', 's': '全部赛道', 'big': 1, 'desc': 'Q2业绩定调'},
    ]
    existing_events = preserve.get('events', []) or []
    merged_ev = list(auto_events)
    hand_events = [e for e in existing_events if e.get('u') and e['u'].strip()]
    auto_keys = {(e['d'], e['e']) for e in auto_events}
    for he in hand_events:
        if (he['d'], he['e']) not in auto_keys: merged_ev.append(he)
    preserve['events'] = merged_ev

    # Build output
    out = {
        'updated': cst.strftime('%Y-%m-%d %H:%M CST'),
        'nextSentinel': next_update,
        'updateCount': int(time.time() / 900),
        'recap': {
            'index': indices[:6] if indices else [],
            'heat': sectors[:25] if sectors else [],
            'flow': fund,
            'winners': winners,
            'losers': losers,
            'ztLadder': zt_ladder,
            'note': f"{cst.strftime('%m/%d %H:%M')} GitHub Actions云更新 | {len(codes)}只 | {len(sectors)}板块",
            'cycle': cycle
        },
        'livePrices': live,
        'runtime': {'cloud': True, 'autoUpdate': True, 'interval': '15min',
                    'stockCount': len(codes), 'liveCount': len(live),
                    'updateCount': int(time.time() / 900), 'trading': is_trading}
    }
    out.update(preserve)

    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Archive snapshot at market close
    if is_trading and cst.hour == 15 and cst.minute < 45:
        archive_dir = os.path.join(DIR, 'archive')
        os.makedirs(archive_dir, exist_ok=True)
        date_key = cst.strftime('%Y-%m-%d')
        shutil.copy2(DATA_PATH, os.path.join(archive_dir, f'{date_key}.json'))
        existing_ar = sorted([os.path.basename(f).replace('.json','') for f in _glob.glob(os.path.join(archive_dir, '*.json')) if not os.path.basename(f) == 'index.json'], reverse=True)
        with open(os.path.join(archive_dir, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump(existing_ar, f, ensure_ascii=False)
        print(f"📦 Archived: {date_key} ({len(existing_ar)} snapshots)")

    print(f"OK {out['updated']} | {len(indices)} idx | {len(sectors)} sec | {len(live)} stks | flow={len(fund)} | zt={zt_ladder and zt_ladder.get('totalCount',0) or 0} | trading={is_trading}")
'''

# Replace from def main() to end
new_content = content[:idx_def_main] + clean_main

with open('D:/projects/market-dashboard/.github/scripts/fetch_data.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Rewritten fetch_data.py main()')
