"""Generador de assets para Devpost - Shipaton 2026

Este script crea el icono y screenshot requeridos para Devpost
usando Python y PIL (Pillow).
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("PIL no está instalado. Instala con: pip install Pillow")

import os
from pathlib import Path

# Crear directorios si no existen
Path("assets/icons").mkdir(parents=True, exist_ok=True)
Path("assets/screenshots").mkdir(parents=True, exist_ok=True)

# Paleta de colores de SaberLink
COLORS = {
    'ink': '#101513',        # Fondo principal
    'panel': '#18221e',      # Paneles
    'paper': '#f5f0e4',      # Texto claro
    'muted': '#9ea99b',      # Texto secundario
    'gold': '#d5a94d',       # Acentos principales
    'mint': '#8fbe9d',       # Éxito/activos
    'copper': '#db8662',     # Alertas/errores
    'line': '#334139',       # Bordes
}

def hex_to_rgb(hex_color):
    """Convierte color hex a RGB."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_app_icon():
    """Crea icono de la app 1024x1024 px."""
    if not PIL_AVAILABLE:
        print("No se puede crear el icono sin PIL/Pillow")
        return False
    
    size = (1024, 1024)
    img = Image.new('RGB', size, hex_to_rgb(COLORS['ink']))
    draw = ImageDraw.Draw(img)
    
    # Centros de los círculos (triángulo equilátero)
    center_x, center_y = 512, 512
    radius = 100
    offset = 180
    
    centers = [
        (center_x, center_y - offset),           # Círculo superior
        (center_x - offset * 0.866, center_y + offset * 0.5),  # Inferior izquierdo
        (center_x + offset * 0.866, center_y + offset * 0.5)   # Inferior derecho
    ]
    
    # Dibujar conexiones (triángulo)
    draw.polygon(centers, outline=hex_to_rgb(COLORS['gold']), width=12)
    
    # Dibujar círculos
    for i, center in enumerate(centers):
        color = hex_to_rgb(COLORS['mint']) if i == 0 else hex_to_rgb(COLORS['copper'])
        draw.ellipse([
            center[0] - radius, center[1] - radius,
            center[0] + radius, center[1] + radius
        ], fill=color, outline=hex_to_rgb(COLORS['gold']), width=6)
    
    # Añadir pequeño punto central
    draw.ellipse([
        center_x - 15, center_y - 15,
        center_x + 15, center_y + 15
    ], fill=hex_to_rgb(COLORS['gold']))
    
    # Guardar
    output_path = 'assets/icons/app_icon.png'
    img.save(output_path)
    print(f"✅ Icono creado: {output_path} (1024×1024)")
    return True

def create_screenshot_placeholder():
    """Crea placeholder de screenshot 1179×2556 px."""
    if not PIL_AVAILABLE:
        print("No se puede crear el screenshot sin PIL/Pillow")
        return False
    
    size = (1179, 2556)
    img = Image.new('RGB', size, hex_to_rgb(COLORS['ink']))
    draw = ImageDraw.Draw(img)
    
    # Header (80px height)
    draw.rectangle([0, 0, 1179, 80], fill=hex_to_rgb(COLORS['panel']))
    
    # Título en header
    try:
        title_font = ImageFont.truetype("arial.ttf", 28)
        subtitle_font = ImageFont.truetype("arial.ttf", 16)
        body_font = ImageFont.truetype("arial.ttf", 18)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    
    draw.text((30, 25), "SaberLink", fill=hex_to_rgb(COLORS['paper']), font=title_font)
    draw.text((180, 35), "— atlas del conocimiento", fill=hex_to_rgb(COLORS['muted']), font=subtitle_font)
    
    # Badge de uso en header
    draw.rectangle([1000, 20, 1150, 60], fill=hex_to_rgb(COLORS['panel']), outline=hex_to_rgb(COLORS['gold']), width=2)
    draw.text((1020, 30), "3/20 PDFs", fill=hex_to_rgb(COLORS['gold']), font=body_font)
    
    # Hero section (200px height)
    draw.rectangle([30, 120, 1149, 320], fill=hex_to_rgb(COLORS['panel']), outline=hex_to_rgb(COLORS['line']), width=2)
    draw.text((50, 140), "INVESTIGACIÓN, CONECTADA", fill=hex_to_rgb(COLORS['gold']), font=body_font)
    draw.text((50, 180), "Mira lo que tu investigación todavía no te muestra.", fill=hex_to_rgb(COLORS['paper']), font=title_font)
    draw.text((50, 220), "Convierte fuentes y necesidades en conexiones explicables.", fill=hex_to_rgb(COLORS['muted']), font=body_font)
    
    # Search panel (300px height)
    draw.rectangle([30, 350, 1149, 650], fill=hex_to_rgb(COLORS['panel']), outline=hex_to_rgb(COLORS['line']), width=2)
    draw.text((50, 370), "NUEVA EXPLORACIÓN", fill=hex_to_rgb(COLORS['gold']), font=body_font)
    
    # Chips de búsqueda
    chip_width = 150
    chip_height = 40
    chips = ["ID", "Texto", "PDF", "Biblioteca"]
    for i, chip in enumerate(chips):
        x = 50 + i * (chip_width + 15)
        y = 420
        color = hex_to_rgb(COLORS['gold']) if i == 0 else hex_to_rgb(COLORS['ink'])
        text_color = hex_to_rgb(COLORS['ink']) if i == 0 else hex_to_rgb(COLORS['muted'])
        draw.rectangle([x, y, x + chip_width, y + chip_height], fill=color, outline=hex_to_rgb(COLORS['line']), width=1)
        draw.text((x + 50, y + 12), chip, fill=text_color, font=body_font)
    
    # Input de búsqueda
    draw.rectangle([50, 480, 1129, 540], fill=hex_to_rgb(COLORS['ink']), outline=hex_to_rgb(COLORS['line']), width=2)
    draw.text((70, 500), "NEED-001", fill=hex_to_rgb(COLORS['muted']), font=body_font)
    
    # Botón de búsqueda
    draw.rectangle([50, 560, 1129, 620], fill=hex_to_rgb(COLORS['gold']), outline=hex_to_rgb(COLORS['gold']), width=2)
    draw.text((500, 580), "Buscar Conexiones", fill=hex_to_rgb(COLORS['ink']), font=title_font)
    
    # Graph panel (800px height)
    draw.rectangle([30, 680, 1149, 1480], fill=hex_to_rgb(COLORS['panel']), outline=hex_to_rgb(COLORS['line']), width=2)
    draw.text((50, 700), "MAPA DE CONEXIONES", fill=hex_to_rgb(COLORS['gold']), font=body_font)
    draw.text((50, 740), "4 nodos · 3 enlaces", fill=hex_to_rgb(COLORS['muted']), font=body_font)
    
    # Nodos del grafo (simplificados)
    nodes = [
        (200, 900, 'NEED-001', COLORS['gold']),
        (600, 1200, 'PRJ-014', COLORS['mint']),
        (900, 900, 'INV-032', COLORS['copper']),
        (400, 1100, 'GRP-009', COLORS['muted'])
    ]
    
    for x, y, label, color in nodes:
        # Círculo del nodo
        draw.ellipse([x - 40, y - 40, x + 40, y + 40], fill=hex_to_rgb(color), outline=hex_to_rgb(COLORS['line']), width=2)
        # Texto del nodo
        draw.text((x - 30, y - 10), label[:8], fill=hex_to_rgb(COLORS['ink']), font=body_font)
    
    # Conexiones entre nodos
    draw.line([nodes[0][:2], nodes[1][:2]], fill=hex_to_rgb(COLORS['gold']), width=3)
    draw.line([nodes[1][:2], nodes[2][:2]], fill=hex_to_rgb(COLORS['gold']), width=3)
    draw.line([nodes[2][:2], nodes[3][:2]], fill=hex_to_rgb(COLORS['gold']), width=3)
    
    # Results panel (500px height)
    draw.rectangle([30, 1510, 1149, 2010], fill=hex_to_rgb(COLORS['panel']), outline=hex_to_rgb(COLORS['line']), width=2)
    draw.text((50, 1530), "RANKING", fill=hex_to_rgb(COLORS['gold']), font=body_font)
    draw.text((50, 1570], "3 resultados", fill=hex_to_rgb(COLORS['muted']), font=body_font)
    
    # Resultados simplificados
    results = [
        ("01", "PRJ-014", "Aprendizaje adaptativo", 0.91),
        ("02", "INV-032", "Analítica educativa", 0.76),
        ("03", "GRP-009", "IA aplicada", 0.62)
    ]
    
    for i, (rank, id_val, title, score) in enumerate(results):
        y = 1620 + i * 120
        draw.rectangle([50, y, 1129, y + 100], fill=hex_to_rgb(COLORS['ink']), outline=hex_to_rgb(COLORS['line']), width=1)
        draw.text((70, y + 20), rank, fill=hex_to_rgb(COLORS['paper']), font=title_font)
        draw.text((130, y + 20), id_val, fill=hex_to_rgb(COLORS['gold']), font=body_font)
        draw.text((130, y + 50), title, fill=hex_to_rgb(COLORS['muted']), font=body_font)
        draw.text((1000, y + 30), f"{score:.2f}", fill=hex_to_rgb(COLORS['paper']), font=title_font)
    
    # Footer
    draw.rectangle([0, 2480, 1179, 2556], fill=hex_to_rgb(COLORS['panel']))
    draw.text((30, 2500], "SaberLink - Shipaton 2026 - Next Gen Award", fill=hex_to_rgb(COLORS['muted']), font=body_font)
    
    # Guardar
    output_path = 'assets/screenshots/app_screenshot.png'
    img.save(output_path)
    print(f"✅ Screenshot placeholder creado: {output_path} (1179×2556)")
    return True

def main():
    """Función principal para generar todos los assets."""
    print("🎨 Generando assets para Devpost - Shipaton 2026")
    print("=" * 50)
    
    if not PIL_AVAILABLE:
        print("❌ Error: PIL/Pillow no está instalado")
        print("Instala con: pip install Pillow")
        return
    
    success = True
    
    # Generar icono
    if not create_app_icon():
        success = False
    
    # Generar screenshot
    if not create_screenshot_placeholder():
        success = False
    
    if success:
        print("=" * 50)
        print("✅ Todos los assets generados exitosamente")
        print("📁 Ubicación:")
        print("   - Icono: assets/icons/app_icon.png")
        print("   - Screenshot: assets/screenshots/app_screenshot.png")
        print("=" * 50)
        print("📝 Recuerda:")
        print("   - El screenshot es un placeholder")
        print("   - Para el real, captura la app funcionando")
        print("   - Usa Canva o Squoosh.app para redimensionar")
    else:
        print("❌ Hubo errores al generar los assets")

if __name__ == "__main__":
    main()