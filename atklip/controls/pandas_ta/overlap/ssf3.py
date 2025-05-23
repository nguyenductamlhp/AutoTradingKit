# -*- coding: utf-8 -*-
from pandas import Series
from atklip.controls.pandas_ta._typing import DictLike, Int, IntFloat
from atklip.controls.pandas_ta.utils import v_offset, v_pos_default, v_series
from atklip.controls.pandas_ta.utils._numba import nb_ssf3


def ssf3(
    close: Series,
    length: Int = None,
    pi: IntFloat = None,
    sqrt3: IntFloat = None,
    offset: Int = None,
    **kwargs: DictLike,
):
    """Ehler's 3 Pole Super Smoother Filter (SSF) © 2013

    John F. Ehlers's solution to reduce lag and remove aliasing noise
    with his research in aerospace analog filter design. This is
    implementation has three poles. Since SSF is a (Recursive) Digital
    Filter, the number of poles determine how many prior recursive SSF bars
    to include in the filter design.

    For Everget's calculation on TradingView, set arguments:
        pi = np.pi, sqrt3 = 1.738

    Sources:
        https://www.tradingview.com/script/VdJy0yBJ-Ehlers-Super-Smoother-Filter/
        https://www.mql5.com/en/code/589

    Args:
        close (pd.Series): Series of 'close's
        length (int): It's period. Default: 20
        pi (float): The value of PI to use. The default is Ehler's
            truncated value 3.14159. Adjust the value for more precision.
            Default: 3.14159
        sqrt3 (float): The value of sqrt(3) to use. The default is Ehler's
            truncated value 1.732. Adjust the value for more precision.
            Default: 1.732
        offset (int): How many periods to offset the result. Default: 0

    Kwargs:
        fillna (value, optional): pd.DataFrame.fillna(value)

    Returns:
        pd.Series: New feature generated.
    """
    # Validate
    length = v_pos_default(length, 20)
    close = v_series(close, length)

    if close is None:
        return

    pi = v_pos_default(pi, 3.14159)
    sqrt3 = v_pos_default(sqrt3, 1.732)
    offset = v_offset(offset)

    # Calculate
    np_close = close.to_numpy()
    ssf = nb_ssf3(np_close, length, pi, sqrt3)
    ssf = Series(ssf, index=close.index)

    # Offset
    if offset != 0:
        ssf = ssf.shift(offset)

    # Fill
    if "fillna" in kwargs:
        ssf.fillna(kwargs["fillna"], inplace=True)

    # Name and Category
    ssf.name = f"SSF3_{length}"
    ssf.category = "overlap"

    return ssf
