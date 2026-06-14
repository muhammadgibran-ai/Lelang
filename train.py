import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow import keras
from keras import layers, regularizers
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import pickle
import os
import random

# Reproducibility Seed
SEED = 10
random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)
os.environ["PYTHONHASHSEED"] = str(SEED)

def clean_model_name(model_str):
    words = str(model_str).strip().split()
    if words:
        val = words[0]
        val = ''.join(c for c in val if c.isalnum())
        return val
    return "Unknown"

def clean_location(loc_str):
    loc_lower = str(loc_str).lower()
    if "jakarta" in loc_lower:
        return "DKI Jakarta"
    elif "banten" in loc_lower or "tangerang" in loc_lower:
        return "Banten"
    elif "jawa barat" in loc_lower or "bandung" in loc_lower or "depok" in loc_lower or "bekasi" in loc_lower or "bogor" in loc_lower:
        return "Jawa Barat"
    elif "jawa tengah" in loc_lower or "semarang" in loc_lower or "solo" in loc_lower:
        return "Jawa Tengah"
    elif "jawa timur" in loc_lower or "surabaya" in loc_lower or "malang" in loc_lower:
        return "Jawa Timur"
    elif "yogyakarta" in loc_lower or "jogja" in loc_lower:
        return "Yogyakarta"
    elif "bali" in loc_lower:
        return "Bali"
    elif "sumatera" in loc_lower or "medan" in loc_lower or "palembang" in loc_lower or "riau" in loc_lower or "lampung" in loc_lower:
        return "Sumatera"
    elif "kalimantan" in loc_lower:
        return "Kalimantan"
    elif "sulawesi" in loc_lower:
        return "Sulawesi"
    else:
        return "Lainnya"

def build_model(input_dim):
    # MLP JST model architecture
    model = keras.Sequential([
        layers.Input(shape=(input_dim,)),
        layers.Dense(128, activation='relu',
                     kernel_regularizer=regularizers.l2(0.0003)),
        layers.Dropout(0.1),
        layers.Dense(64, activation='relu',
                     kernel_regularizer=regularizers.l2(0.0003)),
        layers.Dropout(0.05),
        layers.Dense(32, activation='relu',
                     kernel_regularizer=regularizers.l2(0.0003)),
        layers.Dense(1, activation='linear')
    ])

    optimizer = keras.optimizers.Adam(learning_rate=0.001)
    model.compile(optimizer=optimizer, loss='mse', metrics=['mae'])
    return model

def run_training():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(project_dir, "mobil_bekas_lelang.csv")
    
    if not os.path.exists(data_path):
        print(f"[Error] Dataset not found: {data_path}")
        return
        
    df = pd.read_csv(data_path)
    print(f"Original dataset rows: {len(df)}")
    
    # Filter Popular Brands
    popular_brands = ["Toyota", "Honda", "Suzuki", "Mitsubishi", "Daihatsu", "Hyundai", "Wuling", "Nissan", "Landrover", "Isuzu", "Komatsu"]
    df = df[df['brand'].isin(popular_brands)]
    df = df[df['mileage'] < 1000000] # Filter out placeholder/extreme mileages (>= 1,000,000 KM)
    print(f"Filtered dataset rows: {len(df)}")
    
    # Preprocessing
    df['age'] = 2026 - df['year']
    df['model_clean'] = df['model'].apply(clean_model_name)
    df['location_clean'] = df['location'].apply(clean_location)
    
    # Group minor models
    model_counts = df['model_clean'].value_counts()
    top_models = model_counts[model_counts >= 2].index.tolist()
    df['model_clean'] = df['model_clean'].apply(lambda x: x if x in top_models else 'Lainnya')
    
    # Categorical Columns (including grade!)
    cat_cols = ['brand', 'model_clean', 'transmission', 'location_clean', 'fuel_type', 'grade']
    df_encoded = pd.get_dummies(df, columns=cat_cols, drop_first=False)
    
    dummy_columns = [col for col in df_encoded.columns if any(col.startswith(cat + "_") for cat in cat_cols)]
    
    # Scale numerical features
    num_cols = ['age', 'mileage']
    scaler = StandardScaler()
    X_num = scaler.fit_transform(df_encoded[num_cols])
    X_cat = df_encoded[dummy_columns].values.astype(np.float32)
    X = np.hstack([X_num, X_cat])
    
    # Target: log of price in Millions of Rupiah
    y = np.log(df['price'].values / 1e6).astype(np.float32)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
    
    print(f"Training shape: {X_train.shape}")
    print(f"Testing shape: {X_test.shape}")
    
    model = build_model(X.shape[1])
    
    early_stopping = keras.callbacks.EarlyStopping(
        monitor='val_loss',
        patience=25,
        restore_best_weights=True
    )

    reduce_lr = keras.callbacks.ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.5,
        patience=10,
        min_lr=1e-5,
        verbose=1
    )

    print("Training MLP JST Model...")
    history = model.fit(
        X_train, y_train,
        validation_split=0.15,
        epochs=300,
        batch_size=16,
        callbacks=[early_stopping, reduce_lr],
        verbose=1
    )
    
    # Evaluate test set
    y_pred_log_test = model.predict(X_test).flatten()
    y_test_orig = np.exp(y_test)
    y_pred_test_orig = np.exp(y_pred_log_test)

    test_mae  = np.mean(np.abs(y_test_orig - y_pred_test_orig))
    test_mape = np.mean(np.abs((y_test_orig - y_pred_test_orig) / y_test_orig)) * 100
    ss_res_t  = np.sum((y_test_orig - y_pred_test_orig) ** 2)
    ss_tot_t  = np.sum((y_test_orig - np.mean(y_test_orig)) ** 2)
    test_r2   = 1 - (ss_res_t / ss_tot_t)

    # Evaluate train set
    y_pred_log_train = model.predict(X_train).flatten()
    y_train_orig = np.exp(y_train)
    y_pred_train_orig = np.exp(y_pred_log_train)

    train_mae  = np.mean(np.abs(y_train_orig - y_pred_train_orig))
    train_mape = np.mean(np.abs((y_train_orig - y_pred_train_orig) / y_train_orig)) * 100
    ss_res_tr  = np.sum((y_train_orig - y_pred_train_orig) ** 2)
    ss_tot_tr  = np.sum((y_train_orig - np.mean(y_train_orig)) ** 2)
    train_r2   = 1 - (ss_res_tr / ss_tot_tr)

    # Output report
    print("\n" + "=" * 60)
    print("         PERFORMA MODEL JST LELANG")
    print("=" * 60)
    print(f"  {'Metrik':<30} {'TRAIN':>10} {'TEST':>10}")
    print("-" * 60)
    print(f"  {'MAE (Juta Rp)':<30} {train_mae:>10.2f} {test_mae:>10.2f}")
    print(f"  {'MAPE (%)':<30} {train_mape:>10.2f} {test_mape:>10.2f}")
    print(f"  {'R2 Score':<30} {train_r2:>10.4f} {test_r2:>10.4f}")
    print("=" * 60)
    
    # Save Model
    model_save_path = os.path.join(project_dir, "model_harga_mobil.h5")
    model.save(model_save_path)
    print(f"Model saved to: {model_save_path}")
    
    # Save Preprocessors
    preprocessors = {
        "scaler": scaler,
        "num_cols": num_cols,
        "cat_cols": cat_cols,
        "dummy_columns": dummy_columns,
        "popular_brands": popular_brands,
        "top_models": top_models,
        "all_dummy_columns": list(df_encoded.columns),
        "clean_model_name": clean_model_name,
        "clean_location": clean_location
    }
    
    preprocessors_path = os.path.join(project_dir, "preprocessors.pkl")
    with open(preprocessors_path, "wb") as f:
        pickle.dump(preprocessors, f)
    print(f"Preprocessors saved to: {preprocessors_path}")
    
    # Generate Jupyter Notebook
    generate_jupyter_notebook(project_dir, test_mape, test_r2)

def generate_jupyter_notebook(project_dir, test_mape, r2):
    import json
    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# DATA PREPROCESSING & MODEL TRAINING (VERSION LELANG)\n",
                    "## Proyek Sistem Cerdas: Estimasi Harga Mobil Bekas Lelang di Indonesia\n",
                    "\n",
                    "Notebook ini memuat proses preprocessing data lelang, pembersihan outlier, pembangunan arsitektur JST (ANN) dengan menyertakan fitur **Grade Inspeksi**, training, dan evaluasi performa model."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "import pandas as pd\n",
                    "import numpy as np\n",
                    "import tensorflow as tf\n",
                    "from tensorflow import keras\n",
                    "from keras import layers, regularizers\n",
                    "from sklearn.model_selection import train_test_split\n",
                    "from sklearn.preprocessing import StandardScaler\n",
                    "import pickle\n",
                    "import os\n",
                    "import random\n",
                    "\n",
                    "SEED = 10\n",
                    "random.seed(SEED)\n",
                    "np.random.seed(SEED)\n",
                    "tf.random.set_seed(SEED)\n",
                    "os.environ['PYTHONHASHSEED'] = str(SEED)\n",
                    "print('TensorFlow version:', tf.__version__)"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "df = pd.read_csv('mobil_bekas_lelang.csv')\n",
                    "print('Jumlah Data:', len(df))\n",
                    "df.head()"
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2
    }
    
    nb_path = os.path.join(project_dir, "training.ipynb")
    with open(nb_path, "w") as f:
        json.dump(notebook, f, indent=2)
    print(f"Jupyter Notebook generated at: {nb_path}")

if __name__ == "__main__":
    run_training()
