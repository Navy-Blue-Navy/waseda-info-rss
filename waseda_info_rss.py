import requests
from bs4 import BeautifulSoup, NavigableString, Tag
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime, parsedate_to_datetime
from urllib.parse import urljoin
import hashlib
import re

URL = "http://www.tt.em-net.ne.jp/~tori/wasedaindex.htm"
OUTPUT = Path(__file__).parent / "waseda_info.xml"

JST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    )
}

# -------------------------
# 既存RSSを読み込む
# -------------------------

old_items = {}

if OUTPUT.exists():
    try:
        old_tree = ET.parse(OUTPUT)

        for item in old_tree.getroot().findall("./channel/item"):
            guid = item.findtext("guid", "")

            if guid:
                old_items[guid] = {
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "description": item.findtext("description", ""),
                    "pubDate": item.findtext("pubDate", ""),
                    "guid": guid,
                }

    except Exception:
        old_items = {}

# -------------------------
# ページ取得
# -------------------------

response = requests.get(
    URL,
    headers=HEADERS,
    timeout=30
)

response.raise_for_status()
response.encoding = response.apparent_encoding

soup = BeautifulSoup(response.text, "html.parser")

date_pattern = re.compile(
    r"^\s*(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\s*$"
)

current_items = []
seen_guids = set()

# -------------------------
# Information欄を取得
# -------------------------

for dt in soup.find_all("dt"):

    # dt自身の直接のテキストだけ取得
    direct_texts = []

    for child in dt.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()

            if text:
                direct_texts.append(text)

    if not direct_texts:
        continue

    date_text = direct_texts[0]

    match = date_pattern.match(date_text)

    if not match:
        continue

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    # このdt直下のddだけを見る
    dd = None

    for child in dt.children:
        if isinstance(child, Tag) and child.name == "dd":
            dd = child
            break

    if dd is None:
        continue

    # ddの直接の文字列だけ取得
    title_parts = []

    for child in dd.children:

        if isinstance(child, NavigableString):
            text = str(child).strip()

            if text:
                title_parts.append(text)

    title = " ".join(title_parts)
    title = re.sub(r"\s+", " ", title).strip()

    # 今回欲しいのは「上井草便り」の更新だけ
    if "上井草便り" not in title:
        continue

    # dd直下のリンクだけ取得
    article_link = None

    for child in dd.children:
        if isinstance(child, Tag) and child.name == "a":
            href = child.get("href")

            if href:
                article_link = urljoin(URL, href)
                break

    if not article_link:
        continue

    # URLをGUIDにする
    # 同じ記事を毎回新着扱いしない
    guid = hashlib.sha256(
        article_link.encode("utf-8")
    ).hexdigest()

    if guid in seen_guids:
        continue

    seen_guids.add(guid)

    event_date = datetime(
        year,
        month,
        day,
        12,
        0,
        0,
        tzinfo=JST
    )

    current_items.append({
        "title": title,
        "link": article_link,
        "description": f"{date_text}　{title}",
        "pubDate": format_datetime(event_date),
        "guid": guid,
    })

# -------------------------
# 過去RSSの項目も残す
# -------------------------

all_items = []
seen = set()

for item in current_items:

    if item["guid"] not in seen:
        all_items.append(item)
        seen.add(item["guid"])

for guid, item in old_items.items():

    if guid not in seen:
        all_items.append(item)
        seen.add(guid)

# 日付の新しい順
def get_date(item):
    try:
        return parsedate_to_datetime(item["pubDate"])
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)

all_items.sort(
    key=get_date,
    reverse=True
)

# 最大300件保存
all_items = all_items[:300]

# -------------------------
# RSS作成
# -------------------------

rss = ET.Element(
    "rss",
    version="2.0"
)

channel = ET.SubElement(
    rss,
    "channel"
)

ET.SubElement(
    channel,
    "title"
).text = "上井草便り Information"

ET.SubElement(
    channel,
    "link"
).text = URL

ET.SubElement(
    channel,
    "description"
).text = "上井草便りの更新情報"

ET.SubElement(
    channel,
    "language"
).text = "ja"

for item in all_items:

    element = ET.SubElement(
        channel,
        "item"
    )

    ET.SubElement(
        element,
        "title"
    ).text = item["title"]

    ET.SubElement(
        element,
        "link"
    ).text = item["link"]

    ET.SubElement(
        element,
        "description"
    ).text = item["description"]

    ET.SubElement(
        element,
        "pubDate"
    ).text = item["pubDate"]

    guid_element = ET.SubElement(
        element,
        "guid"
    )

    guid_element.set(
        "isPermaLink",
        "false"
    )

    guid_element.text = item["guid"]

tree = ET.ElementTree(rss)
ET.indent(tree, space="  ")

tree.write(
    OUTPUT,
    encoding="utf-8",
    xml_declaration=True
)

# -------------------------
# 結果表示
# -------------------------

print("RSS作成成功")
print("今回取得:", len(current_items), "件")
print("RSS保存件数:", len(all_items), "件")
print("保存先:", OUTPUT)

print()
print("最新15件:")

for item in current_items[:15]:
    print(
        item["pubDate"],
        item["title"],
        "->",
        item["link"]
    )