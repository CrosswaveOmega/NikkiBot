import gui
from inspect import currentframe, getframeinfo

DEBUG_MODE = False


def get_linenumber():
    cf = currentframe()
    return cf.f_back.f_back, cf.f_back.f_back.f_back  # .f_lineno


def get_linenumber_rec():
    cf = currentframe()
    thisframe = cf.f_back.f_back
    info = getframeinfo(thisframe)
    if info.function == "evaluateExpression":
        return ""
    out = f"{info.function}[{info.lineno}]->"
    while info.function != "evaluateExpression":
        thisframe = thisframe.f_back
        info = getframeinfo(thisframe)
        out = f"{info.function}[{info.lineno}]->" + out
    return out


printMode = True


def dprint(*args):
    """gui.gprint a debug gui.gprint statement"""
    if printMode:
        line, lineback = get_linenumber()
        info = getframeinfo(line)
        gui.gprint(f"{info.function}-{info.lineno},{args}")


def isNumber(string_input):
    # return true is string can be float, false otherwise.
    try:
        float(string_input)
        return True
    except ValueError:
        return False


def toExpressionString(i):
    # This just removes the :game_die: emoji from the string for the next calculation.
    stri = str(i)
    stri = stri.replace(":game_die:", "")
    return stri


def toNumber(i):
    if isinstance(i, int):
        return float(i)
    if isinstance(i, float):
        return i
    if isinstance(i, str):
        # The Negative Sign is represented by a different symbol for the
        # Expression parser for the sake of simpicity
        # '\u2212' is the negative symbol.
        stri = i.replace("\u2212", "-")
        if i == "-":
            return 0
        r = float(stri)
        return r
