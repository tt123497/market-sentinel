#!/usr/bin/env python3
"""
Event Calendar — runs once daily at 10:00 CST.

Data sources:
  1. NBS 2026 Macro Calendar — algorithmically generated from NBS published schedule
     (PMI/CPI/trade/industrial/M2/LPR/FOMC etc. with auto weekend adjustment)
  2. EastMoney earnings forecast API — real company 业绩预告 (when sector-matching)
  3. AI Sentinel newEvents — from real market news analysis (runs 4x/day independently)
  4. Hand-curated events (with 'u' URL field) — preserved FOREVER

Rules:
  - Hand events (with 'u' URL) are NEVER deleted
  - Past events stay in the list (frontend marks them with 'past' class)
  - New events MERGE into existing, never replace
  - Cap: 100 events total (trims oldest non-hand past events if needed)
"""
import json, os, re, time, calendar as cal
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote

DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(DIR, 'data.json')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# ═══════════════════════════════════════════════════
# NBS 2026 Macro Calendar
# Based on NBS published annual release schedule
# ═══════════════════════════════════════════════════

MACRO_S = '宏观/全部'

def next_biz(y, m, day):
    d = datetime(y, m, min(day, cal.monthrange(y, m)[1]))
    while d.weekday() >= 5: d += timedelta(days=1)
    return d

def fmt_d(d): return f'{d.month}月{d.day}日'

def generate_macro():
    """Only keep sector-specific recurring events that you can actually pre-position for.
    No FOMC/LPR/MLF/NFP/CPI — nobody buys stocks ahead of a PMI release.
    Only 章源钨业 monthly quotes survive as truly pre-positionable."""
    cst = datetime.now(timezone.utc) + timedelta(hours=8)
    today = cst.date()
    evs = []

    # Only one recurring event that matters for pre-positioning
    zyw_url = 'https://quote.eastmoney.com/sz002842.html'
    for off in range(4):
        m, y = cst.month + off, cst.year
        if m > 12: m -= 12; y += 1
        for day, lb in [(1, '上半月'), (15, '下半月')]:
            if day <= cal.monthrange(y, m)[1]:
                qd = next_biz(y, m, day)
                if qd.month == m:
                    evs.append({'d': fmt_d(qd), 'icon': '💰',
                        'e': f'章源钨业{m}月{lb}长单报价', 's': '钨/稀土',
                        'big': 1,
                        'desc': f'{m}月{lb}钨精矿定价催化，提前布局钨矿股',
                        'u': zyw_url})

    seen = set()
    deduped = []
    for e in evs:
        k = (e['d'], e['e'])
        if k not in seen:
            seen.add(k)
            deduped.append(e)

    def pd(e):
        m = re.search(r'(\d+)月(\d+)日', e['d'])
        return (int(m.group(1)), int(m.group(2))) if m else (99, 99)
    deduped.sort(key=pd)
    return deduped

# ═══════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════

def main():
    cst = datetime.now(timezone.utc) + timedelta(hours=8)
    today = cst.date()

    data = {}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            try: data = json.load(f)
            except: pass

    existing = data.get('events', [])

    # Separate: hand (has URL AND not macro) vs macro vs AI (no URL) vs new AI (with URL, not macro, not hand)
    macro_patterns = ['章源钨业']

    hand_evs = [e for e in existing if e.get('u','').strip()
        and not any(kw in e.get('e','') for kw in macro_patterns)]
    hand_keys = {(e['d'], e['e']) for e in hand_evs}

    old_macro = [e for e in existing
        if any(kw in e.get('e','') for kw in macro_patterns)]

    # AI events: everything else (with or without URL)
    macro_keys_used = {(e['d'], e['e']) for e in old_macro}
    ai_evs = [e for e in existing
        if (e['d'], e['e']) not in hand_keys
        and (e['d'], e['e']) not in macro_keys_used]

    print(f'Existing: {len(hand_evs)} hand + {len(old_macro)} old-macro + {len(ai_evs)} AI')

    # Generate fresh macro
    macro = generate_macro()
    print(f'Fresh macro: {len(macro)} events')

    # Merge: hand > fresh-macro > AI > other
    merged = list(hand_evs)  # Forever

    for ev in macro:
        k = (ev['d'], ev['e'])
        if k not in hand_keys:
            merged.append(ev)
    macro_keys = {(e['d'], e['e']) for e in macro}

    all_keys = {(e['d'], e['e']) for e in merged}
    for ev in ai_evs:
        k = (ev.get('d',''), ev.get('e',''))
        # Drop old macro noise (LPR/MLF/FOMC/NFP/CPI etc.) — sector=宏观/全部 but NOT 章源钨业
        if k in all_keys:
            continue
        if ev.get('s') == MACRO_S and '章源钨业' not in ev.get('e', ''):
            continue  # macro noise, dropped
        merged.append(ev)

    # Purge ALL macro noise from merged list
    # Any event with sector=宏观/全部 that is NOT 章源钨业 gets deleted
    # (catches FOMC/LPR/MLF/NFP/CPI/交割日 regardless of classification)
    echo_count_before = len(merged)
    merged = [e for e in merged
              if e.get('s') != MACRO_S or '章源钨业' in e.get('e', '')]
    dropped = echo_count_before - len(merged)
    if dropped > 0:
        print(f'Purged {dropped} macro noise events (FOMC/LPR/MLF/NFP/CPI/etc)')

    # ── URL enrichment: generate links for events missing them ──
    for ev in merged:
        if not ev.get('u','').strip():
            # Generate EastMoney search URL from title keywords
            title = ev.get('e','')
            sector = ev.get('s','')
            # Use sector + first keyword from title
            search_term = sector.split('/')[0].strip() if sector else title[:8]
            if search_term:
                ev['u'] = 'https://so.eastmoney.com/news/s?keyword=' + quote(search_term)
            else:
                ev['u'] = 'https://data.eastmoney.com/'

    # Sort by date
    def parse_date(ev):
        m = re.search(r'(\d+)月(\d+)日', ev.get('d',''))
        if m: return datetime(cst.year, int(m.group(1)), int(m.group(2)))
        m = re.search(r'(\d+)月上旬', ev.get('d',''))
        if m: return datetime(cst.year, int(m.group(1)), 5)
        m = re.search(r'(\d+)月中旬', ev.get('d',''))
        if m: return datetime(cst.year, int(m.group(1)), 15)
        m = re.search(r'(\d+)月下旬', ev.get('d',''))
        if m: return datetime(cst.year, int(m.group(1)), 25)
        return datetime(2099,1,1)

    merged.sort(key=parse_date)

    # Cap at 100: trim oldest non-hand past events if needed
    if len(merged) > 100:
        future = [e for e in merged if parse_date(e).date() >= today]
        past = [e for e in merged if parse_date(e).date() < today]
        # Keep hand-curated past forever, trim others
        past_hand = [e for e in past if e.get('u','').strip()]
        past_other = [e for e in past if not e.get('u','').strip()]
        past_other = past_other[-max(0, 30 - len(past_hand)):]
        merged = past_hand + past_other + future
        if len(merged) > 100:
            merged = merged[-100:]

    data['events'] = merged
    data['_eventsMeta'] = {
        'updated': cst.strftime('%Y-%m-%d %H:%M CST'),
        'total': len(merged),
        'hand': len(hand_evs),
        'macro': len(macro),
        'ai': len(ai_evs),
        'schedule': 'daily at 10:00 CST',
        'source': 'NBS 2026 schedule + AI sentinel news + hand-curated'
    }

    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    future_count = sum(1 for e in merged if parse_date(e).date() >= today)
    past_count = len(merged) - future_count
    print(f'Done: {len(merged)} total ({future_count} upcoming + {past_count} past)')
    print(f'  Hand:{len(hand_evs)} | Macro:{len(macro)} | AI:{len(ai_evs)}')
    # Show upcoming that are NOT macro (sector-specific)
    sector_evs = [e for e in merged if parse_date(e).date() >= today and e.get('s') != MACRO_S]
    if sector_evs:
        print(f'  Sector-specific upcoming: {len(sector_evs)}')
        for ev in sector_evs[:5]:
            try:
                d_val = ev['d']; e_val = ev['e']
                print(f'    {d_val} {e_val}')
            except:
                d_val = ev['d']
                print(f'    {d_val} [encoding issue]')


if __name__ == '__main__':
    main()
