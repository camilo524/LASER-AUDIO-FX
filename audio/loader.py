"""Lectura de archivos de audio a mono.

Intenta primero el modulo ``aud`` de Blender (que soporta mp3/ogg/flac) y
cae a WAV puro de Python si no esta disponible.
"""

import os
import wave

import bpy
import numpy as np


def load_audio_mono(path, target_sr=22050):
    """Devuelve ``(muestras_float32, sample_rate)`` en mono."""
    path = bpy.path.abspath(path)
    if not os.path.isfile(path):
        raise RuntimeError("No encuentro el archivo de audio: " + path)
    err = None
    try:
        import aud
        snd = aud.Sound(path).rechannel(1).resample(target_sr, False)
        data = np.asarray(snd.data(), dtype=np.float32).reshape(-1)
        try:
            sr = int(snd.specs[0])
        except Exception:
            sr = target_sr
        if len(data) > sr:
            return data, sr
    except Exception as e:
        err = e
    try:
        with wave.open(path, "rb") as w:
            sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
            raw = w.readframes(w.getnframes())
        if sw == 2:
            a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        elif sw == 4:
            a = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
        elif sw == 1:
            a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        else:
            raise RuntimeError("WAV de " + str(sw * 8) + " bits no soportado")
        a = a.reshape(-1, ch).mean(axis=1)
        k = max(1, sr // target_sr)
        m = (len(a) // k) * k
        return a[:m].reshape(-1, k).mean(axis=1), sr // k
    except Exception as e2:
        raise RuntimeError("No pude leer el audio (" + str(err) + " / " + str(e2) +
                           "). Prueba convirtiendolo a WAV o MP3.")
