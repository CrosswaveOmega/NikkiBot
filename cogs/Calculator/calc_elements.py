from .c_util import *
import math
import re

"""This file defines the operator list, DatabitType, DataBit, 
and functions for transforming a string into a list of DataBits
That can be evaluated.  Done as an experiment a while ago.
"""

operatorList=["+","*","-","℘","`","/","d","^", "[","]",",","Σ","!", "|","κ","δ","τ","τ",  "⊕", "<",">","≤","≥", "⊜"]

from enum import Enum

class DatabitType(Enum):
    NUMBER = 1
    OPERATOR = 2
    SEQUENCE = 3
    BOOLEAN = 4
    INVALID =0
    DETERMINE = 5

def identify_type(inputStr):
    '''guess what DataBit inputStr will be'''
    if inputStr in operatorList:
        if inputStr == "[" or inputStr =="]":
            return DatabitType.SEQUENCE
        return DatabitType.OPERATOR
    if (isNumber(inputStr)):
        return DatabitType.NUMBER
    return DatabitType.INVALID

def substitutions(strings):
    "Substitute certain phrases for unicode values in the string for easier parsing"
    "Then split the list up by operators."
    strings=strings.replace("∗","*")

    strings=strings.replace("!!", "|")
    strings=strings.replace("<", "<")
    strings=strings.replace(">", ">")
    strings=strings.replace("<=", "≤")
    strings=strings.replace(">=", "≥")
    strings=strings.replace("==", "⊜")
    strings=strings.replace("**", "^")
    strings=strings.replace("keep", "κ")
    strings=strings.replace("drop", "δ")
    strings=strings.replace("reroll","τ")
    strings=strings.replace("avg","℘")
    strings=strings.replace("sum","Σ")
    strings=strings.replace(":+", "⊕")
    for c in operatorList:
        strings=strings.replace(c,"_"+c+"_")
    return strings

class DataBit:
    """Class that represents a single element in a expression."""
    def __init__(self, typ=DatabitType.NUMBER, value=0, display=None, fromdie=False):
        if(typ==DatabitType.DETERMINE):
            if(value in operatorList):
                self.type=DatabitType.OPERATOR
                self.value=value
            else:
                self.type=DatabitType.NUMBER
                self.value=toNumber(value)
        else:
            self.type=typ
            if(self.type==DatabitType.NUMBER):
                self.value=toNumber(value)
            else:
                self.value=value
        self.enabled=True #was the databit not used yet in an operation?
        self.answered=False #Was the databit answered?
        self.answer=None #What is the answer?
        self.fromdie=fromdie
        self.display=display


    def sequenceAppend(self, val):
        '''append value to end of sequence'''
        if(self.type==DatabitType.SEQUENCE):
            self.value.append(val)
    def getAverage(self):
        '''Get the average if it's a sequence.  if it's a number, just return the value of said number.'''
        if(self.type==DatabitType.SEQUENCE):
            sum=0
            for i in self.value:
                sum=sum+i
            return sum/len(self.value)
        elif(self.type==DatabitType.NUMBER):
            return self.value
    def average(self):
        avg=self.getAverage()
        return(DataBit(DatabitType.NUMBER,avg))

    def factorial(self):
        if(self.type==DatabitType.SEQUENCE):
            return(DataBit(DatabitType.SEQUENCE), self.value)
        elif(self.type==DatabitType.NUMBER):
            answer=math.factorial(self.value)
            dprint(answer)
            return (DataBit(DatabitType.NUMBER,float(answer)))

    def __add__(self, o):
        '''Addition Operation'''
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            '''For a sequence, it adds a number to the sequence.'''
            newValue=[]
            for i in self.value:
                newValue.append(i)
            if(o.value!=0):
                newValue.append(o.value)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            '''For a sequence, it adds a number to the sequence.'''
            newValue=[]
            for i in o.value:
                newValue.append(i)
            newValue.append(self.value)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            '''For two sequences sequence, it combines two sequences into one.'''
            newValue=[]
            for i in self.value:
                newValue.append(i)
            for i in o.value:
                newValue.append(i)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            return DataBit(DatabitType.NUMBER, self.value+o.value)

    def __sub__(self, o):
        '''Subtraction Operation.  Equivalent to A+(-1*B).'''
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            newValue=[]
            for i in self.value:
                newValue.append(i)
            if(o.value!=0):
                newValue.append(o.value*-1)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            newValue=[]
            newValue.append(self.value)
            for i in o.value:
                newValue.append(i*-1)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            '''For two sequences sequence, it combines two sequences into one.'''
            newValue=[]
            for i in self.value:
                newValue.append(i)
            for i in o.value:
                newValue.append(i*-1)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            return DataBit(DatabitType.NUMBER, self.value-o.value)

    def is_whole(self, other=None):
        if(other!=None):
            return other %1 == 0
        if(self.type==DatabitType.NUMBER):
            return self.value %1 ==0

    def __mul__(self, o):
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            newValue=[]
            for i in self.value:
                newValue.append(i*o.value)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            newValue=[]
            for i in o.value:
                newValue.append(self.value*i)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            newValue=[]
            for i in self.value:
                newValue.append(i)
            for i in o.value:
                newValue.append(i)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            dprint("Class B")
            return DataBit(DatabitType.NUMBER, self.value*o.value)

    def __truediv__(self, o):
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            newValue=[]
            for i in self.value:
                newValue.append(i/o.value)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            newValue=[]
            for i in o.value:
                newValue.append(self.value/i)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            newValue=[]
            for i in self.value:
                newValue.append(i)
            for i in o.value:
                newValue.append(i)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            return DataBit(DatabitType.NUMBER, self.value/o.value)

    def __pow__(self, o):
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            newValue=[]
            sumV=self.getSum()
            for i in self.value:
                newValue.append(i**o.value)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            newValue=[]
            for i in o.value:
                newValue.append(self.value**i)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            newValue=[]
            for i in self.value:
                newValue.append(i)
            for i in o.value:
                newValue.append(i)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            return DataBit(DatabitType.NUMBER, self.value**o.value)

    def __rmul__(self, o):
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            newValue=[]
            for i in self.value:
                newValue.append(i*o.value)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            newValue=[]
            for i in o.value:
                newValue.append(self.value*i)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            newValue=[]
            for i in self.value:
                newValue.append(i)
            for i in o.value:
                newValue.append(i)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            return DataBit(DatabitType.NUMBER, self.value*o.value)

    def getSum(self):
        if(self.type==DatabitType.SEQUENCE):
            return DataBit(DatabitType.NUMBER, sum(self.value))
        return DataBit(DatabitType.NUMBER, self.value)

    def getLength(self):
        if(self.type==DatabitType.SEQUENCE):
            return DataBit(DatabitType.NUMBER, len(self.value))
        return DataBit(DatabitType.NUMBER, 1)
    def directSum(self, o):
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            newValue=[]
            for i in self.value:
                newValue.append(i+o.value)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            newValue=[]
            for i in o.value:
                newValue.append(self.value+i)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            newValue=[]
            for i in self.value:
                 for v in o.value:
                    newValue.append(i+v)
            return(DataBit(DatabitType.SEQUENCE,newValue))
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            return DataBit(DatabitType.NUMBER, self.value+o.value)

    def drop(self, number):
         if(self.type==DatabitType.SEQUENCE):
            dropped=[]
            for count in range(0,number):
                mini=min(self.value)
                dropped.append(mini)
                self.value.remove(mini)
            return DataBit(DatabitType.SEQUENCE, self.value), dropped


    def keep(self, number):
        #Keep X numbers in sequence
        if(self.type==DatabitType.SEQUENCE):
            sequ=[]
            for count in range(0,number):
                mini=max(self.value)
                sequ.append(mini)
                self.value.remove(mini)
            return DataBit(DatabitType.SEQUENCE, sequ)

    def getType(self):
        if(self.type==DatabitType.NUMBER):
            return DatabitType.NUMBER
        if(self.type==DatabitType.OPERATOR):
            return DatabitType.OPERATOR
        if(self.type==DatabitType.SEQUENCE):
            return DatabitType.SEQUENCE
        if(self.type=="boolean"):
            return DatabitType.BOOLEAN

    #FOR COMPARING.  GREATER THAN, LESS THAN, EQUAL TO, GREATER THAN OR EQUAL TO, LESS THAN OR EQUAL TO.
    def __gt__(self, o):
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            okCount=0
            for i in self.value:
               if(i>o.value):
                   okCount+=1
            retVal=okCount>0
            return retVal, okCount
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            okCount=0
            for i in o.value:
               if(i>self.value):
                   okCount+=1
            retVal=okCount>0
            return retVal, okCount
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            newValue=[]
            return self.getAverage()>o.getAverage()
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            return self.value>o.value

    def __ge__(self, o):
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            okCount=0
            for i in self.value:
               if(i>=o.value):
                   okCount+=1
            retVal=okCount>0
            return retVal, okCount
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            okCount=0
            for i in o.value:
               if(i>=self.value):
                   okCount+=1
            retVal=okCount>0
            return retVal, okCount
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            newValue=[]
            return self.getAverage()>=o.getAverage()
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            return self.value>=o.value

    def __lt__(self, o):
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            okCount=0
            for i in self.value:
               if(i<o.value):
                   okCount+=1
            retVal=okCount>0
            return retVal, okCount
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            okCount=0
            for i in o.value:
               if(i<self.value):
                   okCount+=1
            retVal=okCount>0
            return retVal, okCount
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            newValue=[]
            return self.getAverage()<o.getAverage()
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            return self.value<o.value

    def __le__(self, o):
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            okCount=0
            for i in self.value:
               if(i<=o.value):
                   dprint(i<=o.value)
                   okCount+=1
            retVal=okCount>0
            return retVal, okCount
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            okCount=0
            for i in o.value:
               if(i<=self.value):
                   okCount+=1
            retVal=okCount>0
            return retVal, okCount
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            newValue=[]
            return self.getAverage()<=o.getAverage()
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            return self.value<=o.value

    def __eq__(self, o):
        #check if databits are equal.
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.NUMBER):
            okCount=0
            for i in self.value:
               if(i==o.value):
                   dprint(i==o.value)
                   okCount+=1
            retVal=okCount>0
            return retVal, okCount
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.SEQUENCE):
            okCount=0
            for i in o.value:
               if(i==self.value):
                   okCount+=1
            retVal=okCount>0
            return retVal, okCount
        if(self.type==DatabitType.SEQUENCE and o.type==DatabitType.SEQUENCE):
            newValue=[]
            return self.getAverage()==o.getAverage()
        if(self.type==DatabitType.NUMBER and o.type==DatabitType.NUMBER):
            return self.value==o.value

    def single_num_output(self,start):
        val=start
        if self.is_whole(start):
            val=int(start)
        st= str(val)
        if self.fromdie:
            st=f":game_die:{st}"
        return st

    def formatValue(self):
        if(self.type==DatabitType.NUMBER):
            st=self.single_num_output(self.value)
            return st
        if(self.type==DatabitType.SEQUENCE):
            count=0
            outStr="["
            tot=len(self.value)
            for i in range(0,tot):
                outStr+=self.single_num_output(self.value[i])
                if(i<tot-1):
                    outStr+=", "
            outStr+="]"
            return outStr
        else:
            return str(self.value)


    def __str__(self):
        if(self.enabled==False):
            return f"⚛{self.formatValue()}⚛"
        #return self.formatValue()
        return str(self.formatValue())

    def __repr__(self):
        if(self.enabled==False):
            return "⚛"
        return self.formatValue()
       # return str(self.value)

def preprocess_string(strings):
    
    negative_sign_regex = re.compile(r'(?<!\d)-(?=\d)')
    strings = negative_sign_regex.sub('\u2212', strings)
    newString=substitutions(strings)
    
    prenegative_operands= newString.split("_")
    
    
    operands=[]
    length=len(prenegative_operands)
    dashes_to_add=""
    for i in range(0,length):
        thischar=prenegative_operands[i].strip()
        operands.append(thischar)

    dprint("operands",operands)
    sequen=False
    lastStitch=None

    #transform characters into DataBit classes.
    stitched_operands=[]
    for i in operands:
        
        if(i!=""):
            if(i=="["):
                sequen=True
                lastStitch=DataBit(DatabitType.SEQUENCE, [])
            elif(sequen):
                if(i=="]"):
                    sequen=False
                    stitched_operands.append(lastStitch)
                elif(i!=","):
                    lastStitch.sequenceAppend(toNumber(i))
            else:
                stitched_operands.append(DataBit(DatabitType.DETERMINE, i))

    current_expression = []
    pos=0

    for pos,i in enumerate(stitched_operands):
        current_expression.append(i)
        if(i.type==DatabitType.NUMBER):
            if 0 <= pos+1 < len(stitched_operands):
                if(stitched_operands[pos+1].type==DatabitType.SEQUENCE):
                      current_expression.append(DataBit(DatabitType.OPERATOR,"*"))
        elif(i.type==DatabitType.SEQUENCE):
            if 0 <= pos+1 < len(stitched_operands):
                if(stitched_operands[pos+1].type==DatabitType.NUMBER):
                    current_expression.append(DataBit(DatabitType.OPERATOR,"*"))
    return current_expression