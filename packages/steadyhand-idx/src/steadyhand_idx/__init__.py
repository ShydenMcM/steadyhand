"""steadyhand-idx: the Indonesia Stock Exchange distribution of steadyhand."""

from importlib.metadata import version

from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.fees import BrokerPreset, FeeSchedule

__version__: str = version("steadyhand-idx")

__all__ = [
    "BrokerPreset",
    "DataFileError",
    "FeeSchedule",
    "IdxCalendar",
    "__version__",
]
