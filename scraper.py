import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
import random
import os

def clean_price(price_str):
    if not price_str:
        return None
    price_str = price_str.replace("Rp", "").replace(".", "").replace(",", "").strip()
    match = re.search(r'\d+', price_str)
    if match:
        return int(match.group())
    return None

def clean_mileage(mileage_str):
    if not mileage_str:
        return None
    mileage_str = mileage_str.upper().replace("KM", "").replace(",", "").replace(".", "").strip()
    match = re.search(r'\d+', mileage_str)
    if match:
        return int(match.group())
    return None

def parse_item(item, grade_letter):
    try:
        # Title
        car_name_elem = item.find(class_='car-name')
        if not car_name_elem:
            return None
        title = car_name_elem.text.strip()
        
        # Split Brand and Model
        words = title.split()
        if not words:
            return None
        brand = words[0].title()
        model = " ".join(words[1:]) if len(words) > 1 else "Unknown"
        
        # Price
        price_elem = None
        price_text_elem = item.find_all(string=re.compile(r'Rp\s?\d+'))
        if price_text_elem:
            price_elem = price_text_elem[0]
                    
        if not price_elem:
            return None
            
        price_str = price_elem.strip()
        price = clean_price(price_str)
        if not price or price == 0:
            return None
            
        # Parse info fields
        leaf_texts = [t.strip() for t in item.find_all(string=True) if t.strip()]
        
        year = None
        transmission = "Unknown"
        mileage = None
        fuel_type = "Bensin"
        location = "Unknown"
        
        info_idx = -1
        for idx, txt in enumerate(leaf_texts):
            if "info kendaraan" in txt.lower():
                info_idx = idx
                break
                
        if info_idx != -1 and info_idx + 5 < len(leaf_texts):
            candidate_year = leaf_texts[info_idx + 1]
            if candidate_year.isdigit() and len(candidate_year) == 4:
                year = int(candidate_year)
                
            candidate_trans = leaf_texts[info_idx + 2].upper()
            if "AT" in candidate_trans or "AUTOMATIC" in candidate_trans:
                transmission = "Automatic"
            elif "MT" in candidate_trans or "MANUAL" in candidate_trans:
                transmission = "Manual"
                
            candidate_mileage = leaf_texts[info_idx + 3]
            mileage = clean_mileage(candidate_mileage)
            
            candidate_fuel = leaf_texts[info_idx + 5]
            if "solar" in candidate_fuel.lower() or "diesel" in candidate_fuel.lower():
                fuel_type = "Diesel"
            elif "hybrid" in candidate_fuel.lower():
                fuel_type = "Hybrid"
            else:
                fuel_type = "Bensin"
                
        # Find Location
        loc_elem = item.find(class_='auction-loc')
        if loc_elem:
            location = loc_elem.text.replace("JBA -", "").strip().title()
        else:
            for txt in leaf_texts:
                if "jba -" in txt.lower():
                    location = txt.replace("JBA -", "").strip().title()
                    break
                
        # Fallback
        if not year or not mileage or transmission == "Unknown":
            for txt in leaf_texts:
                if txt.isdigit() and len(txt) == 4 and int(txt) >= 2000 and int(txt) <= 2027:
                    year = int(txt)
                elif txt.upper() in ["AT", "MT", "AUTOMATIC", "MANUAL"]:
                    transmission = "Automatic" if txt.upper() in ["AT", "AUTOMATIC"] else "Manual"
                elif "km" in txt.lower() or ("," in txt and not "/" in txt and len(txt) <= 7):
                    m_val = clean_mileage(txt)
                    if m_val:
                        mileage = m_val
            
        if not year or not mileage or transmission == "Unknown":
            return None
            
        return {
            "brand": brand,
            "model": model,
            "year": year,
            "mileage": mileage,
            "transmission": transmission,
            "location": location,
            "fuel_type": fuel_type,
            "price": price,
            "grade": grade_letter
        }
    except Exception as e:
        print(f"Error parsing item: {e}")
        return None

def scrape_jba(max_pages_per_grade=5):
    all_cars = []
    seen_keys = set()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    grades = ['A', 'B', 'C', 'D', 'E', 'F']
    
    print("Starting to scrape real used car data from JBA Indonesia...")
    
    for grade in grades:
        print(f"\n=== Scraping Grade: {grade} ===")
        for page in range(1, max_pages_per_grade + 1):
            url = f"https://www.jba.co.id/id/lelang-mobil/search?machine_grade={grade}&page={page}"
            print(f"Fetching Page {page}: {url}")
            
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code != 200:
                    print(f"  [Warning] Failed page {page}. Status: {response.status_code}")
                    break
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.find_all(class_=lambda c: c and any(x in c for x in ['product-item', 'car-item-auction']))
                
                if not items:
                    print("  No items found on this page. Stopping pagination for this grade.")
                    break
                
                page_extracted = 0
                for item in items:
                    parsed = parse_item(item, grade)
                    if parsed:
                        # Create unique key
                        key = f"{parsed['year']}_{parsed['brand']}_{parsed['model']}_{parsed['price']}_{parsed['mileage']}_{parsed['transmission']}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            all_cars.append(parsed)
                            page_extracted += 1
                
                print(f"  Successfully extracted {page_extracted} unique cars from Page {page}.")
                
                # Check if page is empty of new unique records, if so break early to save time
                if page_extracted == 0:
                    print("  No new unique cars found on this page. Moving to next grade.")
                    break
                
                time.sleep(random.uniform(1.0, 2.0))
                
            except Exception as e:
                print(f"  [Error] Scraping failed on page {page}: {e}")
                time.sleep(3.0)
                
    print(f"\nScraping completed! Total unique vehicles scraped: {len(all_cars)}")
    
    # Save to CSV
    df = pd.DataFrame(all_cars)
    if not df.empty:
        project_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(project_dir, "mobil_bekas_lelang.csv")
        df.to_csv(output_file, index=False)
        print(f"Dataset successfully saved to: {output_file}")
        print("\nDataset Summary:")
        print(df.info())
        print(df.head())
    else:
        print("[Error] No data collected!")

if __name__ == "__main__":
    scrape_jba(max_pages_per_grade=10)
