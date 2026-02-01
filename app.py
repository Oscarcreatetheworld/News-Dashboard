import streamlit as st
import pandas as pd
import altair as alt # 用來畫漂亮的圖
from collections import Counter
import re

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="北美廚電戰情室 Pro", page_icon="🍳", layout="wide")

st.title("🍳 北美廚電市場監測儀表板 Pro")
st.markdown("### Market Intelligence & Trend Analysis")

# --- 🔥 請把你的 CSV 網址貼在下面這行引號裡 ---
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQai1zkVJlpDcZhzs76S_JiCsm1JogWxdYlw4vA4k1IeWLHqiReRRY29xQm7ephIk9QJfri7OlvfdmF/pub?output=csv" 

# --- 2. 資料處理函數 (清洗數據用) ---
@st.cache_data # 加上快取，讓網站跑得更快
def load_data(url):
    try:
        df = pd.read_csv(url)
        # 確保日期格式正確
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except Exception as e:
        return None

# 讀取資料
df = load_data(sheet_url)

if df is not None:
    # --- 3. 側邊欄：全域篩選器 ---
    with st.sidebar:
        st.header("🔍 篩選條件")
        
        # 類別篩選
        all_cats = ["全部"] + list(df['Category'].unique())
        cat_filter = st.selectbox("選擇情報類別", all_cats)
        
        # 日期篩選 (預設選最近 30 天)
        min_date = df['Date'].min().date()
        max_date = df['Date'].max().date()
        date_range = st.date_input("選擇日期範圍", [min_date, max_date])

    # 套用篩選邏輯
    filtered_df = df.copy()
    if cat_filter != "全部":
        filtered_df = filtered_df[filtered_df['Category'] == cat_filter]
    
    # 套用日期篩選
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[(filtered_df['Date'].dt.date >= start_date) & (filtered_df['Date'].dt.date <= end_date)]

    # --- 4. 關鍵指標卡片 (KPI Cards) ---
    col1, col2, col3 = st.columns(3)
    col1.metric("總資料筆數", len(filtered_df))
    col2.metric("來源媒體數", filtered_df['Source'].nunique())
    # 簡單計算最新一天的新增量
    today_count = len(filtered_df[filtered_df['Date'] == filtered_df['Date'].max()])
    col3.metric("最新更新數", today_count, help="最近一次抓取的新資料量")

    st.divider() # 分隔線

    # --- 5. 主要內容區：使用分頁 (Tabs) ---
    tab1, tab2, tab3 = st.tabs(["📈 聲量趨勢", "☁️ 熱門關鍵字", "📋 詳細資料表"])

    with tab1:
        st.subheader("每日聲量趨勢圖")
        # 整理數據：算每天有幾篇文章
        trend_data = filtered_df.groupby('Date').size().reset_index(name='Count')
        
        # 畫圖 (長條圖)
        st.bar_chart(trend_data.set_index('Date'), color="#FF4B4B")
        st.caption("觀察重點：某天突然變高，通常代表有新品發布或特定話題發酵。")

    with tab2:
        st.subheader("標題熱詞分析 (Top Keywords)")
        
        # 簡單的文字分析邏輯
        text = " ".join(filtered_df['Title'].astype(str).tolist())
        # 移除標點符號和轉小寫
        text = re.sub(r'[^\w\s]', '', text).lower()
        words = text.split()
        
        # 設定停用詞 (不想看到的廢話)
        stopwords = set(['the', 'a', 'in', 'of', 'for', 'to', 'and', 'is', 'on', 'with', 'best', '2026', 'kitchen', 'appliances'])
        meaningful_words = [w for w in words if w not in stopwords and len(w) > 2]
        
        # 計算詞頻
        word_counts = Counter(meaningful_words).most_common(20)
        word_df = pd.DataFrame(word_counts, columns=['Keyword', 'Count'])
        
        # 用橫向長條圖呈現
        st.dataframe(word_df, use_container_width=True)
        st.caption("觀察重點：這些是標題中最常出現的單字，可以看出目前的市場焦點功能或品牌。")

    with tab3:
        st.subheader("原始資料列表")
        
        # 搜尋框放這裡
        search_term = st.text_input("搜尋標題關鍵字", placeholder="輸入品牌名或功能 (例如: Samsung, Quiet)...")
        if search_term:
            filtered_df = filtered_df[filtered_df['Title'].str.contains(search_term, case=False, na=False)]

        st.data_editor(
            filtered_df[['Date', 'Category', 'Title', 'Source', 'Link']],
            column_config={
                "Link": st.column_config.LinkColumn("閱讀連結", display_text="點擊前往"),
                "Date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
                "Title": st.column_config.TextColumn("文章標題", width="large"),
            },
            hide_index=True,
            use_container_width=True
        )

else:
    st.error("⚠️ 無法讀取資料，請檢查 app.py 中的 CSV 網址是否正確。")
