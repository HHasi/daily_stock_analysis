#!/usr/bin/env python3
"""Portfolio summary: fetch prices, calc P&L, push to Feishu."""
import json, os, requests, hashlib, base64, time

codes = os.environ.get('PORTFOLIO_CODES', '510300,159819,513100,159915,600703').split(',')
qtys = [float(x) for x in os.environ.get('PORTFOLIO_QTY', '1000,900,1000,500,600').split(',')]
costs = [float(x) for x in os.environ.get('PORTFOLIO_COST', '4.795,2.029,2.188,3.828,14.20').split(',')]
names = os.environ.get('PORTFOLIO_NAMES', '🏛️沪深300,🤖AI,🌐纳指,📈创业板,🟡三安光电').split(',')
markets = os.environ.get('PORTFOLIO_MARKETS', 'sh,sz,sh,sz,sh').split(',')
cash = float(os.environ.get('PORTFOLIO_CASH', '4309'))

# Fetch live prices
symbols = ','.join(f"{m}{c}" for m, c in zip(markets, codes))
resp = requests.get(f"http://qt.gtimg.cn/q={symbols}", timeout=10)
resp.encoding = 'gbk'
lines = [l.strip() for l in resp.text.strip().split(';') if l.strip()]

total_mv, total_pl = 0, 0
rows = []
worst = ("", 0)

for i, code in enumerate(codes):
    for line in lines:
        if f"{markets[i]}{code}" in line:
            fields = line.split('~')
            if len(fields) < 40: continue
            try:
                price = float(fields[3])
                change_pct = float(fields[32])
            except: continue
            mv = price * qtys[i]
            pl = (price - costs[i]) * qtys[i]
            pl_pct = ((price - costs[i]) / costs[i]) * 100 if costs[i] else 0
            total_mv += mv; total_pl += pl
            if pl_pct < worst[1]: worst = (names[i], pl_pct)
            arrow = '🔴' if pl < 0 else '🟢'
            rows.append(f"{arrow} {names[i]:<8} {int(qtys[i]):>4}份{str(costs[i]):>8}{price:>8.3f} {change_pct:>+5.2f}% {mv:>7.0f} {pl:>+7.0f}({pl_pct:>+.1f}%)")
            break

total_pct = (total_pl / (total_mv - total_pl)) * 100 if (total_mv - total_pl) else 0
total_assets = total_mv + cash

out_lines = []
out_lines.append("━" * 45)
out_lines.append("💰 持仓汇总")
out_lines.append("━" * 45)
for r in rows: out_lines.append(r)
out_lines.append("─" * 45)
out_lines.append(f"💰 合计                   {total_mv:>8.0f}  {total_pl:>+8.0f}({total_pct:>+.1f}%)")
out_lines.append(f"💵 现金                    {cash:>8.0f}")
out_lines.append(f"📊 总资产                  {total_assets:>8.0f}")
out_lines.append(f"📌 仓位                 {total_mv/total_assets*100:>5.1f}%")
out_lines.append(f"⚠️ {worst[0]}亏损最深({worst[1]:.1f}%)")
out_lines.append("━" * 45)
report = '
'.join(out_lines)
print(report)

# Push to Feishu webhook if configured
webhook_url = os.environ.get('FEISHU_WEBHOOK_URL', '')
webhook_secret = os.environ.get('FEISHU_WEBHOOK_SECRET', '')
if webhook_url:
    ts = str(int(time.time()))
    sign = ''
    if webhook_secret:
        sign = base64.b64encode(
            hashlib.sha256(f"{ts}{webhook_secret}".encode()).hexdigest().encode()
        ).decode()
    payload = json.dumps({
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "💰 持仓汇总"}, "template": "red"},
            "elements": [{"tag": "markdown", "content": report}]
        }
    })
    headers = {"Content-Type": "application/json"}
    if sign:
        headers["X-Lark-Sign"] = sign
        headers["X-Lark-Timestamp"] = ts
    requests.post(webhook_url, headers=headers, data=payload, timeout=10)
