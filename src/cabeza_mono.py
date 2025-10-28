"""
Flujo:
- Cargar cascades (cara/ojos/sonrisa) desde cv2.data.haarcascades.
- Cargar imágenes del mono desde la carpeta del script (soporta rutas con caracteres Unicode).
- Capturar frames de la cámara (o URL) y detectar caras en una versión reducida para mejorar FPS.
- Para cada cara seleccionar la imagen del mono apropiada (ojos cerrados / boca abierta / normal).
- Mostrar la cámara en una ventana y el mono en otra ventana de tamaño fijo, centrado.
"""
import cv2
import numpy as np
import os
import sys

# ----------------- CONFIGURACIÓN -----------------
# carpeta del script (rutas absolutas para evitar problemas con OneDrive/encoding)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ventana del mono: tamaño fijo (ancho, alto)
MONO_W, MONO_H = 400, 400

# fuente de video: 0/1 para cámaras locales o una URL 
CAM_INDEX = 1

# detección en imagen reducida: <1.0 acelera la detección a costa de precisión
DETECT_SCALE = 0.5

# nombres de archivos de recursos (colocar en la misma carpeta que este script)
IMAGES = {
    'normal': os.path.join(BASE_DIR, 'mono_normal.jpg'),
    'ojos_cerrados': os.path.join(BASE_DIR, 'mono_ojos_cerrados.jpeg'),
    'boca_abierta': os.path.join(BASE_DIR, 'mono_boca_abierta.jpeg'),
}

# ----------------- FUNCIONES -----------------
"""
    Carga imagen desde ruta Windows que puede contener caracteres especiales.
    Usa np.fromfile + cv2.imdecode en lugar de cv2.imread.
    Devuelve None si falla.
"""
def load_image_unicode(path, flags=cv2.IMREAD_UNCHANGED):
    
    if not os.path.exists(path):
        return None
    try:
        data = np.fromfile(path, dtype=np.uint8) # leer archivo como array de bytes
        return cv2.imdecode(data, flags) # decodificar imagen
    except Exception:
        return None

"""
    Carga un Haar cascade desde la carpeta de OpenCV (cv2.data.haarcascades).
    Devuelve CascadeClassifier vacío si no está disponible.
"""
def load_cascade(name):
    
    p = os.path.join(cv2.data.haarcascades, name) # ruta completa
    if os.path.exists(p):
        c = cv2.CascadeClassifier(p) # intentar cargar
        if not c.empty():
            return c
    return cv2.CascadeClassifier()  # vacío si no se pudo cargar

"""
    Escala la imagen manteniendo la relación de aspecto y la centra en un canvas
    de tamaño (canvas_w, canvas_h). Devuelve la imagen resultante (BGR).
"""
def fit_image_to_canvas(img, canvas_w=MONO_W, canvas_h=MONO_H, bg_color=(0,0,0)):
    
    if img is None:
        return np.full((canvas_h, canvas_w, 3), bg_color, dtype=np.uint8)
    h, w = img.shape[:2]
    scale = min(canvas_w / w, canvas_h / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale)) # nuevas dimensiones
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA) # redimensionar
    canvas = np.full((canvas_h, canvas_w, 3), bg_color, dtype=np.uint8) 
    x = (canvas_w - nw) // 2
    y = (canvas_h - nh) // 2
    canvas[y:y+nh, x:x+nw] = resized # centrar
    return canvas

# ----------------- CARGA DE RECURSOS -----------------
# cascades: face + eye son obligatorios; smile (boca) es opcional (se usa solo smile)
face_cascade = load_cascade('haarcascade_frontalface_default.xml')
eye_cascade  = load_cascade('haarcascade_eye.xml')
mouth_cascade = load_cascade('haarcascade_smile.xml')  # fallback: vacío si no existe

if face_cascade.empty() or eye_cascade.empty():
    print("Error: no se pudieron cargar los cascades esenciales (face/eye).")
    sys.exit(1)
if mouth_cascade.empty():
    # No crítico: el script continúa sin detección de boca/sonrisa
    print("Aviso: no se cargó haarcascade_smile.xml; la detección de boca/sonrisa se omitirá.")

# cargar imágenes del mono (robusto frente a rutas con caracteres especiales)
images = {}
for key, path in IMAGES.items(): # cargar cada imagen
    img = load_image_unicode(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"Advertencia: no se pudo leer '{key}' desde: {path}")
    else:
        # Normalizar: asegurar BGR (no escala de grises)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        images[key] = img

# la imagen 'normal' es obligatoria para mostrar cuando no hay caras
if 'normal' not in images or images['normal'] is None:
    print("Error: falta la imagen 'normal'. Coloca mono_normal.jpg en la carpeta del script.")
    sys.exit(1)

# ----------------- INICIALIZAR VENTANAS Y CÁMARA -----------------
mono_win = 'Mono Avatar Separado'  # ventana fija para el mono
cam_win = 'Camara'                # ventana de la cámara original

cv2.namedWindow(mono_win, cv2.WINDOW_NORMAL)
cv2.resizeWindow(mono_win, MONO_W, MONO_H)  # forzar tamaño inicial fijo
cv2.namedWindow(cam_win, cv2.WINDOW_NORMAL)

# abrir cámara o URL
cam = cv2.VideoCapture(CAM_INDEX)
if not cam.isOpened():
    print(f"Error: no se pudo abrir la cámara (index/URL: {CAM_INDEX}).")
    sys.exit(1)

# ----------------- BUCLE PRINCIPAL -----------------
try:
    while True:
        ret, frame = cam.read()
        if not ret:
            print("Error: no se pudo leer frame de la cámara.")
            break

        # espejo horizontal para interfaz tipo "espejo"
        frame = cv2.flip(frame, 1)

        # Detectar en versión reducida para mejorar rendimiento (mapear coords luego)
        small = cv2.resize(frame, (0,0), fx=DETECT_SCALE, fy=DETECT_SCALE, interpolation=cv2.INTER_LINEAR)
        gray_small = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # Detectar caras en la imagen pequeña (parámetros razonables por defecto)
        faces_small = face_cascade.detectMultiScale(gray_small, scaleFactor=1.3, minNeighbors=5)

        # Mapear coordenadas a tamaño original
        faces = [(int(x/DETECT_SCALE), int(y/DETECT_SCALE), int(w/DETECT_SCALE), int(h/DETECT_SCALE))
                 for (x,y,w,h) in faces_small]

        # lista con la/s imagen/es de mono a mostrar (una por cara)
        monos_to_show = []

        # preparar visualización de la cámara
        frame_display = frame.copy()
        gray_display = cv2.cvtColor(frame_display, cv2.COLOR_BGR2GRAY)

        # procesar cada cara detectada
        for (x, y, w, h) in faces:
            # dibujar caja en la ventana de cámara
            cv2.rectangle(frame_display, (x, y), (x+w, y+h), (0, 255, 0), 2)

            # ROI para ojos: mitad superior de la cara
            roi_byn = gray_display[y:y+h, x:x+w]
            roi_ojos = roi_byn[0:int(h*0.5), :]
            ojos = eye_cascade.detectMultiScale(roi_ojos, scaleFactor=1.1, minNeighbors=10, minSize=(20,20))

            # ROI para boca/sonrisa: zona inferior aproximada
            roi_boca = roi_byn[int(h*0.6):h, :]
            bocas = []
            # comprobar tamaño de ROI antes de detectar
            if not mouth_cascade.empty() and roi_boca.size > 0:
                # parámetros estrictos para smile para reducir falsos positivos
                bocas = mouth_cascade.detectMultiScale(roi_boca, scaleFactor=1.7, minNeighbors=22, minSize=(25,25))

            # elegir imagen del mono según detecciones
            if len(bocas) > 0: 
                mono_img = images.get('boca_abierta', images['normal'])
            elif len(ojos) <= 1:
                mono_img = images.get('ojos_cerrados', images['normal'])
            else:
                mono_img = images['normal']

            # redimensionar la imagen del mono al tamaño aproximado de la cara
            try:
                mono_resized = cv2.resize(mono_img, (w, h), interpolation=cv2.INTER_AREA)
            except Exception:
                mono_resized = mono_img
            monos_to_show.append(mono_resized)

        # preparar canvas fijo para la ventana del mono
        if len(monos_to_show) == 0:
            # sin caras: mostrar mono "normal" centrado en canvas fijo
            mono_canvas = fit_image_to_canvas(images['normal'], MONO_W, MONO_H)
        else:
            # si hay caras, mostrar la primera centrada en el canvas fijo
            mono_canvas = fit_image_to_canvas(monos_to_show[0], MONO_W, MONO_H)

        # mostrar ventanas
        cv2.imshow(cam_win, frame_display)
        cv2.imshow(mono_win, mono_canvas)

        # salir con 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    # permitir terminar con Ctrl+C
    pass
finally:
    # siempre liberar recursos
    cam.release()
    cv2.destroyAllWindows()