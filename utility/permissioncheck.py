from discord.ext import commands


# I need to redo the permission system.
def serverOwner(ctx: commands.context):
    user = ctx.message.author
    guild = ctx.message.channel.guild
    guild_owner = guild.owner_id
    if user.id == guild_owner:
        return True
    return False


def serverAdmin(ctx: commands.context, gchan=None):
    user = ctx.message.author
    perm = user.guild_permissions
    perm_chan = ctx.channel.permissions_for(user)
    if perm.administrator or perm.manage_messages:
        return True

    if gchan:
        if perm_chan.manage_channels:
            return True

    return False
