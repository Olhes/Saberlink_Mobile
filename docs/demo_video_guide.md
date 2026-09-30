# Guía para Video de Demostración - Next Gen Award

## Requisitos del Shipaton Next Gen Award

Para tu participación en la categoría **Next Gen Award**, necesitas:

### ✅ Lo que ya está implementado:
- [x] **SDK RevenueCat integrado** en frontend web y móvil
- [x] **Sistema de límites de uso** funcionando
- [x] **3 planes de suscripción** (Gratis, Pro Mensual, Pro Anual)
- [x] **UI de planes/pricing** interactiva
- [x] **Tracking de uso en tiempo real**
- [x] **Arquitectura modular** en backend (saberlink/payments/)

### 📋 Lo que necesitas para el video:

## 1. Guion del Video (2 minutos máximo)

### Intro (15 segundos)
- Mostrar el logo de SaberLink
- Narración: "SaberLink es un atlas del conocimiento institucional que conecta investigaciones, proyectos y expertos"
- Mostrar la interfaz principal

### Demo Principal (45 segundos)
- **Escena 1**: Búsqueda por ID existente
  - Mostrar input "NEED-001"
  - Clic en "Buscar conexiones"
  - Mostrar grafo de conexiones
  - Narración: "Dado un ID de necesidad, SaberLink traza automáticamente la red de conexiones"

- **Escena 2**: Búsqueda por texto libre
  - Cambiar a modo "Texto libre"
  - Escribir: "Necesitamos mejorar el aprendizaje con IA"
  - Clic en "Buscar conexiones"
  - Mostrar resultados y explicación
  - Narración: "También funciona con texto libre, creando una necesidad temporal"

- **Escena 3**: Subida de PDF
  - Cambiar a modo "PDF temporal"
  - Seleccionar un PDF de prueba
  - Mostrar procesamiento
  - Narración: "Puedes subir PDFs y el sistema extrae el conocimiento automáticamente"

### Monetización con RevenueCat (45 segundos)
- **Escena 4**: Sistema de límites
  - Mostrar indicadores de uso en el header
  - Narración: "SaberLink incluye un sistema de límites de uso por suscripción"

- **Escena 5**: Página de planes
  - Clic en botón "Planes"
  - Mostrar los 3 planes con límites
  - Narración: "Integramos RevenueCat SDK para gestionar suscripciones con 3 planes diferentes"

- **Escena 6**: Demo del SDK
  - Clic en plan "Pro Mensual"
  - Mostrar el flujo de compra (simulado o real con SDK)
  - Narración: "El SDK de RevenueCat maneja todo el proceso de compra de forma segura"

- **Escena 7**: Actualización de límites
  - Mostrar cómo se actualizan los límites después de la "compra"
  - Narración: "Los límites se actualizan inmediatamente, permitiendo más consultas y PDFs"

### Cierre (15 segundos)
- Mostrar el código en GitHub
- Narración: "Todo el código es open source en GitHub, con arquitectura modular y limpia"
- Pantalla final con logo y "SaberLink - Shipaton 2026"

## 2. Configuración para el Video

### Backend (Terminal 1)
```powershell
cd backend
uvicorn api.main:app --reload --port 8000
```

### Frontend Web (Terminal 2)
```powershell
cd frontend
npm run dev
# Abre http://localhost:8000
```

### App Móvil (Opcional)
```powershell
cd mobile
npm install
Copy-Item .env.example .env
# Configura EXPO_PUBLIC_API_BASE con tu IP local
npx expo start
# Escanea QR con Expo Go
```

## 3. Archivos de Prueba

### PDF de Prueba
Crea un PDF simple para demostrar la subida:
- Nombre: `research_paper.pdf`
- Contenido: Un paper académico sobre aprendizaje con IA
- Ubicación: `mobile/test_files/research_paper.pdf`

### IDs de Prueba
Usa estos IDs que funcionan en modo demo:
- `NEED-001` - Necesidad sobre IA en educación
- `PRJ-014` - Proyecto de aprendizaje adaptativo
- `INV-032` - Investigador de analítica educativa

## 4. Captura del Video

### Opciones de Grabación:
1. **OBS Studio** (gratis) - Para grabar pantalla
2. **Loom** - Grabación fácil con narración
3. **Zoom** - Grabación de pantalla compartida
4. **Phone camera** - Grabar directamente el móvil

### Resolución Requerida:
- Mínimo: 720p
- Recomendado: 1080p
- Formato: MP4

### Tips para el Video:
- **Iluminación**: Buena luz natural
- **Audio**: Microfone claro, sin ruido de fondo
- **Duración**: Máximo 2 minutos (se aplica estrictamente)
- **Sin música con copyright**: Usa música libre de derechos o sin música

## 5. Subida a YouTube/Vimeo

### Pasos:
1. Sube el video a YouTube o Vimeo
2. Configura como "Público" o "No listado"
3. Copia el enlace
4. Úsalo en el formulario de Devpost

### Título Sugerido:
"SaberLink - Atlas del Conocimiento Institucional con RevenueCat"

### Descripción:
```
SaberLink es una aplicación que conecta investigaciones, proyectos y expertos en instituciones académicas. 
Integra RevenueCat SDK para gestión de suscripciones con límites de uso.

Participante: Shipaton 2026 - Next Gen Award
Categoría: Estudiante
```

## 6. Código en GitHub

### Estructura del Repositorio:
```
saberlink-mobile/
├── backend/          # Backend modular con Python
├── frontend/         # Frontend web con React
├── mobile/          # App móvil con Expo
├── docs/            # Documentación
└── README.md        # Documentación principal
```

### Asegúrate de:
- [ ] Repositorio público en GitHub
- [ ] README.md claro y completo
- [ ] Licencia open source (MIT recomendada)
- [ ] Todos los archivos necesarios incluidos
- [ ] Sin secrets/keys en el código

## 7. Checklist de Devpost

### Para el formulario de Devpost:

**Descripción:**
- Explicar el problema que resuelve
- Describir la solución técnica
- Mencionar la integración con RevenueCat
- Destacar la arquitectura modular

**Enlaces:**
- [ ] Repositorio GitHub
- [ ] Video de demostración (YouTube/Vimeo)
- [ ] (Opcional) Enlace a la app en tiendas (no requerido para Next Gen)

**Assets:**
- [ ] Icono 1024×1024 px
- [ ] Screenshot 1179×2556 px (sin marco)
- [ ] Código promocional o prueba gratis

**Categoría:**
- [ ] Next Gen Award (Estudiantes)
- [ ] HAMM Award (Monetización)

## 8. Destacar para los Jueces

### Puntos Fuertes para tu Video:

1. **Integración Real del SDK**:
   - Mostrar que el SDK está realmente implementado
   - Demostrar el flujo de compra completo
   - Explicar la arquitectura modular

2. **Sistema de Límites Funcional**:
   - Mostrar cómo se actualizan los contadores
   - Demostrar la validación de límites
   - Explicar el reinicio mensual automático

3. **Arquitectura Modular**:
   - Mencionar que el módulo de pagos puede eliminarse sin romper el core
   - Mostrar la estructura de archivos
   - Explicar la separación de responsabilidades

4. **UX Premium**:
   - UI limpia y profesional
   - Feedback inmediato al usuario
   - Indicadores de uso en tiempo real

## 9. Script de Narración (Español)

```text
"SaberLink es un atlas del conocimiento institucional que conecta investigaciones, proyectos y expertos académicos. 

Puedes buscar por ID existente, como NEED-001, y el sistema traza automáticamente la red de conexiones, mostrando proyectos relacionados, investigadores y grupos de investigación.

También funciona con texto libre: simplemente describes lo que estás investigando y SaberLink crea una necesidad temporal y encuentra las conexiones relevantes.

Para el análisis de documentos, puedes subir PDFs y el sistema extrae el conocimiento automáticamente usando procesamiento de texto avanzado.

SaberLink incluye un sistema completo de monetización con RevenueCat SDK. Tres planes de suscripción con límites de uso diferentes: Gratis para explorar, Pro Mensual para uso intensivo, y Pro Anual para investigación continua.

El SDK de RevenueCat maneja todo el proceso de compra de forma segura, y los límites se actualizan inmediatamente, permitiendo más consultas y análisis de PDFs.

Todo el código es open source con arquitectura modular limpia, siguiendo mejores prácticas de desarrollo. 

SaberLink - Shipaton 2026, Next Gen Award."
```

## 10. Tiempos Sugeridos

- 0:00-0:15 - Intro y logo
- 0:15-0:30 - Búsqueda por ID
- 0:30-0:45 - Búsqueda por texto
- 0:45-1:00 - Subida de PDF
- 1:00-1:15 - Sistema de límites
- 1:15-1:30 - Página de planes
- 1:30-1:45 - Demo SDK RevenueCat
- 1:45-2:00 - Cierre y código

## 11. Errores Comunes a Evitar

❌ **No hacer:**
- Exceder los 2 minutos (jueces no verán más allá)
- Usar música con copyright
- Mostrar información personal o secrets
- Grabar con mala iluminación o audio
- Mostrar la app sin datos/funcionamiento

✅ **Sí hacer:**
- Mantener el video conciso y enfocado
- Mostrar el SDK realmente funcionando
- Explicar la arquitectura modular
- Demostrar el valor del producto
- Mostrar código limpio y bien estructurado

## 12. Preparación Final

### Antes de grabar:
1. ✅ Prueba todos los flujos de la app
2. ✅ Verifica que el backend y frontend funcionen
3. ✅ Prepara los archivos de prueba (PDF)
4. ✅ Configura el entorno de grabación
5. ✅ Practica el guion varias veces

### Después de grabar:
1. ✅ Revisa el audio y video
2. ✅ Verifica la duración (máx 2 min)
3. ✅ Sube a YouTube/Vimeo
4. ✅ Prepara el repositorio GitHub
5. ✅ Completa el formulario Devpost

---

**¡Buena suerte con el Shipaton 2026!** 🚀

Tu implementación de RevenueCat con arquitectura modular es sólida y demuestra habilidades avanzadas de desarrollo. El Next Gen Award es perfecto para mostrar tu talento como estudiante desarrollador.