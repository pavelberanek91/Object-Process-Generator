"""Modul pro převod přirozeného jazyka (NL) na OPL věty pomocí AI/LLM."""
import re
from pathlib import Path
from dataclasses import dataclass
# LangChain framework pro práci s LLM
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


# Cesty k souborům s prompt šablonami pro AI model
SYSTEM_PROMPT_FILE = Path(Path.cwd(), "ai", "prompts", "system.prompt")
USER_PROMPT_FILE = Path(Path.cwd(), "ai", "prompts", "human.prompt")


def load_prompt_texts(system_prompt_path, user_prompt_path) -> tuple[str, str]:
    """
    Načte system a user prompt ze souborů.
    
    Args:
        system_prompt_path: Cesta k souboru se system promptem (instrukce pro AI)
        user_prompt_path: Cesta k souboru s user promptem (šablona pro vstup uživatele)
    
    Returns:
        Dvojice (system_prompt, user_prompt) jako textové řetězce
    """
    sys_prompt = system_prompt_path.read_text(encoding="utf-8")
    usr_prompt = user_prompt_path.read_text(encoding="utf-8")
    return sys_prompt, usr_prompt


def build_prompt() -> ChatPromptTemplate:
    """
    Sestaví ChatPromptTemplate z načtených šablon v prompt souborech.
    
    Returns:
        ChatPromptTemplate připravený pro použití s LangChain
    """
    sys_prompt, usr_prompt = load_prompt_texts(SYSTEM_PROMPT_FILE, USER_PROMPT_FILE)
    # Vytvoří šablonu s rolemi "system" (instrukce) a "human" (vstup uživatele)
    return ChatPromptTemplate.from_messages([("system", sys_prompt), ("human", usr_prompt)])


def nl_to_opl(nl_text: str, model: str = "gpt-5-chat-latest", temperature: float = 0.0) -> str:
    """
    Převede přirozený jazyk (CZ/EN) na OPL věty pomocí LLM (LangChain + OpenAI).
    
    Při selhání připojení k AI modelu použije heuristický fallback založený na regexech.
    
    Args:
        nl_text: Text v přirozeném jazyce popisující proces/vztahy
        model: Název OpenAI modelu (výchozí "gpt-5-chat-latest")
        temperature: Teplota pro generování (0.0 = deterministické, 1.0 = kreativní)
    
    Returns:
        OPL věty, každá na novém řádku
    """
    # Sestavení prompt šablony a inicializace LLM
    prompt = build_prompt()
    llm = ChatOpenAI(model=model, temperature=temperature)
    
    try:
        # Zavolání LLM chain: prompt | llm
        resp = (prompt | llm).invoke({"nl": nl_text})
        content = getattr(resp, "content", "").strip()
        
        # Vyčištění případných markdown code fences (```) z odpovědi LLM
        content = re.sub(r"^```[a-zA-Z]*|```$", "", content.strip(), flags=re.MULTILINE)
        return content.strip()
    except Exception:
        # Při chybě připojení k LLM použijeme heuristický fallback
        # TODO: dopsat upozornění do GUI, že byl problém s připojením
        return heuristic_fallback(nl_text)


def heuristic_fallback(nl: str) -> str:
    """
    Heuristický (regexový) převod z NL na OPL jako záložní varianta v případě chyby připojení k LLM.
    
    Používá sadu regexových vzorů pro rozpoznání běžných frází v češtině i angličtině
    a převod na OPL věty.
    
    Args:
        nl: Text v přirozeném jazyce
    
    Returns:
        OPL věty (pokud nějaké rozpozná), jinak prázdný řetězec
    """
    # TODO: popřemýšlet o úhledním načítání regexů ze souboru
    text = nl.strip()
    lines = []  # Seznam vygenerovaných OPL vět

    # === Vzor 1: <PROCESS> uses|používá <INS> to produce|k vytvoření <OUTS> ===
    # Příklad: "Manufacturing uses tools to produce products"
    m = re.search(r'(?P<p>[\w\s"]+?)\s+(uses|používá)\s+(?P<ins>.+?)\s+(to\s+produce|k\s+vytvoření)\s+(?P<outs>.+)', text, re.I)
    if m:
        P = m.group("p").strip('" ')  # Název procesu
        # Rozdělení instrumentů (může být seznam oddělený čárkami nebo "and"/"a")
        INS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("ins")) if x.strip()]
        # Rozdělení výstupů
        OUTS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("outs")) if x.strip()]
        if INS:  lines.append(f'{P} requires {", ".join(INS)}.')
        if OUTS: lines.append(f'{P} yields {", ".join(OUTS)}.')
    
    # === Vzor 2: <PROCESS> consumes|spotřebovává <OBJS> ===
    # Příklad: "Manufacturing consumes raw materials"
    m = re.search(r'(?P<p>[\w\s"]+?)\s+(consumes|spotřebovává)\s+(?P<objs>.+)', text, re.I)
    if m:
        P = m.group("p").strip('" ')
        OBJS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("objs")) if x.strip()]
        if OBJS: lines.append(f'{P} consumes {", ".join(OBJS)}.')
    
    # === Vzor 3: <AGENTS> handle|řídí <PROCESS> ===
    # Příklad: "Workers handle manufacturing"
    m = re.search(r'(?P<ag>[\w\s",]+?)\s+(handle|řídí)\s+(?P<p>[\w\s"]+)', text, re.I)
    if m:
        AGS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("ag")) if x.strip()]
        P = m.group("p").strip('" ')
        if AGS: lines.append(f'{", ".join(AGS)} handle {P}.')
    
    # === Vzor 4: <PROCESS> requires|vyžaduje <INS> ===
    # Příklad: "Manufacturing requires tools"
    m = re.search(r'(?P<p>[\w\s"]+?)\s+(requires|vyžaduje)\s+(?P<ins>.+)', text, re.I)
    if m:
        P = m.group("p").strip('" ')
        INS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("ins")) if x.strip()]
        if INS: lines.append(f'{P} requires {", ".join(INS)}.')
   
    # === Vzor 5: <PROCESS> yields|produces|vyrábí|generuje <OUTS> ===
    # Příklad: "Manufacturing yields products"
    m = re.search(r'(?P<p>[\w\s"]+?)\s+(yields|produces|vyrábí|generuje)\s+(?P<outs>.+)', text, re.I)
    if m:
        P = m.group("p").strip('" ')
        OUTS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("outs")) if x.strip()]
        if OUTS: lines.append(f'{P} yields {", ".join(OUTS)}.')
    
    # === Vzor 6: <X> affects|ovlivňuje <Y> ===
    # Příklad: "Temperature affects quality"
    m = re.search(r'(?P<x>[\w\s"]+?)\s+(affects|ovlivňuje)\s+(?P<y>[\w\s",]+)', text, re.I)
    if m:
        X = m.group("x").strip('" ')
        Ys = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("y")) if x.strip()]
        if Ys: lines.append(f'{X} affects {", ".join(Ys)}.')
    
    # === Vzor 7: <WHOLE> is composed of |se skládá z <PARTS> ===
    # Příklad: "Car is composed of engine, wheels and body"
    m = re.search(r'(?P<w>[\w\s"]+?)\s+(is composed of|se skládá z)\s+(?P<p>.+)', text, re.I)
    if m:
        W = m.group("w").strip('" ')
        Ps = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("p")) if x.strip()]
        if Ps: lines.append(f'{W} is composed of {", ".join(Ps)}.')
    
    # === Vyčištění a deduplikace vět ===
    # Zajistíme, že každá věta končí tečkou a odstraníme duplicity
    clean, seen = [], set()
    for ln in lines:
        ln = ln.rstrip(".") + "."  # Zajištění tečky na konci
        if ln not in seen:
            seen.add(ln)
            clean.append(ln)

    return "\n".join(clean) if clean else ""