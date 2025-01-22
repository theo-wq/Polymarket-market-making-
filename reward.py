import os, logging, json, time
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, PartialCreateOrderOptions
from py_clob_client.constants import AMOY
from py_clob_client.exceptions import PolyApiException
from slippage import OrderBookAnalyzer
from dotenv import load_dotenv
import telebot
from datetime import datetime

class TradingBot:
    def __init__(self):
        load_dotenv(override=True)
        self.config = self._load_config()
        self._validate_config()  # Validation avant setup
        self._setup_env_and_client()
        self.bot = telebot.TeleBot(self.env['TELEGRAM_BOT_TOKEN'])
        self._init_trading_state()
        self.setup_logging()
        self.notify("🤖 Bot démarré")

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'clean_prod', 'config.json')
        try:
            with open(config_path, 'r') as config_file:
                config = json.load(config_file)
                return config
        except FileNotFoundError:
            raise FileNotFoundError(f"Config non trouvée: {config_path}")

    def _validate_config(self):
        """Valide la présence des paramètres requis dans la configuration"""
        if not self.config or 'trading_parameters' not in self.config:
            raise ValueError("Configuration trading_parameters manquante")
        
        required_params = ['TOKEN_ID', 'size', 'spread_slip', 'host']
        missing_params = [param for param in required_params 
                         if param not in self.config['trading_parameters']]
        
        if missing_params:
            raise ValueError(f"Paramètres manquants dans la configuration: {', '.join(missing_params)}")

    def _setup_env_and_client(self):
        """Configure les variables d'environnement et initialise le client"""
        env_vars = ['API_KEY', 'API_SECRET', 'API_PASSPHRASE', 'PRIVATE_KEY', 
                   'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
        self.env = {var: os.getenv(var) for var in env_vars}
        
        missing_vars = [var for var, value in self.env.items() if not value]
        if missing_vars:
            raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing_vars)}")
            
        self.client = ClobClient(
            self.config['trading_parameters']['host'],
            key=self.env['PRIVATE_KEY'],
            chain_id=AMOY,
            creds=ApiCreds(
                api_key=self.env['API_KEY'],
                api_secret=self.env['API_SECRET'],
                api_passphrase=self.env['API_PASSPHRASE']
            )
        )

    def _init_trading_state(self):
        """Initialise les paramètres de trading"""
        params = self.config['trading_parameters']
        self.token_id = params['TOKEN_ID']
        self.size = params['size']
        self.spread_slip = params['spread_slip']
        self.ask_price = self.bid_price = 0
        self.order_id_ask = self.order_id_bid = ""
        self.is_position = False
        self.act_price = 0

    def setup_logging(self):
        """Configure le système de logging"""
        os.makedirs("logs", exist_ok=True)
        logging.basicConfig(
            filename="logs/Polymarket_bot.log",
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def notify(self, message):
        """Envoie une notification Telegram et log le message"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.bot.send_message(self.env['TELEGRAM_CHAT_ID'], f"[{timestamp}]\n{message}")
            logging.info(message)
        except Exception as e: 
            logging.error(f"Erreur Telegram: {e}")

    def process_shares_size(self):
        return int(self.size / (float(self.get_last_trade_price()) + self.spread_slip))

    def order_pusher(self, action, side):
        try:
            price = self.ask_price if side == 'ask' else self.bid_price
            order_args = OrderArgs(
                token_id=self.token_id,
                side=action,
                size=self.process_shares_size() / 2.05,
                price=float(price)
            )
            
            signed_order = self.client.create_order(order_args, PartialCreateOrderOptions(neg_risk=False))
            resp = self.client.post_order(signed_order)
            order_id = resp['orderID'] if isinstance(resp, dict) else eval(resp)['orderID']
            
            setattr(self, f'order_id_{side}', order_id)
            self.notify(f"📊 Ordre {action} placé à {price} (ID: {order_id})")
            return order_id
            
        except Exception as e:
            self.notify(f"⚠️ Erreur ordre {action}: {e}")
            return None

    def cancel_order(self, side):
        order_id = getattr(self, f'order_id_{side}')
        try:
            self.client.cancel(order_id=order_id)
            self.notify(f"❌ Ordre annulé: {order_id}")
        except Exception as e:
            self.notify(f"⚠️ Erreur annulation {side}: {e}")

    def get_last_trade_price(self):
        try:
            response = self.client.get_last_trade_price(self.token_id)
            return float(response[self.token_id] if isinstance(response, dict) else response)
        except Exception as e:
            logging.error(f"Erreur prix: {e}")
            return None

    def get_market_status(self):
        return OrderBookAnalyzer().get_market_status()['is_favorable']

    def update_prices(self):
        try:
            orderbook = self.client.get_orderbook(self.token_id)
            if not orderbook or not (orderbook.bids and orderbook.asks):
                return False
                
            self.bid_price = round(float(sorted(orderbook.bids, key=lambda x: float(x.price), reverse=True)[1].price), 4)
            self.ask_price = round(float(sorted(orderbook.asks, key=lambda x: float(x.price))[1].price), 4)
            return True
            
        except Exception as e:
            logging.error(f"Erreur orderbook: {e}")
            return False

    def main_loop(self):
        last_heartbeat = 0
        self.update_prices()  # Mise à jour initiale des prix
        logging.info('Initialisation Polymarket, calculs en cours...')
        
        while True:
            try:
                now = time.time()
                if now - last_heartbeat >= 60:
                    self.notify(f"💗 Bot actif 💗")
                    last_heartbeat = now

                self.act_price = self.get_last_trade_price()

                if not self.get_market_status():
                    self.notify("🔴 Marché non favorable 🔴")
                    if self.is_position:
                        for side in ['ask', 'bid']:
                            self.cancel_order(side)
                        self.is_position = False
                else:
                    new_price = self.get_last_trade_price()
                    if new_price != self.act_price and self.is_position:
                        self.notify(f"💱 Prix: {self.act_price} → {new_price} 💱")
                        for side in ['ask', 'bid']:
                            self.cancel_order(side)
                        self.is_position = False
                    
                    if not self.is_position and self.update_prices():
                        self.order_pusher('SELL', 'ask')
                        self.order_pusher('BUY', 'bid')
                        self.is_position = True

                time.sleep(1)

            except Exception as e:
                self.notify(f"🚨 Erreur: {str(e)}")
                time.sleep(10)

if __name__ == "__main__":
    bot = None
    try:
        bot = TradingBot()
        bot.main_loop()
    except KeyboardInterrupt:
        shutdown_msg = "⛔ Bot arrêté par l'utilisateur ⛔"
        print(shutdown_msg)
        if bot:
            bot.notify(shutdown_msg)
    except Exception as e:
        fatal_error_msg = f"💥 Erreur fatale: {str(e)}"
        print(fatal_error_msg)
        logging.critical(fatal_error_msg)
        if bot and hasattr(bot, 'notify'):
            bot.notify(fatal_error_msg)