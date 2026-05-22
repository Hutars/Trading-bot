import ccxt
import pandas as pd
import pandas_ta as ta
import time
import logging
import streamlit as st
import plotly.graph_objects as go
import json
import os

# FIX 1: Use streamlit-autorefresh instead of time.sleep(15) at the bottom
# Install with: pip install streamlit-autorefresh
try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False

logging.basicConfig(filename='paper_trades.log', level=logging.INFO, format='%(asctime)s - %(message)s')

@st.cache_resource
def get_exchange():
    return ccxt.binanceus({'enableRateLimit': True})

exchange = get_exchange()

symbol = 'ETH/USDT'
PORTFOLIO_FILE = 'paper_portfolio.json'

# FIX 2: Unified cooldown dict — both buy and sell now use the same timeframe-based wait
TIMEFRAME_COOLDOWN = {
    '1m': 60,
    '3m': 180,
    '5m': 300,
    '15m': 900,
    '1h': 3600,
}

MAX_LOG_ENTRIES = 200  # FIX 3: Cap log size to prevent unbounded growth

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                data = json.load(f)
                if 'paper_usdt' in data:
                    data.setdefault('total_profit_usdt', 0.0)
                    data.setdefault('total_loss_usdt', 0.0)
                    data.setdefault('winning_trades', 0)
                    data.setdefault('losing_trades', 0)
                    data.setdefault('bot_active', True)
                    data.setdefault('timeframe', '5m')
                    data.setdefault('rsi_buy_level', 36)
                    data.setdefault('rsi_sell_level', 65)
                    data.setdefault('trailing_input', 2.0)
                    data.setdefault('auto_buy_amount_eth', 0.5)
                    data.setdefault('logs', [])
                    return data
        except Exception:
            pass
    return {
        "paper_usdt": 15000.0,
        "paper_eth": 1.0,
        "highest_price": 0.0,
        "avg_buy_price": 2000.0,
        "total_profit_usdt": 0.0,
        "total_loss_usdt": 0.0,
        "winning_trades": 0,
        "losing_trades": 0,
        "bot_active": True,
        "timeframe": "5m",
        "rsi_buy_level": 36,
        "rsi_sell_level": 65,
        "trailing_input": 2.0,
        "auto_buy_amount_eth": 0.5,
        "logs": []
    }

def save_portfolio():
    data = {
        "paper_usdt": st.session_state.paper_usdt,
        "paper_eth": st.session_state.paper_eth,
        "highest_price": st.session_state.highest_price,
        "avg_buy_price": st.session_state.avg_buy_price,
        "total_profit_usdt": st.session_state.total_profit_usdt,
        "total_loss_usdt": st.session_state.total_loss_usdt,
        "winning_trades": st.session_state.winning_trades,
        "losing_trades": st.session_state.losing_trades,
        "bot_active": st.session_state.get('bot_active_state', True),
        "timeframe": st.session_state.get('timeframe_state', '5m'),
        "rsi_buy_level": st.session_state.get('rsi_buy_state', 36),
        "rsi_sell_level": st.session_state.get('rsi_sell_state', 65),
        "trailing_input": st.session_state.get('trailing_state', 2.0),
        "auto_buy_amount_eth": st.session_state.get('auto_amount_state', 0.5),
        # FIX 3: Trim logs before saving
        "logs": st.session_state.logs[-MAX_LOG_ENTRIES:]
    }
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(data, f)

def fetch_data(symbol, timeframe):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=300)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['ema50'] = ta.ema(df['close'], length=50)  # FIX 4: Added EMA50 trend filter
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=3)
    return df.tail(100).reset_index(drop=True)

st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.title("🔒 Вход в Трейдинг Панела")
    password_input = st.text_input("Въведете парола:", type="password", key="password_field")

    if st.button("Влизане", use_container_width=True):
        if password_input == "admin123":
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.session_state["password_correct"] = False
            st.error("❌ Грешна парола! Опитайте отново.")

    return False

if not check_password():
    st.stop()

st.title("🤖 Крипто Трейдинг Бот — Мониторинг & Контрол")

# FIX 1: Trigger auto-refresh via streamlit-autorefresh (non-blocking)
if AUTOREFRESH_AVAILABLE:
    st_autorefresh(interval=15000, key="autorefresh")
else:
    st.info("Инсталирайте `streamlit-autorefresh` за автоматично опресняване: pip install streamlit-autorefresh")

# --- INITIALIZE SESSION STATE FROM FILE ---
# FIX 5: All keys guaranteed to exist before sidebar widgets render
if 'paper_usdt' not in st.session_state:
    saved_data = load_portfolio()
    st.session_state.paper_usdt = saved_data["paper_usdt"]
    st.session_state.paper_eth = saved_data["paper_eth"]
    st.session_state.highest_price = saved_data["highest_price"]
    st.session_state.avg_buy_price = saved_data["avg_buy_price"]
    st.session_state.total_profit_usdt = saved_data["total_profit_usdt"]
    st.session_state.total_loss_usdt = saved_data["total_loss_usdt"]
    st.session_state.winning_trades = saved_data["winning_trades"]
    st.session_state.losing_trades = saved_data["losing_trades"]
    st.session_state.logs = saved_data["logs"]
    st.session_state.bot_active_state = saved_data["bot_active"]
    st.session_state.timeframe_state = saved_data["timeframe"]
    st.session_state.rsi_buy_state = saved_data["rsi_buy_level"]
    st.session_state.rsi_sell_state = saved_data["rsi_sell_level"]
    st.session_state.trailing_state = saved_data["trailing_input"]
    st.session_state.auto_amount_state = saved_data["auto_buy_amount_eth"]
    st.session_state.last_trade_time = 0.0
    # FIX 6: Two-click reset confirmation flag initialized here
    st.session_state.confirm_reset = False
    save_portfolio()

# --- SIDEBAR SETTINGS ---
st.sidebar.header("⚙️ Настройки на Бота")

bot_active = st.sidebar.checkbox("🤖 Автоматичен режим (ON/OFF)", key="bot_active_state", on_change=save_portfolio)

tf_options = ['1m', '3m', '5m', '15m', '1h']
default_tf_index = tf_options.index(st.session_state.timeframe_state) if st.session_state.timeframe_state in tf_options else 2
timeframe = st.sidebar.selectbox(label="Таймфрейм на графиката:", options=tf_options, index=default_tf_index, key="timeframe_state", on_change=save_portfolio)

rsi_buy_level = st.sidebar.number_input(label="RSI Ниво за покупка (Долно):", min_value=10, max_value=50, key="rsi_buy_state", step=1, on_change=save_portfolio)
rsi_sell_level = st.sidebar.number_input(label="RSI Ниво за продажба (Горно):", min_value=50, max_value=90, key="rsi_sell_state", step=1, on_change=save_portfolio)
trailing_input = st.sidebar.number_input(label="Trailing Stop Loss (%)", min_value=0.1, max_value=20.0, key="trailing_state", step=0.1, format="%.1f", on_change=save_portfolio)
trailing_pct = trailing_input / 100.0
auto_buy_amount_eth = st.sidebar.number_input(label="Автоматично количество (ETH):", min_value=0.001, max_value=10.0, key="auto_amount_state", step=0.05, format="%.3f", on_change=save_portfolio)

# FIX 2: Use unified cooldown from dict
wait_time = TIMEFRAME_COOLDOWN.get(timeframe, 300)

st.sidebar.markdown("---")
st.sidebar.header("🕹️ Ръчно управление")
manual_amount = st.sidebar.number_input(label="Количество ETH за ръчна сделка:", min_value=0.001, max_value=100.0, value=0.5, step=0.01, format="%.3f")

try:
    df = fetch_data(symbol, timeframe)
    current_price = df['close'].iloc[-1]
    current_rsi = df['rsi'].iloc[-1]
    current_ema50 = df['ema50'].iloc[-1]  # FIX 4: EMA50 for trend filter

    # 1. Manual buy
    if st.sidebar.button("🟩 Ръчно КУПУВА", use_container_width=True):
        cost = manual_amount * current_price
        if st.session_state.paper_usdt >= cost:
            new_total_eth = st.session_state.paper_eth + manual_amount
            st.session_state.avg_buy_price = (
                (st.session_state.paper_eth * st.session_state.avg_buy_price) +
                (manual_amount * current_price)
            ) / new_total_eth
            st.session_state.paper_usdt -= cost
            st.session_state.paper_eth = new_total_eth
            st.session_state.highest_price = max(st.session_state.highest_price, current_price)
            msg = f"[{time.strftime('%H:%M:%S')}] 👤 МАНУАЛ КУПУВА | Количество: {manual_amount:.3f} ETH | Цена: ${current_price:.2f} | RSI: {current_rsi:.2f}"
            st.session_state.logs.append(msg)
            logging.info(msg)
            save_portfolio()
            st.rerun()
        else:
            st.sidebar.error("Няма достатъчно USDT!")

    # 2. Manual sell
    if st.sidebar.button("🟨 Ръчно ПРОДАВА", use_container_width=True):
        if st.session_state.paper_eth >= manual_amount:
            trade_pnl_usdt = manual_amount * (current_price - st.session_state.avg_buy_price)
            if trade_pnl_usdt >= 0:
                st.session_state.total_profit_usdt += trade_pnl_usdt
                st.session_state.winning_trades += 1
            else:
                st.session_state.total_loss_usdt += abs(trade_pnl_usdt)
                st.session_state.losing_trades += 1
            st.session_state.paper_usdt += manual_amount * current_price
            st.session_state.paper_eth -= manual_amount
            msg = f"[{time.strftime('%H:%M:%S')}] 👤 МАНУАЛ ПРОДАЖБА | Количество: {manual_amount:.3f} ETH | Цена: ${current_price:.2f} | RSI: {current_rsi:.2f}"
            st.session_state.logs.append(msg)
            logging.info(msg)
            if st.session_state.paper_eth < 0.001:
                st.session_state.avg_buy_price = 0
                st.session_state.highest_price = 0
            # FIX 7: save_portfolio AFTER all state mutations, before rerun
            save_portfolio()
            st.rerun()
        else:
            st.sidebar.error("Нямате толкова ETH!")

    # 3. Panic Sell
    if st.sidebar.button("🚨 ПАНИК СЕЛ (Продай всичко)", use_container_width=True):
        if st.session_state.paper_eth > 0:
            trade_pnl_usdt = st.session_state.paper_eth * (current_price - st.session_state.avg_buy_price)
            if trade_pnl_usdt >= 0:
                st.session_state.total_profit_usdt += trade_pnl_usdt
                st.session_state.winning_trades += 1
            else:
                st.session_state.total_loss_usdt += abs(trade_pnl_usdt)
                st.session_state.losing_trades += 1
            total_sale = st.session_state.paper_eth * current_price
            st.session_state.paper_usdt += total_sale
            msg = f"[{time.strftime('%H:%M:%S')}] 🚨 PANIC SELL | Ликвидирани {st.session_state.paper_eth:.4f} ETH на ${current_price:.2f} | RSI: {current_rsi:.2f}"
            st.session_state.logs.append(msg)
            logging.info(msg)
            # FIX 7: Mutate state fully BEFORE save and rerun
            st.session_state.paper_eth = 0
            st.session_state.avg_buy_price = 0
            st.session_state.highest_price = 0
            save_portfolio()
            st.rerun()

    # FIX 6: Two-click reset confirmation
    st.sidebar.markdown("---")
    st.sidebar.subheader("🚨 Нулиране")
    if not st.session_state.get('confirm_reset', False):
        if st.sidebar.button("🗑️ RESET БОТ", use_container_width=True, type="primary"):
            st.session_state.confirm_reset = True
            st.rerun()
    else:
        st.sidebar.warning("Сигурни ли сте? Всички данни ще бъдат изтрити!")
        col_yes, col_no = st.sidebar.columns(2)
        if col_yes.button("✅ Да, нулирай", use_container_width=True):
            reset_data = {
                "paper_usdt": 15000.0, "paper_eth": 1.0, "highest_price": 0.0,
                "avg_buy_price": 2000.0, "total_profit_usdt": 0.0, "total_loss_usdt": 0.0,
                "winning_trades": 0, "losing_trades": 0, "bot_active": True,
                "timeframe": "5m", "rsi_buy_level": 36, "rsi_sell_level": 65,
                "trailing_input": 2.0, "auto_buy_amount_eth": 0.5,
                "logs": ["[СИСТЕМА] Всички показатели бяха нулирани."]
            }
            with open(PORTFOLIO_FILE, 'w') as f:
                json.dump(reset_data, f)
            st.toast("Портфейлът беше занулен!")
            for key in list(st.session_state.keys()):
                if key != "password_correct":
                    del st.session_state[key]
            st.rerun()
        if col_no.button("❌ Отказ", use_container_width=True):
            st.session_state.confirm_reset = False
            st.rerun()

    # --- WIN RATE & PROFIT FACTOR ---
    total_trades = st.session_state.winning_trades + st.session_state.losing_trades
    win_rate = (st.session_state.winning_trades / total_trades) * 100 if total_trades > 0 else 0.0

    # FIX 8: profit_factor returns "N/A" string when there's no data yet
    if st.session_state.total_loss_usdt > 0:
        profit_factor_val = st.session_state.total_profit_usdt / st.session_state.total_loss_usdt
        profit_factor_str = f"{profit_factor_val:.2f}"
    elif st.session_state.total_profit_usdt > 0:
        profit_factor_str = "∞"
    else:
        profit_factor_str = "N/A"

    # --- TOP METRICS ---
    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1.3, 1.2, 1, 1])
    with col1:
        st.metric(label="Текуща Цена ETH", value=f"${current_price:,.2f}")
    with col2:
        st.metric(label=f"RSI ({timeframe})", value=f"{current_rsi:.2f}")
    with col3:
        st.metric(label="Виртуален Портфейл", value=f"${st.session_state.paper_usdt:,.2f} USDT")
    with col4:
        st.metric(label="Наличен ETH", value=f"{st.session_state.paper_eth:.4f} ETH")
    with col5:
        st.metric(label="📈 Win Rate", value=f"{win_rate:.1f}%", help=f"Общо затворени сделки: {total_trades}")
    with col6:
        st.metric(label="📊 Profit Factor", value=profit_factor_str)

    # --- TRADING LOGIC ---
    current_time = time.time()

    # Trailing stop
    if st.session_state.paper_eth > 0.001 and st.session_state.avg_buy_price > 0:
        # FIX 9: highest_price initialized to avg_buy_price, not 0, to avoid false stops
        if st.session_state.highest_price < st.session_state.avg_buy_price:
            st.session_state.highest_price = st.session_state.avg_buy_price

        if current_price > st.session_state.highest_price:
            st.session_state.highest_price = current_price

        stop_level = st.session_state.highest_price * (1 - trailing_pct)
        unrealized_pl = ((current_price - st.session_state.avg_buy_price) / st.session_state.avg_buy_price) * 100

        st.sidebar.markdown("---")
        st.sidebar.subheader("🛡️ Мониторинг на риска")
        st.sidebar.write(f"Средна цена: **${st.session_state.avg_buy_price:.2f}**")
        st.sidebar.write(f"Текущ P/L: **{unrealized_pl:+.2f}%**")
        st.sidebar.write(f"Ниво на Стоп ({trailing_input}%): **${stop_level:.2f}**")

        if current_price <= stop_level:
            trade_pnl_usdt = st.session_state.paper_eth * (current_price - st.session_state.avg_buy_price)
            if trade_pnl_usdt >= 0:
                st.session_state.total_profit_usdt += trade_pnl_usdt
                st.session_state.winning_trades += 1
            else:
                st.session_state.total_loss_usdt += abs(trade_pnl_usdt)
                st.session_state.losing_trades += 1
            st.session_state.paper_usdt += st.session_state.paper_eth * current_price
            msg = f"[{time.strftime('%H:%M:%S')}] [TRAILING STOP] | Продадени {st.session_state.paper_eth:.4f} ETH на ${current_price:.2f} (P/L: {unrealized_pl:+.2f}%) | RSI: {current_rsi:.2f}"
            st.session_state.logs.append(msg)
            logging.info(msg)
            # FIX 7: Mutate fully before save
            st.session_state.paper_eth = 0
            st.session_state.highest_price = 0
            st.session_state.avg_buy_price = 0
            save_portfolio()
            st.rerun()

    if bot_active:
        # FIX 4: Auto-buy only when RSI is low AND price is above EMA50 (uptrend filter)
        ema_uptrend = current_price > current_ema50

        if (current_rsi <= rsi_buy_level and
                ema_uptrend and
                (current_time - st.session_state.last_trade_time) > wait_time):
            cost = auto_buy_amount_eth * current_price
            if st.session_state.paper_usdt >= cost:
                new_total_eth = st.session_state.paper_eth + auto_buy_amount_eth
                st.session_state.avg_buy_price = (
                    (st.session_state.paper_eth * st.session_state.avg_buy_price) +
                    (auto_buy_amount_eth * current_price)
                ) / new_total_eth
                st.session_state.paper_usdt -= cost
                st.session_state.paper_eth = new_total_eth
                st.session_state.last_trade_time = current_time
                st.session_state.highest_price = max(st.session_state.highest_price, current_price)
                msg = f"[{time.strftime('%H:%M:%S')}] [АВТО КУПУВА] | {auto_buy_amount_eth} ETH | ${current_price:.2f} | RSI: {current_rsi:.2f} | EMA50: ${current_ema50:.2f}"
                st.session_state.logs.append(msg)
                logging.info(msg)
                save_portfolio()
                st.rerun()

        # FIX 2: Auto-sell also uses wait_time from timeframe dict (was hardcoded 300)
        elif (current_rsi >= rsi_sell_level and
              st.session_state.paper_eth >= 0.1 and
              (current_time - st.session_state.last_trade_time) > wait_time):
            sell_amount = min(auto_buy_amount_eth, st.session_state.paper_eth)
            trade_pnl_usdt = sell_amount * (current_price - st.session_state.avg_buy_price)
            if trade_pnl_usdt >= 0:
                st.session_state.total_profit_usdt += trade_pnl_usdt
                st.session_state.winning_trades += 1
            else:
                st.session_state.total_loss_usdt += abs(trade_pnl_usdt)
                st.session_state.losing_trades += 1
            st.session_state.paper_usdt += sell_amount * current_price
            st.session_state.paper_eth -= sell_amount
            st.session_state.last_trade_time = current_time
            unrealized_pl = ((current_price - st.session_state.avg_buy_price) / st.session_state.avg_buy_price) * 100
            msg = f"[{time.strftime('%H:%M:%S')}] [ЧАСТИЧНА ПРОДАЖБА] | {sell_amount} ETH | ${current_price:.2f} | P/L: {unrealized_pl:+.2f}% | RSI: {current_rsi:.2f}"
            st.session_state.logs.append(msg)
            logging.info(msg)
            if st.session_state.paper_eth < 0.001:
                st.session_state.avg_buy_price = 0
                st.session_state.highest_price = 0
            # FIX 7: save after all mutations
            save_portfolio()
            st.rerun()
    else:
        st.sidebar.warning("⚠️ Автоматичният бот е СПРЯН.")

    # --- CHARTS ---
    main_col, side_panel = st.columns([3, 1])

    with main_col:
        from plotly.subplots import make_subplots
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.6, 0.4])

        fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Цена"), row=1, col=1)
        # FIX 4: Show EMA50 on chart
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema50'], mode='lines', name='EMA50', line=dict(color='magenta', width=1.5, dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['rsi'], mode='lines', name='RSI', line=dict(color='orange')), row=2, col=1)

        fig.add_hline(y=rsi_sell_level, line_dash="dash", line_color="red", annotation_text=f"Продажби ({rsi_sell_level})", row=2, col=1)
        fig.add_hline(y=rsi_buy_level, line_dash="dash", line_color="green", annotation_text=f"Покупки ({rsi_buy_level})", row=2, col=1)
        fig.add_hline(y=current_price, line_dash="dot", line_color="cyan", row=1, col=1)

        fig.update_layout(
            title=f"ETH/USDT ({timeframe}) + RSI + EMA50",
            xaxis_rangeslider_visible=False,
            height=650,
            margin=dict(l=10, r=120, t=40, b=40),
            hovermode="x unified",
            annotations=[
                dict(x=1.01, y=current_price, yref="y1", xref="paper", text=f"👉 ${current_price:,.2f}", showarrow=False, font=dict(size=14, color="cyan", family="Arial Black"), xanchor="left", yanchor="middle"),
                dict(x=1.01, y=current_rsi, yref="y2", xref="paper", text=f"📊 RSI: {current_rsi:.2f}", showarrow=False, font=dict(size=13, color="orange", family="Arial Black"), xanchor="left", yanchor="middle")
            ],
            xaxis=dict(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1, spikecolor="rgba(255, 255, 255, 0.4)", spikedash="dash"),
            yaxis=dict(side="right", tickmode="auto", title=dict(text=""), showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1, spikecolor="rgba(0, 255, 255, 0.6)", spikedash="dash")
        )

        fig.update_yaxes(side="right", range=[0, 100], row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)

    with side_panel:
        st.subheader("📜 Лог на сделките")
        # FIX 4: Show EMA trend status
        trend_label = "📈 Uptrend (EMA50)" if current_price > current_ema50 else "📉 Downtrend (EMA50)"
        st.caption(trend_label)
        if st.session_state.logs:
            for log in reversed(st.session_state.logs[-12:]):
                st.write(log)
        else:
            st.info("Няма извършени транзакции.")

except Exception as e:
    st.error(f"Грешка: {e}")
    logging.error(f"СИСТЕМНА ГРЕШКА: {e}")

# FIX 1: Removed time.sleep(15) and st.rerun() from here.
# Auto-refresh is now handled by st_autorefresh() at the top (non-blocking).
# If streamlit-autorefresh is not installed, the page refreshes only on user interaction.
