# -*- coding: utf-8 -*-
"""持股異動判定:比對同一 ETF 兩份快照,產生 ADD/REMOVE/INCREASE/DECREASE 事件。

核心:ETF 被申購/贖回時全部持股股數會「等比例」增減,那是資金流不是經理人
操作。以全體共同持股股數比值的中位數當規模效應基準(scale),個股偏離基準
超過門檻才視為主動加減碼;權重差同時要過門檻(權重受股價被動影響,單獨
不可靠,但可濾掉「股數動、佔比根本沒變」的噪音)。
"""

SHARES_THR = 0.05   # 校正後股數變化 ≥5%
WEIGHT_THR = 0.1    # 且權重變化 ≥0.1 個百分點


def _ev(h, typ, prev=None, adj=None):
    e = {"code": h.code, "name": h.name, "type": typ,
         "weight": h.weight, "shares": h.shares}
    if prev is not None:
        e["prev_weight"] = prev.weight
        e["weight_delta"] = round(h.weight - prev.weight, 4)
        e["prev_shares"] = prev.shares
        # 絕對股數變化(未扣規模效應)。shares_delta_pct 是扣掉申購贖回後的
        # 主動幅度,適合判定;要顯示「買了幾張」則需要這個原始差額。
        e["shares_delta"] = h.shares - prev.shares
    else:
        e["shares_delta"] = h.shares  # ADD:整個部位都是新建的
    if adj is not None:
        e["shares_delta_pct"] = round(adj * 100, 2)
    return e


def compute_events(prev, curr, shares_thr=SHARES_THR, weight_thr=WEIGHT_THR):
    """prev/curr: {code: Holding}。回傳事件 list(dict)。"""
    common = [c for c in curr if c in prev and prev[c].shares > 0]
    ratios = sorted(curr[c].shares / prev[c].shares for c in common)
    scale = ratios[len(ratios) // 2] if ratios else 1.0
    events = []
    for c, h in curr.items():
        if c not in prev:
            events.append(_ev(h, "ADD"))
            continue
        p = prev[c]
        adj = (h.shares / (p.shares * scale) - 1) if p.shares and scale else 0.0
        dw = h.weight - p.weight
        if adj >= shares_thr and dw >= weight_thr:
            events.append(_ev(h, "INCREASE", p, adj))
        elif adj <= -shares_thr and dw <= -weight_thr:
            events.append(_ev(h, "DECREASE", p, adj))
    for c, p in prev.items():
        if c not in curr:
            events.append({"code": p.code, "name": p.name, "type": "REMOVE",
                           "prev_weight": p.weight, "prev_shares": p.shares,
                           "shares_delta": -p.shares})  # 出清:全數賣出
    return events
