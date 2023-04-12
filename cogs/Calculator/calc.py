from typing import List


from random import randint, seed

from .c_util import *

from .calc_elements import DataBit, substitutions
from .calc_nested import parse_and_calculate_string




expressDictionary={
    "ATestValue":"((num1)+((5d8reroll<3)+(8d8keep4)+sum(2d4)+(4+(3*(10-2*3+4+5-4*4+4[1,2,3]):+2))+8d8!>=5))",
}


#Here is code that turns nested parenthesis expressions into a specialized
#expression tree.  
class ExpressionTreeNode:
    #A node of the expression tree.
    def __init__(self, value):
        self.value = value
        self.children = []
        self.eval=""

    def add_child(self, child_node):
        #add a child to the tree, and ensure it has something in
        #The value of the node.
        e=self.childnum()
        self.value += f'<child_no_{e}>'
        self.children.append(child_node)

    def childnum(self):
        return len(self.children)
    def get_bounds(self,spl,depth=0):
        ve=str(self)
        print(depth,ve)
        splitup=ve.split(spl)
        sa,sb="",""
        if len(splitup)>0:sa=splitup[0]
        if len(splitup)>1:sb=splitup[1]
        return sa,sb
    def parse_children(self,root,outputFunc, depth=0):
        if self.childnum()<=0:
            sa,sb=root.get_bounds(self.value,depth)
            newstring, preformed_printworthy_op = parse_and_calculate_string(self.value, sa, sb, outputFunc)
            self.eval=newstring
            return newstring
        val=self.value
        for e, i in enumerate(self.children):
            newval=i.parse_children(root,outputFunc,depth=depth+1)
            val=val.replace(f"<child_no_{e}>",newval)
        sa,sb=root.get_bounds(val,depth)
        newstring, preformed_printworthy_op = parse_and_calculate_string(val, sa, sb, outputFunc)
        self.eval=newstring
        return newstring
    
    def __eq__(self, other):
        return str(self)==str(other)
    
    def __repr__(self):
        #return representation of self and children.
        di=f"v:{self.value}, "
        chi=[]
        val=self.value
        if self.eval:
            return self.eval
        for e, i in enumerate(self.children):
            newval=f"({str(i)})"
            if i.eval:
                newval=str(i)
            val=val.replace(f"<child_no_{e}>",newval)

        return val
    

def parse_expression(expression):
    # Turn a nested parenthesis expression into an expression tree.
    # Add multiplication symbols between numbers and parentheses with no operator between them.
    root = ExpressionTreeNode('')
    stack = [root]
    pcal_count = 0
    lastchar=None
    for i, char in enumerate(expression):
        if char == '(':
            # If the previous character was a number, insert a multiplication symbol.
            if i > 0 and expression[i-1].isdigit():
                stack[-1].value += '*'
            if i > 0 and expression[i-1]==")":
                stack[-1].value += '*'
            new_node = ExpressionTreeNode('')
            stack[-1].add_child(new_node)

            stack.append(new_node)
            pcal_count += 1

        elif char == ')':
            stack.pop()
            pcal_count-=1
            # If the next character is a number, insert a multiplication symbol.
            if i < len(expression)-1 and expression[i+1].isdigit():
                stack[-1].value += '*'

        else:
            stack[-1].value += char
        lastchar=char
    if pcal_count>0:
        raise Exception(f"{pcal_count} Unmatched parenthesis.")
    return root

def evaluate_expression(expr: str, *args, outputFunc):
    """
    Evaluate the given expression by parsing it and replacing variables with their corresponding values.

    Parameters:
    expr (str): A string representing the expression to be evaluated.
    args: A tuple containing the values of variables used in the expression.
    outputFunc: A function object that is used to output the evaluated result.

    Returns:
    str: A string representing the evaluated result.
    """
    # Replace expression strings with their corresponding values from the dictionary.
    stri = expr
    replaces = False
    for i, v in expressDictionary.items():
        if i in stri:
            replaces = True
        stri = stri.replace(i, v)

    # Replace variable names with their corresponding values.
    count = 1
    numDictionary = {}
    for i in args:
        numDictionary[f"num{count}"] = str(i)
        count += 1
    for i, v in numDictionary.items():
        if i in stri:
            replaces = True
        stri = stri.replace(i, v)

    # Output the parsed expression if it has been modified.
    if replaces:
        outputFunc.outFunc(stri, verb=-1)
    stri=f"({stri})"

    # Check if all parenthesis expressions have matching pairs.
    #boolA, boolB = check_parentheses(stri)
    node=parse_expression(stri)
    result=node.parse_children(node,outputFunc)

    print(result)
    final_result = str(result)
    outputFunc.outFunc(final_result, verb=0)

    return final_result

    
class OutContainer():
    '''container for output function.'''
    def __init__(self, verb=0,sayop=False,mode="short", showverb=False,debug=False):
        self.out=""
        self.verb=verb
        self.showverb=showverb
        self.debugmode=debug
        self.sayop=sayop
        self.mode="short"
    def setverb(self,verbmode):
        self.showverb=verbmode
    def set(self,verbmode):
        self.showverb=verbmode
    def formatStr(self, stre=""):
        stre=stre.replace("\u2212","-")
        return stre
    def formatStrField(self, stre=""):
        stre=stre.replace("\u2212","-")
        stre=stre.replace("*","⋅")
        return stre
    def outFunc(self, *args, verb=0,mode="all", isop=False):
        if isop==True:
            if not self.sayop:
                return
        if verb<=self.verb and (mode=="all" or self.mode==mode):
            stre=""
            first=True
            for x in args:
                if not first:
                    stre+=","
                stre+=str(x)
                first=False
            stre=stre.replace("\u2212","-")
         #   stre=stre.replace("*","∗")
            stre=stre
            if verb>0:
               stre="> "+stre
            toput=stre
            if self.showverb:
                toput=f"\t[v:{verb}]:\t {stre}"

            if (self.debugmode):
                nesteddeb=get_linenumber_rec()
                toput=(f"{toput}\t;\t{nesteddeb};")
                #toput=toput+str(get_linenumber())+"\n"
            self.out+=toput+"\n"
