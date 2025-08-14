import re
# Procedural
RE_CONSUMES  = re.compile(r'^\s*(?P<p>.+?)\s+consume(?:s)?\s+(?P<objs>.+?)\.\s*$', re.I)
RE_INPUTS    = re.compile(r'^\s*(?P<p>.+?)\s+take(?:s)?\s+(?P<objs>.+?)\s+as\s+input\.\s*$', re.I)
RE_YIELDS    = re.compile(r'^\s*(?P<p>.+?)\s+yield(?:s)?\s+(?P<objs>.+?)\.\s*$', re.I)
RE_HANDLES   = re.compile(r'^\s*(?P<agents>.+?)\s+handle(?:s)?\s+(?P<p>.+?)\.\s*$', re.I)
RE_REQUIRES  = re.compile(r'^\s*(?P<p>.+?)\s+require(?:s)?\s+(?P<objs>.+?)\.\s*$', re.I)
RE_AFFECTS   = re.compile(r'^\s*(?P<x>.+?)\s+affect(?:s)?\s+(?P<y>.+?)\.\s*$', re.I)
# Structural
RE_COMPOSED  = re.compile(r'^\s*(?P<whole>.+?)\s+is\s+composed\s+of\s+(?P<parts>.+?)\.\s*$', re.I)
RE_CHARAC    = re.compile(r'^\s*(?P<obj>.+?)\s+is\s+characterized\s+by\s+(?P<attrs>.+?)\.\s*$', re.I)
RE_EXHIBITS  = re.compile(r'^\s*(?P<obj>.+?)\s+exhibit(?:s)?\s+(?P<attrs>.+?)\.\s*$', re.I)
RE_GENER     = re.compile(r'^\s*(?P<super>.+?)\s+generalize(?:s)?\s+(?P<subs>.+?)\.\s*$', re.I)
RE_INSTANCES = re.compile(r'^\s*(?P<class>.+?)\s+has\s+instances\s+(?P<insts>.+?)\.\s*$', re.I)