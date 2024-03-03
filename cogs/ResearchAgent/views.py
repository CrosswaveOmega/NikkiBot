import discord
from discord import Interaction, PartialEmoji
import gui
from utility import pages_of_embeds_2


class Followup(discord.ui.View):
    """buttons for the audio player."""

    def __init__(self, *, bot=None, timeout=None, page_content=[]):
        super().__init__(timeout=timeout)
        self.my_sources = page_content
        self.bot = bot

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item
    ) -> None:
        gui.gprint(str(error))
        await self.bot.send_error(error, "followuperror")
        # await interaction.response.send_message(f'Oops! Something went wrong: {str(error)}.', ephemeral=True)

    @discord.ui.button(
        emoji="⬅️", label="view sources", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def showsauce(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(title="sauces")
        field_count = 0
        embeds = []
        for id, tup in enumerate(self.my_sources[:10]):
            doc, score = tup
            if field_count == 3:
                # Send the embed here or add it to a list of embeds
                # Reset the field count and create a new embed
                field_count = 0
                embeds.append(embed)
                embed = discord.Embed(title="sauces")

            meta = doc.metadata
            content = doc.page_content

            output = f"""**ID**:{id}
            **Name:** {meta.get('title','TITLE UNAVAILABLE')[:100]}
            **Link:** {meta['source']}
            **Text:** {content}"""
            embed.add_field(name=f"s: score:{score}", value=output[:1020], inline=False)
            field_count += 1
        embeds.append(embed)
        PCC, buttons = await pages_of_embeds_2("ANY", embeds)

        await interaction.response.send_message(embed=PCC.make_embed(), view=buttons)
        # await self.callbacker.playlistcallback(interaction,self,"back")


class QuestionButton(discord.ui.Button):
    def __init__(self, myvalue=False, **kwargs):
        self.value = myvalue
        super().__init__(**kwargs)

        if self.value:
            self.style = discord.ButtonStyle.green
        else:
            self.style = discord.ButtonStyle.grey

    async def callback(self, interaction: discord.Interaction):
        self.value = not self.value
        await self.view.destroy_button(self.custom_id, interaction)


class FollowupAddModal(discord.ui.Modal, title="Add Followup Questions"):
    """Modal for adding a followup."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.followup_input = discord.ui.TextInput(
            label="Add followup quesitons", max_length=1024, required=True, 
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.followup_input)

    async def on_submit(self, interaction):
        followup = self.followup_input.value
        self.done = followup
        await interaction.response.defer()
        self.stop()


class FollowupSuggestModal(discord.ui.Modal, title="Suggest followups"):
    """Modal for suggesting."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.suggestion_input = discord.ui.TextInput(
            label="Focus", max_length=256, required=True
        )
        self.add_item(self.suggestion_input)

    async def on_submit(self, interaction):
        suggestion = self.suggestion_input.value
        self.done = suggestion
        await interaction.response.defer()
        self.stop()


class ChangeQueryModal(discord.ui.Modal, title="Enter a different google search query."):
    """Modal for removing a followup."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.titlev = discord.ui.TextInput(
            label="Enter a different google search query here", max_length=256, required=True
        )
        self.add_item(self.titlev)

    async def on_submit(self, interaction):
        output = self.titlev.value
        self.done = output
        await interaction.response.defer()
        self.stop()


class FollowupJustifyModal(discord.ui.Modal, title="Justify"):
    """Modal for justifying."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.justification_input = discord.ui.TextInput(
            label="Justification", max_length=256, required=True
        )
        self.add_item(self.justification_input)

    async def on_submit(self, interaction):
        justification = self.justification_input.value
        self.done = justification
        await interaction.response.defer()
        self.stop()


class FollowupSourceDetailModal(discord.ui.Modal, title="Source Detail"):
    """Modal for source details."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.source_detail_input = discord.ui.TextInput(
            label="Source Detail", required=True
        )
        self.add_item(self.source_detail_input)

    async def on_submit(self, interaction):
        source_detail = self.source_detail_input.value
        self.done = source_detail
        await interaction.response.defer()
        self.stop()





class Dropdown(discord.ui.Select):
    def __init__(self, option_kwarg, this_label="default", key="", user=None):
        self.user = user
        options = []
        for i in option_kwarg:
            options.append(discord.SelectOption(**i))

        self.key = key
        self.selected=None
        super().__init__(
            placeholder=this_label, min_values=1, max_values=1, options=options
        )

    async def interaction_check(self, interaction: Interaction[discord.Client]):
        if interaction.user == self.user:
            return True
        return False

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        gui.gprint(str(error))
        await interaction.response.send_message(
            f"Oops! Something went wrong: {str(error)}.", ephemeral=True
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        place=''
        for f in self.options:
            if f.value == value:
                f.default = True
                place=f"{f.label}:{f.description}"
            else:
                f.default = False
        self.selected=value
        self.placeholder=place
        await self.view.defer(interaction)



class TimedResponseView(discord.ui.View):
    '''Base class for the research views.'''
    def __init__(self, *, user, timeout=30 * 15):
        super().__init__(timeout=timeout)
        self.user = user
        self.value = False
        self.mydrop = None

    async def interaction_check(self, interaction: Interaction[discord.Client]):
        return interaction.user == self.user

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        gui.gprint(str(error))
        await interaction.response.send_message(
            f"Oops! Something went wrong: {str(error)}.", ephemeral=True
        )


    async def toggle_child(self,label,mode=False):
        for child in self.children:
            if isinstance(child,discord.ui.Button) or  isinstance(child,discord.ui.Select):
                if child.custom_id==label:
                    child.disabled=mode

    async def on_timeout(self) -> None:
        self.value=False
        self.stop()

    async def defer(self, interaction:discord.Interaction):
        await interaction.response.edit_message(view=self)
    
    async def change_dropdown_elements(self,elements,title):
        if self.mydrop:
            self.remove_item(self.mydrop)
        if elements:
            dl = []
            for e,i in enumerate(elements):
                dl.append({"label": e, "description": f"{i}"[:90]})
            d=Dropdown(
                dl,title,"NA",user=self.user
            )
            
            self.mydrop=d
            self.add_item(self.mydrop)

    async def continue_action(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Assuming there's a function to handle continuing

        self.value = True
        self.stop()

    async def cancel_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()

class PreCheck(TimedResponseView):
    def __init__(self, *, rctx,current, user, timeout=30 * 15):
        super().__init__(user=user,timeout=timeout)
        self.rctx=rctx
        self.links=[]
        self.details=[]
        self.current=current
        self.mydrop=None
        self.embed=discord.Embed(title="waiting for something to happen?")
        self.qatup= ("NA", self.current[0], "Let's find out.")

    async def search(self, interaction, edit=True):
        '''Run a google search with the current qatup'''
        
        links,res=await self.rctx.websearch(self.qatup)
        self.links=links
        self.details=res
        embed = discord.Embed(
            title=f"Web Search Results for: {self.qatup[0]} ",
        )
        for v in self.details:
            embed.add_field(name=v["title"], value=v["desc"], inline=True)
        self.embed=embed
        await self.change_dropdown_elements(self.links,"Current Links")

        await self.toggle_child('manualsearch',True)
        await self.toggle_child('gsearch',False)
        if edit:
            await interaction.edit_original_response(content=str(self.qatup),embed=self.embed,view=self)

    async def gen_query(self):
        '''auto generate the google search query.'''
        self.qatup=await self.rctx.get_query_from_question(self.current[0])


    @discord.ui.button(
        label="Run search",
        custom_id='manualsearch',
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def add_query(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.edit_message(content="Stand by... searching.")
        button.disabled=True
        await self.gen_query()
        await self.search(interaction)

    @discord.ui.button(
        label='google search',
        custom_id='gsearch',
        row=1,
        disabled=True
    )
    async def gsearch(
        self,interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = ChangeQueryModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done is not None:
            print(modal.done)
            query=modal.done
            _, que, com=self.qatup
            self.qatup=(query,que,com)
            await self.search(interaction)

        else:
            await interaction.edit_original_response(
                content="Cancelled"
            )



    @discord.ui.button(
        label="REMOVE_LINK",
        style=discord.ButtonStyle.blurple,
        row=2,
        disabled=False
    )
    async def remove_link(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        #self.qatup=await self.rctx.get_query_from_question(self.current[0])
        #await interaction.response.edit_message(content=str(self.qatup),view=self)
        if not self.mydrop:
            await interaction.response.send_message(content='You need to add links first',ephemeral=True)
            return
        if self.mydrop.selected is None:
            await interaction.response.send_message(content='Select a link to remove.',ephemeral=True)
            return
        
        sel=int(self.mydrop.selected)
        if len(self.links)<sel :
            await interaction.response.send_message(content='This link is not in links',ephemeral=True)
            return
        l=self.links.pop(sel)
        for i in self.details:
            if i['link']==l:
                self.details.remove(i)
        await self.change_dropdown_elements(self.links,"Current Links")
        embed = discord.Embed(
            title=f"Web Search Results for: {self.qatup[0]} ",
        )
        for v in self.details:
            embed.add_field(name=v["title"], value=v["desc"], inline=True)
        self.embed=embed
        await interaction.response.edit_message(embed=self.embed,view=self)


    @discord.ui.button(
        label='continue',
        row=3
    )
    async def continuenext(self,interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    
    @discord.ui.button(
        label="Cancel",
        row=3
    )
    async def no_search(self,interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.links=[]
        self.stop()
        await interaction.response.defer()



class FollowupActionView(TimedResponseView):
    def __init__(self, *, rctx,current, user, timeout=30 * 15):
        super().__init__(user=user,timeout=timeout)
        self.rctx=rctx
        self.links=[]
        self.details=[]
        self.followup_questions=[]
        self.current=current
        self.mydrop=None
        self.qatup= ("NA", self.current[0], "Let's find out.")

    def make_embed(self):
        foll="\n".join(f"* {q}" for q in self.followup_questions)
        emb=discord.Embed(
            title="Current Followups:",
            description=f"out:\n{foll}"
        )
        return emb
    
    @discord.ui.button(
        label="Add Followup",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def add_followup(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if len(self.followup_questions)>5:
            await interaction.response.send_message("Too many followups have been added.",ephemeral=True)
            return
        modal = FollowupAddModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done is not None:
            print(modal.done)
            followups=modal.done.split("\n")
            for fol in followups:
                if fol not in self.followup_questions and len(self.followup_questions)<=5:
                    self.followup_questions.append(fol)

            await self.change_dropdown_elements(self.followup_questions,"Current Followups")
            await interaction.edit_original_response(content="Added followups.",embed=self.make_embed(),view=self)
        else:
            await interaction.edit_original_response(
                content="Cancelled",
                embed=self.make_embed(),
            )

    @discord.ui.button(
        label="Suggest",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def suggest(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        #await interaction.response.send_message("This feature isn't ready yet!",ephemeral=True)
        # return
        modal = FollowupSuggestModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done is not None:
            # Assuming there's a function to handle suggestion

            suggestion=f"Ensure the questions are related to {modal.done}."
            questions,foll=await self.rctx.process_followups(self.current[1],self.current[2],suggestion)

            self.followup_questions=questions
            await self.change_dropdown_elements(self.followup_questions,"Current Followups")
            await interaction.edit_original_response(content="Generated new questions based on suggention!",embed=self.make_embed(),view=self)
        else:
            await interaction.edit_original_response(
                content="Cancelled",
                embed=discord.Embed(description="Suggestion cancelled."),
            )

    @discord.ui.button(
        label="Remove Followup",
        style=discord.ButtonStyle.red,
        row=1,
    )
    async def remove_followup(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not self.mydrop:
            await interaction.response.send_message(content='You need to add followups first!',ephemeral=True)
            return
        if self.mydrop.selected==None:
            await interaction.response.send_message(content='Select a followup to remove with the dropdown.',ephemeral=True)
            return
        
        sel=int(self.mydrop.selected)
        print(sel)
        if len(self.followup_questions)<sel :
            await interaction.response.send_message(content='This index is out of range.',ephemeral=True)
            return

        self.followup_questions.pop(sel)

        await self.change_dropdown_elements(self.followup_questions,"Current Followups")
            
        await interaction.response.edit_message(content="removed.",embed=self.make_embed(),view=self)


    @discord.ui.button(
        label="Justify",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def justify(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message("This feature isn't ready yet!",ephemeral=True)
        return
        modal = FollowupJustifyModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done is not None:
            # Assuming there's a function to handle justification
            print(modal.done)
            await interaction.edit_original_response(
                content="Justification recorded!",
                embed=discord.Embed(description=f"Justified: {modal.done}"),
            )
        else:
            await interaction.edit_original_response(
                content="Cancelled",
                embed=discord.Embed(description="Justification cancelled."),
            )

    @discord.ui.button(
        label="Source Detail",
        style=discord.ButtonStyle.blurple,
        row=2,
    )
    async def source_detail(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message("This feature isn't ready yet!",ephemeral=True)
        return
        modal = FollowupSourceDetailModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done is not None:
            # Assuming there's a function to handle source details
            print(modal.done)
            await interaction.edit_original_response(
                content="Source detail recorded!",
                embed=discord.Embed(description=f"Source detail: {modal.done}"),
            )
        else:
            await interaction.edit_original_response(
                content="Cancelled",
                embed=discord.Embed(description="Source detail recording cancelled."),
            )

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.green,
        row=3,
    )
    async def continue_action(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Assuming there's a function to handle continuing
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()