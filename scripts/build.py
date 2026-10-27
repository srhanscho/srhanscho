"""Build every SVG used by the profile README.

Standard library only, so it runs as-is inside GitHub Actions.

    GITHUB_TOKEN=... python scripts/build.py

With a token it refreshes data/github.json (contribution calendar and
language bytes); without one it renders from the cached file.
"""
import datetime as dt
import json
import math
import os
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DATA = ROOT / "data"
USER = "srhanscho"

# ---- design tokens ----------------------------------------------------------------
BG = "#14121F"       # scan room
MESH = "#3FE8F0"     # wireframe cyan
INK = "#E6F6F7"
FOG = "#7E8AA3"
GRID = "#26304A"
GOLD = "#FFC94A"     # reserved for podiums
HOT = "#CFFBFF"      # scan highlight

MONO = "'Cascadia Code','SF Mono','JetBrains Mono',Consolas,'Liberation Mono',Menlo,monospace"
SANS = "-apple-system,'Segoe UI',system-ui,Roboto,'Helvetica Neue',Arial,sans-serif"

BASE_CSS = f"""
.mono{{font-family:{MONO}}}
.sans{{font-family:{SANS}}}
.eyebrow{{font-family:{MONO};font-size:12px;letter-spacing:3px;fill:{MESH}}}
.label{{font-family:{MONO};font-size:10.5px;letter-spacing:1.6px;fill:{FOG}}}
@media (prefers-reduced-motion:reduce){{.anim{{animation:none!important}}}}
"""

MONTHS = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
MONTHS_LOWER = [m.lower() for m in MONTHS]


def t(s):
    return escape(str(s))


def svg(w, h, body, css="", defs="", frame=True):
    bg = (f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="16" fill="{BG}" stroke="{GRID}"/>'
          if frame else "")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img"><style>{BASE_CSS}{css}</style><defs>{defs}</defs>{bg}{body}</svg>')


def write(name, content):
    (ASSETS / name).write_text(content, encoding="utf-8")


def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + ([cur] if cur else [])


def tspans(lines, x, dy):
    return "".join(f'<tspan x="{x}" dy="{0 if i == 0 else dy}">{t(line)}</tspan>' for i, line in enumerate(lines))


def num(n):
    return f"{n:,}".replace(",", ".")


GLOW = ('<filter id="glow" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="2.2" '
        'result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')


def scan_band(axis, length, thickness):
    """Gradient band used inside a mask to light up the mesh as the laser passes."""
    if axis == "y":
        grad = ('<linearGradient id="band" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" '
                'stop-opacity="0"/><stop offset=".5" stop-color="#fff"/><stop offset="1" stop-color="#fff" '
                'stop-opacity="0"/></linearGradient>')
        rect = f'<rect class="scan anim" x="0" y="{-thickness / 2}" width="{length}" height="{thickness}" fill="url(#band)"/>'
    else:
        grad = ('<linearGradient id="band" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" '
                'stop-opacity="0"/><stop offset=".5" stop-color="#fff"/><stop offset="1" stop-color="#fff" '
                'stop-opacity="0"/></linearGradient>')
        rect = f'<rect class="scan anim" x="{-thickness / 2}" y="0" width="{thickness}" height="{length}" fill="url(#band)"/>'
    return grad, rect


# ---- GitHub data -------------------------------------------------------------------
def gh(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={
        "Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile-build",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_github():
    q = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
        totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    cal = gh("https://api.github.com/graphql", {"query": q, "variables": {"login": USER}})
    cal = cal["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [[d["date"], d["contributionCount"]] for w in cal["weeks"] for d in w["contributionDays"]]

    langs = {}
    repos = gh(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
    for repo in repos:
        if repo["fork"] or repo["archived"]:
            continue
        for lang, size in gh(repo["languages_url"]).items():
            langs[lang] = langs.get(lang, 0) + size
    return {"fetched": dt.date.today().isoformat(), "total": cal["totalContributions"],
            "days": days, "languages": langs}


def load_github():
    cache = DATA / "github.json"
    if os.environ.get("GITHUB_TOKEN"):
        data = fetch_github()
        cache.write_text(json.dumps(data, indent=1), encoding="utf-8")
        return data
    return json.loads(cache.read_text(encoding="utf-8"))


# ---- hero ----------------------------------------------------------------------------
def build_hero():
    holo = json.loads((DATA / "holo.json").read_text(encoding="utf-8"))
    pw, ph = holo["size"]
    lw, lh = holo["logoSize"]
    W, H = 1000, 470
    px, py = 10, 4
    LS = 46 / lw  # logo scale

    grad, band = scan_band("y", pw, 120)
    defs = GLOW + grad + (
        f'<image id="photo" href="{holo["photo"]}" width="{pw}" height="{ph}"/>'
        f'<mask id="scanMask"><rect width="{pw}" height="{ph}" fill="#000"/>{band}</mask>'
        '<filter id="lift"><feComponentTransfer><feFuncR type="linear" slope="1.7"/>'
        '<feFuncG type="linear" slope="1.5"/><feFuncB type="linear" slope="1.4"/></feComponentTransfer></filter>'
        '<filter id="logoGlow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        f'<pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse">'
        f'<circle cx="1" cy="1" r="1" fill="{GRID}"/></pattern>'
        '<clipPath id="typeClip"><rect class="typer anim" x="470" y="244" width="500" height="26"/></clipPath>'
    )
    css = f"""
.scan{{animation:scan 6s cubic-bezier(.45,0,.55,1) infinite}}
@keyframes scan{{0%{{transform:translateY(-80px)}}70%,100%{{transform:translateY({ph + 80}px)}}}}
.typer{{animation:type 2.6s steps(44) .4s both;transform-box:fill-box;transform-origin:left}}
@keyframes type{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
.cursor{{animation:blink 1s steps(1) infinite}}
@keyframes blink{{50%{{opacity:0}}}}
.pulse{{animation:pulse 2s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}
@keyframes pulse{{0%,100%{{opacity:.35;transform:scale(1)}}50%{{opacity:0;transform:scale(2.4)}}}}
"""

    bx0, by0, bx1, by1 = px + 60, py + 2, px + pw - 60, py + ph - 70
    brackets = "".join(
        f'<path d="M{x + dx * 22},{y} L{x},{y} L{x},{y + dy * 22}" />'
        for x, y, dx, dy in ((bx0, by0, 1, 1), (bx1, by0, -1, 1), (bx0, by1, 1, -1), (bx1, by1, -1, -1)))

    readouts = [
        ("PODIOS 2026", "Mejor uso de Gemma 4, un 2.º y un 3.er lugar", GOLD),
        ("EN PRODUCCIÓN", "Grandpa Burgers: pedidos reales por WhatsApp", MESH),
        ("FORMACIÓN", "Desarrollo de Software · Universidad de la Costa", MESH),
    ]
    rows = "".join(
        f'<g transform="translate(470,{304 + i * 40})"><rect width="3" height="30" fill="{c}"/>'
        f'<text x="16" y="11" class="label">{t(k)}</text>'
        f'<text x="16" y="28" class="sans" font-size="15" fill="{INK}">{t(v)}</text></g>'
        for i, (k, v, c) in enumerate(readouts))

    body = f"""
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="url(#dots)" opacity=".55"/>
<g transform="translate({px},{py})">
  <use href="#photo"/>
  <g mask="url(#scanMask)"><use href="#photo" filter="url(#lift)"/></g>
  <g class="scan anim"><rect x="50" y="-1" width="{pw - 100}" height="2" fill="{HOT}" opacity=".85" filter="url(#glow)"/></g>
</g>
<g fill="none" stroke="{MESH}" stroke-width="1.5" stroke-opacity=".7">{brackets}</g>
<text x="{px + 60}" y="{H - 22}" class="label">HOLOGRAMA · BARRANQUILLA 10.96°N 74.80°W</text>

<image href="{holo["logo"]}" x="470" y="34" width="{lw * LS:.1f}" height="{lh * LS:.1f}" filter="url(#logoGlow)"/>
<text x="530" y="62" class="eyebrow">PERFIL // {USER.upper()}</text>
<text x="468" y="136" class="mono" font-size="50" font-weight="700" fill="{INK}" letter-spacing="-1">Han's De Ávila</text>
<text x="470" y="176" class="sans" font-size="21" fill="{INK}">Desarrollador de software en formación</text>
<text x="470" y="206" class="sans" font-size="15.5" fill="{FOG}">IA aplicada, web y videojuegos — Barranquilla, Colombia</text>
<g clip-path="url(#typeClip)"><text x="470" y="262" class="mono" font-size="15" fill="{MESH}">&gt; construyo productos y los pongo a funcionar</text></g>
<rect class="cursor anim" x="903" y="249" width="9" height="17" fill="{MESH}"/>
{rows}
<g transform="translate(470,438)">
  <circle class="pulse anim" cx="6" cy="-5" r="5" fill="{MESH}"/><circle cx="6" cy="-5" r="4" fill="{MESH}"/>
  <text x="20" y="0" class="mono" font-size="13" fill="{INK}">Disponible para trabajar y colaborar</text>
</g>
"""
    write("hero.svg", svg(W, H, body, css, defs))


# ---- section headers & buttons --------------------------------------------------------
def build_header(slug, title, note):
    W, H = 1000, 64
    body = (f'<text x="28" y="39" class="eyebrow" font-size="13">{t(title)}</text>'
            f'<line x1="{40 + len(title) * 10.6}" y1="35" x2="{972 - len(note) * 7.3}" y2="35" stroke="{GRID}"/>'
            f'<text x="972" y="39" text-anchor="end" class="label">{t(note)}</text>')
    write(f"h-{slug}.svg", svg(W, H, body))


def button_icons():
    holo = json.loads((DATA / "holo.json").read_text(encoding="utf-8"))
    lw, lh = holo["logoSize"]
    h = 22 * lh / lw
    return {
        "portafolio": f'<image href="{holo["logo"]}" x="0" y="{11 - h / 2:.1f}" width="22" height="{h:.1f}"/>',
        "linkedin": (f'<rect x="1" y="1" width="20" height="20" rx="4" fill="{MESH}"/>'
                     f'<circle cx="6.3" cy="6.2" r="1.7" fill="{BG}"/><rect x="4.8" y="9" width="3" height="8.5" fill="{BG}"/>'
                     f'<path d="M10,9 h2.9 v1.3 c.5-.9 1.6-1.5 2.8-1.5 c2.2,0 3.3,1.4 3.3,3.9 v4.8 h-3 v-4.3 '
                     f'c0-1.2-.4-1.9-1.4-1.9 c-1,0 -1.6,.7 -1.6,1.9 v4.3 h-3 z" fill="{BG}"/>'),
        "correo": (f'<g fill="none" stroke="{MESH}" stroke-width="1.7" stroke-linejoin="round">'
                   f'<rect x="1.5" y="4" width="19" height="14" rx="2.5"/><path d="M2.5,5.5 L11,12 L19.5,5.5"/></g>'),
    }


def build_button(slug, text, icon):
    w = 58 + len(text) * 8.4 + 34
    body = (f'<g transform="translate(18,12)">{icon}</g>'
            f'<text x="52" y="29" class="mono" font-size="14" fill="{INK}">{t(text)}</text>'
            f'<path d="M{w - 30},30 l9,-9 m-6,0 h6 v6" fill="none" stroke="{MESH}" stroke-width="1.6"/>')
    write(f"btn-{slug}.svg", svg(round(w), 46, body))


# ---- podiums ---------------------------------------------------------------------------
AWARDS = [
    ("lulo", "trophy", "Mejor uso de Gemma 4", "Hacktoberfest Hack Day", "Barranquilla · oct 2026",
     "Lulo", "tutor con IA para niños"),
    ("camila", "2.º", "2.º lugar", "Hackathon CaribeTech", "reto GoToCloud · may 2026",
     "Camila", "agente de voz con IA"),
    ("la-vaca", "3.er", "3.er lugar", "Hackatón", "ago 2026",
     "La Vaca", "pagos con Interledger"),
]


def build_awards():
    W, H = 320, 214
    for slug, medal, prize, event, when, project, what in AWARDS:
        if medal == "trophy":
            glyph = (f'<path d="M-13,-15 h26 v8 a13,13 0 0 1 -26,0 z M-13,-11 h-6 a6,7 0 0 0 7,10 M13,-11 h6 a6,7 0 0 1 -7,10 '
                     f'M0,6 v8 M-8,16 h16" fill="none" stroke="{GOLD}" stroke-width="2" stroke-linejoin="round"/>')
        else:
            glyph = (f'<text y="6" text-anchor="middle" class="mono" font-size="16" font-weight="700" '
                     f'fill="{GOLD}">{t(medal)}</text>')
        body = f"""
<circle cx="52" cy="54" r="28" fill="none" stroke="{GOLD}" stroke-width="1.5" stroke-opacity=".55"/>
<circle cx="52" cy="54" r="22" fill="none" stroke="{GOLD}" stroke-width="1" stroke-dasharray="2 4" stroke-opacity=".6"/>
<g transform="translate(52,54)">{glyph}</g>
<text x="96" y="46" class="label">{t(event.upper())}</text>
<text x="96" y="64" class="label" fill-opacity=".8">{t(when.upper())}</text>
<text x="24" y="122" class="sans" font-size="{22 if len(prize) > 12 else 26}" font-weight="700" fill="{GOLD}">{t(prize)}</text>
<text x="24" y="152" class="sans" font-size="15" fill="{INK}"><tspan font-weight="700">{t(project)}</tspan><tspan fill="{FOG}"> — {t(what)}</tspan></text>
<line x1="24" y1="174" x2="296" y2="174" stroke="{GRID}"/>
<text x="24" y="197" class="mono" font-size="12" fill="{MESH}">ver proyecto ↗</text>
"""
        write(f"award-{slug}.svg", svg(W, H, body))


# ---- projects ----------------------------------------------------------------------------
PROJECTS = [
    ("lulo", "IA · EDUCACIÓN", ("Mejor uso de Gemma 4", GOLD), "Lulo",
     "Tutor con IA para niños de 6 a 12 años que aprende cómo aprende cada uno y adapta la siguiente clase.",
     ["Next.js", "TypeScript", "Gemma 4", "Web Speech"], "abrir demo"),
    ("camila", "IA · VOZ", ("2.º lugar", GOLD), "Camila",
     "Agente de voz para contact centers que atiende llamadas telefónicas en tiempo real.",
     ["Gemini Live", "Twilio", "FastAPI", "React"], "abrir demo"),
    ("la-vaca", "FINTECH", ("3.er lugar", GOLD), "La Vaca",
     "Divide la cuenta del restaurante y cada amigo paga su parte desde su propia wallet.",
     ["React", "Open Payments", "Interledger"], "abrir demo"),
    ("panello", "SAAS · MULTI-TENANT", ("Producto propio", FOG), "Panello",
     "Plataforma para que los negocios gestionen productos y pedidos, con los datos de cada uno aislados.",
     ["FastAPI", "React / Expo", "Supabase", "PostgreSQL"], "abrir demo"),
    ("grandpa-burgers", "E-COMMERCE", ("En producción", MESH), "Grandpa Burgers",
     "Menú digital de una hamburguesería real, conectado a Panello, con pedidos por WhatsApp.",
     ["Next.js", "TypeScript", "Tailwind", "Supabase"], "abrir tienda"),
    ("kart-party", "VIDEOJUEGO", ("Descarga para Windows", FOG), "Kart Party",
     "Juego de karts de 1 a 4 jugadores donde cada celular se convierte en el control.",
     ["Unity 6", "C#", "WebSocket"], "ver repositorio"),
]


def build_projects():
    W, H = 490, 236
    for slug, kind, (badge, bcolor), name, desc, chips, cta in PROJECTS:
        rail = GOLD if bcolor == GOLD else (MESH if bcolor == MESH else GRID)
        bw = len(badge) * 7.2 + 22
        x = 28
        chip_svg = ""
        for c in chips:
            cw = len(c) * 7.1 + 18
            chip_svg += (f'<rect x="{x}" y="164" width="{cw:.0f}" height="24" rx="12" fill="none" '
                         f'stroke="{MESH}" stroke-opacity=".45"/><text x="{x + 9}" y="180" class="mono" '
                         f'font-size="11.5" fill="{MESH}">{t(c)}</text>')
            x += cw + 8
        body = f"""
<rect x="1" y="20" width="4" height="{H - 40}" rx="2" fill="{rail}"/>
<text x="28" y="40" class="label">{t(kind)}</text>
<rect x="{W - 24 - bw:.0f}" y="24" width="{bw:.0f}" height="24" rx="12" fill="{bcolor}" fill-opacity=".12" stroke="{bcolor}" stroke-opacity=".6"/>
<text x="{W - 24 - bw / 2:.0f}" y="40" text-anchor="middle" class="mono" font-size="11.5" fill="{bcolor}">{t(badge)}</text>
<text x="27" y="86" class="mono" font-size="30" font-weight="700" fill="{INK}" letter-spacing="-.5">{t(name)}</text>
<text x="28" y="116" class="sans" font-size="15" fill="{FOG}">{tspans(wrap(desc, 56), 28, 21)}</text>
{chip_svg}
<text x="{W - 24}" y="214" text-anchor="end" class="mono" font-size="12" fill="{MESH}">{t(cta)} ↗</text>
"""
        write(f"project-{slug}.svg", svg(W, H, body))


# ---- commits terrain -------------------------------------------------------------------
def streaks(days):
    counts = [c for _, c in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    i = len(counts) - 1
    if counts and counts[i] == 0:
        i -= 1  # today may still be empty
    current = 0
    while i >= 0 and counts[i]:
        current += 1
        i -= 1
    return longest, current


def build_commits(data):
    days = data["days"]
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)]
    peak = max(c for _, c in days) or 1
    W, H = 1000, 470
    OX, OY = 96, 206
    WV, DV = (15.0, 1.5), (-7.4, 8.0)

    def P(w, d, c):
        h = 128 * (c / peak) ** 0.6
        return OX + w * WV[0] + d * DV[0], OY + w * WV[1] + d * DV[1] - h

    def cnt(w, d):
        return weeks[w][d][1] if d < len(weeks[w]) else None

    bands = {0: [], 1: [], 2: []}

    def seg(a, b, ca, cb):
        lvl = ((ca + cb) / 2 / peak) ** 0.6
        bands[0 if lvl < 0.08 else (1 if lvl < 0.45 else 2)].append(f"M{a[0]:.1f},{a[1]:.1f}L{b[0]:.1f},{b[1]:.1f}")

    for w in range(len(weeks)):
        for d in range(7):
            c = cnt(w, d)
            if c is None:
                continue
            p = P(w, d, c)
            if d + 1 < 7 and cnt(w, d + 1) is not None:
                seg(p, P(w, d + 1, cnt(w, d + 1)), c, cnt(w, d + 1))
            if w + 1 < len(weeks) and cnt(w + 1, d) is not None:
                seg(p, P(w + 1, d, cnt(w + 1, d)), c, cnt(w + 1, d))

    style = {0: (MESH, 0.22, 1), 1: (MESH, 0.6, 1.2), 2: (HOT, 0.95, 1.6)}
    paths = "".join(f'<path stroke="{style[b][0]}" stroke-opacity="{style[b][1]}" stroke-width="{style[b][2]}" '
                    f'd="{"".join(v)}"/>' for b, v in bands.items())
    hot = "".join(f'<path d="{"".join(v)}"/>' for b, v in bands.items() if b)

    labels, last = "", None
    for w, week in enumerate(weeks):
        m = int(week[0][0][5:7])
        if m != last and 2 <= w < len(weeks) - 2:
            x, y = P(w, 6, 0)
            labels += f'<text x="{x - 6:.0f}" y="{y + 24:.0f}" class="label">{MONTHS[m - 1]}</text>'
        last = m

    best = max(days, key=lambda d: d[1])
    bd = dt.date.fromisoformat(best[0])
    active = sum(1 for _, c in days if c)
    longest, _ = streaks(days)
    last_month = days[-1][0][:7]
    month_total = sum(c for d, c in days if d.startswith(last_month))
    stats = [
        (num(data["total"]), "contribuciones"),
        (f"{longest} días", "racha más larga"),
        (f"{best[1]}", f"día top · {bd.day} {MONTHS_LOWER[bd.month - 1]}"),
        (f"{active}", "días con commits"),
        (num(month_total), f"en {MONTHS_LOWER[int(last_month[5:]) - 1]} {last_month[:4]}"),
    ]
    stat_svg = "".join(
        f'<g transform="translate({28 + i * 192},404)"><text class="mono" font-size="24" font-weight="700" '
        f'fill="{INK}">{t(v)}</text><text y="22" class="label" font-size="10">{t(k.upper())}</text></g>'
        for i, (v, k) in enumerate(stats))

    grad, band = scan_band("x", H, 140)
    defs = GLOW + grad + f'<mask id="scanMask"><rect width="{W}" height="{H}" fill="#000"/>{band}</mask>'
    css = """.scan{animation:sweep 7s cubic-bezier(.45,0,.55,1) infinite}
@keyframes sweep{0%{transform:translateX(-120px)}70%,100%{transform:translateX(1120px)}}"""
    updated = dt.date.fromisoformat(data["fetched"])
    body = f"""
<text x="28" y="44" class="eyebrow" font-size="13">COMMITS // RELIEVE DEL ÚLTIMO AÑO</text>
<text x="972" y="44" text-anchor="end" class="label">CADA PICO ES UN DÍA · SE ACTUALIZA SOLO · {updated.day} {MONTHS[updated.month - 1]} {updated.year}</text>
<g fill="none" stroke-linecap="round" filter="url(#glow)">{paths}</g>
<g fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" mask="url(#scanMask)" filter="url(#glow)">{hot}</g>
<g class="scan anim"><rect x="-1" y="70" width="2" height="300" fill="{HOT}" opacity=".5" filter="url(#glow)"/></g>
{labels}
<line x1="28" y1="376" x2="972" y2="376" stroke="{GRID}"/>
{stat_svg}
"""
    write("commits.svg", svg(W, H, body, css, defs))


# ---- timeline -----------------------------------------------------------------------------
MOMENTS = [
    ("2024", "Bachiller técnico en TI, con énfasis en programación", False),
    ("2024", "Técnico en programación de software · SENA", False),
    ("2025", "Empiezo Desarrollo de Software en la Universidad de la Costa", False),
    ("2025", "Caribe Game Jam: Dungeon Trade, juego en Unity", False),
    ("MAY 2026", "Camila: 2.º lugar en la Hackathon CaribeTech", True),
    ("AGO 2026", "La Vaca: 3.er lugar en la hackatón", True),
    ("SEP 2026", "Kart Party: karts con el celular como control", False),
    ("OCT 2026", "Lulo gana Mejor uso de Gemma 4 en el Hacktoberfest", True),
]


def build_timeline():
    W, H = 1000, 380
    y0 = 196
    x0, x1 = 84, 900
    step = (x1 - x0) / (len(MOMENTS) - 1)
    items = ""
    for i, (when, what, podium) in enumerate(MOMENTS):
        x = x0 + i * step
        c = GOLD if podium else MESH
        up = i % 2 == 0
        stem_end = y0 - 40 if up else y0 + 40
        lines = wrap(what, 20)
        if up:
            ty = stem_end - 12 - (len(lines) - 1) * 17
            dy = ty - 22
        else:
            dy = stem_end + 22
            ty = dy + 22
        items += (f'<line x1="{x:.0f}" y1="{y0}" x2="{x:.0f}" y2="{stem_end}" stroke="{c}" stroke-opacity=".5"/>'
                  f'<circle cx="{x:.0f}" cy="{y0}" r="{6 if podium else 4.5}" fill="{BG}" stroke="{c}" stroke-width="2"/>'
                  f'<text x="{x:.0f}" y="{dy:.0f}" text-anchor="middle" class="mono" font-size="11" '
                  f'letter-spacing="1.5" fill="{c}">{t(when)}</text>'
                  f'<text x="{x:.0f}" y="{ty:.0f}" text-anchor="middle" class="sans" font-size="13" fill="{INK}">'
                  + "".join(f'<tspan x="{x:.0f}" dy="{0 if j == 0 else 17}">{t(l)}</tspan>' for j, l in enumerate(lines))
                  + "</text>")
    body = f"""
<text x="28" y="44" class="eyebrow" font-size="13">MOMENTOS // CÓMO LLEGUÉ HASTA AQUÍ</text>
<text x="972" y="44" text-anchor="end" class="label"><tspan fill="{GOLD}">●</tspan> PODIO</text>
<line x1="40" y1="{y0}" x2="960" y2="{y0}" stroke="{GRID}" stroke-width="2"/>
<line x1="{x0 + 4 * step - step / 2:.0f}" y1="{y0}" x2="960" y2="{y0}" stroke="{MESH}" stroke-opacity=".5" stroke-width="2"/>
{items}
"""
    write("timeline.svg", svg(W, H, body))


# ---- stack -------------------------------------------------------------------------------
DAILY = [("VS Code", 5, "avanzado"), ("HTML", 4, "intermedio+"), ("Python", 3, "intermedio"),
         ("CSS", 3, "intermedio"), ("GitHub", 3, "intermedio"), ("IA aplicada", 3, "intermedio"),
         ("Supabase", 2, "básico+")]
GROWING = ["React", "JavaScript", "PostgreSQL", "MySQL", "APIs REST", "Arquitectura fullstack"]
ALSO = ["Unity", "C#", "UI design", "Game design"]


def build_stack(data):
    W, H = 1000, 380
    rows = ""
    for i, (name, lvl, word) in enumerate(DAILY):
        y = 98 + i * 36
        segs = "".join(f'<rect x="{180 + k * 26}" y="{y - 12}" width="20" height="12" rx="2" '
                       f'fill="{MESH if k < lvl else "none"}" fill-opacity="{0.35 + 0.13 * k if k < lvl else 0}" '
                       f'stroke="{MESH if k < lvl else GRID}" stroke-opacity="{1 if k < lvl else 1}"/>' for k in range(5))
        rows += (f'<text x="28" y="{y}" class="sans" font-size="15" fill="{INK}">{t(name)}</text>{segs}'
                 f'<text x="322" y="{y}" class="label">{t(word.upper())}</text>')

    langs = sorted(data["languages"].items(), key=lambda kv: -kv[1])
    total = sum(v for _, v in langs) or 1
    top = langs[:6]
    other = total - sum(v for _, v in top)
    if other > 0:
        top.append(("Otros", other))
    bar, legend, x = "", "", 540.0
    for i, (lang, v) in enumerate(top):
        wpx = 420 * v / total
        op = max(0.12, 1 - i * 0.15)
        bar += f'<rect x="{x:.1f}" y="88" width="{max(wpx - 2, 1):.1f}" height="14" fill="{MESH}" fill-opacity="{op:.2f}"/>'
        x += wpx
        col, row = i % 2, i // 2
        lx, ly = 540 + col * 210, 134 + row * 26
        legend += (f'<rect x="{lx}" y="{ly - 10}" width="10" height="10" fill="{MESH}" fill-opacity="{op:.2f}"/>'
                   f'<text x="{lx + 18}" y="{ly}" class="sans" font-size="14" fill="{INK}">{t(lang)}</text>'
                   f'<text x="{lx + 190}" y="{ly}" text-anchor="end" class="mono" font-size="12" fill="{FOG}">'
                   f'{100 * v / total:.1f}%</text>')

    def chips(items, y, color):
        out, x = "", 540
        for c in items:
            cw = len(c) * 7.1 + 18
            if x + cw > 972:
                x, y = 540, y + 32
            out += (f'<rect x="{x}" y="{y}" width="{cw:.0f}" height="24" rx="12" fill="none" stroke="{color}" '
                    f'stroke-opacity=".5" stroke-dasharray="3 3"/><text x="{x + 9}" y="{y + 16}" class="mono" '
                    f'font-size="11.5" fill="{color}">{t(c)}</text>')
            x += cw + 8
        return out

    body = f"""
<text x="28" y="44" class="eyebrow" font-size="13">STACK // LO QUE USO Y LO QUE ESTOY APRENDIENDO</text>
<text x="28" y="72" class="label">USO A DIARIO</text>
{rows}
<line x1="500" y1="64" x2="500" y2="344" stroke="{GRID}"/>
<text x="540" y="72" class="label">LENGUAJES EN MIS REPOS · MEDIDO EN CÓDIGO</text>
{bar}{legend}
<text x="540" y="256" class="label">FORTALECIENDO</text>
{chips(GROWING, 268, MESH)}
<text x="28" y="356" class="label">TAMBIÉN HE USADO: {t(" · ".join(ALSO).upper())}</text>
"""
    write("stack.svg", svg(W, H, body))


def main():
    ASSETS.mkdir(exist_ok=True)
    data = load_github()
    build_hero()
    build_header("podios", "PODIOS // HACKATHONS 2026", "3 DE 3 CON PREMIO")
    build_header("proyectos", "PROYECTOS // LO QUE HE CONSTRUIDO", "TOCA UNA TARJETA PARA ABRIRLA")
    icons = button_icons()
    for slug, text in (("portafolio", "Portafolio"), ("linkedin", "LinkedIn"), ("correo", "Correo")):
        build_button(slug, text, icons[slug])
    build_awards()
    build_projects()
    build_commits(data)
    build_timeline()
    build_stack(data)
    print("built", len(list(ASSETS.glob("*.svg"))), "svgs")


if __name__ == "__main__":
    main()
