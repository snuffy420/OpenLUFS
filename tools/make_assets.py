"""Generate the original OpenLUFS vector mark and Windows multi-size icon."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"assets"
ASSETS.mkdir(exist_ok=True)
svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><rect x="8" y="8" width="496" height="496" rx="118" fill="#142321" stroke="#30574b" stroke-width="10"/><g fill="#65e4bd"><rect x="110" y="212" width="36" height="88" rx="18"/><rect x="174" y="160" width="36" height="192" rx="18"/><rect x="238" y="112" width="36" height="288" rx="18"/><rect x="302" y="160" width="36" height="192" rx="18"/><rect x="366" y="212" width="36" height="88" rx="18"/></g></svg>'''
(ASSETS/"openlufs.svg").write_text(svg,encoding="utf-8")
scale=4
icon=Image.new("RGBA",(512*scale,512*scale))
d=ImageDraw.Draw(icon)
def rect(box, radius, fill, outline=None, width=1):
    d.rounded_rectangle(tuple(int(v*scale) for v in box),int(radius*scale),fill,outline,int(width*scale))
rect((8,8,504,504),118,"#142321","#30574b",10)
for x,y,h in [(110,212,88),(174,160,192),(238,112,288),(302,160,192),(366,212,88)]:
    rect((x,y,x+36,y+h),18,"#65e4bd")
icon=icon.resize((512,512),Image.Resampling.LANCZOS)
icon.save(ASSETS/"mark.png")
icon.save(ASSETS/"openlufs.ico",sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
empty=Image.new("RGBA",(300,110))
ed=ImageDraw.Draw(empty)
heights=[12,22,36,18,46,66,39,82,104,70,46,62,37,22,32,16,10]
for i,h in enumerate(heights):
    ed.rounded_rectangle((i*16+15,55-h/2,i*16+20,55+h/2),3,fill="#65e4bd" if 5<=i<=11 else "#30574b")
empty.save(ASSETS/"empty-state.png")
banner=Image.new("RGB",(1600,420),"#101416")
banner.paste(icon.resize((220,220),Image.Resampling.LANCZOS),(105,100),icon.resize((220,220),Image.Resampling.LANCZOS))
bd=ImageDraw.Draw(banner)
font_path=Path("C:/Windows/Fonts/segoeui.ttf")
font_bold=Path("C:/Windows/Fonts/seguisb.ttf")
if not font_path.exists():
    font_path=Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font_bold=font_path
bd.text((385,117),"OpenLUFS",font=ImageFont.truetype(str(font_bold),88),fill="#e6eceb")
bd.text((391,242),"Audio loudness normalization",font=ImageFont.truetype(str(font_path),32),fill="#8da8a0")
banner.save(ASSETS/"banner.png")
print("Generated app icon, SVG, mark, empty state and GitHub banner")
