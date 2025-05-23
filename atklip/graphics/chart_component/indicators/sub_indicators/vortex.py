import time
from typing import Tuple, List, TYPE_CHECKING
import numpy as np
import pandas as pd
from pyqtgraph import GraphicsObject
from atklip.graphics.chart_component.base_items.plotdataitem import PlotDataItem

from pyqtgraph import functions as fn
from atklip.graphics.chart_component.base_items import PriceLine
from PySide6.QtCore import Signal, QObject, Qt, QRectF
from PySide6.QtGui import QColor, QPicture, QPainter
from PySide6.QtWidgets import QGraphicsItem

from atklip.controls import PD_MAType, IndicatorType, VORTEX
from atklip.controls.models import VORTEXModel

from atklip.appmanager import FastWorker
from atklip.app_utils import *

if TYPE_CHECKING:
    from atklip.graphics.chart_component.viewchart import Chart
    from atklip.graphics.chart_component.sub_panel_indicator import ViewSubPanel


class BasicVTX(GraphicsObject):
    """RSI"""

    on_click = Signal(object)

    last_pos = Signal(tuple)

    signal_visible = Signal(bool)
    signal_delete = Signal()

    sig_change_yaxis_range = Signal()

    sig_change_indicator_name = Signal(str)

    def __init__(self, get_last_pos_worker, chart, panel) -> None:
        """Choose colors of candle"""
        GraphicsObject.__init__(self)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)
        self.chart: Chart = chart
        self._panel: ViewSubPanel = panel

        self._precision = self.chart._precision

        self.has: dict = {
            "name": f"VTX 9 12 26",
            "y_axis_show": True,
            "inputs": {
                "source": self.chart.jp_candle,
                "source_name": self.chart.jp_candle.source_name,
                "indicator_type": IndicatorType.VTX,
                "period": 13,
                "drift": 1,
                "show": True,
            },
            "styles": {
                "pen_vortex_line": "red",
                "width_vortex_line": 1,
                "style_vortex_line": Qt.PenStyle.SolidLine,
                "pen_signal_line": "orange",
                "width_signal_line": 1,
                "style_signal_line": Qt.PenStyle.SolidLine,
            },
        }

        self.id = self.chart.objmanager.add(self)

        self.on_click.connect(self.on_click_event)
        self.signal_visible.connect(self.setVisible)
        self.signal_delete.connect(self.delete)

        self.vortex_line = PlotDataItem(pen="red")  # for z value
        self.vortex_line.setParentItem(self)
        self.signal = PlotDataItem(pen="orange")
        self.signal.setParentItem(self)

        self.price_line = PriceLine()  # for z value
        self.price_line.setParentItem(self)

        self.picture: QPicture = QPicture()

        self.last_pos.connect(
            self.price_line.update_price_line_indicator,
            Qt.ConnectionType.AutoConnection,
        )

        self.worker = None

        self.sig_change_yaxis_range.connect(
            get_last_pos_worker, Qt.ConnectionType.AutoConnection
        )

        self.INDICATOR = VORTEX(self.has["inputs"]["source"], self.model.__dict__)

        self.chart.sig_update_source.connect(
            self.change_source, Qt.ConnectionType.AutoConnection
        )
        self.signal_delete.connect(self.delete)

    @property
    def is_all_updated(self):
        is_updated = self.INDICATOR.is_current_update
        return is_updated

    @property
    def id(self):
        return self.chart_id

    @id.setter
    def id(self, _chart_id):
        self.chart_id = _chart_id

    @property
    def model(self):
        return VORTEXModel(
            self.id,
            "STOCHRSI",
            self.chart.jp_candle.source_name,
            self.has["inputs"]["period"],
            self.has["inputs"]["drift"],
        )

    def disconnect_signals(self):
        try:
            self.INDICATOR.sig_reset_all.disconnect(self.reset_threadpool_asyncworker)
            self.INDICATOR.sig_update_candle.disconnect(self.setdata_worker)
            self.INDICATOR.sig_add_candle.disconnect(self.setdata_worker)
            self.INDICATOR.signal_delete.disconnect(self.replace_source)
            self.INDICATOR.sig_add_historic.connect(self.add_historic_worker)
        except RuntimeError:
            pass

    def connect_signals(self):
        self.INDICATOR.sig_reset_all.connect(
            self.reset_threadpool_asyncworker, Qt.ConnectionType.AutoConnection
        )
        self.INDICATOR.sig_update_candle.connect(
            self.setdata_worker, Qt.ConnectionType.AutoConnection
        )
        self.INDICATOR.sig_add_candle.connect(
            self.setdata_worker, Qt.ConnectionType.AutoConnection
        )
        self.INDICATOR.signal_delete.connect(
            self.replace_source, Qt.ConnectionType.AutoConnection
        )
        self.INDICATOR.sig_add_historic.connect(
            self.add_historic_worker, Qt.ConnectionType.AutoConnection
        )

    def first_gen_data(self):
        self.connect_signals()
        self.INDICATOR.started_worker()

    def delete(self):
        self.INDICATOR.deleteLater()
        self.chart.sig_remove_item.emit(self)

    def regen_indicator(self, setdata):
        xdata, vortex, signalma = self.INDICATOR.get_data()
        self.has["name"] = f"""VTX {self.has["inputs"]["period"]}"""
        self.sig_change_indicator_name.emit(self.has["name"])
        setdata.emit((xdata, vortex, signalma))
        self.sig_change_yaxis_range.emit()

    def replace_source(self):
        self.update_inputs("source", self.chart.jp_candle.source_name)

    def reset_threadpool_asyncworker(self):
        self.reset_indicator()

    def change_source(self, source):
        if self.has["inputs"]["source_name"] == source.source_name:
            self.update_inputs("source", source.source_name)

    def set_Data(self, data):
        xData = data[0]
        lb = data[1]
        cb = data[2]
        self.vortex_line.setData(xData, lb)
        self.signal.setData(xData, cb)
        self.INDICATOR.is_current_update = True

    def add_historic_Data(self, data):
        xData = data[0]
        lb = data[1]
        cb = data[2]
        self.vortex_line.addHistoricData(xData, lb)
        self.signal.addHistoricData(xData, cb)
        self.INDICATOR.is_current_update = True

    def update_Data(self, data):
        xData = data[0]
        lb = data[1]
        cb = data[2]
        self.vortex_line.updateData(xData, lb)
        self.signal.updateData(xData, cb)
        self.INDICATOR.is_current_update = True

    def reset_indicator(self):
        self.worker = None
        self.worker = FastWorker(self.regen_indicator)
        self.worker.signals.setdata.connect(
            self.set_Data, Qt.ConnectionType.AutoConnection
        )
        self.worker.start()

    def setdata_worker(self):
        self.worker = None
        self.worker = FastWorker(self.update_data)
        self.worker.signals.setdata.connect(
            self.update_Data, Qt.ConnectionType.AutoConnection
        )
        self.worker.start()

    def add_historic_worker(self, _len):
        self.worker = None
        self.worker = FastWorker(self.load_historic_data, _len)
        self.worker.signals.setdata.connect(
            self.add_historic_Data, Qt.ConnectionType.AutoConnection
        )
        self.worker.start()

    def load_historic_data(self, _len, setdata):
        xdata, vortex, signalma = self.INDICATOR.get_data(stop=_len)
        setdata.emit((xdata, vortex, signalma))

    def update_data(self, setdata):
        xdata, vortex, signalma = self.INDICATOR.get_data(start=-1)
        setdata.emit((xdata, vortex, signalma))
        self.last_pos.emit((self.has["inputs"]["indicator_type"], signalma[-1]))
        self._panel.sig_update_y_axis.emit()

    def update_inputs(self, _input, _source):
        """ "source":self.has["inputs"]["source"],
        "mamode":self.has["inputs"]["mamode"],
        "ma_period":self.has["inputs"]["ma_period"]"""
        update = False
        if _input == "source":
            if self.chart.sources[_source] != self.has["inputs"][_input]:
                self.has["inputs"]["source"] = self.chart.sources[_source]
                self.has["inputs"]["source_name"] = self.chart.sources[
                    _source
                ].source_name
                self.INDICATOR.change_input(self.has["inputs"]["source"])
        elif _source != self.has["inputs"][_input]:
            self.has["inputs"][_input] = _source
            update = True
        if update:
            self.has["name"] = f"""VTX {self.has["inputs"]["period"]}"""
            self.sig_change_indicator_name.emit(self.has["name"])
            self.INDICATOR.change_input(dict_ta_params=self.model.__dict__)

    def get_inputs(self):
        inputs = {
            "source": self.has["inputs"]["source"],
            "period": self.has["inputs"]["period"],
        }
        return inputs

    def get_styles(self):
        styles = {
            "pen_vortex_line": self.has["styles"]["pen_vortex_line"],
            "width_vortex_line": self.has["styles"]["width_vortex_line"],
            "style_vortex_line": self.has["styles"]["style_vortex_line"],
            "pen_signal_line": self.has["styles"]["pen_signal_line"],
            "width_signal_line": self.has["styles"]["width_signal_line"],
            "style_signal_line": self.has["styles"]["style_signal_line"],
        }
        return styles

    def update_styles(self, _input):
        _style = self.has["styles"][_input]
        if (
            _input == "pen_vortex_line"
            or _input == "width_vortex_line"
            or _input == "style_vortex_line"
        ):
            self.vortex_line.setPen(
                color=self.has["styles"]["pen_vortex_line"],
                width=self.has["styles"]["width_vortex_line"],
                style=self.has["styles"]["style_vortex_line"],
            )
        elif (
            _input == "pen_signal_line"
            or _input == "width_signal_line"
            or _input == "style_signal_line"
        ):
            self.signal.setPen(
                color=self.has["styles"]["pen_signal_line"],
                width=self.has["styles"]["width_signal_line"],
                style=self.has["styles"]["style_signal_line"],
            )

    def get_yaxis_param(self):
        _value = None
        try:
            _time, _value = self.get_last_point()
        except:
            pass
        if _value != None:
            if self._precision != None:
                _value = round(_value, self._precision)
            else:
                _value = round(_value, 3)
        return _value, "#363a45"

    def get_xaxis_param(self):
        return None, "#363a45"

    def setVisible(self, visible):
        if visible:
            self.show()
        else:
            self.hide()

    def paint(self, p: QPainter, *args):
        self.picture.play(p)

    def boundingRect(self) -> QRectF:
        x_left, x_right = int(self.chart.xAxis.range[0]), int(self.chart.xAxis.range[1])
        start_index = self.chart.jp_candle.start_index
        stop_index = self.chart.jp_candle.stop_index
        if x_left > start_index:
            self._start = x_left + 2
        else:
            self._start = start_index + 2
        if x_right < stop_index:
            self._stop = x_right
        else:
            self._stop = stop_index

        if self.vortex_line.yData is None:
            h_low, h_high = self._panel.yAxis.range[0], self._panel.yAxis.range[1]
        elif self.vortex_line.yData.size != 0:
            h_low, h_high = np.nanmin(self.vortex_line.yData), np.nanmax(
                self.vortex_line.yData
            )
        else:
            h_low, h_high = self._panel.yAxis.range[0], self._panel.yAxis.range[1]
        rect = QRectF(self._start, h_low, self._stop - self._start, h_high - h_low)
        return rect

    def get_last_point(self):
        _time = self.signal.xData[-1]
        _value = self.signal.yData[-1]
        return _time, _value

    def get_min_max(self):
        _min = None
        _max = None
        try:
            if len(self.signal.yData) > 0:
                _min, _max = np.nanmin(self.signal.yData), np.nanmax(self.signal.yData)
                if _min == np.nan or _max == np.nan:
                    return None, None
                return _min, _max
        except Exception as e:
            pass
        time.sleep(0.1)
        self.get_min_max()
        return _min, _max

    def on_click_event(self):
        # print("zooo day__________________")
        pass
