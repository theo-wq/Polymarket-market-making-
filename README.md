# 🤖 Polymarket Trading Bot

A high-performance automated trading bot for Polymarket, featuring ultra-low latency order book analysis and real-time execution capabilities.

## 📋 Key Features

- Ultra-low latency order book analysis (<.15s computation time)
- Advanced market analysis metrics:
  - Real-time volume imbalance detection
  - Multi-level price pressure analysis
  - Smart spread calculation
  - Order concentration tracking
  - Buy/Sell pressure indicators
- Optimized order execution with minimal slippage
- Real-time Telegram notifications
- Comprehensive operation logging
- Robust error handling

## ⚡ Performance Highlights

- Order book computation time: <2ms
- Market condition analysis: <1ms
- Order execution latency: ~5ms
- Total decision cycle: <10ms

## 🛠️ Prerequisites

- Python 3.8+
- Polymarket account with API enabled
- Telegram Bot (for notifications)

### 📚 Main Dependencies

```
py-clob-client
python-dotenv
pandas
numpy
telebot
```

## ⚙️ Configuration

1. Create a `.env` file at the project root with the following variables:

```
API_KEY=your_api_key
API_SECRET=your_api_secret
API_PASSPHRASE=your_passphrase
PRIVATE_KEY=your_private_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

2. Configure trading parameters in `config.json`:

```json
{
    "trading_parameters": {
        "TOKEN_ID": "market_ID",
        "size": 10,
        "min_spread": "0.01",
        "host": "https://clob.polymarket.com",
        "spread_slip": 0.01
    },
    "chain_settings": {
        "chain_id": 137,
        "funder": "funder_address"
    }
}
```

## 🚀 Installation

1. Clone the repository
```bash
git clone [repo_url]
cd polymarket-bot
```

2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

## 💫 Usage

1. Start the bot:
```bash
python reward.py
```

2. Monitor logs and Telegram notifications to track bot activity.

## 📁 Project Structure

```
├── reward.py           # Main bot entry point
├── slippage.py        # High-performance order book analysis
├── config.json        # Bot configuration
├── .env              # Environment variables
├── logs/             # Logs directory
└── README.md         # Documentation
```

## 🔧 Core Components

### TradingBot (reward.py)
- Main bot management
- Optimized order execution
- Real-time position management
- Telegram communication
- Error handling and recovery

### OrderBookAnalyzer (slippage.py)
- High-frequency order book analysis
- Advanced market metrics calculation:
  - Volume imbalance ratio
  - Price pressure indicators
  - Order book depth analysis
  - Spread dynamics
  - Liquidity concentration
- Market condition detection with configurable thresholds

## 📊 Order Book Analysis

The bot implements sophisticated order book analysis:

1. **Volume Imbalance Detection**
   - Real-time calculation of bid/ask volume ratios
   - Multi-level depth analysis
   - Dynamic threshold adjustment

2. **Price Pressure Analysis**
   - Weighted pressure calculation across price levels
   - Order concentration measurement
   - Smart spread analysis

3. **Market Condition Evaluation**
   - Combined metric scoring system
   - Adaptive threshold management
   - Real-time market state classification

## ⚠️ Important Notes

1. **Performance Optimization**
   - Run on a dedicated machine for optimal performance
   - Minimize network latency to Polymarket servers
   - Monitor system resources regularly

2. **Risk Management**
   - Set appropriate position sizes
   - Configure reasonable spread thresholds
   - Implement emergency stop conditions

3. **Monitoring**
   - Track execution latency
   - Monitor order fill rates
   - Analyze trading performance metrics

## 📈 Performance Parameters

Key parameters in `slippage.py`:
- `imbalance_threshold`: Imbalance detection sensitivity (default: 3.0)
- `volume_threshold`: Minimum volume requirement (default: 0.4)
- `price_levels`: Order book depth analysis (default: 3)
- `spread_multiplier`: Dynamic spread adjustment (default: 1.5)

## 📄 License

This project is under MIT license. See the `LICENSE` file for more details.


---
⚡ Developed with ❤️ for Polymarket