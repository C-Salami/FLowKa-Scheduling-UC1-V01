# nlp_extractor.py
import os, json, re
from dateutil import parser as dtp
from datetime import datetime
from nlp_schema import INTENT_SCHEMA

# Optional OpenAI structured-output extractor.
# If OPENAI_API_KEY is missing or the call fails, we fall back to regex.
def _extract_with_openai(user_text: str):
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    SYSTEM = (
        "You normalize factory scheduling edit commands for a Gantt. "
        "Return ONLY JSON matching the given schema. "
        "Supported intents: delay_order, move_order, swap_orders. "
        "Order IDs look like O021 (3 digits). "
        "If user says 'tomorrow' etc., convert to ISO date in Asia/Makassar. "
        "If time missing on move_order, default 08:00. "
        "If units missing on delay_order, assume days."
    )
    USER_GUIDE = (
        'Examples:\n'
        '1) "delay O021 one day" -> {"intent":"delay_order","order_id":"O021","days":1}\n'
        '2) "push order O009 by 24h" -> {"intent":"delay_order","order_id":"O009","hours":24}\n'
        '3) "move o014 to Aug 30 9am" -> {"intent":"move_order","order_id":"O014","date":"2025-08-30","time":"09:00"}\n'
        '4) "swap o027 with o031" -> {"intent":"swap_orders","order_id":"O027","order_id_2":"O031"}\n'
        '5) "move O008 on monday morning" -> {"intent":"move_order","order_id":"O008","date":"<monday ISO>","time":"09:00"}\n'
    )
    resp = client.responses.create(
        model="gpt-5.1",  # any structured-output-capable model
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER_GUIDE},
            {"role": "user", "content": user_text},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "Edit", "schema": INTENT_SCHEMA}
        },
    )
    # The python SDK returns parsed text in output[0].content[0].text for structured outputs
    text = resp.output[0].content[0].text
    return json.loads(text)

# Very small regex fallback that handles common phrasings.
def _regex_fallback(user_text: str):
    t = user_text.strip()
    low = t.lower()

    # swap Oxxx with Oyyy
    m = re.search(r"(swap|switch)\s+(o\d{3})\s+(with|and)\s+(o\d{3})", low)
    if m:
        return {"intent": "swap_orders", "order_id": m.group(2).upper(), "order_id_2": m.group(4).upper()}

    # delay/push/postpone Oxxx by N days/hours
    m = re.search(r"(delay|push|postpone)\s+(o\d{3})\s+(by\s+)?(\d+)\s*(day|days|d|hour|hours|h)", low)
    if m:
        unit = m.group(5)
        n = int(m.group(4))
        out = {"intent": "delay_order", "order_id": m.group(2).upper()}
        if unit.startswith("d"):
            out["days"] = n
        else:
            out["hours"] = n
        return out

    # move Oxxx to/on <datetime>
    m = re.search(r"(move|set|schedule)\s+(o\d{3})\s+(to|on)\s+(.+)", low)
    if m:
        when = m.group(4)
        try:
            dt = dtp.parse(when, fuzzy=True)
            return {
                "intent": "move_order",
                "order_id": m.group(2).upper(),
                "date": dt.date().isoformat(),
                "time": dt.strftime("%H:%M"),
            }
        except Exception:
            pass

    # Basic "delay Oxxx one day" text
    m = re.search(r"(delay|push|postpone)\s+(o\d{3}).*(one|1)\s+day", low)
    if m:
        return {"intent": "delay_order", "order_id": m.group(2).upper(), "days": 1}

    return {"intent": "unknown", "raw": user_text}

def extract_intent(user_text: str) -> dict:
    try:
        if os.getenv("OPENAI_API_KEY"):
            return _extract_with_openai(user_text)
    except Exception:
        pass
    return _regex_fallback(user_text)
