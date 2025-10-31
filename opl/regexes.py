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
# Příklad: "Machining consumes Raw Metal Bar."
RE_CONSUMES = re.compile(
    r'^\s*(?P<p>.+?)\s+consume(?:s)?\s+(?P<obj>.+?)(?:\s+at\s+state\s+(?P<state>\w+))?\.\s*$',
    re.I
)

# Input - proces bere objekty jako vstup
# Příklad: "Processing takes A, B and C as input."
RE_INPUTS = re.compile(r'^\s*(?P<p>.+?)\s+take(?:s)?\s+(?P<objs>.+?)\s+as\s+input\.\s*$', re.I)

# Yield/Result - proces vytváří/produkuje objekty
# Příklad: "Manufacturing yields Product."
# Příklad: "Machining yields Part at state pre-tested."
RE_YIELDS = re.compile(
    r'^\s*(?P<p>.+?)\s+yield(?:s)?\s+(?P<obj>.+?)(?:\s+at\s+state\s+(?P<state>\w+(?:-\w+)*))?\.\s*$',
    re.I
)

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

# Generalization - alternativní syntaxe (podtřídy "are" nadřazená třída)
# Příklad: "Freezing, Dehydrating, and Canning are Spoilage Slowing."
RE_ARE = re.compile(r'^\s*(?P<subs>.+?)\s+are\s+(?P<super>.+?)\.\s*$', re.I)

# Instantiation - třída má konkrétní instance
# Příklad: "Person has instances John, Mary and Bob."
RE_INSTANCES = re.compile(r'^\s*(?P<class>.+?)\s+has\s+instances\s+(?P<insts>.+?)\.\s*$', re.I)

# === Stavy objektů ===

# States - výčet možných stavů objektu
# Příklad: "Order can be Pending, Confirmed or Delivered."
RE_STATES = re.compile(r'^\s*(?P<obj>.+?)\s+can\s+be\s+(?P<states>.+?)\.\s*$', re.I)

# Simple "is a" - jednoduchá generalizace
# Příklad: "Car is a Vehicle." nebo "Abs is a Braking System."
# Poznámka: Tento regex se používá pouze pro generalizaci, kdy druhý název (super) začíná velkým písmenem
RE_IS_A = re.compile(r'^\s*(?P<sub>.+?)\s+is\s+a[n]?\s+(?P<super>.+?)\.\s*$')

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

# === Definice objektů a procesů s atributy ===
# Definice s essence a affiliation - podporuje obě pořadí
# Příklad: "A is a informatical and systemic object."
# Příklad: "A is a systemic and informatical object."
# Příklad: "A is informatical and systemic object." (bez a/an)
# Příklad: "B is a physical and environmental process."
# Poznámka: "a[n]?" je volitelné - může být s nebo bez "a/an"
RE_DEFINITION = re.compile(
    r'^\s*(?P<name>.+?)\s+is\s+(?:a[n]?\s+)?'
    r'(?:(?P<essence1>physical|informatical)\s+and\s+(?P<affiliation1>systemic|environmental)|'
    r'(?P<affiliation2>systemic|environmental)\s+and\s+(?P<essence2>physical|informatical))'
    r'\s+(?P<kind>object|process)\.+\s*$',
    re.I
)

# Definice s jedním atributem - essence nebo affiliation
# Příklad: "Car is an informatical object." (affiliation=systemic implicitní)
# Příklad: "Car is a systemic object." (essence=informatical implicitní pro objekty)
# Příklad: "Car is informatical object." (bez a/an, ale s object/process)
# Poznámka: Atributy musí být malými písmeny, jinak jde o generalizaci
# Poznámka: "a[n]?" je volitelné - může být "Car is informatical object." nebo "Car is a informatical object."
RE_DEFINITION_SINGLE = re.compile(
    r'^\s*(?P<name>.+?)\s+is\s+(?:a[n]?\s+)?'
    r'(?P<attr>physical|informatical|systemic|environmental)'
    r'\s+(?P<kind>object|process)\.+\s*$',
    re.I
)

# Minimální definice s jedním atributem - bez "a/an" a bez "object/process" (defaultně objekt)
# Příklad: "Raw Metal Bar is physical." (vytvoří objekt, affiliation=systemic implicitní)
# Příklad: "Car is systemic." (vytvoří objekt, essence=informatical implicitní)
# Poznámka: Atributy musí být malými písmeny, jinak jde o generalizaci. Defaultně vytváří objekt.
RE_DEFINITION_MINIMAL = re.compile(
    r'^\s*(?P<name>.+?)\s+is\s+'
    r'(?P<attr>physical|informatical|systemic|environmental)\.+\s*$',
    re.I
)

# Objekt s jedním stavem - "A is state."
# Příklad: "A is a1." (vytvoří objekt A se stavem a1)
# Příklad: "A is pre-cut." (vytvoří objekt A se stavem pre-cut)
# Poznámka: Stav musí začínat malým písmenem. Pokud začíná velkým písmenem, jde o generalizaci (RE_IS_A).
# Poznámka: Musí být kontrolováno před RE_IS_A, aby se rozlišil stav od generalizace.
RE_IS_STATE = re.compile(
    r'^\s*(?P<obj>.+?)\s+is\s+(?P<state>[^\s.]+)\.\s*$',
    re.I
)