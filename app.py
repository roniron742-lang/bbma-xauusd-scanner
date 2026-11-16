import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="BBMA Oma Ally - XAUUSD", layout="wide")
st.title("📊 BBMA Oma Ally Scanner & Chart (XAUUSD)")

# --- SIDEBAR PENGATURAN ---
st.sidebar.header("Pengaturan Chart & Sinyal")
timeframe = st.sidebar.selectbox("Pilih Timeframe", ["5m", "15m", "1h", "4h", "1d"], index=2)
period = st.sidebar.selectbox("Periode Data", ["5d", "1mo", "3mo", "6mo"], index=1)

st.sidebar.subheader("Tampilkan Sinyal di Chart")
plot_ret = st.sidebar.checkbox("Plot Signal REENTRY (RET)", value=True)
plot_ext = st.sidebar.checkbox("Plot Signal EXTREME (EXT)", value=True)
plot_csa = st.sidebar.checkbox("Plot Signal CSAK (CSA)", value=True)
plot_mmt = st.sidebar.checkbox("Plot Signal CSM (MMT)", value=True)
plot_ali = st.sidebar.checkbox("Plot Alien Candle (ALI)", value=True)

# --- FUNGSI WMA (Weighted Moving Average) ---
def calc_wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

# --- AMBIL DATA XAUUSD ---
@st.cache_data(ttl=60)
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

# --- PERHITUNGAN INDIKATOR BBMA ---
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
df['ema50'] = df['Close'].ewm(span=50, adjust=False).mean()

# --- LOGIKA SINYAL BBMA ---
df['reject_mahi'] = (df['High'] > df['mahi5']) & (df['Close'] < df['mahi5']) & (df['Close'] < df['mahi10']) & (df['Close'] < df['midBB']) & (df['mahi5'] < df['midBB'])
df['reject_malo'] = (df['Low'] < df['malo5']) & (df['Close'] > df['malo5']) & (df['Close'] > df['malo10']) & (df['Close'] > df['midBB']) & (df['malo5'] > df['midBB'])

df['csak_sell'] = (df['Open'] > df['midBB']) & (df['Close'] < df['midBB'])
df['csak_buy'] = (df['Open'] < df['midBB']) & (df['Close'] > df['midBB'])

candle_sz_p = (df['Close'].shift(1) - df['Open'].shift(1)).abs()
candle_sz = (df['Close'] - df['Open']).abs()

df['ext_sell'] = (df['Close'].shift(1) > df['Open'].shift(1)) & (df['Close'] < df['topBB']) & (df['Close'] < df['Open']) & ((df['mahi5_p'] > df['topBB_p']) | (df['mahi5'] > df['topBB'])) & (candle_sz > candle_sz_p / 2)
df['ext_buy'] = (df['Close'].shift(1) < df['Open'].shift(1)) & (df['Close'] > df['lowBB']) & (df['Close'] > df['Open']) & ((df['malo5_p'] < df['lowBB_p']) | (df['malo5'] < df['lowBB'])) & (candle_sz > candle_sz_p / 2)

df['mmt_sell'] = (df['Close'] < df['lowBB']) & (df['Open'] > df['lowBB'])
df['mmt_buy'] = (df['Close'] > df['topBB']) & (df['Open'] < df['topBB'])

df['ali_sell'] = (df['Open'] < df['lowBB']) & (df['Close'] < df['lowBB'])
df['ali_buy'] = (df['Open'] > df['topBB']) & (df['Close'] > df['topBB'])

# --- PANEL STATUS SINYAL TERAKHIR ---
last = df.iloc[-1]
st.subheader(f"Harga Terakhir XAUUSD: ${last['Close']:.2f}")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("REENTRY", "SELL 🔴" if last['reject_mahi'] else ("BUY 🟢" if last['reject_malo'] else "Netral"))
col2.metric("EXTREME", "SELL 🔴" if last['ext_sell'] else ("BUY 🟢" if last['ext_buy'] else "Netral"))
col3.metric("CSAK", "SELL 🔴" if last['csak_sell'] else ("BUY 🟢" if last['csak_buy'] else "Netral"))
col4.metric("CSM", "SELL 🔴" if last['mmt_sell'] else ("BUY 🟢" if last['mmt_buy'] else "Netral"))
col5.metric("ALIEN", "SELL 🔴" if last['ali_sell'] else ("BUY 🟢" if last['ali_buy'] else "Netral"))

# --- VISUALISASI CHART INTERAKTIF (PLOTLY) ---
df_plot = df.tail(120)
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df_plot.index, open=df_plot['Open'], high=df_plot['High'],
    low=df_plot['Low'], close=df_plot['Close'], name="XAUUSD"
))

fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['topBB'], line=dict(color='white', width=1.5), name='Top BB'))
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['midBB'], line=dict(color='yellow', width=1.5), name='Mid BB'))
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['lowBB'], line=dict(color='white', width=1.5), name='Low BB'))
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['mahi5'], line=dict(color='fuchsia', width=1), name='MAHI 5'))
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['mahi10'], line=dict(color='red', width=1.5), name='MAHI 10'))
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['malo5'], line=dict(color='aqua', width=1), name='MALO 5'))
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['malo10'], line=dict(color='blue', width=1.5), name='MALO 10'))
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['ema50'], line=dict(color='lime', width=2.5), name='EMA 50'))

def add_markers(condition_col, y_col, offset, symbol, color, name):
    sub = df_plot[df_plot[condition_col]]
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
if plot_ali:
    add_markers('ali_sell', 'Low', -3.0, 'star', 'red', 'Alien Sell')
    add_markers('ali_buy', 'High', 3.0, 'star', 'lime', 'Alien Buy')

fig.update_layout(
    template="plotly_dark", height=650,
    xaxis_rangeslider_visible=False,
    margin=dict(l=10, r=10, t=30, b=10)
)
st.plotly_chart(fig, use_container_width=True)
