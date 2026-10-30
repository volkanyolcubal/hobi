"""
AURA-V — Güvenlik Kamerası Modülü
Webcam fotoğraf ve canlı stream
"""
import base64, threading, time

_stream_aktif  = False
_stream_thread = None

def kamera_foto() -> str:
    """Webcam'den tek kare yakala, FOTO:base64 döndür."""
    try:
        import cv2
    except ImportError:
        return "HATA:opencv"
    cap = None
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "HATA:kamera_yok"
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        if not ret:
            return "HATA:frame_yok"
        ret2, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret2:
            return "HATA:encode"
        b64 = base64.b64encode(buf.tobytes()).decode('utf-8')
        return f"FOTO:{b64}"
    except Exception as e:
        return f"HATA:{e}"
    finally:
        if cap:
            cap.release()

def kamera_stream_baslat(socketio, sid: str, fps: int = 2) -> str:
    """Arka planda canlı stream başlat."""
    global _stream_aktif, _stream_thread
    if _stream_aktif:
        return "zaten_aktif"
    _stream_aktif = True

    def _loop():
        global _stream_aktif
        try:
            import cv2
        except ImportError:
            socketio.emit('kamera_hata', {'msg': 'opencv kurulu değil: pip install opencv-python'}, to=sid)
            _stream_aktif = False
            return
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            socketio.emit('kamera_hata', {'msg': 'Kamera bulunamadı!'}, to=sid)
            _stream_aktif = False
            return
        aralik = 1.0 / fps
        while _stream_aktif:
            ret, frame = cap.read()
            if not ret:
                break
            ret2, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret2:
                b64 = base64.b64encode(buf.tobytes()).decode('utf-8')
                socketio.emit('kamera_frame', {'img': b64}, to=sid)
            time.sleep(aralik)
        cap.release()
        socketio.emit('kamera_durdu', {}, to=sid)
        _stream_aktif = False

    _stream_thread = threading.Thread(target=_loop, daemon=True)
    _stream_thread.start()
    return "baslatildi"

def kamera_stream_durdur() -> str:
    """Canlı stream'i durdur."""
    global _stream_aktif
    _stream_aktif = False
    return "durduruldu"
