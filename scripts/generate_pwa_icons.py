from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'static' / 'core' / 'img'
SOURCE_LOGO = OUTPUT / 'logo.svg'
FONT_PATH = Path(r'C:\Windows\Fonts\arialbd.ttf')
SIZE = 512

# Палитра и надпись берутся из static/core/img/logo.svg.
source = SOURCE_LOGO.read_text(encoding='utf-8')
assert '#0b2946' in source and '#1688dc' in source and 'САНТЕХ' in source

image = Image.new('RGB', (SIZE, SIZE), '#052f52')
draw = ImageDraw.Draw(image)

# Фон с безопасной зоной для круглых и maskable-иконок.
draw.rounded_rectangle((18, 18, 494, 494), radius=118, fill='#073c66')
draw.rounded_rectangle((38, 38, 474, 474), radius=100, fill='#0d6098')
draw.rounded_rectangle((58, 58, 454, 454), radius=84, fill='#0b2946')


def fitted_font(text, max_width, start_size):
    size = start_size
    while size > 20:
        font = ImageFont.truetype(str(FONT_PATH), size)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
        size -= 2
    return ImageFont.truetype(str(FONT_PATH), size)


def centered(text, y, font, fill):
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0]
    draw.text(((SIZE - width) / 2, y), text, font=font, fill=fill)


# Перекомпоновка горизонтального логотипа в две крупные строки.
top_font = fitted_font('САНТЕХ', 338, 86)
bottom_font = fitted_font('ГО.РФ', 300, 112)
centered('САНТЕХ', 142, top_font, '#ffffff')

bottom = 'ГО.РФ'
bottom_box = draw.textbbox((0, 0), bottom, font=bottom_font)
bottom_x = (SIZE - (bottom_box[2] - bottom_box[0])) / 2
go_width = draw.textbbox((0, 0), 'ГО', font=bottom_font)[2]
draw.text((bottom_x, 232), 'ГО', font=bottom_font, fill='#38b8ff')
draw.text((bottom_x + go_width, 232), '.РФ', font=bottom_font, fill='#ffffff')

# Маленький статусный акцент из интерфейса мастеров.
draw.ellipse((238, 368, 274, 404), fill='#38dc92')
draw.ellipse((247, 377, 265, 395), fill='#caffea')

for size in (512, 192):
    target = image if size == SIZE else image.resize((size, size), Image.Resampling.LANCZOS)
    target.save(OUTPUT / f'pwa-icon-{size}.png', optimize=True)
