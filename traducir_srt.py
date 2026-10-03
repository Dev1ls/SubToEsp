# -*- coding: utf-8 -*-
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from deep_translator import MyMemoryTranslator
from langdetect import detect
import re
import threading
import time
import requests
from PIL import Image, ImageTk

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = getattr(Image, "LANCZOS", Image.ANTIALIAS)


def resource_path(nombre):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, nombre)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), nombre)

def detectar_idioma(texto):
    lineas = texto.split('\n')
    texto_junto = ' '.join([l for l in lineas if l and not l.isdigit() and '-->' not in l])
    try:
        return detect(texto_junto)
    except:
        return "desconocido"

def obtener_nombre_con_1(nombre_archivo):
    base, ext = os.path.splitext(nombre_archivo)
    return f"{base} (1){ext}"

HEADERS_TRADUCCION = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _extraer_texto_traducido(data):
    if isinstance(data, str) and data.strip():
        return data
    if isinstance(data, list) and data:
        return _extraer_texto_traducido(data[0])
    raise RuntimeError("Formato de traduccion no reconocido")


def _traducir_chrome_ex(texto, destino='es', origen='auto'):
    url = "https://clients5.google.com/translate_a/t"
    params = {"client": "dict-chrome-ex", "sl": origen, "tl": destino, "q": texto}
    respuesta = requests.get(url, params=params, headers=HEADERS_TRADUCCION, timeout=20)
    respuesta.raise_for_status()
    return _extraer_texto_traducido(respuesta.json())


def _traducir_gtx(texto, destino='es', origen='auto'):
    url = "https://translate.googleapis.com/translate_a/single"
    params = {"client": "gtx", "sl": origen, "tl": destino, "dt": "t", "q": texto}
    respuesta = requests.get(url, params=params, headers=HEADERS_TRADUCCION, timeout=20)
    respuesta.raise_for_status()
    data = respuesta.json()
    if not data or not data[0]:
        raise RuntimeError("Respuesta vacia de Google Translate")
    return "".join(parte[0] for parte in data[0] if parte and parte[0])


def _traducir_mymemory_http(texto, destino='es'):
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


def _traducir_mymemory(texto, destino='es'):
    return MyMemoryTranslator(source='en-GB', target='es-ES').translate(texto)


def _traducir_texto(texto, destino='es'):
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
            time.sleep(0.4)
    raise RuntimeError("No se pudo traducir. " + " | ".join(errores))


def traducir_lineas_en_bloques(lineas, destino='es', progreso_callback=None):
    bloques = []
    bloque_actual = []
    for linea in lineas:
        if linea is None:
            bloques.append(None)
        else:
            bloque_actual.append(linea)
            if len(bloque_actual) >= 5:
                bloques.append(bloque_actual)
                bloque_actual = []
    if bloque_actual:
        bloques.append(bloque_actual)

    resultado = []
    total = len(bloques)
    pendientes = sum(1 for bloque in bloques if bloque is not None)
    fallos = 0
    for i, bloque in enumerate(bloques):
        if bloque is None:
            resultado.extend([None])
        else:
            try:
                texto = '\n'.join(bloque)
                traducido = _traducir_texto(texto, destino=destino)
                partes = traducido.split('\n')
                if len(partes) != len(bloque):
                    partes = (partes + bloque[len(partes):])[:len(bloque)]
                resultado.extend(partes)
            except Exception:
                fallos += 1
                resultado.extend(bloque)
        if progreso_callback:
            progreso_callback(int((i + 1) * 100 / total))
        time.sleep(0.3)

    if pendientes and fallos == pendientes:
        raise RuntimeError(
            "Ningun bloque se pudo traducir. Google/MyMemory no respondieron."
        )
    return resultado

def extraer_lineas_traducibles(texto):
    lineas = texto.split('\n')
    traducibles = []
    for linea in lineas:
        if re.match(r'^\d+$', linea) or '-->' in linea or linea.strip() == '':
            traducibles.append(None)
        else:
            traducibles.append(linea)
    return traducibles

def reconstruir_srt(original, traducciones):
    lineas = original.split('\n')
    resultado = []
    idx = 0
    for linea in lineas:
        if re.match(r'^\d+$', linea) or '-->' in linea or linea.strip() == '':
            resultado.append(linea)
        else:
            while traducciones[idx] is None:
                idx += 1
            resultado.append(traducciones[idx])
            idx += 1
    return '\n'.join(resultado)

def cargar_subtitulo():
    archivo = filedialog.askopenfilename(filetypes=[("Archivos SRT", "*.srt")])
    if archivo:
        with open(archivo, 'r', encoding='utf-8') as f:
            contenido = f.read()
        idioma = detectar_idioma(contenido)
        messagebox.showinfo("Idioma detectado", f"Idioma del subtitulo: {idioma.upper()}")
        app.archivo_actual = archivo
        app.contenido_actual = contenido
        app.label_archivo.config(text=f"Archivo cargado: {os.path.basename(archivo)}")
        app.progreso_barra['value'] = 0
        app.label_porcentaje.config(text="")

def traducir_subtitulo():
    if not app.archivo_actual:
        messagebox.showwarning("Advertencia", "Primero debes cargar un archivo.")
        return

    def ejecutar_traduccion():
        app.boton_traducir.config(state=tk.DISABLED)
        try:
            texto = app.contenido_actual
            lineas = extraer_lineas_traducibles(texto)

            def actualizar_progreso(p):
                app.progreso_barra['value'] = p
                app.label_porcentaje.config(text=f"{p}%")
                app.root.update_idletasks()

            inicio = time.time()
            try:
                traducciones = traducir_lineas_en_bloques(lineas, destino='es', progreso_callback=actualizar_progreso)
            except Exception as e:
                messagebox.showerror("Error de traduccion", str(e))
                return
            nuevo_contenido = reconstruir_srt(texto, traducciones)
            fin = time.time()
            duracion = round(fin - inicio, 1)

            nuevo_nombre = obtener_nombre_con_1(app.archivo_actual)
            with open(nuevo_nombre, 'w', encoding='utf-8') as f:
                f.write(nuevo_contenido)

            if texto.count('-->') == nuevo_contenido.count('-->'):
                app.label_porcentaje.config(text=f"✅ Traduccion completada ({duracion}s)")
            else:
                app.label_porcentaje.config(text=f"⚠️ Traduccion con diferencias de bloques ({duracion}s)")
                messagebox.showwarning("Sincronizacion", "La cantidad de bloques no coincide. Revisa el archivo.")

            messagebox.showinfo("Listo", f"Archivo traducido guardado como:\n{os.path.basename(nuevo_nombre)}")
        except Exception as e:
            messagebox.showerror("Error de traduccion", str(e))
        finally:
            app.boton_traducir.config(state=tk.NORMAL)

    threading.Thread(target=ejecutar_traduccion).start()

def salir():
    app.root.quit()

# --- Interfaz GUI ---
class App:
    def __init__(self):
        self.archivo_actual = None
        self.contenido_actual = None
        self.root = tk.Tk()
        self.root.title("Traductor de Subtitulos")
        self.root.geometry("440x330")
        self.root.configure(bg="#1e1e1e")

        # Set app icon (replaces feather icon)
        try:
            icon = Image.open(resource_path("Logo1.png"))
            icon = icon.resize((32, 32), RESAMPLE)
            self.icon_img = ImageTk.PhotoImage(icon)
            self.root.iconphoto(False, self.icon_img)
        except Exception as e:
            print("Error cargando icono de ventana:", e)

        tk.Label(self.root, text="Menu de subtitulos", fg="white", bg="#1e1e1e", font=("Arial", 16)).pack(pady=10)

        tk.Button(self.root, text="1. Cargar subtitulo", width=30, command=cargar_subtitulo).pack(pady=5)
        self.label_archivo = tk.Label(self.root, text="Ningun archivo cargado", fg="lightgray", bg="#1e1e1e", font=("Arial", 10))
        self.label_archivo.pack()

        self.boton_traducir = tk.Button(self.root, text="2. Traducir al español", width=30, command=traducir_subtitulo)
        self.boton_traducir.pack(pady=8)

        self.progreso_barra = ttk.Progressbar(self.root, orient='horizontal', length=300, mode='determinate')
        self.progreso_barra.pack(pady=5)

        self.label_porcentaje = tk.Label(self.root, text="", fg="#FFFFFF", bg="#1e1e1e", font=("Arial", 10))
        self.label_porcentaje.pack()

        tk.Button(self.root, text="3. Salir", width=30, command=salir).pack(pady=8)

        # Marca: Logo + texto VVoz.enterprise abajo
        marca_frame = tk.Frame(self.root, bg="#1e1e1e")
        marca_frame.pack(side="bottom", fill="x", pady=(10, 4))

        try:
            logo = Image.open(resource_path("Logo1.png"))
            logo = logo.resize((20, 20), RESAMPLE)
            self.logo_img = ImageTk.PhotoImage(logo)
            logo_label = tk.Label(marca_frame, image=self.logo_img, bg="#1e1e1e")
            logo_label.pack(side="left", padx=(10, 4))
        except Exception as e:
            print("Error cargando logo:", e)

        texto_marca = tk.Label(
            marca_frame,
            text="VVoz.enterprise",
            fg="gray",
            bg="#1e1e1e",
            font=("Arial", 9, "italic")
        )
        texto_marca.pack(side="left")

    def run(self):
        self.root.mainloop()

app = App()
app.run()
