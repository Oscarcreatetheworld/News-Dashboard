import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
from datetime import datetime
import time
from duckduckgo_search import DDGS
from pytrends.request import TrendReq

# --- 1. 頁面設定 (必須放在第一行) ---
st.set_page_config(page_title="全球廚電情報中心", page_icon="🍳", layout="wide")

# --- 2. Session State 初始化 ---
if 'favorites' not in st.session_state:
    st.session_state.favorites = pd.DataFrame(columns=['Folder', 'Date', 'Title', 'Link', 'Source'])

if 'folder_list' not in st.session_state:
    st.session_state.folder_list = ["📥 未分類", "🔥 方太 (Fotile)", "🔥 老闆 (Robam)", "🇪🇺 歐系品牌", "🇺🇸 美系品牌"]

if 'search_results' not in st.session_state:
    st.session_state.search_results = pd.DataFrame()

# --- 3. 爬蟲函數群 ---

# A. Google News
def fetch_google_news(keyword, lang, region):
    search_query = keyword
    target_gl = region
    try:
        target_ceid = f"{region}:{lang.split('-')[0]}"
    except:
        target_ceid = f"{region}:en"

    if (region in ["US", "CA"]) and ("zh" in lang):
        if region == "US": search_query = f"{keyword} (美國 OR 北美 OR USA)"
        elif region == "CA": search_query = f"{keyword} (加拿大 OR Canada OR 温哥华 OR 多伦多)"
        target_gl = "TW"
        target_ceid = "TW:zh-Hant"

    if region == "HK" and "zh" in lang:
        target_ceid = "HK:zh-Hant"
        target_gl = "HK"

    encoded_keyword = urllib.parse.quote(search_query)
    target_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl={lang}&gl={target_gl}&ceid={target_ceid}"
    
    try:
        feed = feedparser.parse(target_url)
        data = []
        if feed.entries:
            for entry in feed.entries:
                try: pub_date = datetime(*entry.published_parsed[:6])
                except: pub_date = datetime.now()
                data.append({
                    "Select": False,
                    "Date": pub_date,
                    "Type": "📰 新聞",
                    "Title": entry.title,
                    "Source": entry.source.title if 'source' in entry else "Google News",
                    "Link": entry.link
                })
            return pd.DataFrame(data)
        else:
            return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# B. DuckDuckGo
def fetch_web_search(keyword, region_code, time_range, platform_mode=None):
    if region_code == "US": ddg_region = "us-en"
    elif region_code == "CA": ddg_region = "ca-en"
    elif region_code == "HK": ddg_region = "hk-tzh"
    else: ddg_region = "wt-wt"
    
    ddg_time = None 
    if time_range == "過去一天": ddg_time = "d"
    elif time_range == "過去一週": ddg_time = "w"
    elif time_range == "過去一個月": ddg_time = "m"
    elif time_range == "過去一年": ddg_time = "y"
    
    final_keyword = keyword
    search_region = ddg_region
