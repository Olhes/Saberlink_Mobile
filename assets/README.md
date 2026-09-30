# Assets para Devpost - Shipaton 2026

## Requisitos de Assets

### 1. Icono de la App (1024×1024 px)
- **Tamaño**: 1024×1024 píxeles
- **Formato**: PNG con transparencia
- **Ubicación**: `assets/icons/app_icon.png`
- **Estilo**: Minimalista, profesional, relacionado con conocimiento/conexiones

### 2. Screenshot de la App (1179×2556 px)
- **Tamaño**: 1179×2556 píxeles
- **Formato**: PNG o JPG
- **Ubicación**: `assets/screenshots/app_screenshot.png`
- **Sin marco de dispositivo**: Solo la interfaz de la app
- **Contenido**: Mostrar la pantalla principal con grafo de conexiones

## Instrucciones para Crear los Assets

### Opción 1: Usar Herramientas Online (Recomendado)

#### Para el Icono:
1. **Canva** (gratuito):
   - Crea un diseño de 1024×1024 px
   - Usa un fondo oscuro (#101513 - color ink de SaberLink)
   - Añade un logo simple: círculos conectados o un átomo de conocimiento
   - Colores: Gold (#d5a94d), Mint (#8fbe9d), Copper (#db8662)
   - Exporta como PNG

2. **Figma** (gratuito):
   - Crea un frame de 1024×1024 px
   - Diseña un logo minimalista
   - Exporta como PNG

#### Para el Screenshot:
1. **Captura desde el navegador**:
   - Abre http://localhost:5173
   - Asegúrate de tener una búsqueda activa con resultados
   - Usa la herramienta de captura de pantalla
   - Recorta a 1179×2556 px

2. **Herramientas de redimensionado**:
   - **Squoosh.app** (gratuito de Google)
   - **TinyPNG.com** (compresión)
   - **Canva** (redimensionado preciso)

### Opción 2: Diseño Personalizado

#### Paleta de Colores de SaberLink:
```css
--color-ink: #101513        /* Fondo principal */
--color-panel: #18221e      /* Paneles */
--color-paper: #f5f0e4      /* Texto claro */
--color-muted: #9ea99b      /* Texto secundario */
--color-gold: #d5a94d       /* Acentos principales */
--color-mint: #8fbe9d       /* Éxito/activos */
--color-copper: #db8662     /* Alertas/errores */
--color-line: #334139       /* Bordes */
```

#### Concepto del Icono:
- **Tema**: Conexiones de conocimiento
- **Elementos**: 
  - 3 círculos conectados (representando entidades)
  - Líneas doradas conectando los círculos
  - Fondo oscuro con el logo centrado
- **Estilo**: Minimalista, moderno, profesional

#### Concepto del Screenshot:
- **Pantalla**: Resultados de búsqueda con grafo
- **Elementos visuales**:
  - Header con logo "SaberLink"
  - Panel de búsqueda con input
  - Grafo de conexiones visualizado
  - Lista de resultados con rankings
  - Indicadores de uso en el header
- **Estado**: Con una búsqueda activa mostrando resultados

### Opción 3: Usar Python para Generar (Avanzado)

```python
from PIL import Image, ImageDraw, ImageFont
import os

# Crear directorio si no existe
os.makedirs('assets/icons', exist_ok=True)
os.makedirs('assets/screenshots', exist_ok=True)

# Generar icono 1024x1024
def create_app_icon():
    size = (1024, 1024)
    img = Image.new('RGB', size, '#101513')
    draw = ImageDraw.Draw(img)
    
    # Centros de los círculos
    centers = [
        (512, 300),   # Círculo superior
        (350, 600),   # Círculo inferior izquierdo
        (674, 600)    # Círculo inferior derecho
    ]
    
    # Dibujar conexiones
    draw.line([centers[0], centers[1]], fill='#d5a94d', width=8)
    draw.line([centers[1], centers[2]], fill='#d5a94d', width=8)
    draw.line([centers[2], centers[0]], fill='#d5a94d', width=8)
    
    # Dibujar círculos
    for center in centers:
        draw.ellipse([
            center[0] - 60, center[1] - 60,
            center[0] + 60, center[1] + 60
        ], fill='#8fbe9d', outline='#d5a94d', width=4)
    
    # Guardar
    img.save('assets/icons/app_icon.png')
    print("Icono creado: assets/icons/app_icon.png")

# Crear screenshot placeholder 1179x2556
def create_screenshot_placeholder():
    size = (1179, 2556)
    img = Image.new('RGB', size, '#101513')
    draw = ImageDraw.Draw(img)
    
    # Header
    draw.rectangle([0, 0, 1179, 100], fill='#18221e')
    
    # Placeholder para contenido
    draw.rectangle([50, 150, 1129, 400], fill='#18221e', outline='#334139', width=2)
    draw.rectangle([50, 450, 1129, 1200], fill='#18221e', outline='#334139', width=2)
    draw.rectangle([50, 1250, 1129, 2000], fill='#18221e', outline='#334139', width=2)
    
    # Texto placeholder
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    draw.text((50, 80), "SaberLink - Atlas del Conocimiento", fill='#f5f0e4', font=font)
    draw.text((50, 170), "Búsqueda de Conexiones", fill='#9ea99b', font=font)
    draw.text((50, 470), "Grafo de Conexiones", fill='#9ea99b', font=font)
    draw.text((50, 1270), "Resultados de Ranking", fill='#9ea99b', font=font)
    
    # Guardar
    img.save('assets/screenshots/app_screenshot.png')
    print("Screenshot placeholder creado: assets/screenshots/app_screenshot.png")

if __name__ == "__main__":
    create_app_icon()
    create_screenshot_placeholder()
```

## Checklist de Assets

### Para el Icono (1024×1024 px):
- [ ] Tamaño exacto: 1024×1024 px
- [ ] Formato: PNG con transparencia
- [ ] Diseño: Minimalista y profesional
- [ ] Colores: Paleta de SaberLink
- [ ] Legible a diferentes tamaños
- [ ] Sin texto (solo gráfico)

### Para el Screenshot (1179×2556 px):
- [ ] Tamaño exacto: 1179×2556 px
- [ ] Sin marco de dispositivo
- [ ] Muestra funcionalidad clave
- [ ] Interfaz limpia y profesional
- [ ] Buena calidad y resolución
- [ ] Datos visibles (no vacío)

## Archivos de Referencia

### Ubicación Final:
```
assets/
├── icons/
│   └── app_icon.png (1024×1024)
└── screenshots/
    └── app_screenshot.png (1179×2556)
```

### Nombres Recomendados:
- Icono: `saberlink_icon.png`
- Screenshot: `saberlink_screenshot.png`

## Tips para Capturar Screenshots Reales

### Desde el Frontend Web:
1. **Prepara una búsqueda interesante**:
   - Usa ID: `NEED-001`
   - Configura top_k: 8
   - Ejecuta la búsqueda

2. **Configura el navegador**:
   - Zoom al 100%
   - Modo pantalla completa (F11)
   - Oculta bookmarks/devtools

3. **Captura**:
   - Windows: Win+Shift+S
   - Mac: Cmd+Shift+4
   - Linux: PrtScn

4. **Redimensiona**:
   - Usa Canva o Squoosh.app
   - Exactamente 1179×2556 px
   - Asegúrate de no perder calidad

### Desde la App Móvil:
1. **Configura Expo Go** en tu teléfono
2. **Conecta al backend** con tu IP local
3. **Realiza una búsqueda** con resultados
4. **Captura la pantalla** del teléfono
5. **Redimensiona** a 1179×2556 px

## Verificación Final

### Antes de subir a Devpost:
- [ ] Icono es 1024×1024 px exactos
- [ ] Screenshot es 1179×2556 px exactos
- [ ] Ambos archivos son PNG/JPG
- [ ] Diseño es profesional y coherente
- [ ] Sin elementos de terceros (logos, marcas)
- [ ] Calidad de imagen es alta
- [ ] Nombres de archivos son descriptivos

## Herramientas Recomendadas

### Gratuitas:
- **Canva**: Diseño gráfico fácil
- **Figma**: Diseño UI/UX profesional
- **Squoosh.app**: Compresión y redimensionado (Google)
- **TinyPNG**: Compresión de imágenes
- **GIMP**: Edición de imágenes avanzada

### De Pago:
- **Adobe Photoshop**: Edición profesional
- **Sketch**: Diseño UI/UX para Mac
- **Affinity Designer**: Alternativa a Photoshop

---

**Nota**: Los assets son cruciales para la primera impresión en Devpost. Dedica tiempo a crear iconos y screenshots de alta calidad que representen profesionalmente tu aplicación.