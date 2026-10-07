# -*- coding: utf-8 -*-
import json
import os
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import requests
from deep_translator import MyMemoryTranslator
from langdetect import detect
from PIL import Image, ImageTk

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = getattr(Image, "LANCZOS", Image.ANTIALIAS)

PREVIEW_CUES = 20
LOTE_LLM = 4
VARIANT = "latino neutro"

PROMPT_ADAPTADOR = """Eres un adaptador profesional de subtítulos cinematográficos EN→ES.

Objetivo: que suene a diálogo hablado en español latino neutro de cine/streaming, no a traducción automática.

Reglas:
1. Adapta el sentido, el tono y el registro. No traduzcas palabra por palabra.
2. Usa español latino neutro: tú / ustedes. Nunca vosotros, vale, tío, guay, coche, móvil, ordenador, piso (por departamento).
3. Concordancia obligatoria: género, número, persona, tiempos y preposiciones.
4. Mantén el mismo tuteo en todo el lote. No uses voseo rioplatense ni ustedeo formal salvo que el original lo pida.
5. Respeta el registro: calle, formal, infantil, grosero, irónico. Una puteada se adapta por intensidad, no por calco.
6. Nombres propios, apodos, marcas, títulos y términos de universo NO se traducen.
7. Evita calcos: "I am going to" ≠ "Estoy yendo a"; "actually" ≠ "actualmente"; "excited" ≠ "excitado"; "realize" ≠ "realizar".
8. Cada CUE de entrada = una CUE de salida. No juntes, no partas, no reordenes.
9. Conserva la cantidad de líneas internas de cada cue.
10. Largo similar al original (aprox. ±20%). Una cue corta sigue corta.
11. No uses etiquetas HTML ni ASS: nada de <i>, <b>, <font> ni {\\i1}. Texto plano, compatible con Smart TV.
12. No expliques. No pongas notas. No traduzcas números de cue ni timestamps.
13. Si una línea ya está en español o es ininteligible, déjala igual.
14. Interjecciones: adáptalas al tono ("Yeah." → "Sí." / "Claro." / "Ajá.").
15. Chistes y sarcasmo: prioriza el efecto, no la literalidad.
16. No mezcles dos hablantes. Cada cue es independiente.

Formato de entrada:
CUE <n>
<texto original>

Formato de salida (estricto):
CUE <n>
<texto adaptado, misma cantidad de líneas>
"""

HEADERS_TRADUCCION = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

PALABRAS_EN = {
    "the", "and", "you", "your", "you're", "i'm", "i've", "we're", "they're",
    "this", "that", "what", "have", "with", "don't", "doesn't", "it's", "just",
    "they", "are", "not", "for", "but", "because", "about", "from", "will",
    "would", "could", "should", "gonna", "wanna", "gotta",
}

REEMPLAZOS_LATINO = (
    (r"\bVosotros\b", "Ustedes"),
    (r"\bvosotros\b", "ustedes"),
    (r"\bVosotras\b", "Ustedes"),
    (r"\bvosotras\b", "ustedes"),
    (r"\bsois\b", "son"),
    (r"\bestáis\b", "están"),
    (r"\bestais\b", "están"),
    (r"\btenéis\b", "tienen"),
    (r"\bteneis\b", "tienen"),
    (r"\bqueréis\b", "quieren"),
    (r"\bquereis\b", "quieren"),
    (r"\bhacéis\b", "hacen"),
    (r"\bhaceis\b", "hacen"),
    (r"\bpodéis\b", "pueden"),
    (r"\bpodeis\b", "pueden"),
    (r"\bdebéis\b", "deben"),
    (r"\bdebeis\b", "deben"),
    (r"\bvuestro\b", "su"),
    (r"\bvuestra\b", "su"),
    (r"\bvuestros\b", "sus"),
    (r"\bvuestras\b", "sus"),
    (r"\bCoche\b", "Auto"),
    (r"\bcoche\b", "auto"),
    (r"\bcoches\b", "autos"),
    (r"\bOrdenador\b", "Computadora"),
    (r"\bordenador\b", "computadora"),
    (r"\bMóvil\b", "Celular"),
    (r"\bmóvil\b", "celular"),
    (r"\bmovil\b", "celular"),
    (r"\bZumo\b", "Jugo"),
    (r"\bzumo\b", "jugo"),
    (r"\bGuay\b", "Genial"),
    (r"\bguay\b", "genial"),
    (r"\bChaval\b", "Chico"),
    (r"\bchaval\b", "chico"),
    (r"\bVale\.", "Está bien."),
    (r"\bvale\.", "está bien."),
    (r"\bestoy yendo a\b", "voy a"),
    (r"\bEstoy yendo a\b", "Voy a"),
    (r"\bestamos yendo a\b", "vamos a"),
    (r"\bEstamos yendo a\b", "Vamos a"),
)

CALCOS_RAROS = (
    "estoy yendo a",
    "estamos yendo a",
    "tomar esto",
    "realizar que",
    "estoy teniendo",
    "hacer una llamada",
)


def resource_path(nombre):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, nombre)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), nombre)


def ruta_config():
    return os.path.join(os.path.expanduser("~"), ".subtoesp.json")


def cargar_config():
    try:
        with open(ruta_config(), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def guardar_config(data):
    with open(ruta_config(), "w", encoding="utf-8") as f:
        json.dump(data, f)


def api_key_gemini():
    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or cargar_config().get("gemini_api_key")
        or ""
    ).strip()


def detectar_idioma(texto):
    lineas = texto.split("\n")
    texto_junto = " ".join(l for l in lineas if l and not l.isdigit() and "-->" not in l)
    try:
        return detect(texto_junto)
    except Exception:
        return "desconocido"


def obtener_nombre_con_1(nombre_archivo):
    base, ext = os.path.splitext(nombre_archivo)
    return f"{base} (1){ext}"


def limpiar_formato_srt(texto):
    texto = re.sub(r"</?[^>]+>", "", texto or "")
    texto = re.sub(r"\{[^}]*\}", "", texto)
    texto = (
        texto.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    return re.sub(r"[ \t]+", " ", texto).strip()


def limpiar_lineas(lineas):
    return [limpiar_formato_srt(linea) for linea in (lineas or [])]


def texto_cue(lineas):
    return " ".join(linea for linea in limpiar_lineas(lineas) if linea)


def tiempo_corto(tiempo):
    inicio = tiempo.split("-->")[0].strip()
    return inicio.split(",")[0] if "," in inicio else inicio[:8]


def parsear_cues(texto):
    texto = texto.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").strip()
    cues = []
    for bloque in re.split(r"\n\s*\n", texto):
        lineas = bloque.split("\n")
        if not lineas:
            continue
        tiempo_idx = next((i for i, linea in enumerate(lineas) if "-->" in linea), None)
        if tiempo_idx is None:
            continue
        numero = lineas[tiempo_idx - 1].strip() if tiempo_idx > 0 else str(len(cues) + 1)
        cues.append({
            "numero": numero,
            "tiempo": lineas[tiempo_idx].strip(),
            "dialogo": limpiar_lineas(lineas[tiempo_idx + 1:]),
        })
    return cues


def reconstruir_desde_cues(cues):
    partes = []
    for cue in cues:
        dialogo = limpiar_lineas(cue.get("traducido") or cue["dialogo"])
        dialogo = dialogo or [""]
        partes.append("\r\n".join([cue["numero"], cue["tiempo"], *dialogo]))
    return "\r\n\r\n".join(partes) + "\r\n"


def postprocesar_latino(texto):
    for patron, reemplazo in REEMPLAZOS_LATINO:
        texto = re.sub(patron, reemplazo, texto)
    return texto


def ajustar_lineas(partes, original):
    partes = [p.rstrip() for p in partes if p is not None]
    if not original:
        return partes
    if len(partes) == 1 and len(original) == 2:
        palabras = partes[0].split()
        if len(palabras) >= 2:
            mitad = max(1, len(palabras) // 2)
            return [" ".join(palabras[:mitad]), " ".join(palabras[mitad:])]
    if len(partes) != len(original):
        return (partes + original[len(partes):])[:len(original)]
    return partes


def verificar_cue(original_lineas, adaptado_lineas):
    orig = "\n".join(original_lineas).strip()
    ada = "\n".join(adaptado_lineas).strip()
    if not orig:
        return "OK", ""
    if not ada:
        return "MAL", "vacio"
    if ada == orig and len(orig.split()) >= 4:
        return "MAL", "sigue en ingles"
    tokens = re.findall(r"[A-Za-z']+", ada.lower())
    ingles = sum(1 for token in tokens if token in PALABRAS_EN)
    if ingles >= 2:
        return "MAL", "quedo ingles"
    if len(adaptado_lineas) != len(original_lineas):
        return "RARO", "lineas distintas"
    if len(ada) > int(len(orig) * 1.45) + 8:
        return "RARO", "muy largo"
    baja = ada.lower()
    for calco in CALCOS_RAROS:
        if calco in baja:
            return "RARO", "calco literal"
    return "OK", ""


def _extraer_texto_traducido(data):
    if isinstance(data, str) and data.strip():
        return data
    if isinstance(data, list) and data:
        return _extraer_texto_traducido(data[0])
    raise RuntimeError("Formato de traduccion no reconocido")


def _traducir_chrome_ex(texto, destino="es", origen="auto"):
    url = "https://clients5.google.com/translate_a/t"
    params = {"client": "dict-chrome-ex", "sl": origen, "tl": destino, "q": texto}
    respuesta = requests.get(url, params=params, headers=HEADERS_TRADUCCION, timeout=20)
    respuesta.raise_for_status()
    return _extraer_texto_traducido(respuesta.json())


def _traducir_gtx(texto, destino="es", origen="auto"):
    url = "https://translate.googleapis.com/translate_a/single"
    params = {"client": "gtx", "sl": origen, "tl": destino, "dt": "t", "q": texto}
    respuesta = requests.get(url, params=params, headers=HEADERS_TRADUCCION, timeout=20)
    respuesta.raise_for_status()
    data = respuesta.json()
    if not data or not data[0]:
        raise RuntimeError("Respuesta vacia de Google Translate")
    return "".join(parte[0] for parte in data[0] if parte and parte[0])


def _traducir_mymemory_http(texto, destino="es"):
    url = "https://api.mymemory.translated.net/get"
    params = {"q": texto, "langpair": f"en|{destino}"}
    respuesta = requests.get(url, params=params, timeout=20)
    respuesta.raise_for_status()
    data = respuesta.json()
    if data.get("responseStatus") != 200:
        raise RuntimeError(data.get("responseDetails") or "MyMemory fallo")
    traducido = (data.get("responseData") or {}).get("translatedText")
    if not traducido:
        raise RuntimeError("Respuesta vacia de MyMemory")
    if "MYMEMORY WARNING" in traducido.upper():
        raise RuntimeError(traducido)
    return traducido


def _traducir_mymemory(texto, destino="es"):
    return MyMemoryTranslator(source="en-GB", target="es-ES").translate(texto)


def _traducir_maquina(texto, destino="es"):
    errores = []
    motores = (
        ("Google", _traducir_chrome_ex),
        ("Google GTX", _traducir_gtx),
        ("MyMemory", _traducir_mymemory_http),
        ("MyMemory lib", _traducir_mymemory),
    )
    for nombre, motor in motores:
        try:
            return motor(texto, destino=destino)
        except Exception as e:
            errores.append(f"{nombre}: {e}")
            time.sleep(0.3)
    raise RuntimeError("No se pudo traducir. " + " | ".join(errores))


def _parsear_respuesta_llm(texto, cantidad):
    encontrados = {}
    patron = re.compile(r"CUE\s+(\d+)\s*\n(.*?)(?=\nCUE\s+\d+\s*\n|\Z)", re.S)
    for match in patron.finditer(texto.replace("\r\n", "\n")):
        encontrados[int(match.group(1))] = match.group(2).strip("\n")
    if not encontrados:
        raise RuntimeError("El modelo no devolvio cues reconocibles")
    return [
        limpiar_lineas(encontrados[i].split("\n")) if i in encontrados else None
        for i in range(1, cantidad + 1)
    ]


def adaptar_lote_gemini(cues, api_key):
    cuerpo = []
    for i, cue in enumerate(cues, 1):
        cuerpo.append(f"CUE {i}")
        cuerpo.append("\n".join(cue["dialogo"]) if cue["dialogo"] else "")
        cuerpo.append("")
    modelos = (
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-1.5-flash",
    )
    ultimo = None
    for modelo in modelos:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{modelo}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": PROMPT_ADAPTADOR + "\n\n" + "\n".join(cuerpo).strip()}]}],
            "generationConfig": {"temperature": 0.35},
        }
        try:
            respuesta = requests.post(url, json=payload, timeout=60)
            if respuesta.status_code == 404:
                ultimo = f"{modelo}: 404"
                continue
            respuesta.raise_for_status()
            data = respuesta.json()
            texto = data["candidates"][0]["content"]["parts"][0]["text"]
            return _parsear_respuesta_llm(texto, len(cues))
        except Exception as e:
            ultimo = f"{modelo}: {e}"
    raise RuntimeError(ultimo or "Gemini no respondio")


def adaptar_cue_maquina(cue):
    if not any(linea.strip() for linea in cue["dialogo"]):
        return list(cue["dialogo"])
    texto = "\n".join(cue["dialogo"])
    traducido = postprocesar_latino(_traducir_maquina(texto))
    return limpiar_lineas(ajustar_lineas(traducido.split("\n"), cue["dialogo"]))


def _aplicar_traduccion(cue, lineas):
    cue["traducido"] = limpiar_lineas(ajustar_lineas(lineas, cue["dialogo"]))
    cue["traducido"] = [postprocesar_latino(linea) for linea in cue["traducido"]]
    if not any(linea.strip() for linea in cue["traducido"]) and any(cue["dialogo"]):
        cue["traducido"] = list(cue["dialogo"])


def adaptar_cues(cues, cancelar, on_cue):
    clave = api_key_gemini()
    motor = "Gemini latino neutro" if clave else "Google + latino neutro"
    i = 0
    while i < len(cues):
        if cancelar.is_set():
            break
        if clave:
            lote = cues[i:i + LOTE_LLM]
            adaptados = None
            try:
                adaptados = adaptar_lote_gemini(lote, clave)
            except Exception:
                adaptados = None
            if adaptados is not None:
                for j, cue in enumerate(lote):
                    if cancelar.is_set():
                        return motor
                    try:
                        if adaptados[j]:
                            _aplicar_traduccion(cue, adaptados[j])
                        else:
                            cue["traducido"] = adaptar_cue_maquina(cue)
                        tag, motivo = verificar_cue(cue["dialogo"], cue["traducido"])
                    except Exception as e:
                        cue["traducido"] = list(cue["dialogo"])
                        tag, motivo = "MAL", str(e)[:40]
                    on_cue(i + j, len(cues), cue, tag, motivo)
                i += len(lote)
                continue
        cue = cues[i]
        try:
            cue["traducido"] = adaptar_cue_maquina(cue)
            tag, motivo = verificar_cue(cue["dialogo"], cue["traducido"])
        except Exception as e:
            cue["traducido"] = list(cue["dialogo"])
            tag, motivo = "MAL", str(e)[:40]
        on_cue(i, len(cues), cue, tag, motivo)
        i += 1
        time.sleep(0.15)
    return motor


def _en_ui(fn, *args):
    app.root.after(0, lambda fn=fn, args=args: fn(*args))


def cargar_subtitulo():
    archivo = filedialog.askopenfilename(filetypes=[("Archivos SRT", "*.srt")])
    if not archivo:
        return
    with open(archivo, "r", encoding="utf-8") as f:
        contenido = f.read()
    cues = parsear_cues(contenido)
    if not cues:
        messagebox.showerror("Error", "No se encontraron cues en el archivo.")
        return
    idioma = detectar_idioma(contenido)
    app.archivo_actual = archivo
    app.contenido_actual = contenido
    app.label_archivo.config(
        text=f"{os.path.basename(archivo)}   ·   {len(cues)} cues   ·   {idioma.upper()}"
    )
    app.progreso_barra["value"] = 0
    app.label_porcentaje.config(text="Listo. Proba 20 cues o traduce todo.")
    app.cargar_tabla(cues)


def detener_traduccion():
    app.cancelar.set()
    app.label_porcentaje.config(text="Deteniendo...")


def _set_ocupado(ocupado):
    estado = tk.DISABLED if ocupado else tk.NORMAL
    app.boton_cargar.config(state=estado)
    app.boton_preview.config(state=estado)
    app.boton_traducir.config(state=estado)
    app.boton_detener.config(state=tk.NORMAL if ocupado else tk.DISABLED)


def _append_log(indice, total, cue, tag, motivo):
    extra = f" · {motivo}" if motivo else ""
    app.actualizar_fila(indice, cue, tag, motivo)
    app.progreso_barra["value"] = int((indice + 1) * 100 / total)
    app.label_porcentaje.config(text=f"{indice + 1}/{total}   {tag}{extra}")


def _correr_adaptacion(cues, guardar, titulo):
    app.cancelar.clear()
    _en_ui(_set_ocupado, True)
    _en_ui(app.cargar_tabla, cues)
    ok = raro = mal = 0
    inicio = time.time()
    motor = "Gemini latino neutro"

    def on_cue(indice, total, cue, tag, motivo):
        nonlocal ok, raro, mal
        if tag == "OK":
            ok += 1
        elif tag == "RARO":
            raro += 1
        else:
            mal += 1
        _en_ui(_append_log, indice, total, cue, tag, motivo)

    try:
        motor = adaptar_cues(cues, app.cancelar, on_cue)
    except Exception:
        for i, cue in enumerate(cues):
            if cancelar_activo() or cue.get("traducido") is not None:
                continue
            try:
                cue["traducido"] = adaptar_cue_maquina(cue)
                tag, motivo = verificar_cue(cue["dialogo"], cue["traducido"])
            except Exception as e:
                cue["traducido"] = list(cue["dialogo"])
                tag, motivo = "MAL", str(e)[:40]
            on_cue(i, len(cues), cue, tag, motivo)

    duracion = round(time.time() - inicio, 1)
    hechos = sum(1 for cue in cues if cue.get("traducido") is not None)
    cancelado = app.cancelar.is_set()

    def finalizar():
        _set_ocupado(False)
        app.actualizar_motor()
        resumen = f"{titulo}  ·  {motor}  ·  OK {ok}   RARO {raro}   MAL {mal}   ({duracion}s)"
        if cancelado:
            app.label_porcentaje.config(text=f"Detenido  ·  {resumen}")
            if guardar and hechos:
                _guardar_cues(cues)
            return
        app.label_porcentaje.config(text=resumen)
        if guardar:
            _guardar_cues(cues)
        else:
            messagebox.showinfo(
                "Prueba lista",
                f"Revisa las {hechos} cues del panel.\n"
                f"OK {ok}  |  RARO {raro}  |  MAL {mal}\n"
                "Si se ve bien, dale a Traducir todo.",
            )

    _en_ui(finalizar)


def cancelar_activo():
    return app.cancelar.is_set()


def _guardar_cues(cues):
    nuevo = reconstruir_desde_cues(cues)
    nombre = obtener_nombre_con_1(app.archivo_actual)
    with open(nombre, "w", encoding="utf-8-sig", newline="") as f:
        f.write(nuevo)
    messagebox.showinfo("Listo", f"Archivo guardado como:\n{os.path.basename(nombre)}")


def _iniciar_trabajo(limite, guardar, titulo):
    if not app.archivo_actual:
        messagebox.showwarning("Advertencia", "Primero debes cargar un archivo.")
        return
    cues = parsear_cues(app.contenido_actual)
    if limite:
        cues = cues[:limite]
    threading.Thread(
        target=_correr_adaptacion,
        args=(cues, guardar, titulo),
        daemon=True,
    ).start()


def probar_cues():
    _iniciar_trabajo(PREVIEW_CUES, False, "Prueba")


def traducir_subtitulo():
    _iniciar_trabajo(None, True, "Traduccion")


def salir():
    app.cancelar.set()
    app.root.quit()


class App:
    def __init__(self):
        self.archivo_actual = None
        self.contenido_actual = None
        self.cancelar = threading.Event()
        self.root = tk.Tk()
        self.root.title("SubToEsp  ·  Latino neutro")
        self.root.geometry("1040x720")
        self.root.minsize(860, 560)
        self.root.configure(bg="#1e1e1e")

        try:
            icon = Image.open(resource_path("Logo1.png"))
            icon = icon.resize((32, 32), RESAMPLE)
            self.icon_img = ImageTk.PhotoImage(icon)
            self.root.iconphoto(False, self.icon_img)
        except Exception as e:
            print("Error cargando icono de ventana:", e)

        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except Exception:
            pass
        estilo.configure(
            "Treeview",
            background="#141414",
            foreground="#eeeeee",
            fieldbackground="#141414",
            rowheight=30,
            borderwidth=0,
        )
        estilo.configure(
            "Treeview.Heading",
            background="#2b2b2b",
            foreground="#ffffff",
            relief="flat",
            font=("Arial", 9, "bold"),
        )
        estilo.map("Treeview", background=[("selected", "#1f4e5f")])
        estilo.configure("TProgressbar", troughcolor="#2b2b2b", background="#3d9b8f")

        tk.Label(
            self.root,
            text="Subtitulos al espanol latino neutro",
            fg="white",
            bg="#1e1e1e",
            font=("Arial", 16),
        ).pack(pady=(12, 2))
        self.label_motor = tk.Label(self.root, text="", fg="#9ad1c2", bg="#1e1e1e", font=("Arial", 9))
        self.label_motor.pack()

        barra = tk.Frame(self.root, bg="#1e1e1e")
        barra.pack(pady=8)
        self.boton_cargar = tk.Button(barra, text="Cargar", width=14, command=cargar_subtitulo)
        self.boton_cargar.pack(side="left", padx=4)
        self.boton_preview = tk.Button(barra, text="Probar 20", width=14, command=probar_cues)
        self.boton_preview.pack(side="left", padx=4)
        self.boton_traducir = tk.Button(barra, text="Traducir todo", width=14, command=traducir_subtitulo)
        self.boton_traducir.pack(side="left", padx=4)
        self.boton_detener = tk.Button(
            barra, text="Detener", width=14, command=detener_traduccion, state=tk.DISABLED
        )
        self.boton_detener.pack(side="left", padx=4)
        tk.Button(barra, text="Salir", width=10, command=salir).pack(side="left", padx=4)

        self.label_archivo = tk.Label(
            self.root,
            text="Ningun archivo cargado",
            fg="lightgray",
            bg="#1e1e1e",
            font=("Arial", 10),
        )
        self.label_archivo.pack()

        self.progreso_barra = ttk.Progressbar(self.root, orient="horizontal", length=820, mode="determinate")
        self.progreso_barra.pack(pady=(8, 4))
        self.label_porcentaje = tk.Label(self.root, text="", fg="#FFFFFF", bg="#1e1e1e", font=("Arial", 10))
        self.label_porcentaje.pack()

        tabla_frame = tk.Frame(self.root, bg="#1e1e1e")
        tabla_frame.pack(fill="both", expand=True, padx=12, pady=8)
        columnas = ("cue", "tiempo", "en", "es", "estado")
        self.tabla = ttk.Treeview(tabla_frame, columns=columnas, show="headings", selectmode="browse")
        self.tabla.heading("cue", text="#")
        self.tabla.heading("tiempo", text="Tiempo")
        self.tabla.heading("en", text="Ingles")
        self.tabla.heading("es", text="Latino neutro")
        self.tabla.heading("estado", text="Check")
        self.tabla.column("cue", width=50, anchor="center", stretch=False)
        self.tabla.column("tiempo", width=90, anchor="center", stretch=False)
        self.tabla.column("en", width=360, anchor="w")
        self.tabla.column("es", width=360, anchor="w")
        self.tabla.column("estado", width=90, anchor="center", stretch=False)
        self.tabla.tag_configure("ok", foreground="#7dcea0")
        self.tabla.tag_configure("raro", foreground="#f4d03f")
        self.tabla.tag_configure("mal", foreground="#f1948a")
        scroll = ttk.Scrollbar(tabla_frame, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        marca_frame = tk.Frame(self.root, bg="#1e1e1e")
        marca_frame.pack(side="bottom", fill="x", pady=(2, 8))
        try:
            logo = Image.open(resource_path("Logo1.png"))
            logo = logo.resize((20, 20), RESAMPLE)
            self.logo_img = ImageTk.PhotoImage(logo)
            tk.Label(marca_frame, image=self.logo_img, bg="#1e1e1e").pack(side="left", padx=(10, 4))
        except Exception as e:
            print("Error cargando logo:", e)
        tk.Label(
            marca_frame,
            text="VVoz.enterprise",
            fg="gray",
            bg="#1e1e1e",
            font=("Arial", 9, "italic"),
        ).pack(side="left")

        self.actualizar_motor()

    def actualizar_motor(self):
        if api_key_gemini():
            self.label_motor.config(text=f"Gemini listo   ·   espanol {VARIANT}")
        else:
            self.label_motor.config(text=f"Google + reglas   ·   espanol {VARIANT}")

    def cargar_tabla(self, cues):
        self.tabla.delete(*self.tabla.get_children())
        for i, cue in enumerate(cues):
            self.tabla.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    cue["numero"],
                    tiempo_corto(cue["tiempo"]),
                    texto_cue(cue["dialogo"]),
                    texto_cue(cue.get("traducido") or []),
                    "—",
                ),
            )

    def actualizar_fila(self, indice, cue, tag, motivo):
        extra = f" {motivo}" if motivo else ""
        valores = (
            cue["numero"],
            tiempo_corto(cue["tiempo"]),
            texto_cue(cue["dialogo"]),
            texto_cue(cue.get("traducido") or []),
            f"{tag}{extra}",
        )
        iid = str(indice)
        if self.tabla.exists(iid):
            self.tabla.item(iid, values=valores, tags=(tag.lower(),))
        else:
            self.tabla.insert("", "end", iid=iid, values=valores, tags=(tag.lower(),))
        self.tabla.see(iid)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = App()
    app.run()
