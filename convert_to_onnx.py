import os
import sys
import pickle
import numpy as np

project_dir = os.path.dirname(os.path.abspath(__file__))
h5_path       = os.path.join(project_dir, "model_harga_mobil.h5")
weights_path  = os.path.join(project_dir, "model_weights.pkl")

if not os.path.exists(h5_path):
    print(f"File tidak ditemukan: {h5_path}")
    sys.exit(1)

print("Loading Keras model...")
import tensorflow as tf
from tensorflow import keras

model = keras.models.load_model(h5_path, compile=False)
model.summary()
print(f"OK: Input shape: {model.input_shape}")

# Ekstrak semua bobot per layer
layers_data = []
for layer in model.layers:
    weights = layer.get_weights()
    config  = layer.get_config()
    if weights:
        layers_data.append({
            "name":       layer.name,
            "activation": config.get("activation", "linear"),
            "W":          weights[0],   # weight matrix
            "b":          weights[1],   # bias
        })
        print(f"  Layer {layer.name}: W={weights[0].shape}, b={weights[1].shape}, act={config.get('activation','linear')}")

print(f"\nTotal {len(layers_data)} layers dengan bobot diekstrak.")

# Simpan
with open(weights_path, "wb") as f:
    pickle.dump(layers_data, f)

size_kb = os.path.getsize(weights_path) / 1024
print(f"OK: Bobot tersimpan: {weights_path} ({size_kb:.1f} KB)")

# Validasi: inference manual
def relu(x):   return np.maximum(0, x)
def linear(x): return x

act_map = {"relu": relu, "linear": linear}

def numpy_predict(layers, X):
    out = X.copy()
    for layer in layers:
        out = out @ layer["W"] + layer["b"]
        act = act_map.get(layer["activation"], linear)
        out = act(out)
    return out

# Test dengan dummy
dummy = np.zeros((1, model.input_shape[-1]), dtype=np.float32)
pred_manual = numpy_predict(layers_data, dummy)
pred_keras  = model.predict(dummy, verbose=0)
print(f"\nValidasi:")
print(f"  Numpy output : {pred_manual.flatten()[0]:.8f}")
print(f"  Keras output : {pred_keras.flatten()[0]:.8f}")
diff = abs(pred_manual.flatten()[0] - pred_keras.flatten()[0])
print(f"  Selisih      : {diff:.2e}")
assert diff < 1e-4, f"Perbedaan terlalu besar: {diff}"
print("OK: Numpy inference identik dengan Keras!")
print("\nKonversi berhasil! File model_weights.pkl siap digunakan.")
