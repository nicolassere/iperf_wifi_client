import json
from datetime import datetime
from pathlib import Path
from config.config import *


def save_result(result_dict, output_path="data/test_results.json"):
    """Guarda resultado con timestamp."""
    result_dict["timestamp"] = datetime.now().isoformat()
    
    try:
        # Crear directorio si no existe
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Cargar datos existentes
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []
        
        data.append(result_dict)
        
        # Guardar con encoding UTF-8
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
    except Exception as e:
        print(f"✗ Error guardando resultado: {e}")