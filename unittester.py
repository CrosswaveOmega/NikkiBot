import lancedb
from langchain_huggingface import HuggingFaceEmbeddings
import datetime

hug_embed = HuggingFaceEmbeddings(model_name="thenlper/gte-small")
hug_embed.embed_query("The quick brown fox jumped over the lazy frog.")

db = lancedb.connect("./saveData/lance-db")

table = db.open_table("sentence_mem")
print(table)
print(table.head())

print(table.count_rows())

print(table.to_pandas())


table.optimize(cleanup_older_than=datetime.timedelta(days=0))
input()

data = [
    {
        "vector": hug_embed.embed_query("MARIO KARRT"),
        "id": "596",
        "text": "MEHRIO KART",
        "metadata": {
            "channel": 111,
            "date": 1672531199,
            "forguild": 123456,
            "foruser": 654321,
            "role": "assistant",
            "source": "https://discord.com/channels/15/561/212121bb",
            "split": 0,
        },
    },
    {
        "vector": hug_embed.embed_query("MARIO KARRT VEE"),
        "id": "2ou",
        "text": "BLARIO KART VEE",
        "metadata": {
            "channel": 111,
            "date": 1672531199,
            "forguild": 123456,
            "foruser": 654321,
            "role": "assistant",
            "source": "https://discord.com/channels/15/561/212121aa",
            "split": 0,
        },
    },
]
table.merge_insert(
    "id"
).when_matched_update_all().when_not_matched_insert_all().execute(data)


print(table.to_pandas())

input()
