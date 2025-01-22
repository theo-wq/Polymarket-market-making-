import os
import logging
import pandas as pd
from typing import Dict, Tuple, Optional
from datetime import datetime
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, BookParams
from py_clob_client.constants import AMOY
import json

class OrderBookAnalyzer:

    def __init__(self,
                 imbalance_threshold: float = 3.0,
                 volume_threshold: float = 0.4,
                 price_levels: int = 3,
                 spread_multiplier: float = 1.5):
        
        load_dotenv()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(current_dir)
        config_path = os.path.join(base_dir, 'clean_prod', 'config.json')
        
        try:
            with open(config_path, 'r') as config_file:
                self.config = json.load(config_file)
        except FileNotFoundError as e:
            logging.critical(f"Impossible de trouver le fichier de configuration: {config_path}")
            raise FileNotFoundError(f"Le fichier de configuration n'existe pas au chemin: {config_path}")
        except json.JSONDecodeError as e:
            logging.critical(f"Erreur de lecture du fichier de configuration: {str(e)}")
            raise

        self.api_key = os.getenv('API_KEY')
        self.api_secret = os.getenv('API_SECRET')
        self.api_passphrase = os.getenv('API_PASSPHRASE')
        self.private_key = os.getenv('PRIVATE_KEY')
        self.token_id = self.config['trading_parameters']['TOKEN_ID']
        self.host = "https://clob.polymarket.com"

        self._validate_env_variables()

        self.imbalance_threshold = imbalance_threshold
        self.volume_threshold = volume_threshold
        self.price_levels = price_levels
        self.spread_multiplier = spread_multiplier

        self.client = self._initialize_client()
        
        self._setup_logging()

    def _validate_env_variables(self):

        required_vars = [
            'API_KEY',
            'API_SECRET',
            'API_PASSPHRASE',
            'PRIVATE_KEY',
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing_vars)}")

    def _setup_logging(self):

        log_directory = "logs"
        if not os.path.exists(log_directory):
            os.makedirs(log_directory)

        log_filename = os.path.join(log_directory, "order_book_analyzer.log")
        logging.basicConfig(
            filename=log_filename,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def _initialize_client(self) -> ClobClient:

        creds = ApiCreds(
            api_key=self.api_key,
            api_secret=self.api_secret,
            api_passphrase=self.api_passphrase,
        )
        return ClobClient(self.host, key=self.private_key, chain_id=AMOY, creds=creds)


    def get_orderbook(self) -> Optional[pd.DataFrame]:

        try:
            orderbook = self.client.get_order_book(self.token_id)
            
            # Process bids
            bids_df = pd.DataFrame([{
                'price': float(bid.price),
                'size': float(bid.size),
                'type': 'bid'
            } for bid in orderbook.bids])

            # Process asks
            asks_df = pd.DataFrame([{
                'price': float(ask.price),
                'size': float(ask.size),
                'type': 'ask'
            } for ask in orderbook.asks])

            # Combine and sort
            orderbook_df = pd.concat([bids_df, asks_df], ignore_index=True)
            orderbook_df.sort_values('price', ascending=True, inplace=True)
            orderbook_df['cumulative_size'] = orderbook_df.groupby('type')['size'].cumsum()
            orderbook_df['timestamp'] = orderbook.timestamp

            return orderbook_df

        except Exception as e:
            logging.error(f"Erreur lors de la récupération de l'order book: {str(e)}")
            return None


    def _calculate_price_pressure(self, df: pd.DataFrame, ascending: bool) -> float:

        if len(df) < self.price_levels:
            return 0.0

        df_sorted = df.sort_values('price', ascending=ascending)
        volumes = df_sorted['size'].head(self.price_levels).values

        pressure = 0
        for i in range(len(volumes)-1):
            if volumes[i+1] > 0:
                pressure += (volumes[i] / volumes[i+1]) * (1 / (i + 1))

        return pressure / (len(volumes) - 1)


    def calculate_metrics(self, orderbook_df: pd.DataFrame) -> dict:

        bids = orderbook_df[orderbook_df['type'] == 'bid'].copy()
        asks = orderbook_df[orderbook_df['type'] == 'ask'].copy()

        # Basic metrics
        spread = asks['price'].min() - bids['price'].max()
        mid_price = (asks['price'].min() + bids['price'].max()) / 2

        # Volume imbalance
        near_spread_threshold = spread * self.spread_multiplier
        near_bids = bids[bids['price'] >= bids['price'].max() - near_spread_threshold]
        near_asks = asks[asks['price'] <= asks['price'].min() + near_spread_threshold]

        bid_volume = near_bids['size'].sum()
        ask_volume = near_asks['size'].sum()
        volume_imbalance = bid_volume / ask_volume if ask_volume > 0 else float('inf')

        # Price pressure
        bid_pressure = self._calculate_price_pressure(bids, ascending=False)
        ask_pressure = self._calculate_price_pressure(asks, ascending=True)

        # Concentration
        best_bid_concentration = (bids.iloc[0]['size'] / bid_volume) if bid_volume > 0 else 0
        best_ask_concentration = (asks.iloc[0]['size'] / ask_volume) if ask_volume > 0 else 0

        return {
            'spread': spread,
            'mid_price': mid_price,
            'volume_imbalance': volume_imbalance,
            'bid_pressure': bid_pressure,
            'ask_pressure': ask_pressure,
            'best_bid_concentration': best_bid_concentration,
            'best_ask_concentration': best_ask_concentration,
            'best_bid_price': bids['price'].max(),
            'best_ask_price': asks['price'].min(),
            'bid_volume': bid_volume,
            'ask_volume': ask_volume,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


    def is_market_favorable(self, orderbook_df: pd.DataFrame) -> Tuple[bool, str]:

        try:
            metrics = self.calculate_metrics(orderbook_df)
            
            # Conditions favorables
            if metrics['volume_imbalance'] > self.imbalance_threshold:
                if metrics['best_bid_concentration'] > 0.7 or metrics['bid_pressure'] > self.volume_threshold:
                    return True, "Forte pression d'achat"

            if metrics['spread'] < 0.02 and 0.8 <= metrics['volume_imbalance'] <= 1.2:
                if metrics['bid_pressure'] > self.volume_threshold:
                    return True, "Marché équilibré avec pression d'achat"

            if metrics['volume_imbalance'] > 1.5 and metrics['spread'] < 0.015:
                return True, "Fort déséquilibre acheteur avec spread serré"

            # Conditions défavorables
            if metrics['spread'] > 0.02:
                if abs(metrics['volume_imbalance'] - 1) > 0.5:
                    return False, "Spread large avec déséquilibre"

            if metrics['volume_imbalance'] < 1/self.imbalance_threshold:
                if metrics['best_ask_concentration'] > 0.7 or metrics['ask_pressure'] > self.volume_threshold:
                    return False, "Forte pression de vente"

            return False, "Conditions neutres"

        except Exception as e:
            logging.error(f"Erreur lors de l'analyse: {str(e)}")
            return False, f"Erreur d'analyse: {str(e)}"


    def get_market_status(self) -> Dict:

        try:
            orderbook_df = self.get_orderbook()
            if orderbook_df is None:
                return {
                    'is_favorable': False,
                    'reason': "Impossible de récupérer l'orderbook",
                    'metrics': {}
                }

            is_favorable, reason = self.is_market_favorable(orderbook_df)
            metrics = self.calculate_metrics(orderbook_df)

            return {
                'is_favorable': is_favorable,
                'reason': reason,
                'metrics': metrics
            }

        except Exception as e:
            logging.error(f"Erreur dans get_market_status: {str(e)}")
            return {
                'is_favorable': False,
                'reason': f"Erreur: {str(e)}",
                'metrics': {}
            }


    def get_last_trade_price(self) -> Optional[float]:

        try:
            return float(self.client.get_last_trade_price(self.token_id))
        except Exception as e:
            logging.error(f"Erreur lors de la récupération du dernier prix: {str(e)}")
            return None


    def get_midpoint_price(self) -> Optional[float]:

        try:
            resp = self.client.get_midpoints(
                params=[BookParams(token_id=self.token_id)]
            )
            return float(next(iter(resp.values())))
        except Exception as e:
            logging.error(f"Erreur lors de la récupération du prix midpoint: {str(e)}")
            return None