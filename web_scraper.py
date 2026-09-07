import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional
from cache_manager import CacheManager

class UCSSScraper:
    def __init__(self, cache_ttl_hours=24):
        self.base_url = "https://www.ucss.edu.pe"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.cache = CacheManager(ttl_hours=cache_ttl_hours)
        
        # Mapeo de temas a páginas relevantes
        self.topic_pages = {
            'calendario': ['calendario-academico', 'inicio', ''],
            'admision': ['admision', 'pregrado', ''],
            'pregrado': ['pregrado', 'carreras', ''],
            'posgrado': ['posgrado', 'maestrias', ''],
            'contacto': ['contacto', 'nosotros', ''],
            'general': ['', 'nosotros', 'informacion']
        }
    
    def _get_cache_key(self, url: str) -> str:
        """Genera una clave de caché para una URL"""
        return f"scrape_{url.replace('/', '_')}"
    
    def scrape_page(self, url_path: str = "", force_refresh: bool = False) -> Optional[str]:
        """Extrae contenido de una página con caché"""
        if url_path.startswith('http'):
            url = url_path
        else:
            url = f"{self.base_url}/{url_path}" if url_path else self.base_url
        
        cache_key = self._get_cache_key(url)
        
        # Intentar obtener de caché
        if not force_refresh:
            cached_content = self.cache.get(cache_key)
            if cached_content:
                return cached_content
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Eliminar elementos no deseados
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe']):
                element.decompose()
            
            # Extraer texto principal
            contenido = soup.get_text(separator='\n', strip=True)
            contenido = re.sub(r'\n\s*\n', '\n\n', contenido)
            
            # Limitar tamaño
            contenido = contenido[:8000]
            
            # Guardar en caché
            self.cache.set(cache_key, contenido)
            
            return contenido
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def buscar_informacion(self, consulta: str, paginas_especificas: Optional[List[str]] = None, 
                          force_refresh: bool = False) -> str:
        """Busca información en páginas específicas con caché"""
        # Determinar qué páginas consultar basado en la consulta
        if paginas_especificas is None:
            consulta_lower = consulta.lower()
            paginas_especificas = ['']  # Siempre incluir página principal
            
            # Detectar tema
            for topic, pages in self.topic_pages.items():
                if any(palabra in consulta_lower for palabra in [topic, topic[:-1]]):
                    paginas_especificas.extend(pages)
                    break
            else:
                paginas_especificas.extend(['nosotros', 'informacion'])
            
            # Eliminar duplicados y limitar a 3 páginas para no sobrecargar
            paginas_especificas = list(dict.fromkeys(paginas_especificas))[:3]
        
        # Extraer contenido de cada página
        todos_resultados = []
        for pagina in paginas_especificas:
            contenido = self.scrape_page(pagina, force_refresh=force_refresh)
            if contenido:
                titulo = f"Página: {self.base_url}/{pagina}" if pagina else f"Página principal: {self.base_url}"
                todos_resultados.append(f"{titulo}\n{contenido[:2000]}...")  # Limitar cada página
        
        return "\n\n".join(todos_resultados)
    
    def refresh_cache(self, paginas: Optional[List[str]] = None):
        """Fuerza la actualización de la caché"""
        if paginas is None:
            paginas = ['', 'calendario-academico', 'admision', 'pregrado', 'contacto']
        
        resultados = {}
        for pagina in paginas:
            contenido = self.scrape_page(pagina, force_refresh=True)
            resultados[pagina] = bool(contenido)
        
        return resultados