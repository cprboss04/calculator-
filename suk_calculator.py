# 🫧 Liquid Calc - All-in-One Calculator Telegram Bot (no external APIs)
#
# Setup (Termux):
#     pip install python-telegram-bot
#     export BOT_TOKEN="token_from_BotFather"
#     python calc_bot_final.py
import ast
import html
import math
import operator as op
import os
import re
import statistics as st
import sys
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, PicklePersistence, filters)

def load_env(name=".env"):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()
TOKEN = os.getenv("BOT_TOKEN", "")
G = 9.8
HEAD = "🫧 ✦ 𝗟𝗜𝗤𝗨𝗜𝗗 𝗖𝗔𝗟𝗖 ✦ 🫧"
esc = html.escape
rad, deg = math.radians, math.degrees


def B(text, data):
    return InlineKeyboardButton(text, callback_data=data)


def M(rows):
    return InlineKeyboardMarkup(rows)


def m(x):
    return f"₹{x:,.2f}"


def g(x):
    return f"{x:.6g}"


# ------------------------------------------------------------ safe evaluator
OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
       ast.Pow: op.pow, ast.Mod: op.mod, ast.FloorDiv: op.floordiv,
       ast.USub: op.neg, ast.UAdd: op.pos}
FUNCS = {
    "sin": lambda x: math.sin(rad(x)), "cos": lambda x: math.cos(rad(x)),
    "tan": lambda x: math.tan(rad(x)), "asin": lambda x: deg(math.asin(x)),
    "acos": lambda x: deg(math.acos(x)), "atan": lambda x: deg(math.atan(x)),
    "sqrt": math.sqrt, "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x),
    "log": math.log10, "ln": math.log, "exp": math.exp, "abs": abs,
    "fact": lambda x: math.factorial(int(x)) if x <= 3000 else (_ for _ in ()).throw(ValueError("Max 3000")),
    "round": round,
}


def ev(n):
    if isinstance(n, ast.Expression):
        return ev(n.body)
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return n.value
    if isinstance(n, ast.Name) and n.id in ("pi", "e"):
        return getattr(math, n.id)
    if isinstance(n, ast.BinOp) and type(n.op) in OPS:
        a, b = ev(n.left), ev(n.right)
        if isinstance(n.op, ast.Pow) and abs(b) > 1000:
            raise ValueError("Power bahut bada hai")
        return OPS[type(n.op)](a, b)
    if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
        return OPS[type(n.op)](ev(n.operand))
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS:
        return FUNCS[n.func.id](*[ev(a) for a in n.args])
    raise ValueError("Invalid expression")


def calc(expr):
    expr = (expr.replace("^", "**").replace("×", "*").replace("÷", "/")
            .replace("π", "pi").replace(",", ""))
    r = ev(ast.parse(expr.strip(), mode="eval"))
    if isinstance(r, float):
        r = round(r, 10)
        if r == int(r) and abs(r) < 1e15:
            r = int(r)
    return r


# ------------------------------------------------------------ registry
CALCS, CATS, CAT_OF = {}, {}, {}
CAT_T = {"fin": "💎 Finance", "sci": "🔬 Scientific", "geo": "📐 Geometry & Math",
         "phy": "⚛️ Physics", "day": "🧩 Daily Use", "cnv": "🔄 Converter"}


def reg(cat, key, title, fields, fn):
    CALCS[key] = (title, fields, fn)
    CATS.setdefault(cat, []).append(key)
    CAT_OF[key] = cat


# ---- Finance
def sip(p, r, y):
    i, n = r / 1200, int(y * 12)
    fv = p * n if i == 0 else p * (((1 + i) ** n - 1) / i) * (1 + i)
    return f"Invested: {m(p * n)}\nReturns: {m(fv - p * n)}\nMaturity: {m(fv)}"


def stepup(p, r, y, s):
    i, bal, inv, cur = r / 1200, 0.0, 0.0, p
    for k in range(1, int(y * 12) + 1):
        bal = (bal + cur) * (1 + i)
        inv += cur
        if k % 12 == 0:
            cur *= 1 + s / 100
    return f"Invested: {m(inv)}\nReturns: {m(bal - inv)}\nMaturity: {m(bal)}"


def lump(p, r, y):
    fv = p * (1 + r / 100) ** y
    return f"Invested: {m(p)}\nReturns: {m(fv - p)}\nMaturity: {m(fv)}"


def swp(c, w, r, y):
    i, bal, drawn = r / 1200, c, 0.0
    for k in range(1, int(y * 12) + 1):
        bal = bal * (1 + i) - w
        if bal <= 0:
            return (f"⚠️ Corpus {k} mahine ({k / 12:.1f} saal) mein khatam\n"
                    f"Total nikala: {m(drawn + w + bal)}")
        drawn += w
    return f"Total nikala: {m(drawn)}\nBacha corpus: {m(bal)}"


def emi(p, r, y):
    i, n = r / 1200, int(y * 12)
    e = p / n if i == 0 else p * i * (1 + i) ** n / ((1 + i) ** n - 1)
    return f"EMI: {m(e)}/month\nTotal Interest: {m(e * n - p)}\nTotal Payment: {m(e * n)}"


def ci(p, r, t, n=1):
    a = p * (1 + r / (100 * n)) ** (n * t)
    return f"Interest: {m(a - p)}\nTotal: {m(a)}"


def cagr(a, b, y):
    return (f"CAGR: {((b / a) ** (1 / y) - 1) * 100:.2f}% p.a.\n"
            f"Absolute return: {(b / a - 1) * 100:.2f}%")


def infl(a, r, y):
    return (f"Future cost: {m(a * (1 + r / 100) ** y)}\n"
            f"Aaj ke {m(a)} ki value tab: {m(a / (1 + r / 100) ** y)}")


def gst(a, r):
    base = a * 100 / (100 + r)
    return (f"GST add: {m(a * r / 100)} → Total {m(a * (1 + r / 100))}\n"
            f"GST hatao: Base {m(base)}, GST {m(a - base)}")


def lic(prem, term, sa, bonus):
    mat = sa + sa / 1000 * bonus * term
    lo, hi = -0.5, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        fv = sum(prem * (1 + mid) ** (term - k) for k in range(int(term)))
        lo, hi = (mid, hi) if fv < mat else (lo, mid)
    return (f"Total Premium: {m(prem * term)}\nMaturity (approx): {m(mat)}\n"
            f"Return (IRR): {mid * 100:.2f}% p.a.\n\n"
            "Note: Sirf andaza. Asli bonus LIC declare karta hai.")


reg("fin", "sip", "📈 SIP", ["Monthly amount ₹", "Return % p.a.", "Saal"], sip)
reg("fin", "stepup", "🪜 Step-up SIP", ["Monthly amount ₹", "Return %", "Saal", "Yearly badhotri %"], stepup)
reg("fin", "lump", "💰 Lumpsum", ["Amount ₹", "Return %", "Saal"], lump)
reg("fin", "swp", "💸 SWP", ["Corpus ₹", "Monthly withdrawal ₹", "Return %", "Saal"], swp)
reg("fin", "emi", "🏦 EMI", ["Loan ₹", "Interest % p.a.", "Saal"], emi)
reg("fin", "si", "🧾 Simple Interest", ["Principal ₹", "Rate %", "Saal"],
    lambda p, r, t: f"Interest: {m(p * r * t / 100)}\nTotal: {m(p + p * r * t / 100)}")
reg("fin", "ci", "📊 Compound Int.",
    ["Principal ₹", "Rate %", "Saal", "Saal mein kitni baar compound (1/2/4/12)"], ci)
reg("fin", "fd", "🏧 FD (quarterly)", ["Amount ₹", "Rate %", "Saal"], lambda p, r, t: ci(p, r, t, 4))
reg("fin", "lic", "🛡️ LIC Endowment",
    ["Annual premium ₹", "Term (saal)", "Sum assured ₹", "Bonus per ₹1000/saal"], lic)
reg("fin", "cagr", "🚀 CAGR", ["Starting value", "Ending value", "Saal"], cagr)
reg("fin", "infl", "🎈 Inflation", ["Aaj ki value ₹", "Inflation %", "Saal"], infl)
reg("fin", "gst", "🧮 GST", ["Amount ₹", "GST %"], gst)


# ---- Scientific
def trig(a):
    s, c = round(FUNCS["sin"](a), 10), round(FUNCS["cos"](a), 10)
    t = round(FUNCS["tan"](a), 10)
    vals = [("sin", s), ("cos", c), ("tan", t),
            ("cot", c / s if s else None), ("sec", 1 / c if c else None),
            ("cosec", 1 / s if s else None)]
    return "\n".join(
        f"{n}({g(a)}°) = {g(v) if v is not None and abs(v) < 1e12 else 'undefined'}"
        for n, v in vals)


def fact(n):
    if n < 0 or n > 3000:
        raise ValueError("n 0 se 3000 ke beech rakho")
    s = str(math.factorial(int(n)))
    short = s if len(s) < 30 else f"{s[0]}.{s[1:6]}e+{len(s) - 1}"
    return f"{int(n)}! = {short}"


def quad(a, b, c):
    if a == 0:
        raise ValueError("a zero nahi ho sakta")
    d = b * b - 4 * a * c
    if d >= 0:
        return (f"D = {g(d)}\nx₁ = {g((-b + math.sqrt(d)) / (2 * a))}\n"
                f"x₂ = {g((-b - math.sqrt(d)) / (2 * a))}")
    return f"D = {g(d)} (complex)\nx = {g(-b / (2 * a))} ± {g(math.sqrt(-d) / (2 * abs(a)))}i"


def prime(n):
    n = int(n)
    if n < 2 or n > 10 ** 12:
        raise ValueError("n 2 se 10^12 ke beech rakho")
    f, x, d = [], n, 2
    while d * d <= x:
        while x % d == 0:
            f.append(d)
            x //= d
        d += 1
    if x > 1:
        f.append(x)
    return (f"{n} {'prime hai ✅' if f == [n] else 'prime nahi hai'}\n"
            f"Prime factors: {' × '.join(map(str, f))}")


def stats(t):
    v = [float(x) for x in t.replace(",", " ").split()]
    if not v:
        raise ValueError("Kuch numbers do")
    mo = st.multimode(v)
    r = (f"Count: {len(v)} | Sum: {g(sum(v))}\nMean: {g(st.mean(v))}\n"
         f"Median: {g(st.median(v))}\nMode: {g(mo[0]) if len(mo) < len(v) else 'none'}\n"
         f"Min: {g(min(v))} | Max: {g(max(v))}\nStd Dev (pop): {g(st.pstdev(v))}")
    return r + (f"\nStd Dev (sample): {g(st.stdev(v))}" if len(v) > 1 else "")


reg("sci", "expr", "⌨️ Expression", ["~Expression (jaise sin(30)+2^3)"], lambda t: f"{t} = {calc(t)}")
reg("sci", "trig", "📐 Trigonometry", ["Angle (degrees)"], trig)
reg("sci", "fact", "❗ Factorial", ["n"], fact)
reg("sci", "ncr", "🎲 nCr / nPr", ["n", "r"],
    lambda n, r: f"nCr = {math.comb(int(n), int(r))}\nnPr = {math.perm(int(n), int(r))}")
reg("sci", "log", "📉 Logarithm", ["x"],
    lambda x: f"log₁₀ = {g(math.log10(x))}\nln = {g(math.log(x))}\nlog₂ = {g(math.log2(x))}")
reg("sci", "pow", "⚡ Powers & Roots", ["x"],
    lambda x: (f"x² = {g(x ** 2)}\nx³ = {g(x ** 3)}\n√x = {g(math.sqrt(x))}\n"
               f"∛x = {g(FUNCS['cbrt'](x))}\n1/x = {g(1 / x)}"))
reg("sci", "quad", "🧩 Quadratic", ["a", "b", "c"], quad)
reg("sci", "base", "💻 Number Base", ["Decimal number"],
    lambda n: f"Binary: {int(n):b}\nOctal: {int(n):o}\nHex: {int(n):X}")
reg("sci", "prime", "🔢 Prime & Factors", ["n"], prime)
reg("sci", "gcd", "🔗 HCF & LCM", ["a", "b"],
    lambda a, b: f"HCF = {math.gcd(int(a), int(b))}\nLCM = {math.lcm(int(a), int(b))}")
reg("sci", "stats", "📊 Statistics", ["~Numbers (space se: 4 8 15 16)"], stats)


# ---- Geometry & Math
def tri(a, b, c):
    if not (a + b > c and b + c > a and a + c > b):
        raise ValueError("Yeh triangle ban nahi sakta")
    s = (a + b + c) / 2
    return f"Perimeter = {g(a + b + c)}\nArea = {g(math.sqrt(s * (s - a) * (s - b) * (s - c)))}"


reg("geo", "circle", "⭕ Circle", ["Radius"],
    lambda r: f"Area = {g(math.pi * r * r)}\nCircumference = {g(2 * math.pi * r)}\nDiameter = {g(2 * r)}")
reg("geo", "rect", "▭ Rectangle", ["Length", "Breadth"],
    lambda l, b: f"Area = {g(l * b)}\nPerimeter = {g(2 * (l + b))}\nDiagonal = {g(math.hypot(l, b))}")
reg("geo", "tri", "🔺 Triangle (3 sides)", ["Side a", "Side b", "Side c"], tri)
reg("geo", "sphere", "🔮 Sphere", ["Radius"],
    lambda r: f"Volume = {g(4 / 3 * math.pi * r ** 3)}\nSurface = {g(4 * math.pi * r * r)}")
reg("geo", "cyl", "🥫 Cylinder", ["Radius", "Height"],
    lambda r, h: (f"Volume = {g(math.pi * r * r * h)}\nCurved SA = {g(2 * math.pi * r * h)}\n"
                  f"Total SA = {g(2 * math.pi * r * (r + h))}"))
reg("geo", "cone", "🍦 Cone", ["Radius", "Height"],
    lambda r, h: (f"Slant = {g(math.hypot(r, h))}\nVolume = {g(math.pi * r * r * h / 3)}\n"
                  f"Total SA = {g(math.pi * r * (r + math.hypot(r, h)))}"))
reg("geo", "pyth", "📏 Pythagoras", ["Side a", "Side b"],
    lambda a, b: f"Hypotenuse c = {g(math.hypot(a, b))}\nAngle A = {g(deg(math.atan2(a, b)))}°")
reg("geo", "ap", "➕ AP", ["First term a", "Common diff d", "n"],
    lambda a, d, n: f"nth term = {g(a + (n - 1) * d)}\nSum = {g(n / 2 * (2 * a + (n - 1) * d))}")
reg("geo", "gp", "✖️ GP", ["First term a", "Common ratio r", "n"],
    lambda a, r, n: (f"nth term = {g(a * r ** (n - 1))}\n"
                     f"Sum = {g(a * n if r == 1 else a * (r ** n - 1) / (r - 1))}"))


# ---- Daily use
def age(t):
    d, mo, y = [int(x) for x in re.split(r"[-/. ]+", t.strip())]
    b, td = date(y, mo, d), date.today()
    if b > td:
        raise ValueError("Birth date future ki nahi ho sakti")
    yrs = td.year - b.year - ((td.month, td.day) < (b.month, b.day))
    mns = (td.month - b.month - (td.day < b.day)) % 12

    def bday(year):
        try:
            return date(year, b.month, b.day)
        except ValueError:
            return date(year, 3, 1)

    nb = bday(td.year)
    if nb < td:
        nb = bday(td.year + 1)
    nxt = "Aaj birthday hai 🎉" if nb == td else f"Agla birthday: {(nb - td).days} din baad 🎂"
    return f"Umar: {yrs} saal {mns} mahine\nTotal din: {(td - b).days:,}\n{nxt}"


def bmi(kg, cm):
    v = kg / (cm / 100) ** 2
    cat = "Underweight" if v < 18.5 else "Normal" if v < 25 else "Overweight" if v < 30 else "Obese"
    return f"BMI = {v:.1f} ({cat})\n\nNote: BMI sirf general guide hai, doctor ki salah nahi."


reg("day", "disc", "🏷️ Discount", ["Price ₹", "Discount %"],
    lambda p, d: f"Bachat: {m(p * d / 100)}\nFinal price: {m(p * (1 - d / 100))}")
reg("day", "pct", "％ Percentage", ["a", "b"],
    lambda a, b: f"{g(a)}% of {g(b)} = {g(a * b / 100)}\n{g(a)} is {g(a / b * 100)}% of {g(b)}")
reg("day", "pchg", "📈 % Change", ["Purani value", "Nayi value"],
    lambda a, b: f"Change: {(b - a) / a * 100:+.2f}%")
reg("day", "bmi", "🏃 BMI", ["Weight (kg)", "Height (cm)"], bmi)
reg("day", "age", "🎂 Age", ["~Birth date (DD-MM-YYYY)"], age)
reg("day", "split", "🍽️ Bill Split", ["Bill ₹", "Tip %", "Kitne log"],
    lambda b, t, n: f"Total: {m(b * (1 + t / 100))}\nPer person: {m(b * (1 + t / 100) / n)}")
reg("day", "fuel", "⛽ Fuel Cost", ["Distance (km)", "Mileage (km/l)", "Petrol ₹/litre"],
    lambda d, mi, p: f"Petrol: {g(d / mi)} L\nKharcha: {m(d / mi * p)}")


# ---- Converter
def conv(unit, table):
    return lambda x: "\n".join([f"{g(x)} {unit} ="] + [f"  {g(x * f)} {u}" for u, f in table.items()])


reg("cnv", "len", "📏 Length", ["Value (metre)"],
    conv("m", {"km": 1e-3, "cm": 100, "mm": 1000, "inch": 39.3701, "ft": 3.28084,
               "yard": 1.09361, "mile": 6.21371e-4}))
reg("cnv", "wt", "⚖️ Weight", ["Value (kg)"],
    conv("kg", {"g": 1000, "quintal": .01, "tonne": .001, "lb": 2.20462, "oz": 35.274}))
reg("cnv", "spd", "🏎️ Speed", ["Value (km/h)"],
    conv("km/h", {"m/s": 1 / 3.6, "mph": .621371, "knot": .539957}))
reg("cnv", "area", "🗺️ Area", ["Value (m²)"],
    conv("m²", {"ft²": 10.7639, "yd²": 1.19599, "acre": 2.47105e-4, "hectare": 1e-4}))
reg("cnv", "vol", "🧪 Volume", ["Value (litre)"],
    conv("L", {"ml": 1000, "m³": .001, "US gallon": .264172}))
reg("cnv", "data", "💾 Data", ["Value (MB)"],
    conv("MB", {"KB": 1024, "GB": 1 / 1024, "TB": 1 / 1048576, "bits": 8388608}))
reg("cnv", "time", "⏱️ Time", ["Value (hours)"],
    conv("hr", {"min": 60, "sec": 3600, "days": 1 / 24, "weeks": 1 / 168}))
reg("cnv", "temp", "🌡️ Temperature", ["Value (°C)"],
    lambda c: f"{g(c)}°C =\n  {g(c * 9 / 5 + 32)} °F\n  {g(c + 273.15)} K")


# ---- Physics
def proj(u, a):
    t = rad(a)
    return (f"Range = {g(u * u * math.sin(2 * t) / G)} m\n"
            f"Max height = {g((u * math.sin(t)) ** 2 / (2 * G))} m\n"
            f"Time = {g(2 * u * math.sin(t) / G)} s")


def rs(t):
    v = [float(x) for x in t.replace(",", " ").split()]
    if not v:
        raise ValueError("Resistance values do")
    return v


reg("phy", "v", "🚀 v = u+at", ["u (m/s)", "a (m/s²)", "t (s)"], lambda u, a, t: f"v = {g(u + a * t)} m/s")
reg("phy", "s", "📍 s = ut+½at²", ["u (m/s)", "a (m/s²)", "t (s)"],
    lambda u, a, t: f"s = {g(u * t + .5 * a * t * t)} m")
reg("phy", "v2", "🏁 v² = u²+2as", ["u (m/s)", "a (m/s²)", "s (m)"],
    lambda u, a, s: f"v = {g(math.sqrt(u * u + 2 * a * s))} m/s")
reg("phy", "force", "💪 Force F=ma", ["m (kg)", "a (m/s²)"], lambda a, b: f"F = {g(a * b)} N")
reg("phy", "mom", "🎯 Momentum", ["m (kg)", "v (m/s)"], lambda a, b: f"p = {g(a * b)} kg·m/s")
reg("phy", "ke", "🔥 Kinetic Energy", ["m (kg)", "v (m/s)"], lambda a, b: f"KE = {g(.5 * a * b * b)} J")
reg("phy", "pe", "🏔️ Potential Energy", ["m (kg)", "h (m)"], lambda a, b: f"PE = {g(a * G * b)} J")
reg("phy", "work", "🛠️ Work", ["F (N)", "d (m)", "angle (°, 0 agar seedha)"],
    lambda f, d, a: f"W = {g(f * d * math.cos(rad(a)))} J")
reg("phy", "power", "⚡ Power", ["Work (J)", "Time (s)"], lambda w, t: f"P = {g(w / t)} W")
reg("phy", "press", "🎈 Pressure", ["Force (N)", "Area (m²)"], lambda f, a: f"P = {g(f / a)} Pa")
reg("phy", "dens", "🧊 Density", ["Mass (kg)", "Volume (m³)"], lambda a, b: f"ρ = {g(a / b)} kg/m³")
reg("phy", "ohm", "🔌 Ohm's Law", ["V (volt)", "R (ohm)"],
    lambda v, r: f"I = {g(v / r)} A\nP = {g(v * v / r)} W")
reg("phy", "rser", "➰ Resistance Series", ["~R values (space se)"], lambda t: f"R = {g(sum(rs(t)))} Ω")
reg("phy", "rpar", "🔀 Resistance Parallel", ["~R values (space se)"],
    lambda t: f"R = {g(1 / sum(1 / x for x in rs(t)))} Ω")
reg("phy", "proj", "🏹 Projectile", ["u (m/s)", "angle (°)"], proj)
reg("phy", "fall", "🍎 Free Fall", ["Height (m)"],
    lambda h: f"Time = {g(math.sqrt(2 * h / G))} s\nSpeed = {g(math.sqrt(2 * G * h))} m/s")
reg("phy", "wave", "🌊 Wave v=fλ", ["f (Hz)", "λ (m)"], lambda f, l: f"v = {g(f * l)} m/s")
reg("phy", "heat", "♨️ Heat Q=mcΔT", ["m (kg)", "c (J/kg·K)", "ΔT (K)"],
    lambda a, c, d: f"Q = {g(a * c * d)} J")
reg("phy", "grav", "🌍 Gravitation", ["m₁ (kg)", "m₂ (kg)", "r (m)"],
    lambda a, b, r: f"F = {g(6.674e-11 * a * b / r ** 2)} N")

# ------------------------------------------------------------ UI
KEYS = [[("C", "C"), ("⌫", "BK"), ("(", "("), (")", ")")],
        [("7", "7"), ("8", "8"), ("9", "9"), ("÷", "/")],
        [("4", "4"), ("5", "5"), ("6", "6"), ("×", "*")],
        [("1", "1"), ("2", "2"), ("3", "3"), ("−", "-")],
        [("0", "0"), (".", "."), ("^", "^"), ("+", "+")],
        [("√", "sqrt("), ("π", "pi"), ("%", "/100"), ("=", "=")],
        [("sin", "sin("), ("cos", "cos("), ("tan", "tan("), ("log", "log(")]]
CANCEL = M([[B("✖️ Cancel", "m")]])
HOME = B("🏠 Menu", "m")


async def send(update, text, kb=None):
    q = update.callback_query
    try:
        if q:
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception as e:
        if "not modified" not in str(e).lower():
            print("SEND ERROR:", e)


def menu(update, ctx):
    n = ctx.user_data.get("n", 0)
    name = (update.effective_user.first_name if update.effective_user else None) or "dost"
    t = (f"{HEAD}\n\nHey <b>{esc(name)}</b> 👋\nKaunsa calculator chahiye? Category chuno 👇\n\n"
         "<i>Ya seedha type karo: 25*4+10</i>")
    if n:
        t += f"\n\n🔥 Tumhari calculations: <b>{n}</b>"
    keys = list(CAT_T)
    rows = [[B(CAT_T[k], "c:" + k) for k in keys[i:i + 2]] for i in range(0, len(keys), 2)]
    rows.append([B("🧮 Glass Keypad", "kp")])
    return t, M(rows)


def cat_view(cat):
    ks = CATS[cat]
    rows = [[B(CALCS[k][0], "s:" + k) for k in ks[i:i + 2]] for i in range(0, len(ks), 2)]
    rows.append([HOME])
    return f"{HEAD}\n\n<b>{CAT_T[cat]}</b>\nKaunsa calculator? 👇", M(rows)


def kp_view(ctx, hist=""):
    e = ctx.user_data.get("kp", "").replace("*", "×").replace("/", "÷")
    rows = [[B(l, "k:" + t) for l, t in r] for r in KEYS] + [[HOME]]
    return (f"{HEAD}\n\n🧮 <b>Glass Keypad</b>\n<blockquote>{esc(e or '0')}\n{esc(hist)}</blockquote>",
            M(rows))


async def prompt(update, ctx):
    job = ctx.user_data["job"]
    title, fields, _ = CALCS[job["key"]]
    i = len(job["vals"])
    done = "".join(
        f"✅ {esc(fields[j].lstrip('~'))}: <b>{esc(g(v) if isinstance(v, float) else v)}</b>\n"
        for j, v in enumerate(job["vals"]))
    t = (f"{HEAD}\n\n<b>{title}</b>\n<blockquote>{done}👉 {esc(fields[i].lstrip('~'))}</blockquote>"
         f"\nStep {i + 1}/{len(fields)} — value bhejo\n"
         "<i>Ek saath kai values space se bhi bhej sakte ho</i>")
    await send(update, t, CANCEL)


async def result(update, ctx, key, body):
    ctx.user_data["n"] = ctx.user_data.get("n", 0) + 1
    cat = CAT_OF[key]
    kb = M([[B("🔁 Dobara", "s:" + key), B("📂 " + CAT_T[cat].split(" ", 1)[1], "c:" + cat)], [HOME]])
    await send(update, f"{HEAD}\n\n🧊 <b>{CALCS[key][0]}</b>\n<blockquote>{esc(body)}</blockquote>", kb)


async def on_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data or ""
    if d == "m":
        ctx.user_data.pop("job", None)
        await send(update, *menu(update, ctx))
    elif d.startswith("c:") and d[2:] in CATS:
        ctx.user_data.pop("job", None)
        await send(update, *cat_view(d[2:]))
    elif d.startswith("s:") and d[2:] in CALCS:
        ctx.user_data["job"] = {"key": d[2:], "vals": []}
        await prompt(update, ctx)
    elif d == "kp":
        ctx.user_data["kp"] = ""
        await send(update, *kp_view(ctx))
    elif d.startswith("k:"):
        tok, e, hist = d[2:], ctx.user_data.get("kp", ""), ""
        if tok == "C":
            e = ""
        elif tok == "BK":
            e = e[:-1]
        elif tok == "=":
            try:
                r = calc(e)
                hist, e = f"= {r}", str(r)
            except Exception:
                hist = "❌ Error"
        else:
            e += tok
        ctx.user_data["kp"] = e
        await send(update, *kp_view(ctx, hist))


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t, job = update.message.text, ctx.user_data.get("job")
    if not job:
        nav = M([[HOME, B("🧮 Keypad", "kp")]])
        try:
            out = f"{HEAD}\n\n<blockquote>{esc(t)} = <b>{esc(str(calc(t)))}</b></blockquote>"
        except Exception:
            out = f"{HEAD}\n\n❌ Samajh nahi aaya. Menu se calculator chuno 👇"
        await send(update, out, nav)
        return
    key = job["key"]
    fields, fn = CALCS[key][1], CALCS[key][2]
    toks, new = t.split(), []
    try:
        while toks and len(job["vals"]) + len(new) < len(fields):
            if fields[len(job["vals"]) + len(new)].startswith("~"):
                new.append(" ".join(toks))
                toks = []
            else:
                new.append(float(toks.pop(0).replace(",", "")))
    except ValueError:
        await send(update, "❌ Sirf number bhejo (jaise 5000 ya 12.5)", CANCEL)
        return
    job["vals"] = job["vals"] + new
    ctx.user_data["job"] = job
    if len(job["vals"]) < len(fields):
        await prompt(update, ctx)
        return
    ctx.user_data.pop("job", None)
    try:
        body = fn(*job["vals"])
    except ZeroDivisionError:
        body = "❌ Zero se divide nahi ho sakta"
    except OverflowError:
        body = "❌ Number bahut bada hai"
    except Exception as e:
        body = f"❌ {e}"
    await result(update, ctx, key, body)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("job", None)
    await send(update, *menu(update, ctx))


async def on_error(update, ctx: ContextTypes.DEFAULT_TYPE):
    print("ERROR:", type(ctx.error).__name__, ctx.error)


def main():
    if not TOKEN:
        sys.exit('Pehle token set karo:  export BOT_TOKEN="tumhara_token"')
    app = Application.builder().token(TOKEN).persistence(PicklePersistence("calcbot.pkl")).build()
    app.add_error_handler(on_error)
    app.add_handler(CommandHandler(["start", "menu", "help"], start))
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print("🫧 Liquid Calc chal raha hai...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
