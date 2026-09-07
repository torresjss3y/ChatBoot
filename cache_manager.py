import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class CacheManager:
    def __init__(self, cache_dir="cache", ttl_hours=24):
        self.cache_dir = cache_dir
        self.ttl = timedelta(hours=ttl_hours)
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_file(self, key: str) -> str:
        """Genera el nombre del archivo de caché"""
        # Limpiar el key para usarlo como nombre de archivo
        safe_key = key.replace('/', '_').replace('?', '_')
        return os.path.join(self.cache_dir, f"{safe_key}.json")
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Obtiene un valor de la caché si no ha expirado"""
        cache_file = self._get_cache_file(key)
        
        if not os.path.exists(cache_file):
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Verificar si ha expirado
            timestamp = datetime.fromisoformat(data['timestamp'])
            if datetime.now() - timestamp > self.ttl:
                return None
                
            return data['value']
        except Exception:
            return None
    
    def set(self, key: str, value: Any):
        """Guarda un valor en la caché"""
        cache_file = self._get_cache_file(key)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'value': value
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error guardando en caché: {e}")
    
    def clear(self, key: Optional[str] = None):
        """Limpia la caché (todo o una clave específica)"""
        if key:
            cache_file = self._get_cache_file(key)
            if os.path.exists(cache_file):
                os.remove(cache_file)
        else:
            for file in os.listdir(self.cache_dir):
                if file.endswith('.json'):
                    os.remove(os.path.join(self.cache_dir, file))
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la caché"""
        files = [f for f in os.listdir(self.cache_dir) if f.endswith('.json')]
        return {
            'total_keys': len(files),
            'directory': self.cache_dir,
            'ttl_hours': self.ttl.total_seconds() / 3600
        }