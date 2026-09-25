# SaberLink Mobile

MVP Android-first construido con Expo y React Native. Reutiliza la API FastAPI existente: no duplica el pipeline de embeddings, scoring ni grafo.

## Arranque inmediato sin Android Studio

```powershell
cd mobile
npm install
Copy-Item .env.example .env
# En un teléfono físico, cambia EXPO_PUBLIC_API_BASE por la IP local de tu PC.
npx expo start
```

Instala **Expo Go** en el teléfono y escanea el QR. La API incluye un modo demo autonomo, por lo que puedes probar ID, texto libre y PDF sin instalar datos externos. Para datos reales, ejecuta la API desde `backend`:

```powershell
uvicorn api.main:app --reload --port 8000
```

## RevenueCat y entrega del hackatón

El botón `PRO` ya contiene el flujo de compra y usa `react-native-purchases`. Sin clave, funciona en modo demo; para una compra real:

1. Crea un proyecto en RevenueCat, una offering `default` y un producto mensual/anual.
2. Define `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY` en `mobile/.env`.
3. Crea un development build con EAS, porque Expo Go no carga módulos nativos de RevenueCat:

```powershell
npm install -g eas-cli
eas login
eas build:configure
eas build --profile preview --platform android
```

No necesitas Android Studio ni un JDK local para este camino: EAS compila en la nube. La clave pública de RevenueCat no es un secreto; nunca pongas una clave privada en la app.

## Flujo del MVP

- Consulta por ID existente, texto libre o PDF.
- Ranking explicable y evidencia trazable.
- Mapa horizontal táctil con selección de nodos.
- Oportunidad relacionada cuando el backend la devuelve.
- Paywall Pro listo para RevenueCat, con fallback demo para la presentación.

## Biblioteca real de PDFs

La pestaña `Biblioteca` crea un proyecto local llamado `mi-investigacion`.
Puedes seleccionar varios PDFs desde el teléfono. La API los guarda en
`backend/processed/user_library/`, extrae el texto por páginas, lo divide en
fragmentos y genera embeddings locales con `sentence-transformers` en ChromaDB.

Después escribe una pregunta en la Biblioteca y pulsa `Trazar conexiones`.
El ranking se calcula contra los fragmentos de los PDFs indexados y cada
resultado conserva el nombre del archivo, la página y el fragmento usado.

Este flujo no necesita Cohere. Cohere queda como mejora opcional para
re-ranking o respuestas generativas.

El backend debe ser accesible desde el teléfono. En la misma red Wi-Fi usa la IPv4 de tu PC, por ejemplo `http://192.168.1.100:8000`; `localhost` en el teléfono significa el propio teléfono.
