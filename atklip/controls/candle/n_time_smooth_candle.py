from concurrent.futures import Future
import pandas as pd
from typing import Any, Dict, List, Tuple
from atklip.controls.pandas_ta.ma import ma
from atklip.controls.ma_type import PD_MAType
from atklip.controls.ohlcv import OHLCV
from .candle import JAPAN_CANDLE
from .heikinashi import HEIKINASHI
from atklip.appmanager import ThreadPoolExecutor_global as ApiThreadPool, HeavyProcess
from PySide6.QtCore import Qt, Signal, QObject, QCoreApplication


class N_SMOOTH_CANDLE(QObject):
    """
    _candles: JAPAN_CANDLE|HEIKINASHI
    lastcandle: signal(list)  - the list of 2 last candle of para "_candles: JAPAN_CANDLE|HEIKINASHI"
    mamode: IndicatorType  - IndicatorType.SMA
    ma_leng: int - 20
    """

    sig_update_candle = Signal(list)
    sig_add_candle = Signal(list)
    sig_add_historic = Signal(int)
    sig_reset_all = Signal()
    candles: List[OHLCV] = []
    dict_index_time = {}
    dict_n_ma: Dict[str, pd.Series] = {}
    dict_n_frame: Dict[str, pd.DataFrame] = {}
    signal_delete = Signal()
    sig_update_source = Signal()

    def __init__(
        self, chart, candles, n, mamode, ma_leng, dict_candle_params: dict = {}
    ) -> None:
        super().__init__(parent=None)
        self.chart = chart
        if candles != None:
            self._candles: JAPAN_CANDLE | HEIKINASHI = candles
        if dict_candle_params != {}:
            self.id_exchange: str = dict_candle_params["id_exchange"]
            self.symbol: str = dict_candle_params["symbol"]
            self.interval: str = dict_candle_params["interval"]
            self.mamode: PD_MAType = dict_candle_params["mamode"]
            self.ma_leng: int = dict_candle_params["ma_leng"]
            self.source: str = dict_candle_params["source"]
            self.precision = dict_candle_params["precision"]
            self.canlde_id = dict_candle_params["canlde_id"]
            self.chart_id = dict_candle_params["chart_id"]
            self.name: str = dict_candle_params.get("name")
            self.n: int = dict_candle_params["n_smooth"]
        else:
            self.mamode: PD_MAType = mamode
            self.ma_leng: int = ma_leng
            self.n: int = n
            self.precision = self.chart.get_precision()

        self.start_index: int = 0
        self.stop_index: int = 0
        self.signal_delete.connect(self.deleteLater)
        self._candles.sig_update_source.connect(self.sig_update_source)
        self.is_current_update = False
        self.is_histocric_load = False
        self.first_gen = False
        self.is_genering = True
        self._is_update = False
        self.n_len: int = 0
        self._source_name = f"N_SMOOTH_CANDLE_{self.ma_leng}_{self.n}"
        self.df = pd.DataFrame([])
        self.worker = ApiThreadPool
        self.connect_signals()

    @property
    def is_current_update(self) -> bool:
        return self._is_current_update

    @is_current_update.setter
    def is_current_update(self, _is_current_update):
        self._is_current_update = _is_current_update

    @property
    def precision(self):
        return self.chart.get_precision()

    @precision.setter
    def precision(self, precision):
        self._precision = precision

    def change_input(self, candles=None, dict_candle_params: dict = {}):

        if candles != None:
            self.disconnect_signals()
            self._candles: JAPAN_CANDLE | HEIKINASHI = candles
            self.connect_signals()

        if dict_candle_params != {}:
            self.id_exchange: str = dict_candle_params["id_exchange"]
            self.symbol: str = dict_candle_params["symbol"]
            self.interval: str = dict_candle_params["interval"]
            self.mamode: PD_MAType = dict_candle_params["mamode"]
            self.ma_leng: int = dict_candle_params["ma_leng"]
            self.source: str = dict_candle_params["source"]
            self.precision = dict_candle_params["precision"]
            self.canlde_id = dict_candle_params["canlde_id"]
            self.chart_id = dict_candle_params["chart_id"]
            self.name: str = dict_candle_params.get("name")
            self.n: int = dict_candle_params["n_smooth"]

            source_name = f"{self.chart_id}-{self.canlde_id}-{self.id_exchange}-{self.source}-{self.name}-{self.symbol}-{self.interval}-{self.mamode.name}-{self.ma_leng}-{self.n}".encode(
                "utf-8"
            ).decode(
                "utf-8"
            )
            self.source_name = source_name
        self.first_gen = False
        self.is_genering = True
        self.first_gen_data()

    def set_candle_infor(self, id_exchange, symbol, interval):
        self.id_exchange = id_exchange
        self.symbol = symbol
        self.interval = interval

    def get_candle_infor(self):
        return self.id_exchange, self.symbol, self.interval

    # def delete(self):
    #     self.deleteLater()

    def connect_signals(self):
        self._candles.sig_update_source.connect(self.sig_update_source)
        self._candles.sig_reset_all.connect(self.first_gen_data)
        self._candles.sig_update_candle.connect(self.update_worker)
        self._candles.sig_add_candle.connect(self.update_worker)
        self._candles.sig_add_historic.connect(self.update_historic_worker)

    def disconnect_signals(self):
        try:
            self._candles.sig_update_source.disconnect(self.sig_update_source)
            self._candles.sig_reset_all.disconnect(self.first_gen_data)
            self._candles.sig_update_candle.disconnect(self.update_worker)
            self._candles.sig_add_candle.disconnect(self.update_worker)
            self._candles.sig_add_historic.disconnect(self.update_historic_worker)
        except:
            pass

    def update_source(self, candle: JAPAN_CANDLE | HEIKINASHI):
        self.disconnect_signals()
        self._candles = candle
        self.connect_signals()

    @property
    def source_name(self):
        return self._source_name

    @source_name.setter
    def source_name(self, _source_name):
        self._source_name = _source_name

    def get_df(self, n: int = None):
        if not n:
            return self.df
        if n > len(self.df):
            return self.df
        return self.df.tail(n)

    def get_head_df(self, n: int = None):
        if not n:
            return self.df
        return self.df.head(n)

    def get_tail_df(self, n: int = None):
        if not n:
            return self.df
        return self.df.tail(n)

    def get_last_row_df(self):
        return self.df.iloc[-1]

    def update_worker(self, candle):
        self.worker.submit(self.update, candle)

    def threadpool_asyncworker(self):
        self.worker.submit(self.first_gen_data)

    def update_historic_worker(self, n):
        self.worker.submit(self.gen_historic_data, n)

    # @lru_cache(maxsize=128)
    def get_times(self, start: int = 0, stop: int = 0) -> List[int]:
        if start == 0 and stop == 0:
            avg = self.df["time"].to_numpy()
        elif start == 0 and stop != 0:
            avg = self.df["time"].iloc[:stop].to_numpy()
        elif start != 0 and stop == 0:
            avg = self.df["time"].iloc[start:].to_numpy()
        else:
            avg = self.df["time"].iloc[start:stop].to_numpy()
        return avg

    # @lru_cache(maxsize=128)
    def get_indexs(self, start: int = 0, stop: int = 0) -> List[int]:
        if start == 0 and stop == 0:
            avg = self.df["index"].to_numpy()
        elif start == 0 and stop != 0:
            avg = self.df["index"].iloc[:stop].to_numpy()
        elif start != 0 and stop == 0:
            avg = self.df["index"].iloc[start:].to_numpy()
        else:
            avg = self.df["index"].iloc[start:stop].to_numpy()
        return avg

    # @lru_cache(maxsize=128)
    def get_values(self, start: int = 0, stop: int = 0) -> List[List[float]]:

        if start == 0 and stop == 0:
            avg = [
                self.df["open"].to_numpy(),
                self.df["high"].to_numpy(),
                self.df["low"].to_numpy(),
                self.df["close"].to_numpy(),
            ]
        elif start == 0 and stop != 0:
            avg = [
                self.df["open"].iloc[:stop].to_numpy(),
                self.df["high"].iloc[:stop].to_numpy(),
                self.df["low"].iloc[:stop].to_numpy(),
                self.df["close"].iloc[:stop].to_numpy(),
            ]
        elif start != 0 and stop == 0:
            avg = [
                self.df["open"].iloc[start:].to_numpy(),
                self.df["high"].iloc[start:].to_numpy(),
                self.df["low"].iloc[start:].to_numpy(),
                self.df["close"].iloc[start:].to_numpy(),
            ]
        else:
            avg = [
                self.df["open"].iloc[start:stop].to_numpy(),
                self.df["high"].iloc[start:stop].to_numpy(),
                self.df["low"].iloc[start:stop].to_numpy(),
                self.df["close"].iloc[start:stop].to_numpy(),
            ]
        return avg

    # @lru_cache(maxsize=128)
    def get_volumes(self, start: int = 0, stop: int = 0) -> List[List[float]]:
        if start == 0 and stop == 0:
            avg = [
                self.df["open"].to_numpy(),
                self.df["close"].to_numpy(),
                self.df["volume"].to_numpy(),
            ]
        elif start == 0 and stop != 0:
            avg = [
                self.df["open"].iloc[:stop].to_numpy(),
                self.df["close"].iloc[:stop].to_numpy(),
                self.df["volume"].iloc[:stop].to_numpy(),
            ]
        elif start != 0 and stop == 0:
            avg = [
                self.df["open"].iloc[start:].to_numpy(),
                self.df["close"].iloc[start:].to_numpy(),
                self.df["volume"].iloc[start:].to_numpy(),
            ]
        else:
            avg = [
                self.df["open"].iloc[start:stop].to_numpy(),
                self.df["close"].iloc[start:stop].to_numpy(),
                self.df["volume"].iloc[start:stop].to_numpy(),
            ]
        return avg

    # @lru_cache(maxsize=128)
    def get_n_last_candles(self, n: int = 0) -> List[OHLCV]:
        if n == 0:
            return self.candles
        else:
            return self.candles[n:]

    # @lru_cache(maxsize=128)
    def get_n_first_candles(self, n: int = 0) -> List[OHLCV]:
        if n == 0:
            return self.candles
        else:
            return self.candles[:n]

    def get_data(self, start: int = 0, stop: int = 0):
        all_time = self.get_times(start, stop)
        all_data = self.get_values(start, stop)
        return all_time, all_data

    # @lru_cache(maxsize=128)
    def get_index_data(self, start: int = 0, stop: int = 0):
        if start == 0 and stop == 0:
            all_index = self.df["index"].to_numpy()
            all_open = self.df["open"].to_numpy()
            all_high = self.df["high"].to_numpy()
            all_low = self.df["low"].to_numpy()
            all_close = self.df["close"].to_numpy()
        elif start == 0 and stop != 0:
            all_index = self.df["index"].iloc[:stop].to_numpy()
            all_open = self.df["open"].iloc[:stop].to_numpy()
            all_high = self.df["high"].iloc[:stop].to_numpy()
            all_low = self.df["low"].iloc[:stop].to_numpy()
            all_close = self.df["close"].iloc[:stop].to_numpy()

        elif start != 0 and stop == 0:
            all_index = self.df["index"].iloc[start:].to_numpy()
            all_open = self.df["open"].iloc[start:].to_numpy()
            all_high = self.df["high"].iloc[start:].to_numpy()
            all_low = self.df["low"].iloc[start:].to_numpy()
            all_close = self.df["close"].iloc[start:].to_numpy()
        else:
            all_index = self.df["index"].iloc[start:stop].to_numpy()
            all_open = self.df["open"].iloc[start:stop].to_numpy()
            all_high = self.df["high"].iloc[start:stop].to_numpy()
            all_low = self.df["low"].iloc[start:stop].to_numpy()
            all_close = self.df["close"].iloc[start:stop].to_numpy()

        return all_index, [all_open, all_high, all_low, all_close]

    def get_index_volumes(self, start: int = 0, stop: int = 0):
        if start == 0 and stop == 0:
            all_index = self.df["index"].to_numpy()
            all_open = self.df["open"].to_numpy()
            all_close = self.df["close"].to_numpy()
            all_volume = self.df["volume"].to_numpy()
        elif start == 0 and stop != 0:
            all_index = self.df["index"].iloc[:stop].to_numpy()
            all_open = self.df["open"].iloc[:stop].to_numpy()
            all_volume = self.df["volume"].iloc[:stop].to_numpy()
            all_close = self.df["close"].iloc[:stop].to_numpy()

        elif start != 0 and stop == 0:
            all_index = self.df["index"].iloc[start:].to_numpy()
            all_open = self.df["open"].iloc[start:].to_numpy()
            all_volume = self.df["volume"].iloc[start:].to_numpy()
            all_close = self.df["close"].iloc[start:].to_numpy()
        else:
            all_index = self.df["index"].iloc[start:stop].to_numpy()
            all_open = self.df["open"].iloc[start:stop].to_numpy()
            all_volume = self.df["volume"].iloc[start:stop].to_numpy()
            all_close = self.df["close"].iloc[start:stop].to_numpy()
        return all_index, [all_open, all_close, all_volume]

    # @lru_cache(maxsize=128)
    def get_ohlc4(self, start: int = 0, stop: int = 0) -> List[List[float]]:
        if start == 0 and stop == 0:
            avg = (
                self.df["open"].to_numpy()
                + self.df["high"].to_numpy()
                + self.df["low"].to_numpy()
                + self.df["close"].to_numpy()
            ) / 4
        elif start == 0 and stop != 0:
            avg = (
                self.df["open"].to_numpy()
                + self.df["high"].iloc[:stop].to_numpy()
                + self.df["low"].iloc[:stop].to_numpy()
                + self.df["close"].to_numpy()
            ) / 4
        elif start != 0 and stop == 0:
            avg = (
                self.df["open"].to_numpy()
                + self.df["high"].iloc[start:].to_numpy()
                + self.df["low"].iloc[start:].to_numpy()
                + self.df["close"].to_numpy()
            ) / 4
        else:
            avg = (
                self.df["open"].to_numpy()
                + self.df["high"].iloc[start:stop].to_numpy()
                + self.df["low"].iloc[start:stop].to_numpy()
                + self.df["close"].to_numpy()
            ) / 4
        return avg

    # @lru_cache(maxsize=128)
    def get_hlc3(self, start: int = 0, stop: int = 0) -> List[List[float]]:
        if start == 0 and stop == 0:
            avg = (
                self.df["high"].to_numpy()
                + self.df["low"].to_numpy()
                + self.df["close"].to_numpy()
            ) / 3
        elif start == 0 and stop != 0:
            avg = (
                self.df["high"].iloc[:stop].to_numpy()
                + self.df["low"].iloc[:stop].to_numpy()
                + self.df["close"].to_numpy()
            ) / 3
        elif start != 0 and stop == 0:
            avg = (
                self.df["high"].iloc[start:].to_numpy()
                + self.df["low"].iloc[start:].to_numpy()
                + self.df["close"].to_numpy()
            ) / 3
        else:
            avg = (
                self.df["high"].iloc[start:stop].to_numpy()
                + self.df["low"].iloc[start:stop].to_numpy()
                + self.df["close"].to_numpy()
            ) / 3
        return avg

    # @lru_cache(maxsize=128)
    def get_hl2(self, start: int = 0, stop: int = 0) -> List[List[float]]:
        if start == 0 and stop == 0:
            avg = (self.df["high"].to_numpy() + self.df["low"].to_numpy()) / 2
        elif start == 0 and stop != 0:
            avg = (
                self.df["high"].iloc[:stop].to_numpy()
                + self.df["low"].iloc[:stop].to_numpy()
            ) / 2
        elif start != 0 and stop == 0:
            avg = (
                self.df["high"].iloc[start:].to_numpy()
                + self.df["low"].iloc[start:].to_numpy()
            ) / 2
        else:
            avg = (
                self.df["high"].iloc[start:stop].to_numpy()
                + self.df["low"].iloc[start:stop].to_numpy()
            ) / 2
        return avg

    # @lru_cache(maxsize=128)
    def get_index_hl2(self, start: int = 0, stop: int = 0):
        all_index = self.get_indexs(start, stop)
        all_data = self.get_hl2(start, stop)
        return all_index, all_data

    # @lru_cache(maxsize=128)
    def get_index_hlc3(self, start: int = 0, stop: int = 0):
        all_index = self.get_indexs(start, stop)
        all_data = self.get_hlc3(start, stop)
        return all_index, all_data

    # @lru_cache(maxsize=128)
    def get_index_ohlc4(self, start: int = 0, stop: int = 0):
        all_index = self.get_indexs(start, stop)
        all_data = self.get_ohlc4(start, stop)
        return all_index, all_data

    def get_last_candle(self):
        return self.df.iloc[-1].to_dict()

    # @lru_cache(maxsize=128)
    def get_list_index_data(self, start: int = 0, stop: int = 0):
        all_index = self.get_indexs(start, stop)
        all_data = self.get_values(start, stop)
        return all_index, all_data

    def last_data(self) -> OHLCV:
        """_summary_

        Returns:
            OHLCV: open: float | None,
                high: float | None,
                low: float | None,
                close: float | None,
                hl2: float | None,
                hlc3: float | None,
                ohlc4: float | None,
                volume: float | None,
                time: int | None,
                index: int | None
        """
        last_df = self.get_last_candle()
        return OHLCV(
            last_df["open"],
            last_df["high"],
            last_df["low"],
            last_df["close"],
            last_df["hl2"],
            last_df["hlc3"],
            last_df["ohlc4"],
            last_df["volume"],
            last_df["time"],
            last_df["index"],
        )

    # @lru_cache(maxsize=128)
    def get_ma_ohlc_at_index(
        self,
        index: int,
        opens: pd.Series,
        highs: pd.Series,
        lows: pd.Series,
        closes: pd.Series,
        hl2s: pd.Series,
        hlc3s: pd.Series,
        ohlc4s: pd.Series,
    ):
        # _index = opens.output_times.get(index)
        ohlc = [
            opens._dict_time_value.get(index),
            highs._dict_time_value.get(index),
            lows._dict_time_value.get(index),
            closes._dict_time_value.get(index),
            hl2s._dict_time_value.get(index),
            hlc3s._dict_time_value.get(index),
            ohlc4s._dict_time_value.get(index),
        ]
        return index, ohlc

    def refresh_data(self, mamode, ma_ma_leng, n_smooth_ma_leng):
        self.reset_parameters(mamode, ma_ma_leng, n_smooth_ma_leng)
        self.first_gen_data()

    def reset_parameters(self, mamode, ma_ma_leng, n_smooth_ma_leng):
        self.mamode = mamode
        self.ma_leng = ma_ma_leng
        self.n = n_smooth_ma_leng

    def _gen_data(self, df: pd.DataFrame):
        volumes = df["volume"]
        times = df["time"]
        indexs = df["index"]
        for i in range(self.n):
            highs = (
                ma(self.mamode.name, df["high"], length=self.ma_leng)
                .dropna()
                .round(self.precision)
            )
            lows = (
                ma(self.mamode.name, df["low"], length=self.ma_leng)
                .dropna()
                .round(self.precision)
            )
            closes = (
                ma(self.mamode.name, df["close"], length=self.ma_leng)
                .dropna()
                .round(self.precision)
            )
            opens = (
                ma(self.mamode.name, df["open"], length=self.ma_leng)
                .dropna()
                .round(self.precision)
            )
            hl2s = (
                ma(self.mamode.name, df["hl2"], length=self.ma_leng)
                .dropna()
                .round(self.precision)
            )
            hlc3s = (
                ma(self.mamode.name, df["hlc3"], length=self.ma_leng)
                .dropna()
                .round(self.precision)
            )
            ohlc4s = (
                ma(self.mamode.name, df["ohlc4"], length=self.ma_leng)
                .dropna()
                .round(self.precision)
            )

            df = pd.DataFrame(
                {
                    "open": opens,
                    "high": highs,
                    "low": lows,
                    "close": closes,
                    "hl2": hl2s,
                    "hlc3": hlc3s,
                    "ohlc4": ohlc4s,
                }
            )
        _new_len_df = len(df)

        return pd.DataFrame(
            {
                "open": df["open"],
                "high": df["high"],
                "low": df["low"],
                "close": df["close"],
                "hl2": df["hl2"],
                "hlc3": df["hlc3"],
                "ohlc4": df["ohlc4"],
                "volume": volumes.tail(_new_len_df),
                "time": times.tail(_new_len_df),
                "index": indexs.tail(_new_len_df),
            }
        )

    @staticmethod
    def pro_gen_data(df: pd.DataFrame, n, mamode, ma_leng, precision):
        volumes = df["volume"]
        times = df["time"]
        indexs = df["index"]
        for i in range(n):
            highs = ma(mamode, df["high"], length=ma_leng).dropna().round(precision)
            lows = ma(mamode, df["low"], length=ma_leng).dropna().round(precision)
            closes = ma(mamode, df["close"], length=ma_leng).dropna().round(precision)
            opens = ma(mamode, df["open"], length=ma_leng).dropna().round(precision)
            hl2s = ma(mamode, df["hl2"], length=ma_leng).dropna().round(precision)
            hlc3s = ma(mamode, df["hlc3"], length=ma_leng).dropna().round(precision)
            ohlc4s = ma(mamode, df["ohlc4"], length=ma_leng).dropna().round(precision)

            df = pd.DataFrame(
                {
                    "open": opens,
                    "high": highs,
                    "low": lows,
                    "close": closes,
                    "hl2": hl2s,
                    "hlc3": hlc3s,
                    "ohlc4": ohlc4s,
                }
            )
        _new_len_df = len(df)

        return pd.DataFrame(
            {
                "open": df["open"],
                "high": df["high"],
                "low": df["low"],
                "close": df["close"],
                "hl2": df["hl2"],
                "hlc3": df["hlc3"],
                "ohlc4": df["ohlc4"],
                "volume": volumes.tail(_new_len_df),
                "time": times.tail(_new_len_df),
                "index": indexs.tail(_new_len_df),
            }
        )

    def gen_candles(self):
        for i in range(len(self.df)):
            _open, _high, _low, _close, hl2, hlc3, ohlc4, _volume, _time, _index = (
                self.df["open"].iloc[i],
                self.df["high"].iloc[i],
                self.df["low"].iloc[i],
                self.df["close"].iloc[i],
                self.df["hl2"].iloc[i],
                self.df["hlc3"].iloc[i],
                self.df["ohlc4"].iloc[i],
                self.df["volume"].iloc[i],
                self.df["time"].iloc[i],
                self.df["index"].iloc[i],
            )
            variables = [
                _open,
                _high,
                _low,
                _close,
                hl2,
                hlc3,
                ohlc4,
                _volume,
                _time,
                _index,
            ]
            if _index not in list(self.map_index_ohlcv.keys()):
                if not any(v is None for v in variables):
                    ohlcv = OHLCV(
                        _open,
                        _high,
                        _low,
                        _close,
                        hl2,
                        hlc3,
                        ohlc4,
                        _volume,
                        _time,
                        _index,
                    )
                    self.map_index_ohlcv[ohlcv.index] = ohlcv
                    self.map_time_ohlcv[ohlcv.time] = ohlcv
                    self.candles.append(ohlcv)

    def _gen_historic_data(self, future: Future):
        # print("zoooooooooooooooooooooooooooooooooooooo")
        # print(future.result())
        df = future.result()
        volumes = df["volume"]
        times = df["time"]
        indexs = df["index"]
        _new_len_df = len(df)
        _df = pd.DataFrame(
            {
                "open": df["open"],
                "high": df["high"],
                "low": df["low"],
                "close": df["close"],
                "hl2": df["hl2"],
                "hlc3": df["hlc3"],
                "ohlc4": df["ohlc4"],
                "volume": volumes.tail(_new_len_df),
                "time": times.tail(_new_len_df),
                "index": indexs.tail(_new_len_df),
            }
        )
        self.df = pd.concat([_df, self.df], ignore_index=True)

        self.is_genering = False
        if self.first_gen == False:
            self.first_gen = True
            self.is_genering = False
        self.is_histocric_load = True
        self.sig_add_historic.emit(self.n_len)
        return self.candles

    def gen_historic_data(self, n_len):
        self.n_len = n_len
        self.is_genering = True
        self.is_histocric_load = False
        _pre_len = len(self.df)
        df = self._candles.get_df().iloc[: -1 * _pre_len]
        process = HeavyProcess(
            self.pro_gen_data,
            self._gen_historic_data,
            df,
            self.n,
            self.mamode.name,
            self.ma_leng,
            self.precision,
        )
        process.start()

    def callback(self, future: Future):
        self.df = future.result()
        self.is_genering = False
        if self.first_gen == False:
            self.first_gen = True
            self.is_genering = False
        # self.start_index:int = self.df["index"].iloc[0]
        # self.stop_index:int = self.df["index"].iloc[-1]
        # self.is_current_update = True
        self.sig_reset_all.emit()
        return future.result()

    def first_gen_data(self):
        self.is_current_update = False
        self.is_genering = True
        self.df = pd.DataFrame([])
        self.map_index_ohlcv: Dict[int, OHLCV] = {}
        self.map_time_ohlcv: Dict[int, OHLCV] = {}
        self.dict_n_frame.clear()
        self.dict_n_ma.clear()
        df = self._candles.get_df()
        process = HeavyProcess(
            self.pro_gen_data,
            self.callback,
            df,
            self.n,
            self.mamode.name,
            self.ma_leng,
            self.precision,
        )
        process.start()

    def callback_update_ma_ohlc(self, future: Future):
        update_df = future.result()
        if self._is_update:
            self.df.iloc[-1] = update_df.iloc[-1]
        else:
            self.df = pd.concat([self.df, update_df.iloc[[-1]]], ignore_index=True)

        _open, _high, _low, _close, hl2, hlc3, ohlc4, _volume, _time, _index = (
            self.df["open"].iloc[-1],
            self.df["high"].iloc[-1],
            self.df["low"].iloc[-1],
            self.df["close"].iloc[-1],
            self.df["hl2"].iloc[-1],
            self.df["hlc3"].iloc[-1],
            self.df["ohlc4"].iloc[-1],
            self.df["volume"].iloc[-1],
            self.df["time"].iloc[-1],
            self.df["index"].iloc[-1],
        )

        ohlcv = OHLCV(
            _open, _high, _low, _close, hl2, hlc3, ohlc4, _volume, _time, _index
        )
        if self._is_update:
            # self.start_index:int = self.df["index"].iloc[0]
            # self.stop_index:int = self.df["index"].iloc[-1]
            # self.is_current_update = True
            self.sig_update_candle.emit([ohlcv])
        else:
            # self.start_index:int = self.df["index"].iloc[0]
            # self.stop_index:int = self.df["index"].iloc[-1]
            # self.is_current_update = True
            self.sig_add_candle.emit([ohlcv])

    def update(self, _candle: List[OHLCV]):
        self.is_current_update = False
        if (self.first_gen == True) and (self.is_genering == False):
            new_candle = _candle[-1]
            _new_time = new_candle.time
            df = self._candles.get_df().tail(self.ma_leng * (self.n + 1))
            _last_time = self.df["time"].iloc[-1]
            self._is_update = False

            if _new_time == _last_time:
                self._is_update = True

            process = HeavyProcess(
                self.pro_gen_data,
                self.callback_update_ma_ohlc,
                df,
                self.n,
                self.mamode.name,
                self.ma_leng,
                self.precision,
            )
            process.start()
        else:
            pass
            # self.is_current_update = True
