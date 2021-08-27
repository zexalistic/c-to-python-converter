from enum import Enum, unique, IntEnum

@unique
class MY_BOOL(IntEnum):
    MY_TRUE = 1
    MY_FALSE = 0


@unique
class WEEKDAYS(IntEnum):
    TUE = 0
    WED = 1
    THU = 2
    FRI = 3


@unique
class MONTHS(IntEnum):
    JAN = 0
    FEB = 1


