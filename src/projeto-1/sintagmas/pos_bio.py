# -*- coding: utf-8 -*-
"""POS tagging (Viterbi) e codificacao BIO de um caso clinico do MultiCaRe.

    python3 pos_bio.py --case-id PMC5137649_01
    python3 pos_bio.py --case-id PMC5137649_01 --out PMC5137649_01.conll
    python3 pos_bio.py --case-id PMC5137649_01 --show-pos
    python3 pos_bio.py --treinar          # regera model/hmm_pos.json (usa NLTK)

Entrada: um `case_id` de sample/cases.csv.
Saida:   CoNLL de quatro colunas -- token, POS, BIO camada 0, BIO camada 1.

--------------------------------------------------------------------- Viterbi

O tagger e um HMM bigrama treinado no Penn Treebank com o tagset universal (12
etiquetas). O modelo fica em model/hmm_pos.json; em execucao este arquivo nao
depende de nada alem da biblioteca padrao.

    delta[0][t] = log P(t | <s>) + log P(w0 | t)
    delta[i][t] = max_s ( delta[i-1][s] + log P(t | s) ) + log P(wi | t)
    psi[i][t]   = argmax_s ( ... )

No fim volta-se pelos backpointers a partir do melhor estado final. Custo
O(n * |T|^2). Viterbi escolhe a *sequencia* de maior probabilidade conjunta, nao
cada etiqueta isolada -- por isso 'revealed' sai VERB em "pathology revealed a
cyst" e ADJ em "which revealed normal echotexture".

Palavra fora do vocabulario nao tem P(w|t); usa-se um modelo de assinatura
(sufixo de ate 3 caracteres, senao formato grafico) estimado sobre as palavras
raras do corpus e convertido para emissao por Bayes: P(w|t) ~ P(t|sig) / P(t).

------------------------------------------------------------------------- BIO

Variante IOB2: todo span abre com B-, continua com I-, e O fora. IOB1 so poe B-
na fronteira entre spans adjacentes do mesmo tipo, o que torna a contagem
ambigua -- em IOB2 o numero de entidades de um tipo e o numero de tags B-.

Spans aninhados: BIO plano nao representa AnatomicalSite dentro de Symptom
('lower quadrant abdominal pain'). Por isso ha duas camadas -- camada 0 e o span
mais externo, camada 1 o aninhado. Duas bastam para o esquema do doc 01.
"""
import argparse
import csv
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "model", "hmm_pos.json")
DEFAULT_CASES = os.path.join(HERE, "..", "..", "..", "sample", "cases.csv")

csv.field_size_limit(10 ** 7)


# ============================================================== tokenizacao ==
# Os offsets de caractere sao preservados: sem eles nao ha como ancorar o span
# no case_text original.
UNITS = ["ng/ml", "ng/dl", "pg/ml", "mg/dl", "g/dl", "mmol/l", "mcg/ml",
         "iu/ml", "u/ml", "u/l", "mm/h", "mmhg", "meq/l", "/ul", "/mm3",
         "au/ml", "mg", "mcg", "kg", "cm", "mm", "ml", "dl", "cc", "iu", "g",
         "l", "%"]
AMBIGUOUS_UNITS = {"g", "l", "cc", "iu", "u"}
_UNIT_ALT = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
NUMBER = r"\d+(?:,\d{3})*(?:\.\d+)?"

TOKEN_RE = re.compile(
    r"""
      (?P<numword>""" + NUMBER + r"""(?:-[A-Za-z][A-Za-z0-9]*)+)        # 44-year-old
    | (?P<numrange>""" + NUMBER + r"""(?:-""" + NUMBER + r""")+)        # 0-0.04
    | (?P<numunit>""" + NUMBER + r""")(?=(?:""" + _UNIT_ALT + r""")\b)  # 6 de "6cm"
    | (?P<unit>(?:""" + _UNIT_ALT + r"""))(?![A-Za-z])
    | (?P<num>""" + NUMBER + r""")
    | (?P<word>[A-Za-z][A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*)               # EUS-FNA
    | (?P<punct>[^\sA-Za-z0-9])
    """,
    re.VERBOSE | re.IGNORECASE)


class Token(object):
    __slots__ = ("text", "start", "end", "index", "tag", "role")

    def __init__(self, text, start, end, index):
        self.text, self.start, self.end, self.index = text, start, end, index
        self.tag = None
        self.role = None      # UNIT | ABBREV | FINITE


def tokenize(text):
    tokens = []
    for m in TOKEN_RE.finditer(text):
        tok = Token(m.group(), m.start(), m.end(), len(tokens))
        if m.lastgroup == "unit":
            prev = tokens[-1] if tokens else None
            glued = prev is not None and prev.end == tok.start \
                and re.match(r"^" + NUMBER + r"$", prev.text)
            if tok.text.lower() not in AMBIGUOUS_UNITS or glued:
                tok.role = "UNIT"
        tokens.append(tok)
    return tokens


def surface(tokens):
    """Texto do span respeitando a colagem original ('6cm' vs '6 cm')."""
    out = []
    for k, tok in enumerate(tokens):
        if k and tokens[k - 1].end != tok.start:
            out.append(" ")
        out.append(tok.text)
    return "".join(out)


# ============================================================ HMM + Viterbi ==
NEG_INF = float("-inf")
FLOOR = -30.0
NUM_RE = re.compile(r"^[\d]+([.,][\d]+)*$")


def shape(word):
    if NUM_RE.match(word):
        return "NUM"
    if word.isupper() and len(word) > 1:
        return "ALLCAPS"
    if word[:1].isupper():
        return "CAP"
    if any(c.isdigit() for c in word):
        return "HASDIGIT"
    if "-" in word:
        return "HYPHEN"
    return "LOWER"


class HMMTagger(object):
    def __init__(self, path=MODEL_PATH):
        if not os.path.exists(path):
            sys.exit("modelo ausente: %s -- rode 'python3 pos_bio.py --treinar'"
                     % path)
        with io.open(path, encoding="utf-8") as fh:
            m = json.load(fh)
        self.tags = m["tags"]
        self.start = m["start"]
        self.log_trans = m["log_trans"]
        self.log_emit = m["log_emit"]
        self.log_prior = m["log_prior"]
        self.log_sig = m["log_sig"]
        self.max_suffix = m["max_suffix"]

    def log_emission(self, word, tag):
        row = self.log_emit.get(word.lower())
        if row is not None:
            return row.get(tag, FLOOR)
        w = word.lower()
        for n in range(min(self.max_suffix, len(w)), 0, -1):
            row = self.log_sig.get("suf:" + w[-n:])
            if row:
                return row.get(tag, FLOOR) - self.log_prior[tag]
        row = self.log_sig.get("shape:" + shape(word)) or self.log_sig["*"]
        return row.get(tag, FLOOR) - self.log_prior[tag]

    def viterbi(self, words, constraints=None):
        """Sequencia de etiquetas mais provavel. constraints[i]: set ou None."""
        n = len(words)
        if n == 0:
            return []
        constraints = constraints or [None] * n

        def allowed(i):
            c = constraints[i]
            return [t for t in self.tags if t in c] if c else self.tags

        delta = [{} for _ in range(n)]
        psi = [{} for _ in range(n)]

        row0 = self.log_trans[self.start]
        for t in allowed(0):
            delta[0][t] = row0[t] + self.log_emission(words[0], t)
            psi[0][t] = None

        for i in range(1, n):
            for t in allowed(i):
                best_s, best_v = None, NEG_INF
                for s, prev_v in delta[i - 1].items():
                    v = prev_v + self.log_trans[s][t]
                    if v > best_v:
                        best_v, best_s = v, s
                delta[i][t] = best_v + self.log_emission(words[i], t)
                psi[i][t] = best_s

        last = max(delta[n - 1], key=delta[n - 1].get)
        out = [last]
        for i in range(n - 1, 0, -1):
            last = psi[i][last]
            out.append(last)
        out.reverse()
        return out

    def tag(self, tokens, constraints=None):
        for tok, t in zip(tokens, self.viterbi([x.text for x in tokens],
                                               constraints)):
            tok.tag = t
        return tokens


# ============================== restricoes e reparos de etiqueta =============
PARTICIPLE_RE = re.compile(r".*(ed|ing|en)$", re.IGNORECASE)
ABBREV_RE = re.compile(r"^[A-Z][A-Z0-9-]{1,6}$")
MED_NOUN_RE = re.compile(
    r".*(ectomy|otomy|ostomy|itis|osis|oma|omas|pathy|emia|aemia|plasty|scopy|"
    r"graphy|gram|algia|megaly|penia|uria|texture|plasia|trophy|centesis)$",
    re.IGNORECASE)
AUX = {"be", "am", "is", "are", "was", "were", "been", "being", "has", "have",
       "had", "do", "does", "did", "will", "would", "shall", "should", "can",
       "could", "may", "might", "must"}
RELATIVE = {"which", "that", "who", "whom"}


def build_constraints(tokens, tagger, noun_heads):
    """Fatos conhecidos antes de decodificar reduzem o espaco de estados.

      unidade         -> X     'ng/mL' como NOUN e absorvido pelo sintagma
      sigla           -> NOUN  'CT', 'EUS' saem etiquetados X pelo modelo
      nucleo clinico  -> NOUN  'cyst', 'pancreatectomy' vao para VERB/ADJ e o
                               sintagma fica sem nucleo
      pontuacao       -> '.'   o Treebank escreve '-LRB-', entao '(' vira NOUN
    """
    cons = []
    for tok in tokens:
        if tok.role == "UNIT":
            cons.append({"X"})
        elif not any(c.isalnum() for c in tok.text):
            cons.append({"."})
        elif ABBREV_RE.match(tok.text) and tok.text.isupper():
            tok.role = "ABBREV"
            cons.append({"NOUN"})
        elif tok.text.lower() in noun_heads:
            cons.append({"NOUN"})
        elif tok.text.lower() not in tagger.log_emit and MED_NOUN_RE.match(tok.text):
            cons.append({"NOUN"})
        else:
            cons.append(None)
    return cons


def repair_tags(tokens):
    """Correcoes que so podem ser decididas com a sequencia ja decodificada."""
    applied = []

    # R-relverb: apos pronome relativo, palavra em -ed/-ing e verbo.
    # 'which revealed normal echotexture' -- sem isto o verbo entra no sintagma.
    for i, tok in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]
        if tok.text.lower() in RELATIVE and nxt.tag in ("ADJ", "NOUN") \
                and PARTICIPLE_RE.match(nxt.text):
            applied.append(("R-relverb", nxt.text, nxt.tag, "VERB"))
            nxt.tag, nxt.role, tok.tag = "VERB", "FINITE", "PRON"

    # R-passiva: participio apos auxiliar e o verbo principal, nao modificador.
    # 'was discharged home' viraria um sintagma nominal so.
    for i, tok in enumerate(tokens[:-1]):
        if tok.text.lower() in AUX and tok.tag == "VERB":
            nxt = tokens[i + 1]
            if PARTICIPLE_RE.match(nxt.text) and nxt.tag in ("VERB", "ADJ"):
                if nxt.tag != "VERB":
                    applied.append(("R-passiva", nxt.text, nxt.tag, "VERB"))
                nxt.tag, nxt.role = "VERB", "FINITE"

    # R-premod: VERB nao-participio seguido de participio/ADJ que leva a um NOUN
    # e premodificador nominal. 'contrast enhanced computed tomography' -- sem
    # isto o sintagma sai 'enhanced computed tomography'.
    for tok in tokens:
        if tok.tag != "VERB" or PARTICIPLE_RE.match(tok.text) \
                or tok.text.lower() in AUX:
            continue
        j, seen = tok.index + 1, False
        while j < len(tokens) and _is_premod(tokens[j]):
            seen, j = True, j + 1
        if seen and j < len(tokens) and tokens[j].tag == "NOUN":
            applied.append(("R-premod", tok.text, tok.tag, "NOUN"))
            tok.tag = "NOUN"
    return applied


def _is_premod(tok):
    return tok.tag == "ADJ" or (tok.tag == "VERB"
                                and bool(PARTICIPLE_RE.match(tok.text)))


# ======================================================= sintagmas nominais ==
def chunk_nps(tokens):
    """NP := DET? (NUM UNIT?)? MOD* NOUN+,  MOD := ADJ | NOUN | participio.

    O participio conta como modificador para que 'contrast enhanced computed
    tomography' saia como um sintagma so. O par NUM+UNIT entra no span ('a 6 cm
    cystic lesion') porque a dimensao e atributo do achado, nao entidade.
    """
    chunks, i, n = [], 0, len(tokens)
    while i < n:
        j = _match_np(tokens, i)
        if j > i:
            chunks.append(tokens[i:j])
            i = j
        else:
            i += 1
    return [p for ch in chunks for p in _split_coordination(ch)]


def _is_mod(tok):
    if tok.role in ("UNIT", "FINITE"):
        return False
    return tok.tag in ("ADJ", "NOUN") or _is_premod(tok)


def _match_np(tokens, i):
    j, n = i, len(tokens)
    if j < n and tokens[j].tag == "DET":
        j += 1
    if j < n and tokens[j].tag == "NUM" and tokens[j].role != "UNIT":
        j += 1
        if j < n and tokens[j].role == "UNIT":
            j += 1
    mod_start = j
    while j < n and _is_mod(tokens[j]):
        j += 1
    if j >= n or tokens[j].tag != "NOUN" or tokens[j].role == "UNIT":
        k = j - 1
        while k >= mod_start and (tokens[k].tag != "NOUN"
                                  or tokens[k].role == "UNIT"):
            k -= 1
        return k + 1 if k >= mod_start else i
    while j < n and tokens[j].tag == "NOUN" and tokens[j].role != "UNIT":
        j += 1
    return j


def _split_coordination(chunk):
    """'right flank and lower quadrant abdominal pain' e 'nausea and
    constipation' sao dois candidatos cada, nao um sintagma longo."""
    pieces, cur = [], []
    for tok in chunk:
        if tok.tag == "CONJ" or tok.text == ",":
            if cur:
                pieces.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        pieces.append(cur)
    return pieces or [chunk]


# ============================================================= lexico minimo ==
# Rudimentar de proposito: o que este arquivo demonstra e a fronteira do span,
# nao a cobertura do dicionario. O tipo restringe-se a lista fechada do doc 01.
TERMS = {
    "Symptom": ["pain", "abdominal pain", "chest pain", "headache", "nausea",
                "vomiting", "constipation", "diarrhea", "fever", "chills",
                "fatigue", "weakness", "dyspnea", "cough", "weight loss",
                "night sweating", "dizziness", "seizure", "jaundice", "rash",
                "swelling", "edema", "hematuria", "myalgia", "sore throat"],
    "Finding": ["lesion", "mass", "cyst", "nodule", "tumor", "abscess",
                "effusion", "infiltrate", "opacity", "calcification",
                "thrombus", "hemorrhage", "hematoma", "tenderness", "murmur",
                "hepatomegaly", "splenomegaly", "lymphadenopathy",
                "echotexture", "septations", "mucin", "malignancy", "necrosis",
                "inflammation", "ascites", "pneumothorax"],
    "Exam": ["computed tomography", "ct scan", "magnetic resonance imaging",
             "ultrasound", "radiograph", "echocardiogram", "angiography",
             "endoscopy", "colonoscopy", "bronchoscopy", "biopsy",
             "fine needle aspiration", "electrocardiogram", "blood count",
             "complete blood count", "culture", "urinalysis", "pathology",
             "cytology", "carcinoembryonic antigen", "carbohydrate antigen",
             "troponin", "creatine kinase", "d-dimer", "ferritin",
             "hemoglobin", "platelet count", "creatinine", "bilirubin",
             "c-reactive protein", "donath-landsteiner test", "coombs test"],
    "Diagnosis": ["pancreatitis", "appendicitis", "cholecystitis", "hepatitis",
                  "meningitis", "myocarditis", "pneumonia", "tuberculosis",
                  "sepsis", "carcinoma", "adenocarcinoma", "lymphoma",
                  "leukemia", "sarcoma", "melanoma", "neoplasm",
                  "cystic neoplasm", "mucinous pancreatic cystic neoplasm",
                  "gastric duplication cyst", "diabetes", "diabetes mellitus",
                  "hypertension", "asthma", "myocardial infarction", "stroke",
                  "pulmonary embolism", "anemia", "cirrhosis",
                  "paroxysmal cold hemoglobinuria"],
    "Medication": ["oseltamivir", "arbidol", "moxifloxacin", "prednisone",
                   "dexamethasone", "aspirin", "heparin", "warfarin",
                   "metformin", "insulin", "furosemide", "omeprazole",
                   "morphine", "paracetamol", "ibuprofen", "ceftriaxone",
                   "vancomycin", "azithromycin", "amoxicillin",
                   "metronidazole", "rituximab", "methotrexate",
                   "immunoglobulin", "antibiotics", "corticosteroids"],
    "Treatment": ["surgery", "resection", "open resection", "pancreatectomy",
                  "distal pancreatectomy", "appendectomy", "cholecystectomy",
                  "gastrectomy", "colectomy", "nephrectomy", "splenectomy",
                  "laparotomy", "laparoscopy", "craniotomy", "drainage",
                  "stenting", "embolization", "transfusion",
                  "blood transfusion", "dialysis", "chemotherapy",
                  "radiotherapy", "intubation", "mechanical ventilation",
                  "exploration", "valve replacement"],
    "AnatomicalSite": ["abdomen", "chest", "head", "neck", "flank", "quadrant",
                       "stomach", "pancreas", "liver", "spleen", "kidney",
                       "gallbladder", "duodenum", "colon", "rectum",
                       "appendix", "esophagus", "lung", "heart", "aorta",
                       "artery", "vein", "brain", "sylvian fissure",
                       "lesser sac", "posterior wall", "bladder", "uterus",
                       "breast", "thyroid", "skin", "bone", "spine", "pleura",
                       "bile duct"],
    "History": ["past medical history", "medical history", "family history",
                "surgical history", "smoking history"],
    "Outcome": ["discharge", "death", "recovery", "resolution", "recurrence",
                "remission", "complication", "improvement"],
}

TERM_INDEX = {tuple(t.lower().split()): typ
              for typ, terms in TERMS.items() for t in terms}
MAX_TERM_LEN = max(len(k) for k in TERM_INDEX)
HEAD_NOUNS = {k[-1] for k in TERM_INDEX}
MODIFIERS = {"left", "right", "bilateral", "upper", "lower", "proximal",
             "distal", "anterior", "posterior", "medial", "lateral"}


def lookup(words):
    """Casamento mais longo. Devolve (tipo, inicio, fim) ou None."""
    for size in range(min(MAX_TERM_LEN, len(words)), 0, -1):
        for i in range(0, len(words) - size + 1):
            typ = TERM_INDEX.get(tuple(words[i:i + size]))
            if typ:
                return typ, i, i + size
    return None


# ==================================================================== spans ==
class Span(object):
    __slots__ = ("type", "tokens", "layer")

    def __init__(self, type_, tokens, layer):
        self.type, self.tokens, self.layer = type_, tokens, layer

    @property
    def i0(self):
        return self.tokens[0].index

    @property
    def i1(self):
        return self.tokens[-1].index + 1


def find_spans(chunks):
    """Camada 0: o sintagma tipado pelo lexico.
    Camada 1: um AnatomicalSite dentro de um span de outro tipo."""
    spans = []
    for ch in chunks:
        words = [t.text.lower() for t in ch]
        hit = lookup(words)
        if hit:
            spans.append(Span(hit[0], ch, 0))

    nested = []
    for sp in spans:
        if sp.type == "AnatomicalSite":
            continue
        words = [t.text.lower() for t in sp.tokens]
        for size in range(min(MAX_TERM_LEN, len(words)), 0, -1):
            done = False
            for i in range(0, len(words) - size + 1):
                if TERM_INDEX.get(tuple(words[i:i + size])) != "AnatomicalSite":
                    continue
                while i > 0 and words[i - 1] in MODIFIERS:
                    i, size = i - 1, size + 1
                sub = sp.tokens[i:i + size]
                if len(sub) < len(sp.tokens):
                    nested.append(Span("AnatomicalSite", sub, 1))
                done = True
                break
            if done:
                break
    return sorted(spans + nested, key=lambda s: (s.i0, s.layer))


def encode_bio(tokens, spans, n_layers=2):
    """IOB2, uma coluna por camada."""
    layers = [["O"] * len(tokens) for _ in range(n_layers)]
    for sp in spans:
        if sp.layer < n_layers:
            for k, tok in enumerate(sp.tokens):
                layers[sp.layer][tok.index] = \
                    ("B-" if k == 0 else "I-") + sp.type
    return [[t.text, t.tag or "_"] + [layers[l][t.index] for l in range(n_layers)]
            for t in tokens]


# ================================================================ pipeline ===
def process(case_text, tagger):
    tokens = tokenize(case_text)
    cons = build_constraints(tokens, tagger, HEAD_NOUNS)
    tagger.tag(tokens, cons)
    repairs = repair_tags(tokens)
    chunks = chunk_nps(tokens)
    spans = find_spans(chunks)
    return tokens, chunks, spans, repairs


# ================================================================== treino ===
def train(out_path=MODEL_PATH):
    """Treina o HMM no Penn Treebank. Unico ponto que usa NLTK.

        pip install nltk
        python3 -c "import nltk; nltk.download('treebank');
                    nltk.download('universal_tagset')"
    """
    from collections import Counter, defaultdict
    from nltk.corpus import treebank

    sents = list(treebank.tagged_sents(tagset="universal"))
    START, ALPHA, RARE_MAX, MAX_SUFFIX = "<s>", 0.1, 5, 3
    tags = sorted({t for s in sents for _, t in s})

    trans, emit = defaultdict(Counter), defaultdict(Counter)
    tag_count, word_count = Counter(), Counter()
    for sent in sents:
        prev = START
        for word, tag in sent:
            trans[prev][tag] += 1
            emit[tag][word.lower()] += 1
            tag_count[tag] += 1
            word_count[word.lower()] += 1
            prev = tag

    def signatures(word):
        w = word.lower()
        return ["suf:" + w[-n:] for n in range(min(MAX_SUFFIX, len(w)), 0, -1)] \
            + ["shape:" + shape(word), "*"]

    sig_counts = defaultdict(Counter)
    for sent in sents:
        for word, tag in sent:
            if word_count[word.lower()] <= RARE_MAX:
                for sig in signatures(word):
                    sig_counts[sig][tag] += 1

    log_trans = {}
    for prev in [START] + tags:
        total = sum(trans[prev].values())
        log_trans[prev] = {t: math.log((trans[prev][t] + ALPHA)
                                       / (total + ALPHA * len(tags)))
                           for t in tags}
    log_emit = defaultdict(dict)
    for tag, counter in emit.items():
        for word, c in counter.items():
            log_emit[word][tag] = math.log(c / tag_count[tag])
    total = sum(tag_count.values())

    model = {
        "tags": tags, "start": START, "log_trans": log_trans,
        "log_emit": dict(log_emit),
        "log_prior": {t: math.log(tag_count[t] / total) for t in tags},
        "log_sig": {sig: {t: math.log(c / sum(cnt.values()))
                          for t, c in cnt.items()}
                    for sig, cnt in sig_counts.items()},
        "max_suffix": MAX_SUFFIX,
        "corpus": "nltk treebank (tagset universal)",
        "n_sents": len(sents), "n_tokens": sum(len(s) for s in sents),
    }
    with io.open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(model, separators=(",", ":")))
    print("modelo: %s  (%d sentencas, %d tokens, vocabulario %d)"
          % (out_path, model["n_sents"], model["n_tokens"], len(log_emit)))


# ===================================================================== main ==
def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case-id")
    ap.add_argument("--cases", default=DEFAULT_CASES)
    ap.add_argument("--out", help="grava o CoNLL neste arquivo")
    ap.add_argument("--show-pos", action="store_true",
                    help="mostra a sequencia etiquetada")
    ap.add_argument("--show-np", action="store_true",
                    help="mostra os sintagmas nominais")
    ap.add_argument("--treinar", action="store_true",
                    help="regera model/hmm_pos.json a partir do NLTK")
    args = ap.parse_args()

    if args.treinar:
        train()
        return
    if not args.case_id:
        ap.error("informe --case-id (ou --treinar)")
    if not os.path.exists(args.cases):
        sys.exit("nao encontrei %s -- baixe sample/cases.csv do repositorio da "
                 "disciplina" % args.cases)

    with io.open(args.cases, encoding="utf-8") as fh:
        cases = {r["case_id"]: r for r in csv.DictReader(fh)}
    if args.case_id not in cases:
        sys.exit("case_id %s nao esta em %s" % (args.case_id, args.cases))

    tagger = HMMTagger()
    tokens, chunks, spans, repairs = process(cases[args.case_id]["case_text"],
                                             tagger)

    sys.stderr.write("%s: %d tokens, %d sintagmas, %d spans\n"
                     % (args.case_id, len(tokens), len(chunks), len(spans)))
    if repairs:
        sys.stderr.write("reparos: %s\n" % ", ".join(
            "%s %s:%s->%s" % r for r in repairs))

    if args.show_pos:
        print(" ".join("%s/%s" % (t.text, t.tag) for t in tokens))
        print()
    if args.show_np:
        for ch in chunks:
            print("[%s]" % surface(ch))
        print()

    rows = encode_bio(tokens, spans)
    text = "\n".join("\t".join(r) for r in rows) + "\n"
    if args.out:
        with io.open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        sys.stderr.write("escrito em %s\n" % args.out)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
