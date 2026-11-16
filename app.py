import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="BBMA Oma Ally - Multi-TF Scanner", layout="wide")
st.title("📊 BBMA Oma Ally Multi-TF Scanner & Live Chart (XAUUSD)")

# --- SIDEBAR PENGATURAN ---
st.sidebar.header("Pengaturan Chart Utama")
timeframe = st.sidebar.selectbox("Pilih Timeframe Chart", ["15m", "30m", "1h", "4h", "1d"], index=2)

period_options = {
    "1 Daily (Harian)": "1mo",
    "1 Weekly (Mingguan)": "1y",
    "1 Monthly (Bulanan)": "5y"
}
selected_period_label = st.sidebar.selectbox("Periode Data Chart", list(period_options.keys()), index=0)
period = period_options[selected_period_label]

st.sidebar.subheader("Tampilkan Sinyal di Chart")
plot_ret = st.sidebar.checkbox("Plot Signal REENTRY (RET)", value=True)
plot_ext = st.sidebar.checkbox("Plot Signal EXTREME (EXT)", value=True)
plot_csa = st.sidebar.checkbox("Plot Signal CSAK (CSA)", value=True)
plot_mmt = st.sidebar.checkbox("Plot Signal CSM (MMT)", value=True)

# --- FUNGSI WMA & ANALISIS BBMA ---
def calc_wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def analyze_bbma(df):
    if df.empty or len(df) < 30:
        return "Netral"
    
    df = df.copy()
    df['midBB'] = df['Close'].rolling(20).mean()
    df['midBB_p'] = df['midBB'].shift(1)
    df['BBdev'] = 2 * df['Close'].rolling(20).std()
    df['topBB'] = df['midBB_p'] + df['BBdev']
    df['lowBB'] = df['midBB_p'] - df['BBdev']
    df['topBB_p'] = df['topBB'].shift(1)
    df['lowBB_p'] = df['lowBB'].shift(1)

    df['mahi5'] = calc_wma(df['High'], 5)
    df['mahi10'] = calc_wma(df['High'], 10)
    df['malo5'] = calc_wma(df['Low'], 5)
    df['malo10'] = calc_wma(df['Low'], 10)
    df['mahi5_p'] = df['mahi5'].shift(1)
    df['malo5_p'] = df['malo5'].shift(1)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Logika Sinyal
    is_reentry = (last['High'] > last['mahi5'] and last['Close'] < last['mahi5'] and last['Close'] < last['mahi10'] and last['Close'] < last['midBB']) or \
                 (last['Low'] < last['malo5'] and last['Close'] > last['malo5'] and last['Close'] > last['malo10'] and last['Close'] > last['midBB'])
    
    is_csak = (last['Open'] > last['midBB'] and last['Close'] < last['midBB']) or \
              (last['Open'] < last['midBB'] and last['Close'] > last['midBB'])
    
    candle_sz_p = abs(prev['Close'] - prev['Open'])
    candle_sz = abs(last['Close'] - last['Open'])
    is_extreme = ((prev['Close'] > prev['Open']) and (last['Close'] < last['topBB']) and (last['Close'] < last['Open']) and ((last['mahi5_p'] > last['topBB_p']) or (last['mahi5'] > last['topBB'])) and (candle_sz > candle_sz_p / 2)) or \
                 ((prev['Close'] < prev['Open']) and (last['Close'] > last['lowBB']) and (last['Close'] > last['Open']) and ((last['malo5_p'] < last['lowBB_p']) or (last['malo5'] < last['lowBB'])) and (candle_sz > candle_sz_p / 2))
    
    is_csm = (last['Close'] < last['lowBB'] and last['Open'] > last['lowBB']) or \
             (last['Close'] > last['topBB'] and last['Open'] < last['topBB'])

    if is_csm:
        return "Momentum (CSM) ⚡"
    elif is_extreme:
        return "Extreme 🔥"
    elif is_reentry:
        return "Reentry 🎯"
    elif is_csak:
        return "CSAK 💎"
    else:
        return "Netral ⚪"

# --- AMBIL DATA CHART UTAMA ---
@st.cache_data(ttl=30)
def load_data(tf, per):
    df = yf.download("GC=F", interval=tf, period=per, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)
    return df

df = load_data(timeframe, period)

if df.empty:
    st.error("Gagal mengambil data XAUUSD. Coba ubah kombinasi Timeframe & Periode.")
    st.stop()

# --- TABEL SCANNER MULTI-TIMEFRAME (15m, 30m, 1h, 4h, 1d) ---
st.subheader("🔍 Multi-Timeframe BBMA Status Scanner (Live)")
mtf_list = ["15m", "30m", "1h", "4h", "1d"]
mtf_data = []

for tf_item in mtf_list:
    try:
        # Ambil data pendek untuk scanner mtf
        per_val = "5d" if tf_item in ["15m", "30m", "1h"] else ("1mo" if tf_item == "4h" else "3mo")
        df_temp = yf.download("GC=F", interval=tf_item, period=per_val, progress=False)
        if isinstance(df_temp.columns, pd.MultiIndex):
            df_temp.columns = df_temp.columns.get_level_values(0)
        df_temp.dropna(inplace=True)
        status = analyze_bbma(df_temp)
        last_close = df_temp['Close'].iloc[-1]
    except:
        status = "Error"
        last_close = 0.0
    
    mtf_data.append({
        "Timeframe": tf_item.upper(),
        "Harga Close Terakhir": f"${last_close:.2f}" if last_close > 0 else "-",
        "Status BBMA": status
    })

df_mtf = pd.DataFrame(mtf_data)
st.table(df_mtf)

# --- LIVE PRICE & STATUS SECTION ---
@st.fragment(run_every=5)
def render_live_section():
    try:
        ticker = yf.Ticker("GC=F")
        live_price = ticker.fast_info.get('last_price', df['Close'].iloc[-1])
    except:
        live_price = df['Close'].iloc[-1]

    st.subheader(f"🔴 Harga Live XAUUSD: ${live_price:.2f}  *(Auto-refresh tiap 5 detik)*")

    # Kalkulasi indikator untuk chart utama
    dft = df.copy()
    dft['midBB'] = dft['Close'].rolling(20).mean()
    dft['midBB_p'] = dft['midBB'].shift(1)
    dft['BBdev'] = 2 * dft['Close'].rolling(20).std()
    dft['topBB'] = dft['midBB_p'] + dft['BBdev']
    dft['lowBB'] = dft['midBB_p'] - dft['BBdev']
    dft['topBB_p'] = dft['topBB'].shift(1)
    dft['lowBB_p'] = dft['lowBB'].shift(1)
    dft['mahi5'] = calc_wma(dft['High'], 5)
    dft['mahi10'] = calc_wma(dft['High'], 10)
    dft['malo5'] = calc_wma(dft['Low'], 5)
    dft['malo10'] = calc_wma(dft['Low'], 10)
    dft['mahi5_p'] = dft['mahi5'].shift(1)
    dft['malo5_p'] = dft['malo5'].shift(1)

    dft['reject_mahi'] = (dft['High'] > dft['mahi5']) & (dft['Close'] < dft['mahi5']) & (dft['Close'] < dft['mahi10']) & (dft['Close'] < dft['midBB']) & (dft['mahi5'] < dft['midBB'])
    dft['reject_malo'] = (dft['Low'] < dft['malo5']) & (dft['Close'] > dft['malo5']) & (dft['Close'] > dft['malo10']) & (dft['Close'] > dft['midBB']) & (dft['malo5'] > dft['midBB'])
    dft['csak_sell'] = (dft['Open'] > dft['midBB']) & (dft['Close'] < dft['midBB'])
    dft['csak_buy'] = (dft['Open'] < dft['midBB']) & (dft['Close'] > dft['midBB'])
    
    cs_p = (dft['Close'].shift(1) - dft['Open'].shift(1)).abs()
    cs = (dft['Close'] - dft['Open']).abs()
    dft['ext_sell'] = (dft['Close'].shift(1) > dft['Open'].shift(1)) & (dft['Close'] < dft['topBB']) & (dft['Close'] < dft['Open']) & ((dft['mahi5_p'] > dft['topBB_p']) | (dft['mahi5'] > dft['topBB'])) & (cs > cs_p / 2)
    dft['ext_buy'] = (dft['Close'].shift(1) < dft['Open'].shift(1)) & (dft['Close'] > dft['lowBB']) & (dft['Close'] > dft['Open']) & ((dft['malo5_p'] < dft['lowBB_p']) | (dft['malo5'] < dft['lowBB'])) & (cs > cs_p / 2)
    
    dft['mmt_sell'] = (dft['Close'] < dft['lowBB']) & (dft['Open'] > dft['lowBB'])
    dft['mmt_buy'] = (dft['Close'] > dft['topBB']) & (dft['Open'] < dft['topBB'])

    last = dft.iloc[-1]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("REENTRY", "SELL 🔴" if last['reject_mahi'] else ("BUY 🟢" if last['reject_malo'] else "Netral"))
    col2.metric("EXTREME", "SELL 🔴" if last['ext_sell'] else ("BUY 🟢" if last['ext_buy'] else "Netral"))
    col3.metric("CSAK", "SELL 🔴" if last['csak_sell'] else ("BUY 🟢" if last['csak_buy'] else "Netral"))
    col4.metric("CSM", "SELL 🔴" if last['mmt_sell'] else ("BUY 🟢" if last['mmt_buy'] else "Netral"))

render_live_section()

# --- VISUALISASI CHART UTAMA (PLOTLY) ---
df_plot = df.copy()
df_plot['midBB'] = df_plot['Close'].rolling(20).mean()
df_plot['midBB_p'] = df_plot['midBB'].shift(1)
df_plot['BBdev'] = 2 * df_plot['Close'].rolling(20).std()
df_plot['topBB'] = df_plot['midBB_p'] + df_plot['BBdev']
df_plot['lowBB'] = df_plot['midBB_p'] - df_plot['BBdev']
df_plot['topBB_p'] = df_plot['topBB'].shift(1)
df_plot['lowBB_p'] = df_plot['lowBB'].shift(1)
df_plot['mahi5'] = calc_wma(df_plot['High'], 5)
df_plot['mahi10'] = calc_wma(df_plot['High'], 10)
df_plot['malo5'] = calc_wma(df_plot['Low'], 5)
df_plot['malo10'] = calc_wma(df_plot['Low'], 10)
df_plot['mahi5_p'] = df_plot['mahi5'].shift(1)
df_plot['malo5_p'] = df_plot['malo5'].shift(1)
df_plot['ema50'] = df_plot['Close'].ewm(span=50, adjust=False).mean()

df_plot['reject_mahi'] = (df_plot['High'] > df_plot['mahi5']) & (df_plot['Close'] < df_plot['mahi5']) & (df_plot['Close'] < df_plot['mahi10']) & (df_plot['Close'] < df_plot['midBB']) & (df_plot['mahi5'] < df_plot['midBB'])
df_plot['reject_malo'] = (df_plot['Low'] < df_plot['malo5']) & (df_plot['Close'] > df_plot['malo5']) & (df_plot['Close'] > df_plot['malo10']) & (df_plot['Close'] > df_plot['midBB']) & (df_plot['malo5'] > df_plot['midBB'])
df_plot['csak_sell'] = (df_plot['Open'] > df_plot['midBB']) & (df_plot['Close'] < df_plot['midBB'])
df_plot['csak_buy'] = (df_plot['Open'] < df_plot['midBB']) & (df_plot['Close'] > df_plot['midBB'])

cs_p = (df_plot['Close'].shift(1) - df_plot['Open'].shift(1)).abs()
cs = (df_plot['Close'] - df_plot['Open']).abs()
df_plot['ext_sell'] = (df_plot['Close'].shift(1) > df_plot['Open'].shift(1)) & (df_plot['Close'] < df_plot['topBB']) & (df_plot['Close'] < df_plot['Open']) & ((df_plot['mahi5_p'] > df_plot['topBB_p']) | (df_plot['mahi5'] > df_plot['topBB'])) & (cs > cs_p / 2)
df_plot['ext_buy'] = (df_plot['Close'].shift(1) < df_plot['Open'].shift(1)) & (df_plot['Close'] > df_plot['lowBB']) & (df_plot['Close'] > df_plot['Open']) & ((df_plot['malo5_p'] < df_plot['lowBB_p']) | (df_plot['malo5'] < df_plot['lowBB'])) & (cs > cs_p / 2)

df_plot['mmt_sell'] = (df_plot['Close'] < df_plot['lowBB']) & (df_plot['Open'] > df_plot['lowBB'])
df_plot['mmt_buy'] = (df_plot['Close'] > df_plot['topBB']) & (df_plot['Open'] < df_plot['topBB'])

df_sub = df_plot.tail(120)
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df_sub.index, open=df_sub['Open'], high=df_sub['High'],
    low=df_sub['Low'], close=df_sub['Close'], name="XAUUSD"
))

fig.add_trace(go.Scatter(x=df_sub.index, y=df_sub['topBB'], line=dict(color='white', width=1.5), name='Top BB'))
fig.add_trace(go.Scatter(x=df_sub.index, y=df_sub['midBB'], line=dict(color='yellow', width=1.5), name='Mid BB'))
fig.add_trace(go.Scatter(x=df_sub.index, y=df_sub['lowBB'], line=dict(color='white', width=1.5), name='Low BB'))
fig.add_trace(go.Scatter(x=df_sub.index, y=df_sub['mahi5'], line=dict(color='fuchsia', width=1), name='MAHI 5'))
fig.add_trace(go.Scatter(x=df_sub.index, y=df_sub['mahi10'], line=dict(color='red', width=1.5), name='MAHI 10'))
fig.add_trace(go.Scatter(x=df_sub.index, y=df_sub['malo5'], line=dict(color='aqua', width=1), name='MALO 5'))
fig.add_trace(go.Scatter(x=df_sub.index, y=df_sub['malo10'], line=dict(color='blue', width=1.5), name='MALO 10'))
fig.add_trace(go.Scatter(x=df_sub.index, y=df_sub['ema50'], line=dict(color='lime', width=2.5), name='EMA 50'))

def add_markers(condition_col, y_col, offset, symbol, color, name):
    sub = df_sub[df_sub[condition_col]]
    if not sub.empty:
        fig.add_trace(go.Scatter(
            x=sub.index, y=sub[y_col] + offset, mode='markers',
            marker=dict(symbol=symbol, size=10, color=color), name=name
        ))

if plot_ret:
    add_markers('reject_mahi', 'High', 1.5, 'triangle-down', 'red', 'RET Sell')
    add_markers('reject_malo', 'Low', -1.5, 'triangle-up', 'lime', 'RET Buy')
if plot_ext:
    add_markers('ext_sell', 'High', 2.5, 'x', 'red', 'EXT Sell')
    add_markers('ext_buy', 'Low', -2.5, 'x', 'lime', 'EXT Buy')
if plot_csa:
    add_markers('csak_sell', 'High', 3.5, 'diamond', 'orange', 'CSAK Sell')
    add_markers('csak_buy', 'Low', -3.5, 'diamond', 'cyan', 'CSAK Buy')
if plot_mmt:
    add_markers('mmt_sell', 'Low', -2.0, 'arrow-down', 'red', 'CSM Sell')
    add_markers('mmt_buy', 'High', 2.0, 'arrow-up', 'lime', 'CSM Buy')

fig.update_layout(
    template="plotly_dark", height=600,
    xaxis_rangeslider_visible=False,
    margin=dict(l=10, r=10, t=30, b=10)
)
st.plotly_chart(fig, use_container_width=True)
