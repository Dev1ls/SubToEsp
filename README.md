# SubToEsp

Cinematic English-to-Spanish subtitles that sound like streaming dialogue, not Google Translate.

Literal machine translation writes subtitles the way a dictionary would: *vosotros*, *coche*, “estoy yendo a”. On screen that reads as a webpage, not as someone talking. SubToEsp is a desktop app that adapts English `.srt` files into spoken Latin-American Spanish — latino neutro — keeping cue timing, line breaks, and the tone of the scene.

With a Gemini key, each batch is treated as dialogue adaptation: register, sarcasm, and proper names stay put, and Spain-only wording stays out. Without one, the app uses Google Translate and MyMemory, then applies Latino post-rules (*vosotros* → *ustedes*, *coche* → *auto*, and the usual calques). A 20-cue preview shows the voice before the full file runs. Every cue comes back tagged OK, RARO, or MAL, so the weak lines are obvious.

One Python and Tkinter window, packaged with PyInstaller in `dist/`. The footer reads VVoz.enterprise.

## Highlights

- Adapts sense and register, not word-for-word Spanish
- Gemini when a key is present; Google Translate / MyMemory plus Latino rules otherwise
- Preview of 20 cues, then the whole file
- Quality tags on every cue: OK, RARO, MAL
- Plain-text SRT, safe for Smart TVs
- Desktop build shipped in `dist/`

## Stack

Python · tkinter · deep_translator · langdetect · Pillow · requests · optional Gemini

## Status

Personal utility tool. Public repository. Solo work by Nicolas Wozniak (Chile) — TECHNOLOGIES SOLUTIONS CARLOS NICOLAS CONCHA WOZNIAK E.I.R.L. / W.Enterprise.

---

# SubToEsp

Subtítulos cinematográficos de inglés a español que suenan a diálogo de streaming, no a Google Translate.

La traducción literal escribe subtítulos como un diccionario: *vosotros*, *coche*, “estoy yendo a”. En pantalla se lee texto pegado, no a alguien hablando. SubToEsp es una app de escritorio que adapta archivos `.srt` en inglés a español latinoamericano hablado — latino neutro — respetando tiempos, saltos de línea y el tono de la escena.

Con una clave de Gemini, cada lote se trabaja como adaptación de diálogo: se conserva el registro, el sarcasmo y los nombres propios, y queda fuera el léxico de España. Sin clave, usa Google Translate y MyMemory y después aplica reglas latinas (*vosotros* → *ustedes*, *coche* → *auto*, y los calcos de siempre). Una vista previa de 20 cues muestra la voz antes de traducir el archivo entero. Cada cue vuelve etiquetada OK, RARO o MAL, así que las líneas flojas se ven al tiro.

Una sola ventana en Python y Tkinter, empaquetada con PyInstaller en `dist/`. El pie de marca dice VVoz.enterprise.

## Destacados

- Adapta sentido y registro, no un español palabra por palabra
- Gemini cuando hay clave; si no, Google Translate / MyMemory más reglas latinas
- Vista previa de 20 cues y después el archivo completo
- Etiqueta de calidad en cada cue: OK, RARO, MAL
- SRT en texto plano, compatible con Smart TV
- Ejecutable de escritorio en `dist/`

## Stack

Python · tkinter · deep_translator · langdetect · Pillow · requests · Gemini opcional

## Estado

Herramienta personal. Repositorio público. Trabajo en solitario de Nicolas Wozniak (Chile) — TECHNOLOGIES SOLUTIONS CARLOS NICOLAS CONCHA WOZNIAK E.I.R.L. / W.Enterprise.
