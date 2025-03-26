import asyncio
from unittest.mock import AsyncMock, MagicMock


# Spoof Discord Message class
class FakeMessage:
    def __init__(self, content, author, guild, channel_id, created_at, jump_url):
        self.content = content
        self.author = author
        self.guild = guild
        self.channel = MagicMock(id=channel_id)
        self.created_at = created_at
        self.jump_url = jump_url


async def test_sentence_memory():
    from gptmod.sentence_mem import SentenceMemory
    from langchain_huggingface import HuggingFaceEmbeddings

    hug_embed = HuggingFaceEmbeddings(model_name="thenlper/gte-small")
    hug_embed.embed_query("The quick brown fox jumped over the lazy frog.")
    # Mock bot and dependencies
    bot = MagicMock()
    bot.embedding = MagicMock(return_value=hug_embed)
    guild = MagicMock(id=123456)
    user = MagicMock(id=654321)

    # Initialize SentenceMemory
    memory = SentenceMemory(bot, guild, user)
    # Create a fake message
    # Perform a search
    message = FakeMessage(
        content="Super Mario Goes down PIPES!",
        author=user,
        guild=user,
        channel_id=111,
        created_at=MagicMock(timestamp=lambda: 167253112199),
        jump_url="https://discord.com/channels/123456/111/4648623",
    )

    message2 = FakeMessage(
        content="Super Luigi Goes down PIPES!",
        author=user,
        guild=user,
        channel_id=111,
        created_at=MagicMock(timestamp=lambda: 1672531199),
        jump_url="https://discord.com/channels/15/561/212121",
    )

    # Mock add_to_mem method
    ctx = MagicMock()
    ctx.bot = bot
    await memory.add_to_mem(ctx, message)

    await memory.add_to_mem(ctx, message2)

    # Perform a search
    docs = memory.coll.similarity_search_with_relevance_scores("testing")
    print("relevance score - ", docs[0][1])
    print("text- ", docs[0][0].page_content[:1000])
    print(docs)
    # memory.coll.asimilarity_search_with_relevance_scores = AsyncMock(return_value=[])
    docs, output, timers = await memory.search_sim(message)

    print("Search Results:", docs)
    print("Formatted Output:", output)
    print("Execution Timers:", timers)


# Run the test
asyncio.run(test_sentence_memory())
