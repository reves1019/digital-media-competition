"""Rebuild the original, seeded vector illustrations used by the prototype."""
from pathlib import Path
import math
import random

ROOT = Path(__file__).resolve().parents[1]
random.seed(30)

def panel(name, accent, geometry, label):
    dots = []
    for _ in range(700):
        x, y = random.uniform(40, 1560), random.uniform(40, 960)
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{random.uniform(.6, 1.8):.1f}" fill="{accent}" opacity="{random.uniform(.08,.38):.2f}"/>')
    grid = ''.join(f'<path d="M{x} 0V1000"/>' for x in range(0,1601,100)) + ''.join(f'<path d="M0 {y}H1600"/>' for y in range(0,1001,100))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000">
<rect width="1600" height="1000" fill="#0d1514"/>
<g stroke="#cfc7af" opacity=".055" stroke-width="1">{grid}</g>
{''.join(dots)}
{geometry}
<path d="M60 100V60H100M1500 60H1540V100M60 900V940H100M1500 940H1540V900" fill="none" stroke="{accent}" stroke-opacity=".45"/>
<text x="95" y="897" fill="{accent}" font-family="Georgia,serif" font-size="20" letter-spacing="8">{label}</text>
</svg>'''
    (ROOT / 'assets' / name).write_text(svg, encoding='utf-8')

flames = []
for i in range(34):
    spread = i * 10
    x = 800 + math.sin(i*.8)*12
    flames.append(f'<path d="M{650-spread/2} 740 C{420-spread/4} 480 {850-spread/3} 420 {x} {150+i*6} C{1150+spread/4} 570 {780+spread} 490 {950+spread/3} 740" fill="none" stroke="#e5a66e" stroke-width="1.2" opacity="{.12+i*.014:.2f}"/>')
panel('fire.svg', '#e8ac76', ''.join(flames), 'FIRE / GATHERING')

orbits = []
for i in range(24):
    orbits.append(f'<ellipse cx="800" cy="500" rx="{220+i*12}" ry="{130+i*9}" transform="rotate({-20+i*1.8} 800 500)" fill="none" stroke="#8cae9e" stroke-width="1" opacity=".27"/>')
orbits += ['<circle cx="626" cy="470" r="145" fill="#dda561"/>', '<circle cx="990" cy="410" r="120" fill="#e2dbc9"/>', '<circle cx="1044" cy="375" r="113" fill="#0d1514"/>', '<path d="M430 500H1190M800 140V860" stroke="#e2dbc9" stroke-dasharray="3 10" opacity=".3"/>']
panel('light.svg', '#b9c9ab', ''.join(orbits), 'LIGHT / ENCOUNTER')

roofs = []
for i in range(24):
    y = 280 + i*15
    roofs.append(f'<path d="M{365+i*3} {y+180} Q650 {y+155} 800 {y} Q950 {y+155} {1235-i*3} {y+180}" fill="none" stroke="#d6b68d" stroke-width="1.4" opacity="{.18+i*.015:.2f}"/>')
roofs += ['<path d="M510 490V760H1090V490M710 760V590H890V760" fill="none" stroke="#d6b68d" stroke-width="2" opacity=".55"/>', '<rect x="734" y="615" width="132" height="145" fill="#dfb66b" opacity=".12"/>', '<circle cx="800" cy="640" r="22" fill="#e2ad68"/>', '<path d="M480 810H1120M575 836H1025" stroke="#d6b68d" opacity=".3"/>']
panel('home.svg', '#d6b68d', ''.join(roofs), 'HOME / RETURN')
print('Created three original vector compositions using seed 30.')
