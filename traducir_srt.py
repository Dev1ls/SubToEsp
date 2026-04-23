# -*- coding: utf-8 -*-
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from deep_translator import GoogleTranslator
from langdetect import detect
import re
import threading
import time
from PIL import Image, ImageTk

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

    traductor = GoogleTranslator(source='auto', target=destino)
    resultado = []
    total = len(bloques)
    for i, bloque in enumerate(bloques):
        if bloque is None:
            resultado.extend([None])
        else:
            try:
                texto = '\n'.join(bloque)
                traducido = traductor.translate(texto)
                resultado.extend(traducido.split('\n'))
            except Exception as e:
                resultado.extend(bloque)
        if progreso_callback:
            progreso_callback(int((i + 1) * 100 / total))
        time.sleep(0.3)
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
        texto = app.contenido_actual
        lineas = extraer_lineas_traducibles(texto)

        def actualizar_progreso(p):
            app.progreso_barra['value'] = p
            app.label_porcentaje.config(text=f"{p}%")
            app.root.update_idletasks()

        inicio = time.time()
        traducciones = traducir_lineas_en_bloques(lineas, destino='es', progreso_callback=actualizar_progreso)
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
            icon = Image.open("Logo1.png")
            icon = icon.resize((32, 32), Image.ANTIALIAS)
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
            logo = Image.open("Logo1.png")
            logo = logo.resize((20, 20), Image.ANTIALIAS)
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
