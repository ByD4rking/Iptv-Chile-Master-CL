import json
from pathlib import Path

FILE = Path("data/channels.json")

with FILE.open("r", encoding="utf-8") as f:
    data = json.load(f)


def fix_text(value):

    if not isinstance(value, str):
        return value

    # Corrige casos típicos de UTF-8 interpretado como Windows-1252.
    if any(x in value for x in (
        "Ã", "Â", "â€"
    )):
        try:
            return value.encode(
                "latin1"
            ).decode(
                "utf-8"
            )
        except (UnicodeEncodeError, UnicodeDecodeError):
            return value

    return value


for channel in data:

    if "name" in channel:
        channel["name"] = fix_text(
            channel["name"]
        )

    if "group" in channel:
        channel["group"] = fix_text(
            channel["group"]
        )

    if "logo" in channel:
        channel["logo"] = fix_text(
            channel["logo"]
        )

    for source in channel.get(
        "sources",
        []
    ):

        if "source" in source:
            source["source"] = fix_text(
                source["source"]
            )


with FILE.open(
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        data,
        f,
        ensure_ascii=False,
        indent=2
    )


print("")
print("=" * 60)
print("CODIFICACION CORREGIDA")
print("=" * 60)
print(
    f"Canales conservados: {len(data)}"
)
print(
    "URLs no modificadas."
)
print(
    f"Archivo: {FILE.resolve()}"
)
print("")

for channel in data[:10]:

    print(
        f"- {channel.get('name', '')}"
    )
