# -*- coding: utf-8 -*-
"""摩根投信(am.jpmorgan.com)adapter。

唯一一家不提供網頁或 JSON 持股、**只給 Excel 下載**的投信。
- GET https://am.jpmorgan.com/FundsMarketingHandler/excel
      ?type=holding_pcf&cusip=<ISIN>&country=tw&role=twetf&locale=zh-TW&date=YYYY-MM-DD
    回 xlsx。sheet1「基金資產 - 股票 (YYYY-MM-DD)」為持股,
    欄位:股票代碼/股票名稱/股數/金額/權重(%);另有期貨、選擇權、現金三張表。
- 同端點 type=m12_pcf 回「現金申購買回清單公告」,sheet1 以「標籤, 值」兩欄
    列出基金淨資產價值、已發行受益權單位總數、每受益權單位淨資產價值。

**locale 與 date 兩個參數都是必填**,少任何一個都回 500(而且錯誤訊息是內部代理
的 404,看起來像端點不存在,其實只是參數不全)。date 是公告日,無法離線推算,
故由今天往前逐日試(最多 7 天);m12 的公告日是「次一營業日」,所以往後試。

ISIN 與聯博同樣由代號算出(見 ab.isin_for),摩根的產品頁網址結尾也正是 ISIN。

xlsx 用 zipfile + 正規表示式直接解:本專案不裝 openpyxl,而 xlsx 就是 zip 包 XML,
只取 sharedStrings 與 sheet 的 <row>/<c> 就夠,沒必要為一家投信多一個相依套件。
"""
import datetime
import io
import re
import zipfile

from .ab import isin_for
from .base import (ADAPTERS, AdapterError, Holding, get, to_num,
                   validate_holdings)

EXCEL = "https://am.jpmorgan.com/FundsMarketingHandler/excel"
UA_REFERER = "https://am.jpmorgan.com/tw/zh/asset-management/twetf/"

ROW_RE = re.compile(r"<row[^>]*>(.*?)</row>", re.S)
CELL_RE = re.compile(r'<c\b([^>]*?)(?:/>|>(.*?)</c>)', re.S)
VAL_RE = re.compile(r"<v>(.*?)</v>", re.S)
SI_RE = re.compile(r"<si>(.*?)</si>", re.S)
T_RE = re.compile(r"<t[^>]*>(.*?)</t>", re.S)
TITLE_DATE_RE = re.compile(r"\((\d{4}-\d{2}-\d{2})\)")
STOCK_CODE_RE = re.compile(r"^[0-9A-Z]{4,6}$")


def read_xlsx(blob):
    """xlsx bytes → {sheet 名稱: [[儲存格字串, …], …]}(依 sheet 檔名排序)。"""
    try:
        z = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        raise AdapterError("jpmorgan: 回應不是 xlsx(參數不全會回 500 HTML)")
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        xml = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        shared = ["".join(T_RE.findall(si)) for si in SI_RE.findall(xml)]
    sheets = {}
    for name in sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet")):
        rows = []
        for row in ROW_RE.findall(z.read(name).decode("utf-8", "replace")):
            cells = []
            for attrs, inner in CELL_RE.findall(row):
                v = VAL_RE.search(inner or "")
                val = v.group(1) if v else ""
                if 't="s"' in attrs and val.isdigit() and int(val) < len(shared):
                    val = shared[int(val)]
                cells.append(val)
            rows.append(cells)
        sheets[name] = rows
    return sheets


def parse_holdings_xlsx(sheets, etf_code):
    """holding_pcf → (data_date, [Holding])。只取標題含「股票」的那張表。"""
    for name, rows in sheets.items():
        title = rows[0][0] if rows and rows[0] else ""
        if "股票" not in title:
            continue
        m = TITLE_DATE_RE.search(title)
        if not m:
            continue
        hdr = next((i for i, r in enumerate(rows) if r and r[0] == "股票代碼"), None)
        if hdr is None:
            continue
        holdings = []
        for r in rows[hdr + 1:]:
            if len(r) < 5 or not STOCK_CODE_RE.match((r[0] or "").strip()):
                continue
            shares, weight = to_num(r[2]), to_num(str(r[4]).replace("%", ""))
            if shares is None or weight is None:
                continue
            holdings.append(Holding(code=r[0].strip(), name=(r[1] or "").strip(),
                                    shares=int(shares), weight=weight))
        if holdings:
            return m.group(1), validate_holdings(holdings, etf_code)
    raise AdapterError("{}: xlsx 找不到股票表(改版?)".format(etf_code))


def parse_meta_xlsx(sheets):
    """m12_pcf sheet1 是「標籤, 值」兩欄。標籤可能帶日期前綴,故用 in 比對。"""
    kv = {}
    for rows in sheets.values():
        for r in rows:
            if len(r) >= 2 and r[0] and r[1]:
                kv[str(r[0])] = r[1]

    def pick(label):
        for k, v in kv.items():
            if label in k:
                return to_num(v)
        return None

    return {"scale": pick("基金淨資產價值"),
            "units": pick("已發行受益權單位總數"),
            "nav_per_unit": pick("每受益權單位淨資產價值"),
            "holders": None}  # 檔案不揭露受益人數


def _download(isin, kind, date):
    r = get(EXCEL, params={"type": kind, "cusip": isin, "country": "tw",
                           "role": "twetf", "locale": "zh-TW", "date": date},
            headers={"Referer": UA_REFERER})
    return r.content


def fetch_holdings(etf):
    code = etf["code"]
    isin = isin_for(code)
    today = datetime.date.today()

    holdings = data_date = None
    for back in range(8):  # 公告日無法離線推算,由今天往前試
        d = (today - datetime.timedelta(days=back)).strftime("%Y-%m-%d")
        try:
            data_date, holdings = parse_holdings_xlsx(
                read_xlsx(_download(isin, "holding_pcf", d)), code)
            break
        except AdapterError:
            continue
    if not holdings:
        raise AdapterError("jpmorgan: {} 連續 8 日取不到 holding_pcf".format(code))

    meta = None
    for fwd in range(6):  # m12 公告的是次一營業日,往後試
        d = (today + datetime.timedelta(days=fwd)).strftime("%Y-%m-%d")
        try:
            meta = parse_meta_xlsx(read_xlsx(_download(isin, "m12_pcf", d)))
            if meta.get("scale"):
                break
        except AdapterError:
            continue
    return data_date, holdings, meta


ADAPTERS["jpmorgan"] = fetch_holdings
