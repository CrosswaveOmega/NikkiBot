import gui
from typing import List
import discord


# import datetime
from datetime import datetime, timedelta
import io
from queue import Queue
from discord.ext import commands, tasks
from discord.utils import find
from discord import Webhook

import random
import operator
from random import randint, seed

import traceback
from bot import TC_Cog_Mixin
from discord import app_commands
from discord.app_commands import Choice

from .StepCalculator import evaluate_expression, OutContainer, dprint, get_linenumber


class CalculatorCog(commands.Cog, TC_Cog_Mixin):
    """A experimental calculator that parses string expressions."""

    def __init__(self, bot):
        self.helptext = (
            "special set of commands used for calculating numbers and rolling dice."
        )
        self.verb = 2
        self.verbshow = False
        self.debugmode = False
        self.bot = bot

    @commands.command(aliases=["setverb"])
    async def changeverb(self, ctx, newverb: int = 0):
        """Change the verbocity of the command output"""
        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel

        self.verb = int(newverb)
        await channel.send("set new verb {}".format(self.verb))

    @commands.command(pass_context=True)
    async def showverb(self, ctx, newshowverb: bool = False):
        """Configure if you want to view the verb integer each output line has."""
        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel

        self.verbshow = newshowverb
        await channel.send("set new show verb {}".format(self.verbshow))

    @commands.command(pass_context=True)
    async def setddebug(self, ctx, debugmode: bool = False):
        """Enable/disable debug mode"""
        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel

        self.debugmode = debugmode
        await channel.send("set new debug {}".format(self.debugmode))

    @commands.command(pass_context=True, aliases=["reseeddice"])
    async def reseed(self, ctx):
        """reseed rng."""
        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel

        seed()

        await channel.send("reseeded RNG")

    @commands.command(aliases=["select"])
    async def choose(self, ctx, *args):
        """
        syntax: choose [0] [1] ... [n]
        Select one passed in argument.

        """

        channel = ctx.message.channel

        if len(args) >= 1:
            listValue = list(args)
            choice = random.choice(listValue)
            embe = discord.Embed(
                title="Selected Value", description="I choose {}.".format(choice)
            )
            await ctx.send(embed=embe)
        else:
            await ctx.send("Not enough parameters")

    @app_commands.command(name="calculatorhelp")
    async def helper_calc(self, interaction: discord.Interaction):
        """get help for the calculator function."""
        gui.gprint("OK.")
        helpsS = """Calc is a powerful command, so it requires some knowhow to use to it's fullest.
                 Example expression:
        `"((50)+((5d8reroll<3)+(8d8keep4)+sum(2d4)+(4+(3*(10-2*3+4+5-4*4+4[1,2,3]):+2))+8d8!>=5))"`
        
        It operates using both numbers(whole and decimal), and sequences of numbers.
        data types: 
        **Number:** `A single number, can be positive or negative.`
        **Sequence:** `A list of numbers.  contained within [] and separated by ,`
        **Operator:** `Characters/Words that indicate operations to be preformed on numbers or sequences.`
        
        THE CALCULATOR WILL ALWAYS EVALUATE THE EXPRESSIONS WITHIN PARENTHESIS FIRST.

        """
        helpsA = """Operator syntax:       `[NumberOfDice]d[Sides][Option]`
            
Returns: **sequence** of the values recieved from the dice operation.  
If you need the sum of values, use the `sum` operator afterwards! 

**Dice Rolling Options**
This operation is based on the in depth dice rolling from the online tabletop RPG simulator roll20, so as such it has some additional options in exploding, compounding, and rerolling dice.

`!` is the regular exploding operation. Add another roll to the sequence if the target value is rolled.
`!!` is for compounding exploding dice. Add another roll's value to the previous dice roll if the target value is rolled.
`reroll` after dice expression to reroll if the target value is rolled.

By default, the target value is the highest value on the dice, can be changed with comparator.
Valid Comparators: `(>,<,>=,<=)`

example: `2d4!<=2` will explode if the rolled value is less than or equal to 2.
  
example: (2d20reroll>10) will reroll any dice that has a value greater than 10."""
        helpsB = """**Keep/Drop**
    Syntax: `[Sequence]keep[number to keep], [Sequence]drop[number to drop]`

    Will keep the highest values of [number to keep], or drop the lowest values of [number to drop] in the previous sequence.
**Sum:**
    Format: `sum[sequence]`
    -Sums up all values in sequence as a number

**Average:**
    Format: `avg[sequence]`
    -Returns average of sequence as a number
"""

        helpsC = """**Exponent:**
    Format: `[number or sequence]^[number]`
    -returns [number or sequence] to the power of [number]

**Multiplication:**
    Format: `[number or sequence]*[number]`
    -returns [number or sequence] times [number].

**Division:**
    Format: `[number or sequence]/[number]`
    -returns [number or sequence] divided by [number].

**Direct Sum:**
    Format: `[sequence] :+ [number]`
    -adds number to every value within sequence.

**Addition/Subtraction:**
    Format: `[sequence or number] +/- [sequence or number]`
    If it's adding/subtracting a number and number, returns the total of the numbers.
    If it's adding/subtracting a number to a sequence, appends the number to the sequence.
    If it's adding/subtracting a sequence to a sequence, merges the two sequences together.
"""
        emb = discord.Embed(title="Calculator Help", description=helpsS)
        emb.add_field(name="Dice Rolling.", value=helpsA, inline=False)
        emb.add_field(name="Sequence Operations", value=helpsB, inline=False)
        emb.add_field(name="Common Operators", value=helpsC, inline=False)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @commands.hybrid_command(name="roll")
    async def calculateroll(self, ctx: commands.Context, expression: str):
        """
        ex: /roll 2+1d20 A powerful command that does dice rolls and basic math.
        syntax:
        `/roll "Expression"
        examples: "4+1d20" "(34*34)/(34^2)"
        use /calculatorhelp to get help!
        (It's an alias for calc.)
        """
        await ctx.invoke(self.bot.get_command("calc"), expression)

    @commands.hybrid_command(
        name="calc", aliases=["rollAdvance", "advanceRoll", "calculate", "eval", "c"]
    )
    async def calculate(self, ctx: commands.Context, expression: str):
        """
        A powerful command that does dice rolls and basic math.
        syntax:
        `>calc "Expression"
        examples: "4+1d20" "(34*34)/(34^2)"
        use /calculatorhelp to get help!
        """
        args = []
        leng = len(args)
        rollv = expression
        newA = []
        if leng >= 1:
            newA = [rollva for rollva in args[0:]]
        f = io.StringIO()
        verb = self.verb
        out = OutContainer(
            verb, sayop=True, showverb=self.verbshow, debug=self.debugmode
        )
        value = ""
        try:
            value = evaluate_expression(rollv, tuple(newA), outputFunc=out)
        except Exception as ex:
            await self.bot.send_error(ex, "Calculation Error")
            value = ex

        cho = out.formatStrField(out.out).split("\n")
        string = ""
        for c in cho:
            if len(string + "`" + c + "` \n") >= (4096 - 20):
                embedv = discord.Embed(
                    title="Result of {}".format(out.formatStr(rollv)),
                    description=string,
                )
                embedv.add_field(name="To be continued...",value='tbc')
                await ctx.send(embed=embedv)
                string = "`" + c + "` \n"
            elif c != "":
                string = string + "" + c + " \n"
        if string != " \n":
            embedv = discord.Embed(
                title="`{}`".format(out.formatStr(rollv)), description=string
            )
            # embedv.set_author(name="Requested by "+auth.name)
            embedv.add_field(name="Result", value=out.formatStrField(str(value)))
            # embedv.set_footer(text="Verbocity Level: {}".format(verb))
            await ctx.send(embed=embedv)


def operateTest(expr, verb=6):
    out = OutContainer(verb)
    rollv = expr
    newA = []

    value = ""
    try:
        value = evaluate_expression(rollv, tuple(newA), outputFunc=out)
    except Exception as ex:
        value = ex
        dprint(traceback.format_exc())
        dprint(str(get_linenumber()))
    cho = out.out.split("\n")
    string = ""
    for i, c in enumerate(cho):
        string = string + f"[{i}]:" + c + " \n"
    gui.gprint("NOW:\n" + string)
    gui.gprint(value)
    return float(value)


if __name__ == "__main__":  # testing
    # operateTest("(((3d4)+(1d8))+(1d20))")
    # operateTest("sum((2d6reroll>2+8d4! )+ 23)")
    # Define the expressions
    expression1 = "(4+5)*(6-2)/(3+2)"
    expression2 = "(1+2+3+4+5+6+7+8+9+10)*(2-1)"
    expression3 = "(10-5)/(2+3)*(8-6)"
    expression4 = "(3+4)*(5-6)/(8-3)"
    toeval = [
        ("6", "(((4 * 9) / (8 + 1)) + ((4 - 10) + (6 + 2)))"),
        ("-10.06349206", "(((8 / 1) / (4 * 9)) - ((5 + 4) / (7 / 8)))"),
        ("148.6", "(((7 + 4) * (5 + 9)) - ((3 / 5) * (1 * 9)))"),
        ("8.727272727", "(((6 + 10) / (5 + 6)) / ((7 / 6) - (4 / 4)))"),
        ("0.010714286", "(((1 / 10) / (8 - 6)) / ((6 + 8) / (3 / 1)))"),
        ("-5.571428571", "(((8 * 2) - (4 * 6)) - ((6 - 8) - (3 / 7)))"),
        ("-28", "(((1 - 6) - (9 * 9)) + ((7 * 7) + (1 * 9)))"),
        ("5824", "(((6 + 8) * (7 + 9)) * ((8 + 4) + (4 + 10)))"),
        ("-7", "(((3 + 4) - (6 - 6)) - ((4 * 2) * (7 / 4)))"),
    ]

    # Define the precalculated answers
    answer1 = 7.2
    answer2 = 55.0
    answer3 = 0.5
    answer4 = -1.4

    # Test the operateTest function
    # assert operateTest(expression1) == answer1
    # assert operateTest(expression2) == answer2
    # assert operateTest(expression3) == answer3
    # assert operateTest(expression4) == answer4
    for a, e in toeval:
        gui.gprint("GO", e, a)
        thisresult = operateTest(e)
        gui.gprint(thisresult, a)
        assert round(thisresult, 4) == round(float(a), 4)
    gui.gprint(operateTest("sum(5d50)"))


async def setup(bot):
    gui.dprint(__name__)
    from .StepCalculator import setup

    await bot.load_extension(setup.__module__)
    await bot.add_cog(CalculatorCog(bot))


async def teardown(bot):
    from .StepCalculator import setup

    await bot.unload_extension(setup.__module__)
    await bot.remove_cog("CalculatorCog")
