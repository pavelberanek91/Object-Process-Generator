"""Regulární výrazy pro parsování OPL (Object-Process Language) vět.

Tento modul obsahuje zkompilované regexové vzory pro rozpoznání jednotlivých
typů OPL vět (procedurálních i strukturálních vztahů).
"""

# === Poznámky k původním verzím (zakomentované) ===
# Původní, jednodušší verze regexů byly nahrazeny pokročilejšími variantami,
# které umožňují parsování stavů a složitějších konstrukcí.
# Ponechané jako reference:
# import re
# # Procedural
# RE_CONSUMES  = re.compile(r'^\s*(?P<p>.+?)\s+consume(?:s)?\s+(?P<objs>.+?)\.\s*$', re.I)
# RE_INPUTS    = re.compile(r'^\s*(?P<p>.+?)\s+take(?:s)?\s+(?P<objs>.+?)\s+as\s+input\.\s*$', re.I)
# RE_YIELDS    = re.compile(r'^\s*(?P<p>.+?)\s+yield(?:s)?\s+(?P<objs>.+?)\.\s*$', re.I)
# RE_HANDLES   = re.compile(r'^\s*(?P<agents>.+?)\s+handle(?:s)?\s+(?P<p>.+?)\.\s*$', re.I)
# RE_REQUIRES  = re.compile(r'^\s*(?P<p>.+?)\s+require(?:s)?\s+(?P<objs>.+?)\.\s*$', re.I)
# RE_AFFECTS   = re.compile(r'^\s*(?P<x>.+?)\s+affect(?:s)?\s+(?P<y>.+?)\.\s*$', re.I)
# # Structural
# RE_COMPOSED  = re.compile(r'^\s*(?P<whole>.+?)\s+is\s+composed\s+of\s+(?P<parts>.+?)\.\s*$', re.I)
# RE_CHARAC    = re.compile(r'^\s*(?P<obj>.+?)\s+is\s+characterized\s+by\s+(?P<attrs>.+?)\.\s*$', re.I)
# RE_EXHIBITS  = re.compile(r'^\s*(?P<obj>.+?)\s+exhibit(?:s)?\s+(?P<attrs>.+?)\.\s*$', re.I)
# RE_GENER     = re.compile(r'^\s*(?P<super>.+?)\s+generalize(?:s)?\s+(?P<subs>.+?)\.\s*$', re.I)
# RE_INSTANCES = re.compile(r'^\s*(?P<class>.+?)\s+has\s+instances\s+(?P<insts>.+?)\.\s*$', re.I)

import re

# === Procedurální vazby (vztahy mezi procesy a objekty) ===

# Consumption - proces spotřebovává objekt (nebo objekt ve stavu)
# Příklad: "Manufacturing consumes Material at state Raw."
RE_CONSUMES = re.compile(
    r'^\s*(?P<p>.+?)\s+consume(?:s)?\s+(?P<obj>\w+)(?:\s+at\s+state\s+(?P<state>\w+))?\.\s*$',
    re.I
)

# Input - proces bere objekty jako vstup
# Příklad: "Processing takes A, B and C as input."
RE_INPUTS = re.compile(r'^\s*(?P<p>.+?)\s+take(?:s)?\s+(?P<objs>.+?)\s+as\s+input\.\s*$', re.I)

# Yield/Result - proces vytváří/produkuje objekty
# Příklad: "Manufacturing yields Product."
RE_YIELDS = re.compile(r'^\s*(?P<p>.+?)\s+yield(?:s)?\s+(?P<objs>.+?)\.\s*$', re.I)

# Agent - kdo řídí proces (agentem může být člověk, stroj, jiný objekt)
# Příklad: "Worker handles Manufacturing."
RE_HANDLES = re.compile(r'^\s*(?P<agents>.+?)\s+handle(?:s)?\s+(?P<p>.+?)\.\s*$', re.I)

# Instrument - proces vyžaduje nástroje/zdroje (ale nespotřebovává je)
# Příklad: "Manufacturing requires Tools."
RE_REQUIRES = re.compile(r'^\s*(?P<p>.+?)\s+require(?:s)?\s+(?P<objs>.+?)\.\s*$', re.I)

# Effect - proces/objekt ovlivňuje jiné objekty
# Příklad: "Temperature affects Quality."
RE_AFFECTS = re.compile(r'^\s*(?P<x>.+?)\s+affect(?:s)?\s+(?P<y>.+?)\.\s*$', re.I)

# === Strukturální vazby (vztahy mezi objekty navzájem) ===

# Aggregation - objekt se skládá z částí
# Příklad: "Car consists of Engine, Wheels and Body."
RE_COMPOSED = re.compile(r'^\s*(?P<whole>.+?)\s+consists\s+of\s+(?P<parts>.+?)\.\s*$', re.I)

# Characterization - objekt je charakterizován atributy
# Příklad: "Person is characterized by Name and Age."
RE_CHARAC = re.compile(r'^\s*(?P<obj>.+?)\s+is\s+characterized\s+by\s+(?P<attrs>.+?)\.\s*$', re.I)

# Exhibition - objekt vykazuje/má vlastnosti
# Příklad: "Product exhibits Quality."
RE_EXHIBITS = re.compile(r'^\s*(?P<obj>.+?)\s+exhibit(?:s)?\s+(?P<attrs>.+?)\.\s*$', re.I)

# Generalization - nadřazená třída generalizuje podtřídy
# Příklad: "Vehicle generalizes Car and Bike."
RE_GENER = re.compile(r'^\s*(?P<super>.+?)\s+generalize(?:s)?\s+(?P<subs>.+?)\.\s*$', re.I)

# Instantiation - třída má konkrétní instance
# Příklad: "Person has instances John, Mary and Bob."
RE_INSTANCES = re.compile(r'^\s*(?P<class>.+?)\s+has\s+instances\s+(?P<insts>.+?)\.\s*$', re.I)

# === Stavy objektů ===

# States - výčet možných stavů objektu
# Příklad: "Order can be Pending, Confirmed or Delivered."
RE_STATES = re.compile(r'^\s*(?P<obj>.+?)\s+can\s+be\s+(?P<states>.+?)\.\s*$', re.I)

# Simple "is a" - jednoduchá generalizace
# Příklad: "Car is a Vehicle."
RE_IS_A = re.compile(r'^\s*(?P<sub>\w+)\s+is\s+a[n]?\s+(?P<super>\w+)\.\s*$', re.I)

# Simple "is an instance of" - jednoduchá instantiace
# Příklad: "John is an instance of Person."
RE_INSTANCE = re.compile(r'^\s*(?P<inst>\w+)\s+is\s+an\s+instance\s+of\s+(?P<class>\w+)\.\s*$', re.I)

# State change - proces mění objekt z jednoho stavu do druhého
# Příklad: "Processing changes Order from Pending to Confirmed."
RE_CHANGES = re.compile(
    r'^\s*(?P<p>.+?)\s+change(?:s)?\s+(?P<obj>.+?)\s+from\s+(?P<from>.+?)\s+to\s+(?P<to>.+?)\.\s*$',
    re.I
)

# Can be - alternativní syntaxe pro stavy (ekvivalent RE_STATES)
# Příklad: "Light can be On or Off."
RE_CANBE = re.compile(
    r'^\s*(?P<obj>.+?)\s+can\s+be\s+(?P<states>.+?)\.\s*$',
    re.I
)