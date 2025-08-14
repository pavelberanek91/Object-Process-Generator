from __future__ import annotations
import re
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

SYSTEM_OPL_GUIDE = (
    "You are an OPM assistant. Convert the user description to strict OPL sentences.\n"
    "Allowed templates (exact wording, one sentence per line, each ending with a period):\n"
    "- {{P}} consumes {{O[, O2, ...]}}.\n"
    "- {{P}} takes {{O[, O2, ...]}} as input.\n"
    "- {{P}} yields {{O[, O2, ...]}}.\n"
    "- {{P}} affects {{O[, O2, ...]}}.\n"
    "- {{A[, A2, ...]}} handle {{P}}.\n"
    "- {{P}} requires {{O[, O2, ...]}}.\n"
    "- {{Whole}} is composed of {{Part[, Part2, ...]}}.\n"
    "- {{Obj}} is characterized by {{Attr[, Attr2, ...]}}.\n"
    "- {{Obj}} exhibits {{Attr[, Attr2, ...]}}.\n"
    "- {{Super}} generalizes {{Sub[, Sub2, ...]}}.\n"
    "- {{Class}} has instances {{i1[, i2, ...]}}.\n\n"
    "Rules:\n"
    "- Output ONLY OPL sentences above, nothing else (no preface, no code fences).\n"
    "- If input is in Czech or Slovak, translate terms to English labels where reasonable (keep proper nouns).\n"
    "- Merge obvious synonyms (e.g., 'produces' → 'yields', 'uses' → 'requires' or 'consumes' depending on context)."
)

PROMPT = ChatPromptTemplate.from_messages(
    [("system", SYSTEM_OPL_GUIDE),
     ("human", "User description (CZ/EN):\n```text\n{nl}\n```")]
)

def nl_to_opl(nl_text: str, model: str = "gpt-5-chat-latest", temperature: float = 0.0) -> str:
    llm = ChatOpenAI(model=model, temperature=temperature)
    try:
        resp = (PROMPT | llm).invoke({"nl": nl_text})
        content = getattr(resp, "content", "").strip()
        content = re.sub(r"^```[a-zA-Z]*|```$", "", content.strip(), flags=re.MULTILINE)
        return content.strip()
    except Exception:
        return heuristic_fallback(nl_text)

def heuristic_fallback(nl: str) -> str:
    text = nl.strip()
    lines = []
    m = re.search(r'(?P<p>[\w\s"]+?)\s+(uses|používá)\s+(?P<ins>.+?)\s+(to\s+produce|k\s+vytvoření)\s+(?P<outs>.+)', text, re.I)
    if m:
        P = m.group("p").strip('" ')
        INS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("ins")) if x.strip()]
        OUTS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("outs")) if x.strip()]
        if INS:  lines.append(f'{P} requires {", ".join(INS)}.')
        if OUTS: lines.append(f'{P} yields {", ".join(OUTS)}.')
    m = re.search(r'(?P<p>[\w\s"]+?)\s+(consumes|spotřebovává)\s+(?P<objs>.+)', text, re.I)
    if m:
        P = m.group("p").strip('" ')
        OBJS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("objs")) if x.strip()]
        if OBJS: lines.append(f'{P} consumes {", ".join(OBJS)}.')
    m = re.search(r'(?P<ag>[\w\s",]+?)\s+(handle|řídí)\s+(?P<p>[\w\s"]+)', text, re.I)
    if m:
        AGS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("ag")) if x.strip()]
        P = m.group("p").strip('" ')
        if AGS: lines.append(f'{", ".join(AGS)} handle {P}.')
    m = re.search(r'(?P<p>[\w\s"]+?)\s+(requires|vyžaduje)\s+(?P<ins>.+)', text, re.I)
    if m:
        P = m.group("p").strip('" ')
        INS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("ins")) if x.strip()]
        if INS: lines.append(f'{P} requires {", ".join(INS)}.')
    m = re.search(r'(?P<p>[\w\s"]+?)\s+(yields|produces|vyrábí|generuje)\s+(?P<outs>.+)', text, re.I)
    if m:
        P = m.group("p").strip('" ')
        OUTS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("outs")) if x.strip()]
        if OUTS: lines.append(f'{P} yields {", ".join(OUTS)}.')
    m = re.search(r'(?P<x>[\w\s"]+?)\s+(affects|ovlivňuje)\s+(?P<y>[\w\s",]+)', text, re.I)
    if m:
        X = m.group("x").strip('" ')
        Ys = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("y")) if x.strip()]
        if Ys: lines.append(f'{X} affects {", ".join(Ys)}.')
    m = re.search(r'(?P<w>[\w\s"]+?)\s+(is composed of|se skládá z)\s+(?P<p>.+)', text, re.I)
    if m:
        W = m.group("w").strip('" ')
        Ps = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("p")) if x.strip()]
        if Ps: lines.append(f'{W} is composed of {", ".join(Ps)}.')
    clean, seen = [], set()
    for ln in lines:
        ln = ln.rstrip(".") + "."
        if ln not in seen:
            seen.add(ln); clean.append(ln)
    return "\n".join(clean) if clean else ""