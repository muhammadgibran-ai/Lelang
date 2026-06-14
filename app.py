import streamlit as st
import pandas as pd
import numpy as np
import pickle
import os
import requests
import matplotlib.pyplot as plt
import seaborn as sns

# Pure-numpy ANN inference (tanpa TensorFlow / ONNX)
def _relu(x):   return np.maximum(0, x)
def _linear(x): return x
_ACT = {"relu": _relu, "linear": _linear}

def numpy_predict(layers, X):
    """Forward pass manual menggunakan bobot yang diekstrak dari Keras."""
    out = np.array(X, dtype=np.float32)
    for layer in layers:
        out = out @ layer["W"] + layer["b"]
        out = _ACT.get(layer["activation"], _linear)(out)
    return out

# Helper functions defined locally to resolve Pickle serialization lookup under __main__
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

# Page configuration
st.set_page_config(
    page_title="Estimasi Harga Mobil Lelang - Sistem Cerdas",
    page_icon="🔨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for premium glassmorphism and modern UI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: #f8fafc;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0b0f19 0%, #111827 100%);
    }
    
    /* Card design */
    .premium-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        margin-bottom: 20px;
    }
    
    .premium-title {
        color: #38bdf8;
        font-weight: 700;
        font-size: 24px;
        margin-bottom: 8px;
    }
    
    .premium-subtitle {
        color: #94a3b8;
        font-size: 14px;
        margin-bottom: 16px;
    }
    
    /* Stats styling */
    .stat-container {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 24px;
    }
    
    .stat-card {
        flex: 1;
        background: rgba(56, 189, 248, 0.05);
        border: 1px solid rgba(56, 189, 248, 0.15);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        transition: transform 0.3s ease;
    }
    
    .stat-card:hover {
        transform: translateY(-5px);
        background: rgba(56, 189, 248, 0.08);
    }
    
    .stat-value {
        font-size: 28px;
        font-weight: 700;
        color: #38bdf8;
    }
    
    .stat-label {
        font-size: 12px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 4px;
    }
    
    /* Form inputs custom */
    div[data-baseweb="select"] {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border-radius: 8px !important;
    }
    
    /* Predict Button */
    .stButton>button {
        background: linear-gradient(90deg, #0ea5e9 0%, #2563eb 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        width: 100% !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(37, 99, 235, 0.6) !important;
    }
    
    /* Result card */
    .result-card {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.1) 100%);
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        margin-top: 20px;
    }
    
    .result-price {
        font-size: 36px;
        font-weight: 800;
        color: #10b981;
        margin: 10px 0;
    }
    
    .result-range {
        font-size: 14px;
        color: #a7f3d0;
    }
</style>
""", unsafe_allow_html=True)

# Path definitions
project_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(project_dir, "model_weights.pkl")
preprocessors_path = os.path.join(project_dir, "preprocessors.pkl")
data_path = os.path.join(project_dir, "mobil_bekas_lelang.csv")

# Load model and preprocessors
@st.cache_resource
def load_resources():
    if not os.path.exists(model_path) or not os.path.exists(preprocessors_path):
        return None, None
    
    with open(model_path, "rb") as f:
        layers = pickle.load(f)
    
    with open(preprocessors_path, "rb") as f:
        preprocessors = pickle.load(f)
        
    return layers, preprocessors

@st.cache_data
def load_car_data():
    if os.path.exists(data_path):
        df_raw = pd.read_csv(data_path)
        # Filter out placeholder/extreme mileages (>= 1,000,000 KM)
        df_raw = df_raw[df_raw['mileage'] < 1000000].copy()
        
        # Apply standard clean matching train.py popular brands
        popular_brands = ["Toyota", "Honda", "Suzuki", "Mitsubishi", "Daihatsu", "Hyundai", "Wuling", "Nissan", "Landrover", "Isuzu", "Komatsu"]
        df_filtered = df_raw[df_raw['brand'].isin(popular_brands)].copy()
        
        df_filtered['age'] = 2026 - df_filtered['year']
        df_filtered['model_clean'] = df_filtered['model'].apply(clean_model_name)
        df_filtered['location_clean'] = df_filtered['location'].apply(clean_location)
        
        if prep is not None:
            df_filtered['model_clean'] = df_filtered['model_clean'].apply(lambda x: x if x in prep["top_models"] else 'Lainnya')
            
        return df_filtered, df_raw
    return None, None
 
model, prep = load_resources()
df, df_raw = load_car_data()

# Navigation Sidebar
st.sidebar.markdown("<div style='text-align: center; padding: 10px;'><h2 style='color:#38bdf8; margin-bottom:0;'>Estimasi Lelang</h2><p style='color:#64748b; font-size:12px;'>Sistem Cerdas JST + Grade</p></div>", unsafe_allow_html=True)
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigasi Menu", ["🏠 Beranda", "🔮 Prediksi Harga", "📊 Analisis Pasar", "🧠 Performa JST"])
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='font-size:11px; color:#64748b; text-align:center;'>Proyek Sistem Informasi Industri Otomotif (SIIO) - 2026</div>", unsafe_allow_html=True)

if page == "🏠 Beranda":
    st.markdown("<h1 style='color:#f8fafc; font-weight:700;'>Sistem Cerdas Estimasi Harga Mobil Lelang di Indonesia</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8; font-size:16px;'>Platform berbasis Jaringan Saraf Tiruan (JST) untuk memprediksi harga dasar lelang mobil bekas berdasarkan data riil dari ribuan unit di Balai Lelang JBA Indonesia, lengkap dengan Grade Inspeksi.</p>", unsafe_allow_html=True)
    
    # Visual stats
    if df_raw is not None:
        st.markdown(f"""
        <div class='stat-container'>
            <div class='stat-card'>
                <div class='stat-value'>{len(df_raw)}</div>
                <div class='stat-label'>Total Data Listing Lelang</div>
            </div>
            <div class='stat-card'>
                <div class='stat-value'>77.72%</div>
                <div class='stat-label'>Akurasi Model (R²)</div>
            </div>
            <div class='stat-card'>
                <div class='stat-value'>17.31%</div>
                <div class='stat-label'>Rata-rata Error (MAPE)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("""
        <div class='premium-card'>
            <div class='premium-title'>Tentang Sistem Cerdas Lelang Ini</div>
            <p style='color:#cbd5e1; font-size:15px; line-height:1.6;'>
                Sistem ini dibangun secara khusus untuk memperkirakan harga dasar mobil bekas yang dijual melalui sistem lelang grosir (B2B). Model ini dilatih menggunakan algoritma <b>Artificial Neural Network (ANN)</b> tipe <b>Multi-Layer Perceptron (MLP)</b> yang secara spesifik mengintegrasikan indikator <b>Grade Inspeksi (A, B, C, D, E, F)</b>. Grade ini merepresentasikan kondisi fisik kendaraan (mesin, eksterior, dan interior) hasil inspeksi multi-point dari inspektor profesional.
            </p>
            <p style='color:#cbd5e1; font-size:15px; line-height:1.6;'>
                <b>Keunggulan Integrasi Grade Inspeksi:</b>
                <ul style='color:#cbd5e1; margin-left: 20px;'>
                    <li><b>Transparansi Fisik</b>: JST secara otomatis membedakan depresiasi harga mobil dengan grade prima (A/B) dibanding mobil dengan grade rendah (D/E) yang membutuhkan banyak perbaikan.</li>
                    <li><b>Data Riil Balai Lelang</b>: Dataset dikumpulkan langsung dari website resmi JBA Indonesia, mencerminkan harga dasar lelang riil.</li>
                    <li><b>Akurasi Tinggi</b>: Model JST mencapai nilai R² sebesar 77.72% dan MAPE sebesar 17.31% pada data pengujian, dengan gap MAPE train-test hanya 4.87% membuktikan kondisi Good Fit yang stabil.</li>
                </ul>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
        <div class='premium-card' style='height: 100%; text-align: center; display: flex; flex-direction: column; justify-content: center; align-items: center;'>
            <div class='premium-title' style='margin-bottom:20px;'>Fitur Utama Aplikasi</div>
            <div style='text-align: left; width: 100%;'>
                <div style='margin-bottom: 15px;'>
                    <span style='font-size: 24px; margin-right: 10px;'>🔮</span>
                    <b>Prediktor Berbasis Grade:</b> Input merek, model, usia, dan grade inspeksi untuk mendapatkan estimasi harga dasar lelang yang disarankan secara instan.
                </div>
                <div style='margin-bottom: 15px;'>
                    <span style='font-size: 24px; margin-right: 10px;'>📊</span>
                    <b>Visualisasi Grade Pasar:</b> Analisis pengaruh grade terhadap depresiasi harga, pangsa pasar per grade, dan harga rata-rata tiap grade.
                </div>
                <div style='margin-bottom: 15px;'>
                    <span style='font-size: 24px; margin-right: 10px;'>🧠</span>
                    <b>Analisis Performa JST:</b> Tinjau statistik performa model JST, matriks bobot, dan sebaran data aktual vs prediksi.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

elif page == "🔮 Prediksi Harga":
    st.markdown("<h1 style='color:#f8fafc; font-weight:700;'>🔮 Estimasi Harga Dasar Mobil Lelang</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8; font-size:15px;'>Masukkan spesifikasi kendaraan beserta Grade Inspeksi untuk memprediksi harga dasar lelang.</p>", unsafe_allow_html=True)
    
    if prep is None or model is None:
        st.error("Model JST atau objek preprocessor tidak ditemukan. Harap pastikan model sudah dilatih.")
    else:
        # Define Input Fields
        brands_list = sorted(prep["popular_brands"])
        transmission_list = ["Automatic", "Manual"]
        location_list = sorted(prep["clean_location"](loc) for loc in ["Jakarta", "Banten", "Jawa Barat", "Jawa Tengah", "Jawa Timur", "Yogyakarta", "Bali", "Sumatera", "Kalimantan", "Sulawesi", "Lainnya"])
        fuel_list = ["Bensin", "Diesel", "Hybrid"]
        grade_list = ["A", "B", "C", "D", "E", "F"]
        
        # Mapping models by brand for dynamic select box
        brand_models = {}
        if df is not None:
            for b in brands_list:
                models_for_b = sorted(df[df['brand'] == b]['model_clean'].unique().tolist())
                if 'Lainnya' in models_for_b:
                    models_for_b.remove('Lainnya')
                models_for_b.append('Lainnya')
                brand_models[b] = models_for_b
        else:
            for b in brands_list:
                brand_models[b] = ['Lainnya']
                
        # Layout Form columns
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
            st.subheader("Spesifikasi Umum")
            brand = st.selectbox("Merek Mobil", brands_list)
            
            # Dynamic Model Box based on brand selection
            model_options = brand_models.get(brand, ['Lainnya'])
            model_name = st.selectbox("Model Utama", model_options)
            
            year = st.slider("Tahun Pembuatan", min_value=2010, max_value=2026, value=2020)
            mileage = st.number_input("Jarak Tempuh / Odometer (KM)", min_value=0, max_value=500000, value=65000, step=5000)
            st.markdown("</div>", unsafe_allow_html=True)
            
        with col2:
            st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
            st.subheader("Teknis, Geografis & Grade")
            transmission = st.radio("Jenis Transmisi", transmission_list, horizontal=True)
            fuel_type = st.radio("Jenis Bahan Bakar", fuel_list, horizontal=True)
            location = st.selectbox("Lokasi Penjualan", location_list)
            grade = st.selectbox("Grade Inspeksi Kendaraan", grade_list, index=1) # Default B
            st.markdown("</div>", unsafe_allow_html=True)
            
        # Prediction logic
        st.markdown("<div style='margin-top:10px;'>", unsafe_allow_html=True)
        if st.button("PREDIKSI HARGA DASAR LELANG"):
            age = 2026 - year
            
            # Ordinal encode grade
            grade_map = prep.get("grade_map", {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'E': 1, 'F': 0})
            grade_ordinal = grade_map.get(grade, 0)
            
            # Map inputs to dummy variables (WITHOUT grade one-hot)
            input_dict = {col: 0 for col in prep["all_dummy_columns"] if col not in prep["num_cols"] and col != 'price' and not col.startswith('grade')}
            
            # Clean model name mapping
            cleaned_model = prep["clean_model_name"](model_name)
            if cleaned_model not in prep["top_models"]:
                cleaned_model = 'Lainnya'
                
            # Clean location mapping
            cleaned_loc = prep["clean_location"](location)
            
            # Set target one-hot encoding columns to 1
            brand_col = f"brand_{brand}"
            model_col = f"model_clean_{cleaned_model}"
            trans_col = f"transmission_{transmission}"
            loc_col = f"location_clean_{cleaned_loc}"
            fuel_col = f"fuel_type_{fuel_type}"
            
            for col in [brand_col, model_col, trans_col, loc_col, fuel_col]:
                if col in input_dict:
                    input_dict[col] = 1
            
            df_cat = pd.DataFrame([input_dict])
            
            # Standardize numerical features (now includes grade_ordinal)
            num_data = pd.DataFrame([{"age": age, "mileage": mileage, "grade_ordinal": grade_ordinal}])
            num_scaled = prep["scaler"].transform(num_data)
            
            # Stack inputs
            X_cat_vals = df_cat[prep["dummy_columns"]].values.astype(np.float32)
            X_input = np.hstack([num_scaled, X_cat_vals])
            
            # Predict (Pure Numpy)
            pred_log = numpy_predict(model, X_input.astype(np.float32)).flatten()[0]
            pred_juta = np.exp(pred_log)
            
            # Final price in Rupiah
            pred_rupiah = pred_juta * 1e6
            
            # Display Prediction Result card
            st.markdown(f"""
            <div class='result-card'>
                <div style='font-size:16px; color:#cbd5e1; font-weight:600;'>HARGA DASAR LELANG YANG DISARANKAN</div>
                <div class='result-price'>Rp {pred_rupiah:,.0f}</div>
                <div class='result-range'>Rentang Harga Wajar (±17.31% MAPE): <b>Rp {pred_rupiah * 0.8269:,.0f} - Rp {pred_rupiah * 1.1731:,.0f}</b></div>
                <p style='color:#a7f3d0; font-size:12px; margin-top:8px;'>Harga dasar lelang dipengaruhi oleh kondisi fisik mobil <b>Grade {grade}</b>, odometer {mileage:,.0f} KM, dan usia {age} tahun.</p>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True)

elif page == "📊 Analisis Pasar":
    st.markdown("<h1 style='color:#f8fafc; font-weight:700;'>📊 Analisis Pasar Mobil Lelang di Indonesia</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8; font-size:15px;'>Eksplorasi visual berdasarkan dataset riil dari portal Balai Lelang JBA Indonesia.</p>", unsafe_allow_html=True)
    
    if df is None:
        st.warning("Dataset tidak tersedia.")
    else:
        # Panel Filter Utama
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.markdown("<div class='premium-title' style='font-size:18px;'>🔍 Filter Data Lelang</div>", unsafe_allow_html=True)
        
        f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
        
        with f_col1:
            all_brands = sorted(df['brand'].unique().tolist())
            selected_brands = st.multiselect("Merek Mobil", options=all_brands, default=all_brands)
            
        with f_col2:
            all_transmissions = sorted(df['transmission'].unique().tolist())
            selected_transmissions = st.multiselect("Transmisi", options=all_transmissions, default=all_transmissions)
            
        with f_col3:
            all_grades = sorted(df['grade'].unique().tolist())
            selected_grades = st.multiselect("Grade Inspeksi", options=all_grades, default=all_grades)
            
        with f_col4:
            min_price = int(df['price'].min() / 1e6)
            max_price = int(df['price'].max() / 1e6)
            price_range = st.slider("Rentang Harga (Juta Rp)", min_value=min_price, max_value=max_price, value=(min_price, max_price))
            
        with f_col5:
            min_mileage = int(df['mileage'].min())
            max_mileage = int(df['mileage'].max())
            mileage_range = st.slider("Rentang Jarak Tempuh (KM)", min_value=min_mileage, max_value=max_mileage, value=(min_mileage, max_mileage), step=5000)
            
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Apply filters
        df_filtered = df[
            (df['brand'].isin(selected_brands)) &
            (df['transmission'].isin(selected_transmissions)) &
            (df['grade'].isin(selected_grades)) &
            (df['price'] >= price_range[0] * 1e6) &
            (df['price'] <= price_range[1] * 1e6) &
            (df['mileage'] >= mileage_range[0]) &
            (df['mileage'] <= mileage_range[1])
        ]
        
        # Validasi jika hasil filter kosong
        if df_filtered.empty:
            st.warning("⚠️ Tidak ada data lelang yang cocok dengan kriteria filter Anda. Silakan sesuaikan kembali filter di atas.")
        else:
            # Tampilkan informasi ringkasan data yang terfilter
            st.markdown(f"""
            <div style='background: rgba(56, 189, 248, 0.05); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; padding: 12px 18px; margin-bottom: 20px; font-size: 14px; color: #e2e8f0;'>
                📊 Menampilkan <b>{len(df_filtered)}</b> dari <b>{len(df)}</b> data bersih hasil filter (Total database: <b>{len(df_raw)}</b> data).
                <br><span style='font-size: 12px; color: #94a3b8;'>*Catatan: Selisih data ({len(df_raw) - len(df)} data) dieliminasi dari database untuk penyelarasan merek populer demi akurasi model JST.</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Layout plots
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
                st.markdown("<div class='premium-title'>Distribusi Harga Dasar Lelang</div>", unsafe_allow_html=True)
                fig, ax = plt.subplots(figsize=(6, 4), facecolor='#1e293b')
                ax.set_facecolor('#0f172a')
                sns.histplot(df_filtered['price'] / 1e6, bins=20, kde=True, color='#38bdf8', ax=ax)
                ax.set_xlabel("Harga (Juta Rupiah)", color='#cbd5e1')
                ax.set_ylabel("Jumlah Kendaraan", color='#cbd5e1')
                ax.tick_params(colors='#cbd5e1')
                plt.tight_layout()
                st.pyplot(fig)
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
                st.markdown("<div class='premium-title'>Depresiasi Harga vs Jarak Tempuh (Berdasarkan Grade)</div>", unsafe_allow_html=True)
                fig, ax = plt.subplots(figsize=(6, 4), facecolor='#1e293b')
                ax.set_facecolor('#0f172a')
                # Scatter plot colored by inspection Grade!
                sns.scatterplot(data=df_filtered, x='mileage', y=df_filtered['price']/1e6, hue='grade', hue_order=sorted(df_filtered['grade'].unique()), palette='viridis', alpha=0.8, ax=ax)
                ax.set_xlabel("Jarak Tempuh (Odometer KM)", color='#cbd5e1')
                ax.set_ylabel("Harga (Juta Rupiah)", color='#cbd5e1')
                ax.tick_params(colors='#cbd5e1')
                ax.legend(facecolor='#0f172a', labelcolor='#cbd5e1', title="Grade Inspeksi", title_fontsize='small')
                plt.tight_layout()
                st.pyplot(fig)
                st.markdown("</div>", unsafe_allow_html=True)
                
            with col2:
                st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
                st.markdown("<div class='premium-title'>Pangsa Pasar Berdasarkan Grade Inspeksi</div>", unsafe_allow_html=True)
                fig, ax = plt.subplots(figsize=(6, 4), facecolor='#1e293b')
                ax.set_facecolor('#0f172a')
                grade_cnt = df_filtered['grade'].value_counts().sort_index()
                ax.pie(grade_cnt, labels=grade_cnt.index, autopct='%1.1f%%', colors=sns.color_palette('viridis', len(grade_cnt)), textprops={'color': '#cbd5e1'})
                plt.tight_layout()
                st.pyplot(fig)
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
                st.markdown("<div class='premium-title'>Rata-Rata Harga Berdasarkan Grade Inspeksi</div>", unsafe_allow_html=True)
                fig, ax = plt.subplots(figsize=(6, 4), facecolor='#1e293b')
                ax.set_facecolor('#0f172a')
                avg_price_grade = df_filtered.groupby('grade')['price'].mean().sort_index() / 1e6
                sns.barplot(x=avg_price_grade.index, y=avg_price_grade.values, palette='viridis', ax=ax)
                ax.set_xlabel("Grade Inspeksi", color='#cbd5e1')
                ax.set_ylabel("Harga Rata-Rata (Juta Rupiah)", color='#cbd5e1')
                ax.tick_params(colors='#cbd5e1')
                plt.tight_layout()
                st.pyplot(fig)
                st.markdown("</div>", unsafe_allow_html=True)

elif page == "🧠 Performa JST":
    st.markdown("<h1 style='color:#f8fafc; font-weight:700;'>🧠 Arsitektur & Performa Jaringan Saraf Tiruan (ANN)</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8; font-size:15px;'>Rincian teknis model MLP JST yang mengintegrasikan fitur Grade Inspeksi lelang.</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        <div class='premium-card'>
            <div class='premium-title'>Arsitektur Jaringan (Grade-Aware MLP)</div>
            <table style='width:100%; border-collapse: collapse; margin-top:10px; color:#cbd5e1;'>
                <tr style='border-bottom: 2px solid rgba(255,255,255,0.1);'><th style='padding:8px;'>Layer Tipe</th><th>Ukuran Output</th><th>Fungsi Aktivasi</th><th>Regularisasi</th></tr>
                <tr style='border-bottom: 1px solid rgba(255,255,255,0.05);'><td style='padding:8px;'><b>Input (Fitur Mobil + Grade Ordinal)</b></td><td>Dimension: 83</td><td>-</td><td>-</td></tr>
                <tr style='border-bottom: 1px solid rgba(255,255,255,0.05);'><td style='padding:8px;'><b>Dense_1 (Hidden)</b></td><td>128</td><td>ReLU</td><td>L2(0.0005) + Dropout(0.15)</td></tr>
                <tr style='border-bottom: 1px solid rgba(255,255,255,0.05);'><td style='padding:8px;'><b>Dense_2 (Hidden)</b></td><td>64</td><td>ReLU</td><td>L2(0.0005) + Dropout(0.08)</td></tr>
                <tr style='border-bottom: 1px solid rgba(255,255,255,0.05);'><td style='padding:8px;'><b>Dense_3 (Hidden)</b></td><td>32</td><td>ReLU</td><td>L2(0.0005)</td></tr>
                <tr style='border-bottom: 1px solid rgba(255,255,255,0.05);'><td style='padding:8px;'><b>Output (Log Harga Dasar)</b></td><td>1</td><td>Linear (Regresi)</td><td>-</td></tr>
            </table>
            <br>
            <b>Optimasi Model:</b>
            <ul style='color:#cbd5e1; margin-top:5px; margin-left:20px;'>
                <li><b>Grade Ordinal Encoding:</b> Grade diubah ke skala ordinal (A=5, B=4, ..., F=0) dan diskala bersama fitur numerik, bukan one-hot. Ini mengurangi dimensi input secara signifikan.</li>
                <li><b>Loss Function:</b> Mean Squared Error (MSE) dihitung pada logaritma harga dasar lelang.</li>
                <li><b>Pencegahan Overfitting:</b> L2 Regularization (0.0005) + Dropout (0.15/0.08) + Early Stopping (patience=30) + batch_size=32.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class='premium-card'>
            <div class='premium-title'>Metrik Evaluasi Model (Good Fit)</div>
            <table style='width:100%; border-collapse: collapse; margin-top:10px; color:#cbd5e1;'>
                <tr style='border-bottom: 2px solid rgba(255,255,255,0.1);'><td style='padding:8px; font-weight:600;'>Metrik</td><td style='font-weight:600;'>TRAIN</td><td style='font-weight:600;'>TEST</td><td style='font-weight:600;'>GAP</td></tr>
                <tr style='border-bottom: 1px solid rgba(255,255,255,0.05);'><td style='padding:8px; font-weight:600;'>MAPE (%)</td><td style='color:#10b981; font-weight:700;'>12.44%</td><td style='color:#10b981; font-weight:700;'>17.31%</td><td style='color:#fbbf24; font-weight:700;'>4.87%</td></tr>
                <tr style='border-bottom: 1px solid rgba(255,255,255,0.05);'><td style='padding:8px; font-weight:600;'>R² Score</td><td style='color:#10b981; font-weight:700;'>0.9091</td><td style='color:#10b981; font-weight:700;'>0.7772</td><td style='color:#fbbf24; font-weight:700;'>0.1319</td></tr>
                <tr style='border-bottom: 1px solid rgba(255,255,255,0.05);'><td style='padding:8px; font-weight:600;'>MAE (Juta Rp)</td><td style='color:#10b981; font-weight:700;'>20.57</td><td style='color:#10b981; font-weight:700;'>26.73</td><td style='color:#fbbf24; font-weight:700;'>6.16</td></tr>
            </table>
            <p style='font-size:12px; color:#94a3b8; margin-top:10px;'>Model JST lelang dioptimasi untuk <b>GOOD FIT</b> dengan gap MAPE train-test hanya <b>4.87%</b>. Grade dienkode secara ordinal (A=5 → F=0) untuk mengurangi dimensi input dari 101 menjadi 83 fitur, meningkatkan rasio data:fitur sehingga generalisasi lebih stabil.</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.markdown("<div class='premium-title'>Grafik Perbandingan: Aktual vs Prediksi Lelang</div>", unsafe_allow_html=True)
        
        if df is not None and model is not None and prep is not None:
            # Let's run prediction on subset for plot
            # Rebuild features matching train.py pipeline
            grade_map = prep.get("grade_map", {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'E': 1, 'F': 0})
            df_plot = df.copy()
            df_plot['grade_ordinal'] = df_plot['grade'].map(grade_map).fillna(0)
            cat_cols = ['brand', 'model_clean', 'transmission', 'location_clean', 'fuel_type']
            df_encoded = pd.get_dummies(df_plot, columns=cat_cols, drop_first=False)
            dummy_columns = [col for col in df_encoded.columns if any(col.startswith(cat + "_") for cat in cat_cols)]
            num_cols = ['age', 'mileage', 'grade_ordinal']
            X_num = prep["scaler"].transform(df_encoded[num_cols])
            X_cat = df_encoded[prep["dummy_columns"]].values.astype(np.float32)
            X_full = np.hstack([X_num, X_cat])
            
            # Predict (Pure Numpy)
            pred_logs = numpy_predict(model, X_full.astype(np.float32)).flatten()
            pred_prices = np.exp(pred_logs)
            actual_prices = df['price'].values / 1e6
            
            # Plot
            fig, ax = plt.subplots(figsize=(6, 5), facecolor='#1e293b')
            ax.set_facecolor('#0f172a')
            
            # Draw line
            max_val = max(max(actual_prices), max(pred_prices))
            ax.plot([0, max_val], [0, max_val], '--', color='#ef4444', label='Garis Sempurna (Prediksi=Aktual)', linewidth=2)
            
            # Scatter
            ax.scatter(actual_prices, pred_prices, color='#38bdf8', alpha=0.6, edgecolors='none', s=25)
            
            ax.set_xlabel("Harga Aktual Lelang (Juta Rupiah)", color='#cbd5e1')
            ax.set_ylabel("Harga Prediksi JST (Juta Rupiah)", color='#cbd5e1')
            ax.tick_params(colors='#cbd5e1')
            ax.legend(facecolor='#0f172a', labelcolor='#cbd5e1')
            plt.tight_layout()
            st.pyplot(fig)
        else:
            st.warning("Grafik tidak dapat ditampilkan.")
        st.markdown("</div>", unsafe_allow_html=True)
