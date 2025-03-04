import gui
from typing import List

from random import randint
from .c_util import *

from .calc_elements import DataBit, DatabitType, preprocess_string

"""This file specifies the functions used for turning a parenthesisless string into a 
List of DataBit objects, and evaluating that list of DataBits via the order of operations.


"""


def defaultOutput(str):
    """default output function."""
    gui.gprint(str)


def redo_current_expression_with_evaluated(
    current_expression, opDone, spartA="", spartB="", outputFunc=defaultOutput
):
    """Return a new expression that replaces all DataBits that had an operation preformed."""
    new_expression = []
    for i in current_expression:
        if i.answered == True:
            new_expression.append(i.answer)
        elif i.enabled == True:
            new_expression.append(i)
    if opDone:
        printOp(new_expression, spartA, spartB, outputFunc)
    return new_expression


def printList(list2, spartA, spartB, outputFunc=defaultOutput):
    outputFunc.outFunc(spartA, " (", str(list2), ") ", spartB, verb=4)


def choosestring(fullstring="", shortstring="", outputFunc=defaultOutput):
    mode = "short"
    if mode == "short":
        return shortstring
    else:
        return fullstring


def printOp(op, spartA, spartB, outputFunc=defaultOutput, verbop=3):
    # output the current operation.
    out = ""
    if type(op) == list:
        for i in op:
            if i.display != None:
                out += str(i.display)
            else:
                out += str(i)
    else:
        out = str(op)
    newString = spartA + " (" + str(out) + ") " + spartB
    if len(newString) > 2000 - 20:
        outputFunc.outFunc("OUTPUT STRING WAY TOO BIG")
    else:
        outputFunc.outFunc(newString, verb=verbop)


def compareValue(valueA, target, lessMode, moreMode, equals):
    if lessMode:
        if equals:
            return valueA <= target
        return valueA < target
    if moreMode:
        if equals:
            return valueA >= target
        return valueA > target


def dice_roll_op(current_expression, spartA, spartB, outputFunc):
    """search for the dice roll operator, and roll the dice."""
    opDone = False
    nextroll = 0
    didrun = False
    rall = [1]
    position = 0
    positions = [[]]
    outputStr = ""
    outputStrPart2 = ""
    rollshorts = []
    for i in current_expression:
        if i.value == "d":  # operator for dice
            opDone = True

            dice_amount = 1  # Default is one.
            dice_sides = 0
            # check if D has a number before it.
            valid_amount_check = True
            valid_sides_check = True

            printList(current_expression, spartA, spartB, outputFunc)
            if (
                position - 1
            ) < 0:  # the position is less than zero, so don't check there!
                valid_amount_check = False
            elif current_expression[position - 1].type != DatabitType.NUMBER:
                valid_amount_check = False

            if (position + 1) >= len(
                current_expression
            ):  # The position is too big!  Don't check there
                valid_sides_check = False
            elif current_expression[position + 1].type != DatabitType.NUMBER:
                valid_sides_check = False

            if valid_sides_check:
                current_expression[position + 1].enabled = False
                dice_sides = int(current_expression[position + 1].value)
            if valid_amount_check:
                current_expression[position - 1].enabled = False
                dice_amount = int(current_expression[position - 1].value)
            current_expression[position].enabled = False

            printList(current_expression, spartA, spartB, outputFunc)

            explodeMode = False
            compoundMode = False
            rerollMode = False
            lessMode = False
            moreMode = False
            equals = False
            checkValue = 0
            # τ⋗
            # ~&⋗

            if 0 <= position + 2 < len(current_expression):
                if current_expression[position + 2].value == "!":  # explodingCheck
                    explodeMode = True
                    outputStrPart2 = choosestring("Will explode values", "explode ")
                    current_expression[position + 2].enabled = False
                if current_expression[position + 2].value == "|":  # CompoundCheck
                    explodeMode = True
                    compoundMode = True
                    outputStrPart2 = choosestring("Will compound values", "compound")
                    current_expression[position + 2].enabled = False
                if current_expression[position + 2].value == "τ":
                    rerollMode = True
                    current_expression[position + 2].enabled = False
                    outputStrPart2 = choosestring("Will reroll values", "reroll")

            printList(current_expression, spartA, spartB, outputFunc)
            if 0 <= position + 4 < len(current_expression):
                comp3 = current_expression[position + 3].value
                comp4 = current_expression[position + 4].value
                checkValue = comp4
                if comp3 == ">":
                    full_string = " if a amount greater than {} is rolled".format(
                        checkValue
                    )
                    outputStrPart2 += choosestring(
                        full_string, "if roll>{}".format(checkValue)
                    )
                    moreMode = True
                    current_expression[position + 3].enabled = False
                    current_expression[position + 4].enabled = False

                if comp3 == "<":
                    full_string = " if a amount less than {} is rolled".format(
                        checkValue
                    )
                    outputStrPart2 += choosestring(
                        full_string, "if roll<{}".format(checkValue)
                    )
                    lessMode = True
                    current_expression[position + 3].enabled = False
                    current_expression[position + 4].enabled = False
                    checkValue = comp4
                if comp3 == "≥":
                    moreMode = True
                    equals = True
                    full_string = (
                        " if a amount greater than or equal to {} is rolled".format(
                            checkValue
                        )
                    )
                    outputStrPart2 += choosestring(
                        full_string, "if roll≥{}".format(checkValue)
                    )
                    current_expression[position + 3].enabled = False
                    current_expression[position + 4].enabled = False
                    checkValue = comp4
                if comp3 == "≤":
                    lessMode = True
                    equals = True
                    full_string = (
                        " if a amount less than or equal to {} is rolled".format(
                            checkValue
                        )
                    )
                    outputStrPart2 += choosestring(
                        full_string, "if roll≤{}".format(checkValue)
                    )
                    current_expression[position + 3].enabled = False
                    current_expression[position + 4].enabled = False

            rolling = []
            outputStrPart2Format = ""
            if outputStrPart2:
                outputStrPart2Format = "(" + outputStrPart2 + ")"

            if int(dice_sides) <= 0:
                outputFunc.outFunc(
                    "...You can't roll a {} sided dice!".format(str(dice_sides))
                )
                raise Exception
            outputStr = ":game_die:Roll {}d{} {}:".format(
                str(dice_amount), str(dice_sides), outputStrPart2Format
            )

            printList(current_expression, spartA, spartB, outputFunc)
            outputFunc.outFunc(outputStr, verb=1, mode="full", isop=True)
            outValue = ""
            displayValue = ""
            totalValues = dice_amount
            if totalValues > 100:
                outputFunc.outFunc(totalValues, " way too high.  Throwing Exception.")
                raise Exception
            for x in range(dice_amount):
                maxvalue = dice_sides
                terminationCount = 0
                rollvalue = randint(1, maxvalue)
                actuallyRan = False
                sumV = rollvalue

                rerollValue = maxvalue
                if lessMode:
                    rerollValue = checkValue
                elif moreMode:
                    rerollValue = checkValue
                outValue += ":game_die:{}".format(rollvalue)
                displayvalue = ""
                displayvalue += ":game_die:{}".format(rollvalue)
                if not compoundMode and not rerollMode:
                    rolling.append(rollvalue)

                if explodeMode:  # EXPLODING dice
                    boolean = compareValue(
                        rollvalue, rerollValue, lessMode, moreMode, equals
                    )
                    if not lessMode and not moreMode:
                        boolean = rollvalue == maxvalue
                    while boolean and terminationCount <= 100000:
                        terminationCount = terminationCount + 1
                        actuallyRan = True
                        rollvalue = randint(1, maxvalue)

                        if compoundMode:
                            sumV += rollvalue
                            full = " which can compound adding {} ".format(rollvalue)
                            short = "+:cmp:{} ".format(rollvalue)

                            todisplay = choosestring(full, short)
                            outValue += todisplay
                            displayvalue += short
                            if printMode:
                                outputFunc.outFunc(
                                    "Compounding, adding ",
                                    rollvalue,
                                    ". new value is",
                                    sumV,
                                )
                        else:
                            full = " which exploded, adding {}".format(rollvalue)
                            short = ":boom:{}".format(rollvalue)
                            todisplay = choosestring(full, short)
                            outValue += todisplay
                            displayvalue += short
                            rolling.append(rollvalue)
                        boolean = compareValue(
                            rollvalue, rerollValue, lessMode, moreMode, equals
                        )
                    if compoundMode and actuallyRan:
                        full = " leaving a final value of {}".format(sumV)
                        short = "={}".format(sumV)
                        todisplay = choosestring(full, short)
                        outValue += todisplay
                        displayvalue = ":game_die:{}".format(sumV)
                        actuallyRan = False
                    elif actuallyRan:
                        actuallyRan = False
                        # outValue+=", which does not explode"
                if rerollMode:
                    boolean = False
                    boolean = compareValue(
                        rollvalue, rerollValue, lessMode, moreMode, equals
                    )
                    if lessMode:
                        if boolean:
                            full = ", which is less than {}".format(rerollValue)
                            short = "(<{})".format(rerollValue)
                            todisplay = choosestring(full, short)
                            outValue += todisplay
                    else:
                        if boolean:
                            full = ", which is greater than {}".format(rerollValue)
                            short = "(>{})".format(rerollValue)
                            todisplay = choosestring(full, short)
                            outValue += todisplay

                    while boolean and terminationCount <= 100000:
                        terminationCount = terminationCount + 1
                        rollvalue = randint(1, maxvalue)
                        full = ", rerolling for {} ".format(rollvalue)
                        short = ", reroll->{} ".format(rollvalue)
                        todisplay = choosestring(full, short)
                        outValue += todisplay

                        boolean = compareValue(
                            rollvalue, rerollValue, lessMode, moreMode, equals
                        )
                        if lessMode:
                            #  boolean=rollvalue<rerollValue
                            if boolean:
                                full = ", which is less than {}".format(rerollValue)
                                short = "(<{})".format(rerollValue)
                                todisplay = choosestring(full, short)
                                outValue += todisplay
                        else:
                            #   boolean=rollvalue>rerollValue

                            if boolean:
                                #        outputFunc.outFunc("GREATER")
                                full = ", which is greater than {}".format(rerollValue)
                                short = "(>{})".format(rerollValue)
                                todisplay = choosestring(full, short)
                                outValue += todisplay
                    rolling.append(rollvalue)
                    displayvalue = ":game_die: {}".format(rollvalue)
                if compoundMode:
                    rolling.append(sumV)
                if x < dice_amount - 1:
                    outValue += ", "
                    displayvalue += ", "
                if x == dice_amount - 2:
                    outValue += choosestring("and", "")
                    displayvalue += ""
                if x < dice_amount - 1:
                    outValue += ""
                    if compoundMode or rerollMode:
                        outValue += ""
                if terminationCount >= 99999:
                    outputFunc.outFunc(
                        "failure limit reached.  Terminating for sake of sanity."
                    )
                    raise Exception
                displayValue += displayvalue

            i.answered = True
            output_type = DatabitType.SEQUENCE  # the default is sequence.
            output_data = rolling  # the data
            if dice_amount == 1:
                output_type = DatabitType.NUMBER
                output_data = rolling[0]  # the data
            display = "" + displayValue + ""
            i.answer = DataBit(output_type, output_data, display, fromdie=True)

            printList(current_expression, spartA, spartB, outputFunc)

            outputFunc.outFunc(outValue + ".", verb=1, mode="full")
            outputFunc.outFunc(outputStr + "," + outValue + ".", verb=1, mode="short")
            rollshorts.append(outputStr + "," + outValue + ".")
            didrun = True
        else:
            nextroll = nextroll + 1

        position += 1
    outputFunc.outFunc("DEBUG STATEMENT", verb=7)
    # Mark and make new list.
    current_expression = redo_current_expression_with_evaluated(
        current_expression, opDone, spartA, spartB, outputFunc
    )
    if didrun:
        if outputFunc.mode == "short":
            printOp(current_expression, spartA, spartB, outputFunc, verbop=1)
    return current_expression, didrun


def drop_and_keep(
    current_expression: List[DataBit], spartA: str, spartB: str, outputFunc
):
    opDone = False
    nextroll = 0
    rall = [1]
    position = 0
    positions = [[]]
    didrun = False
    for i in current_expression:
        if i.value == "δ":
            preformed_printworthy_op = True
            opDone = True
            current_expression[position - 1].enabled = False
            current_expression[position].enabled = False
            current_expression[position + 1].enabled = False
            rolling = current_expression[position - 1]
            dropNum = current_expression[position + 1]
            outputStr = "Dropping {} low values from {}.".format(
                str(dropNum), str(rolling)
            )
            outputFunc.outFunc(outputStr, verb=1, isop=True)
            i.answered = True
            didrun = True
            i.answer = rolling.drop(int(dropNum.value))

        if i.value == "κ":
            preformed_printworthy_op = True
            opDone = True
            current_expression[position - 1].enabled = False
            current_expression[position].enabled = False
            current_expression[position + 1].enabled = False
            rolling = current_expression[position - 1]
            dropNum = current_expression[position + 1].value
            outputStr = "Keeping {} high values from {}.".format(
                str(dropNum), str(rolling)
            )
            outputFunc.outFunc(outputStr, verb=1, isop=True)

            i.answer = rolling.keep(int(dropNum))
            i.answered = True
            didrun = True
        else:
            nextroll = nextroll + 1
            rall.append(0)
            positions.append([])
        position += 1
    # Mark and make new list.
    current_expression = redo_current_expression_with_evaluated(
        current_expression, opDone, spartA, spartB, outputFunc
    )
    return current_expression, didrun


def sequence_sum(current_expression, spartA, spartB, outputFunc):
    opDone = False
    preformed_printworthy_op = False
    position = 0
    for i in current_expression:
        if i.value == "Σ":
            preformed_printworthy_op = True
            opDone = True
            current_expression[position].enabled = False
            current_expression[position + 1].enabled = False
            operatingon = current_expression[position + 1]

            outputStr = f"Preparing sum of {str(operatingon)} "
            outputFunc.outFunc(outputStr, verb=4, isop=True)

            if current_expression[position + 1].type == DatabitType.SEQUENCE:
                val = current_expression[position + 1].value
                newValue = 0
                pos = 0

                for iv in val:
                    newValue = newValue + (iv)
                    pos += 1
                    stringValue = "" + (str(newValue)) + "+" + str(val[pos:])
                    # outputFunc.outFunc(stringValue, spartA, spartB, verb=2)
            i.answered = True
            sum = operatingon.getSum()
            outputStr = f"Sum of {operatingon}: **{sum}** "
            outputFunc.outFunc(outputStr, verb=2, isop=True)
            i.answer = sum
        position += 1
    # Mark and make new list.
    current_expression = redo_current_expression_with_evaluated(
        current_expression, opDone, spartA, spartB, outputFunc
    )
    outputFunc.outFunc("DEBUG STATEMENT 2", verb=7)
    if preformed_printworthy_op:
        printOp(current_expression, spartA, spartB, outputFunc, verbop=2)
    return current_expression, preformed_printworthy_op


def sequence_avg(current_expression, spartA, spartB, outputFunc):
    opDone = False
    preformed_printworthy_op = False
    position = 0
    for i in current_expression:
        if i.value == "℘":
            preformed_printworthy_op = True
            opDone = True
            current_expression[position].enabled = False
            current_expression[position + 1].enabled = False
            operatingon = current_expression[position + 1]
            outputStr = f"Preparing average of{str(operatingon)} "
            outputFunc.outFunc(outputStr, verb=4, isop=True)
            if current_expression[position + 1].type == DatabitType.SEQUENCE:
                val = current_expression[position + 1].value
                newValue = 0
                pos = 0

                for iv in val:
                    newValue = newValue + (iv)
                    pos += 1
                    stringValue = "" + (str(newValue)) + "+" + str(val[pos:])
            i.answered = True
            sum = operatingon.getSum()
            length = operatingon.getLength()
            avg = operatingon.average()
            outputStr = f"Average of {operatingon}: *{sum}/{length}*=**{avg} "
            outputFunc.outFunc(outputStr, verb=2, isop=True)
            i.answer = avg
        position += 1
    # Mark and make new list.
    current_expression = redo_current_expression_with_evaluated(
        current_expression, opDone, spartA, spartB, outputFunc
    )
    if preformed_printworthy_op:
        printOp(current_expression, spartA, spartB, outputFunc, verbop=2)
    return current_expression, preformed_printworthy_op


def exponent_math(current_expression, spartA, spartB, outputFunc):
    preformed_printworthy_op = False
    contin = True
    while contin:
        contin = False
        opDone = False
        position = 0
        prev = None
        for iv in current_expression:
            i = iv.value
            if i == "^" and contin == False:
                preformed_printworthy_op = True
                opDone = True
                contin = True
                current_expression[position - 1].enabled = False
                current_expression[position].enabled = False
                current_expression[position + 1].enabled = False

                valA = current_expression[position - 1]
                valB = current_expression[position + 1]

                newVal = valA**valB
                outputStr = f"{valA}^{valB}=**{newVal}"
                outputFunc.outFunc(outputStr, verb=2, isop=True)
                iv.answered = True
                iv.answer = newVal
            position += 1
        # Mark and make new list.
        current_expression = redo_current_expression_with_evaluated(
            current_expression, opDone, spartA, spartB, outputFunc
        )
    return current_expression, preformed_printworthy_op


def factorial_math(current_expression, spartA, spartB, outputFunc):
    preformed_printworthy_op = False
    contin = True
    while contin:
        contin = False
        opDone = False
        nextmult = 0
        position = 0

        prev = None
        for iv in current_expression:
            i = iv.value
            if i == "!" and contin == False:
                preformed_printworthy_op = True
                opDone = True
                contin = True
                current_expression[position - 1].enabled = False
                current_expression[position].enabled = False

                valA = current_expression[position - 1]
                outputFunc.outFunc("DEBUG STATEMENT 4", verb=7)
                newVal = valA.factorial()

                outputStr = f"{valA}!=**{newVal}"
                outputFunc.outFunc(outputStr, verb=2, isop=True)
                outputFunc.outFunc(newVal, verb=7)
                iv.answered = True
                iv.answer = newVal

            else:
                nextmult = nextmult + 1

            position += 1
        # Mark and make new list.
        outputFunc.outFunc("DEBUG STATEMENT 5", verb=7)
        current_expression = redo_current_expression_with_evaluated(
            current_expression, opDone, spartA, spartB, outputFunc
        )
    return current_expression, preformed_printworthy_op


def multiplication_math(current_expression, spartA, spartB, outputFunc):
    preformed_printworthy_op = False
    contin = True
    while contin:
        contin = False
        opDone = False
        nextmult = 0
        position = 0

        prev = None
        for iv in current_expression:
            i = iv.value
            if i == "*" and contin == False:
                preformed_printworthy_op = True
                opDone = True
                contin = True
                current_expression[position - 1].enabled = False
                current_expression[position].enabled = False
                current_expression[position + 1].enabled = False
                # dprint(current_expression)
                valA = current_expression[position - 1]
                valB = current_expression[position + 1]
                # dprint(valA)
                # dprint(valB)
                newVal = valA * valB
                outputStr = f"{valA}✱{valB}=**{newVal}**"
                outputFunc.outFunc(outputStr, verb=3, isop=True)
                iv.answered = True
                iv.answer = newVal

            else:
                nextmult = nextmult + 1

            position += 1
        # Mark and make new list.
        current_expression = redo_current_expression_with_evaluated(
            current_expression, opDone, spartA, spartB, outputFunc
        )
    return current_expression, preformed_printworthy_op


def division_math(current_expression, spartA, spartB, outputFunc):
    preformed_printworthy_op = False
    contin = True
    while contin:
        contin = False
        opDone = False
        nextmult = 0
        position = 0

        prev = None
        for iv in current_expression:
            i = iv.value
            if i == "/" and contin == False:
                preformed_printworthy_op = True
                opDone = True
                contin = True
                current_expression[position - 1].enabled = False
                current_expression[position].enabled = False
                current_expression[position + 1].enabled = False

                valA = current_expression[position - 1]
                valB = current_expression[position + 1]
                newVal = valA / valB
                outputStr = f"{valA}/{valB}=**{newVal}**"
                outputFunc.outFunc(outputStr, verb=3, isop=True)
                iv.answered = True
                iv.answer = newVal
            else:
                nextmult = nextmult + 1
            position += 1
        # Mark and make new list.
        current_expression = redo_current_expression_with_evaluated(
            current_expression, opDone, spartA, spartB, outputFunc
        )
    return current_expression, preformed_printworthy_op


def DirectSum_math(current_expression, spartA, spartB, outputFunc):
    """Direct sum adds an number to every element in a sequence."""
    preformed_printworthy_op = False
    contin = True
    while contin:
        contin = False
        opDone = False
        nextmult = 0

        position = 0

        prev = None
        for iv in current_expression:
            i = iv.value
            if i == "⊕" and contin == False:
                preformed_printworthy_op = True
                opDone = True
                contin = True
                current_expression[position - 1].enabled = False
                current_expression[position].enabled = False
                current_expression[position + 1].enabled = False

                valA = current_expression[position - 1]
                valB = current_expression[position + 1]
                newVal = valA.directSum(valB)
                outputStr = f"Adding {valB} to every number in {valA}=**{newVal}**"
                outputFunc.outFunc(outputStr, verb=3, isop=True)
                iv.answered = True
                iv.answer = newVal
            else:
                nextmult = nextmult + 1

            position += 1
        # Mark and make new list.

        current_expression = redo_current_expression_with_evaluated(
            current_expression, opDone, spartA, spartB, outputFunc
        )
    return current_expression, preformed_printworthy_op


def addition_math(current_expression, spartA, spartB, outputFunc):
    preformed_printworthy_op = False
    contin = True
    while contin:
        contin = False
        opDone = False
        position = 0
        prev = None
        for iv in current_expression:
            i = iv.value
            if i == "+" and contin == False:
                preformed_printworthy_op = True
                opDone = True
                contin = True

                current_expression[position - 1].enabled = False
                current_expression[position].enabled = False
                current_expression[position + 1].enabled = False

                valB = current_expression[position + 1]
                valA = current_expression[position - 1]
                if (position - 1) < 0:
                    valA = DataBit(DatabitType.NUMBER, 0.0)

                newVal = valA + valB
                outputStr = f"{valA}+{valB}=**{newVal}**"
                outputFunc.outFunc(outputStr, verb=3, isop=True)
                iv.answered = True
                iv.answer = newVal
            position += 1
        # Mark and make new list.
        current_expression = redo_current_expression_with_evaluated(
            current_expression, opDone, spartA, spartB, outputFunc
        )
    #      current_expression=redo_current_expression_with_evaluated(current_expression, opDone, spartA, spartB)D
    return current_expression, preformed_printworthy_op


def subtraction_math(current_expression, spartA, spartB, outputFunc):
    preformed_printworthy_op = False
    contin = True
    while contin:
        contin = False
        opDone = False
        position = 0
        prev = None
        for iv in current_expression:
            i = iv.value
            if i == "-" and contin == False:
                preformed_printworthy_op = True
                opDone = True
                contin = True

                current_expression[position - 1].enabled = False
                current_expression[position].enabled = False
                current_expression[position + 1].enabled = False

                valB = current_expression[position + 1]
                valA = current_expression[position - 1]
                if (position - 1) < 0:
                    valA = DataBit(DatabitType.NUMBER, 0.0)

                newVal = valA - valB
                outputStr = f"{valA}-{valB}=**{newVal}**"
                outputFunc.outFunc(outputStr, verb=3, isop=True)
                iv.answered = True
                iv.answer = newVal
            position += 1
        # Mark and make new list.
        current_expression = redo_current_expression_with_evaluated(
            current_expression, opDone, spartA, spartB, outputFunc
        )
    #      current_expression=redo_current_expression_with_evaluated(current_expression, opDone, spartA, spartB)
    return current_expression, preformed_printworthy_op


def parse_and_calculate_string(
    strings: str, spartA: str, spartB: str, outputFunc=defaultOutput
):
    # Calculates based on String
    """Preform math operations on string"""
    # make single character replacements.
    # Minus a negative equals positive.
    # I really need to redo this part.
    dprint("Start of STR to Cal", strings)
    preformed_printworthy_op = False
    current_expression = preprocess_string(strings)
    printList(current_expression, spartA, spartB, outputFunc)
    dprint("CURRENT_EXPRESSION", current_expression)
    # DICE ROLLING.  Checks for exploding dice
    current_expression, didNewThing = dice_roll_op(
        current_expression, spartA, spartB, outputFunc
    )

    # DropAndKeep
    # δ
    # κ
    current_expression, didNewThing = drop_and_keep(
        current_expression, spartA, spartB, outputFunc
    )

    # Sum Values in Sequence
    # Σ[1,2,...,n]
    current_expression, didNewThing = sequence_sum(
        current_expression, spartA, spartB, outputFunc
    )
    preformed_printworthy_op = preformed_printworthy_op or didNewThing
    # Average of values in sequence
    # ℘[1,2,...,n]
    current_expression, didNewThing = sequence_avg(
        current_expression, spartA, spartB, outputFunc
    )
    preformed_printworthy_op = preformed_printworthy_op or didNewThing
    # Exponentiation operation
    current_expression, didNewThing = exponent_math(
        current_expression, spartA, spartB, outputFunc
    )
    preformed_printworthy_op = preformed_printworthy_op or didNewThing
    outputFunc.outFunc("DEBUG STATEMENT 3", verb=7)

    # Factorial Operation
    current_expression, didNewThing = factorial_math(
        current_expression, spartA, spartB, outputFunc
    )
    preformed_printworthy_op = preformed_printworthy_op or didNewThing

    # Multiplication
    current_expression, didNewThing = multiplication_math(
        current_expression, spartA, spartB, outputFunc
    )
    preformed_printworthy_op = preformed_printworthy_op or didNewThing
    # New Division
    current_expression, didNewThing = division_math(
        current_expression, spartA, spartB, outputFunc
    )
    preformed_printworthy_op = preformed_printworthy_op or didNewThing
    # DirectSum, o(n)
    current_expression, didNewThing = DirectSum_math(
        current_expression, spartA, spartB, outputFunc
    )
    preformed_printworthy_op = preformed_printworthy_op or didNewThing

    # Addition- Will Repeat if it does a op.
    # O(n)
    current_expression, didNewThing = addition_math(
        current_expression, spartA, spartB, outputFunc
    )
    preformed_printworthy_op = preformed_printworthy_op or didNewThing

    # Subtraction.
    current_expression, didNewThing = subtraction_math(
        current_expression, spartA, spartB, outputFunc
    )
    preformed_printworthy_op = preformed_printworthy_op or didNewThing

    if preformed_printworthy_op:
        printOp(current_expression, spartA, spartB, outputFunc, verbop=4)
    preformed_printworthy_op = preformed_printworthy_op
    position = 0
    printR = None
    opDone = False
    for i in current_expression:
        # outputFunc.outFunc("current_expression",current_expression, " i:", i)
        if i.value == ">":
            preformed_printworthy_op = True
            opDone = True
            valA = current_expression[position - 1]
            valB = current_expression[position + 1]
            printR = valA > valB
        #    outputFunc.outFunc("result",printR)
        elif i.value == "<":
            preformed_printworthy_op = True
            opDone = True
            valA = current_expression[position - 1]
            valB = current_expression[position + 1]
            printR = valA < valB
        #    outputFunc.outFunc("result",printR)
        elif i.value == "≤":
            preformed_printworthy_op = True
            opDone = True
            valA = current_expression[position - 1]
            valB = current_expression[position + 1]
            printR = valA <= valB
        #    outputFunc.outFunc("result",printR)
        elif i.value == "≥":
            preformed_printworthy_op = True
            opDone = True
            valA = current_expression[position - 1]
            valB = current_expression[position + 1]
            printR = valA >= valB
        elif i.value == "⊜":
            preformed_printworthy_op = True
            opDone = True
            valA = current_expression[position - 1]
            valB = current_expression[position + 1]
            printR = valA == valB
        #        outputFunc.outFunc("result",printR)
        if printR == True or printR == False:
            # outputFunc.outFunc(position, len(current_expression))

            if printR:
                outputFunc.outFunc("Success.", verb=1)
                i.answered = True
                i.answer = DataBit(DatabitType.BOOLEAN, True)
                current_expression[position - 1].enabled = False
                current_expression[position].enabled = False
                current_expression[position + 1].enabled = False
            else:
                outputFunc.outFunc("Failure.", verb=1)
                i.answered = True
                i.answer = DataBit(DatabitType.BOOLEAN, False)
                current_expression[position - 1].enabled = False
                current_expression[position].enabled = False
                current_expression[position + 1].enabled = False
            printR = None

        elif printR != None:
            true, val = printR
            outputFunc.outFunc("Was successful:" + str(true), verb=1)
            outputFunc.outFunc("Number of successes: " + str(val), verb=1)
            current_expression[position - 1].enabled = False
            current_expression[position].enabled = False
            current_expression[position + 1].enabled = False
            i.answered = True
            i.answer = val
            printR = None
        position += 1
    current_expression = redo_current_expression_with_evaluated(
        current_expression, opDone, spartA, spartB, outputFunc
    )
    resString = toExpressionString(current_expression[0])

    resString = resString.replace("\u2212", "-")  # Replace negative with minus

    return resString, preformed_printworthy_op
